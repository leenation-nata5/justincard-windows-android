from __future__ import annotations

import json
from pathlib import Path
import time
from typing import Any, Callable
import webbrowser

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from justincard.cloud_sync import (
    GoogleSheetsCloud,
    SORT_FIELDS,
    default_token_path,
    merge_collection_records,
    normalize_spreadsheet_id,
    serialize_collection,
    spreadsheet_url,
)
from justincard.v110_features import install_v110_patches

_INSTALLED = False

CLIENT_SECRET_SETTING = "google_cloud_client_secret_path_v120"
SPREADSHEET_SETTING = "google_cloud_spreadsheet_id_v120"
AUTO_SYNC_SETTING = "google_cloud_auto_sync_v120"
LAST_SYNC_SETTING = "google_cloud_last_sync_v120"
SORT_FIELD_SETTING = "google_cloud_sort_field_v122"
SORT_DIRECTION_SETTING = "google_cloud_sort_direction_v122"


def _resolve_layout(widget: QWidget | None) -> Any:
    if widget is None:
        return None
    value = getattr(widget, "layout", None)
    if callable(value):
        try:
            return value()
        except TypeError:
            return None
    return value


def _card_from_record(record: dict[str, Any]) -> dict[str, Any]:
    card = record.get("card")
    if isinstance(card, dict):
        return dict(card)
    raw = record.get("card_json")
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str) and raw.strip():
        try:
            value = json.loads(raw)
            if isinstance(value, dict):
                return value
        except Exception:
            pass
    return {}


def _patch_database() -> None:
    from justincard.database import CardDatabase

    if getattr(CardDatabase, "_jic_v120_cloud_patched", False):
        return

    def export_cloud_collection(self: Any) -> list[dict[str, Any]]:
        return serialize_collection(self.collection_items(""))

    def export_cloud_decks(self: Any) -> list[dict[str, Any]]:
        collection_map = {
            str(item.get("collection_key") or ""): dict(item)
            for item in self.collection_items("")
            if isinstance(item, dict) and item.get("collection_key")
        }
        result: list[dict[str, Any]] = []
        for deck in self.list_decks():
            if not isinstance(deck, dict):
                continue
            deck_id = str(deck.get("deck_id") or deck.get("id") or "")
            payload = dict(deck)
            cards: list[dict[str, Any]] = []
            for item in self.deck_cards(deck_id):
                if not isinstance(item, dict):
                    continue
                source_key = str(item.get("source_collection_key") or item.get("collection_key") or "")
                base = dict(collection_map.get(source_key, {}))
                base.update(item)
                if not isinstance(base.get("card"), dict):
                    card = _card_from_record(base)
                    if card:
                        base["card"] = card
                cards.append(base)
            payload["deck_id"] = deck_id
            payload["cards"] = cards
            result.append(payload)
        return result

    def apply_cloud_decks(self: Any, decks: list[dict[str, Any]]) -> dict[str, int]:
        applied = 0
        skipped = 0
        current = {
            str(deck.get("name") or "").strip().casefold(): dict(deck)
            for deck in self.list_decks()
            if isinstance(deck, dict) and str(deck.get("name") or "").strip()
        }
        for raw_deck in decks:
            if not isinstance(raw_deck, dict):
                skipped += 1
                continue
            name = str(raw_deck.get("name") or "").strip() or "Importiertes Cloud-Deck"
            existing = current.get(name.casefold())
            try:
                if existing is None:
                    deck_id = self.create_deck(name, str(raw_deck.get("description") or ""))
                    existing = {"deck_id": deck_id, "name": name, "favorite": False}
                    current[name.casefold()] = existing
                else:
                    deck_id = str(existing.get("deck_id") or existing.get("id") or "")
                if not deck_id:
                    skipped += 1
                    continue
                with self._write_lock:
                    with self.connect() as connection:
                        connection.execute("DELETE FROM deck_cards WHERE deck_id=?", (deck_id,))
                        columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(decks)").fetchall()}
                        assignments: list[str] = []
                        values: list[Any] = []
                        if "description" in columns:
                            assignments.append("description=?")
                            values.append(str(raw_deck.get("description") or ""))
                        if "updated_at" in columns:
                            assignments.append("updated_at=?")
                            values.append(float(raw_deck.get("updated_at") or time.time()))
                        if assignments:
                            values.append(deck_id)
                            connection.execute(f"UPDATE decks SET {', '.join(assignments)} WHERE deck_id=?", tuple(values))
                for item in raw_deck.get("cards") or []:
                    if not isinstance(item, dict):
                        continue
                    zone = str(item.get("zone") or "main").lower()
                    quantity = max(1, int(item.get("quantity") or 1))
                    card = _card_from_record(item)
                    source_key = str(item.get("source_collection_key") or item.get("collection_key") or "")
                    if source_key.startswith("__placeholder__:"):
                        source_key = source_key.split(":", 1)[1]
                    with self.connect() as connection:
                        exists = connection.execute(
                            "SELECT 1 FROM collection WHERE collection_key=? AND quantity>0 LIMIT 1",
                            (source_key,),
                        ).fetchone() if source_key else None
                    for _ in range(quantity):
                        if exists is not None and source_key:
                            try:
                                self.add_deck_card(deck_id, source_key, zone, allow_placeholder=True)
                                continue
                            except Exception:
                                pass
                        if card:
                            self.add_deck_placeholder(deck_id, source_key, zone, card)
                wanted_favorite = bool(raw_deck.get("favorite"))
                is_favorite = bool(existing.get("favorite"))
                if wanted_favorite != is_favorite:
                    try:
                        self.toggle_deck_favorite(deck_id)
                        existing["favorite"] = wanted_favorite
                    except Exception:
                        pass
                applied += 1
            except Exception:
                skipped += 1
        return {"applied": applied, "skipped": skipped}

    def apply_cloud_collection(self: Any, records: list[dict[str, Any]]) -> dict[str, int]:
        applied = 0
        skipped = 0
        for raw in records:
            if not isinstance(raw, dict):
                skipped += 1
                continue
            card = _card_from_record(raw)
            if not card or not (card.get("id") or card.get("name")):
                skipped += 1
                continue
            print_item = {
                "set_code": str(raw.get("print_code") or ""),
                "set_name": str(raw.get("set_name") or ""),
                "set_rarity": str(raw.get("rarity") or ""),
            }
            if not any(print_item.values()):
                print_item = None
            artwork_url = str(raw.get("artwork_url") or "")
            condition = str(raw.get("condition") or "Unbewertet")
            note = str(raw.get("note") or "")
            try:
                quantity = max(0, int(raw.get("quantity") or 0))
            except (TypeError, ValueError):
                quantity = 0
            try:
                updated_at = float(raw.get("updated_at") or 0.0)
            except (TypeError, ValueError):
                updated_at = 0.0
            try:
                key = self.collection_key(card, print_item, artwork_url)
                with self.connect() as connection:
                    exists = connection.execute(
                        "SELECT 1 FROM collection WHERE collection_key=? LIMIT 1",
                        (key,),
                    ).fetchone()
                if exists is None:
                    # Use the original application API to create a fully valid row,
                    # then set the exact cloud quantity below so downloads never add
                    # duplicate copies on repeated synchronization.
                    self.add_to_collection(card, print_item, max(1, quantity), condition, artwork_url, note)
                with self._write_lock:
                    with self.connect() as connection:
                        columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(collection)").fetchall()}
                        assignments: list[str] = []
                        values: list[Any] = []
                        for column, value in (
                            ("quantity", quantity),
                            ("condition", condition),
                            ("note", note),
                            ("artwork_url", artwork_url),
                            ("language", str(raw.get("language") or card.get("_language") or "")),
                            ("card_json", self._json(card)),
                            ("updated_at", updated_at if updated_at > 0 else time.time()),
                        ):
                            if column in columns:
                                assignments.append(f"{column}=?")
                                values.append(value)
                        if "wishlist" in columns:
                            assignments.append("wishlist=0")
                        if "trade" in columns:
                            assignments.append("trade=0")
                        if assignments:
                            values.append(key)
                            connection.execute(
                                f"UPDATE collection SET {', '.join(assignments)} WHERE collection_key=?",
                                tuple(values),
                            )
                applied += 1
            except Exception:
                skipped += 1
        return {"applied": applied, "skipped": skipped}

    CardDatabase.export_cloud_collection = export_cloud_collection
    CardDatabase.export_cloud_decks = export_cloud_decks
    CardDatabase.apply_cloud_collection = apply_cloud_collection
    CardDatabase.apply_cloud_decks = apply_cloud_decks
    CardDatabase._jic_v120_cloud_patched = True


class _CloudSignals(QObject):
    done = Signal(object)
    failed = Signal(str)


class _CloudTask(QRunnable):
    def __init__(self, callback: Callable[[], Any]) -> None:
        super().__init__()
        self.callback = callback
        self.signals = _CloudSignals()

    def run(self) -> None:
        try:
            result = self.callback()
        except Exception as exc:
            self.signals.failed.emit(f"{type(exc).__name__}: {exc}")
            return
        self.signals.done.emit(result)


def _refresh_collection_windows(window: QWidget) -> None:
    try:
        from justincard.ui.collection_page import CollectionPage
        for page in window.findChildren(CollectionPage):
            try:
                page.refresh()
                page.collection_changed.emit()
            except Exception:
                pass
    except Exception:
        pass


def _add_google_cloud_settings(page: Any) -> None:
    if getattr(page, "_jic_google_cloud_group", None) is not None:
        return
    scroll = page.findChild(QScrollArea)
    content = scroll.widget() if scroll is not None else None
    layout = _resolve_layout(content)
    if not isinstance(layout, QVBoxLayout):
        return

    group = QGroupBox("Google Cloud-Sammlung")
    outer = QVBoxLayout(group)
    intro = QLabel(
        "Melden Sie sich mit Ihrem Google-Konto an. Die browseröffentliche Ansicht wird ausschließlich aus der "
        "mitgelieferten Yu-Gi-Oh!-Vorlage mit den Reitern Monsterkarten, Zauberkarten und Fallenkarten erzeugt. "
        "Die vollständige geräteübergreifende Sicherung liegt getrennt im privaten Google-App-Datenbereich."
    )
    intro.setWordWrap(True)
    intro.setObjectName("Muted")
    outer.addWidget(intro)

    oauth_row = QHBoxLayout()
    oauth_row.addWidget(QLabel("OAuth Desktop-JSON"))
    oauth_path = QLineEdit()
    oauth_path.setReadOnly(True)
    oauth_path.setPlaceholderText("Noch keine Google OAuth-Client-Datei ausgewählt")
    oauth_path.setText(str(page.database.get_setting(CLIENT_SECRET_SETTING, "") or ""))
    oauth_select = QPushButton("JSON auswählen")
    oauth_select.setProperty("role", "ghost")
    oauth_row.addWidget(oauth_path, 1)
    oauth_row.addWidget(oauth_select)
    outer.addLayout(oauth_row)

    account_row = QHBoxLayout()
    account_status = QLabel("Nicht angemeldet")
    account_status.setObjectName("Muted")
    login_button = QPushButton("Mit Google anmelden")
    login_button.setProperty("role", "primary")
    logout_button = QPushButton("Abmelden")
    logout_button.setProperty("role", "ghost")
    account_row.addWidget(QLabel("Google-Konto"))
    account_row.addWidget(account_status, 1)
    account_row.addWidget(login_button)
    account_row.addWidget(logout_button)
    outer.addLayout(account_row)

    sheet_row = QHBoxLayout()
    sheet_row.addWidget(QLabel("Google Sheet"))
    sheet_input = QLineEdit()
    saved_sheet = str(page.database.get_setting(SPREADSHEET_SETTING, "") or "")
    sheet_input.setText(spreadsheet_url(saved_sheet) if normalize_spreadsheet_id(saved_sheet) else saved_sheet)
    sheet_input.setPlaceholderText("Sheet-URL oder ID – auf einem zweiten Gerät optional hier einfügen")
    find_button = QPushButton("Suchen / erstellen")
    find_button.setProperty("role", "ghost")
    open_button = QPushButton("Im Browser öffnen")
    open_button.setProperty("role", "ghost")
    sheet_row.addWidget(sheet_input, 1)
    sheet_row.addWidget(find_button)
    sheet_row.addWidget(open_button)
    outer.addLayout(sheet_row)

    sync_row = QHBoxLayout()
    upload_button = QPushButton("Sammlung hochladen")
    download_button = QPushButton("Cloud laden")
    sync_button = QPushButton("Synchronisieren")
    sync_button.setProperty("role", "primary")
    for button in (upload_button, download_button, sync_button):
        button.setMinimumHeight(38)
        sync_row.addWidget(button)
    sync_row.addStretch(1)
    outer.addLayout(sync_row)

    sort_row = QHBoxLayout()
    sort_row.addWidget(QLabel("Standard-Sortierung für Google Sheets"))
    sort_field = QComboBox()
    for key, label in SORT_FIELDS:
        sort_field.addItem(label, key)
    saved_sort_field = str(page.database.get_setting(SORT_FIELD_SETTING, "name") or "name")
    selected_index = sort_field.findData(saved_sort_field)
    if selected_index >= 0:
        sort_field.setCurrentIndex(selected_index)
    sort_direction = QComboBox()
    sort_direction.addItem("Aufsteigend  A→Z / 0→9", "asc")
    sort_direction.addItem("Absteigend  Z→A / 9→0", "desc")
    saved_direction = str(page.database.get_setting(SORT_DIRECTION_SETTING, "asc") or "asc")
    direction_index = sort_direction.findData(saved_direction)
    if direction_index >= 0:
        sort_direction.setCurrentIndex(direction_index)
    sort_row.addWidget(sort_field, 1)
    sort_row.addWidget(sort_direction)
    outer.addLayout(sort_row)

    auto_sync = QCheckBox("Beim App-Start automatisch synchronisieren")
    auto_sync.setChecked(bool(page.database.get_setting(AUTO_SYNC_SETTING, False)))
    outer.addWidget(auto_sync)

    status = QLabel("Cloud-Synchronisierung noch nicht ausgeführt.")
    last_sync = str(page.database.get_setting(LAST_SYNC_SETTING, "") or "")
    if last_sync:
        status.setText(f"Letzte Synchronisierung: {last_sync}")
    status.setWordWrap(True)
    status.setObjectName("Muted")
    outer.addWidget(status)

    note = QLabel(
        "Einmalig erforderlich: In Google Cloud die Google Sheets API und Google Drive API aktivieren, "
        "einen OAuth-Client vom Typ „Desktop-App“ erstellen und dessen JSON hier auswählen. "
        "Jedes angemeldete Google-Konto erhält seine eigene Vorlagen-Datei im eigenen Drive. Nach dem Update auf 1.2.6 "
        "ist wegen der auf drive.file + drive.appdata reduzierten Berechtigungen einmaliges erneutes Anmelden nötig."
    )
    note.setWordWrap(True)
    note.setObjectName("Muted")
    outer.addWidget(note)

    page._jic_google_cloud_group = group
    page._jic_google_cloud_status = status
    layout.insertWidget(max(0, layout.count() - 1), group)

    buttons = [oauth_select, login_button, logout_button, find_button, open_button, upload_button, download_button, sync_button]

    def set_busy(busy: bool, message: str = "") -> None:
        for button in buttons:
            button.setEnabled(not busy)
        if message:
            status.setText(message)

    def cloud(interactive: bool = False) -> GoogleSheetsCloud:
        path = str(oauth_path.text() or page.database.get_setting(CLIENT_SECRET_SETTING, "") or "")
        if not path:
            try:
                from justincard.paths import resource_path
                bundled = Path(resource_path("assets/google_oauth_client.json"))
                if bundled.exists():
                    path = str(bundled)
            except Exception:
                pass
        service = GoogleSheetsCloud(path, default_token_path())
        if interactive:
            service.load_credentials(interactive=True)
        return service

    def remember_sheet(identifier: str) -> None:
        identifier = normalize_spreadsheet_id(identifier)
        if not identifier:
            return
        page.database.set_setting(SPREADSHEET_SETTING, identifier)
        sheet_input.setText(spreadsheet_url(identifier))

    def current_sheet() -> str:
        entered = normalize_spreadsheet_id(sheet_input.text())
        if entered:
            return entered
        return normalize_spreadsheet_id(str(page.database.get_setting(SPREADSHEET_SETTING, "") or ""))

    def current_sort() -> tuple[str, str]:
        return (
            str(sort_field.currentData() or "name"),
            str(sort_direction.currentData() or "asc"),
        )

    def choose_sort_before_export() -> tuple[str, str] | None:
        dialog = QDialog(page)
        dialog.setWindowTitle("Google Sheets – Sortierung festlegen")
        dialog.setMinimumWidth(520)
        layout = QVBoxLayout(dialog)
        intro = QLabel(
            "Wählen Sie vor dem Export, wie die drei Vorlagen-Reiter in Google Sheets sortiert werden. "
            "Deck-Reiter behalten unabhängig davon exakt die Reihenfolge aus dem Deckbuilder."
        )
        intro.setWordWrap(True)
        intro.setObjectName("Muted")
        layout.addWidget(intro)
        form = QFormLayout()
        field_box = QComboBox(dialog)
        for key, label in SORT_FIELDS:
            field_box.addItem(label, key)
        direction_box = QComboBox(dialog)
        direction_box.addItem("Aufsteigend  A→Z / 0→9", "asc")
        direction_box.addItem("Absteigend  Z→A / 9→0", "desc")
        saved_field, saved_direction = current_sort()
        idx = field_box.findData(saved_field)
        if idx >= 0:
            field_box.setCurrentIndex(idx)
        idx = direction_box.findData(saved_direction)
        if idx >= 0:
            direction_box.setCurrentIndex(idx)
        form.addRow("Sortieren nach", field_box)
        form.addRow("Richtung", direction_box)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=dialog)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.Accepted:
            return None
        field = str(field_box.currentData() or "name")
        direction = str(direction_box.currentData() or "asc")
        page.database.set_setting(SORT_FIELD_SETTING, field)
        page.database.set_setting(SORT_DIRECTION_SETTING, direction)
        sort_field_index = sort_field.findData(field)
        if sort_field_index >= 0:
            sort_field.setCurrentIndex(sort_field_index)
        direction_index = sort_direction.findData(direction)
        if direction_index >= 0:
            sort_direction.setCurrentIndex(direction_index)
        return field, direction

    def finish(message: str) -> None:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        page.database.set_setting(LAST_SYNC_SETTING, timestamp)
        status.setText(f"{message}\nLetzte Synchronisierung: {timestamp}")
        try:
            page.status_message.emit(message)
        except Exception:
            pass

    def run_task(callback: Callable[[], Any], success: Callable[[Any], None], message: str) -> None:
        set_busy(True, message)
        task = _CloudTask(callback)
        page._jic_cloud_task = task

        def done(result: Any) -> None:
            set_busy(False)
            success(result)

        def failed(error: str) -> None:
            set_busy(False)
            status.setText(f"Fehler: {error}")
            QMessageBox.warning(page, "Google Cloud-Synchronisierung", error)

        task.signals.done.connect(done)
        task.signals.failed.connect(failed)
        QThreadPool.globalInstance().start(task)

    def select_oauth() -> None:
        filename, _selected = QFileDialog.getOpenFileName(
            page,
            "Google OAuth Desktop-JSON auswählen",
            str(Path.home()),
            "Google OAuth JSON (*.json);;JSON-Dateien (*.json)",
        )
        if not filename:
            return
        oauth_path.setText(filename)
        page.database.set_setting(CLIENT_SECRET_SETTING, filename)
        try:
            default_token_path().unlink(missing_ok=True)
        except Exception:
            pass
        account_status.setText("Nicht angemeldet")
        status.setText("OAuth-Client-Datei gespeichert. Jetzt mit Google anmelden.")

    def login() -> None:
        def action() -> Any:
            service = cloud(interactive=True)
            account = service.account()
            return account

        def success(account: Any) -> None:
            label = str(getattr(account, "email", "") or getattr(account, "display_name", "") or "Google verbunden")
            account_status.setText(label)
            finish("Google-Konto verbunden")

        run_task(action, success, "Browser für Google-Anmeldung wird geöffnet …")

    def logout() -> None:
        try:
            cloud(False).logout()
        except Exception:
            try:
                default_token_path().unlink(missing_ok=True)
            except Exception:
                pass
        account_status.setText("Nicht angemeldet")
        status.setText("Google-Anmeldung wurde lokal entfernt.")

    def find_sheet() -> None:
        def action() -> str:
            service = cloud(False)
            return service.find_or_create_spreadsheet(current_sheet())

        def success(identifier: Any) -> None:
            remember_sheet(str(identifier))
            finish("Google-Sheets-Sammlung ist verbunden")

        run_task(action, success, "Google-Sheets-Datei wird gesucht oder erstellt …")

    def upload() -> None:
        selected_sort = choose_sort_before_export()
        if selected_sort is None:
            return
        field, direction = selected_sort

        def action() -> dict[str, Any]:
            service = cloud(False)
            identifier = service.find_or_create_spreadsheet(current_sheet())
            rows = page.database.export_cloud_collection()
            decks = page.database.export_cloud_decks()
            return service.upload_collection(
                identifier,
                rows,
                decks=decks,
                sort_field=field,
                sort_direction=direction,
            )

        def success(result: Any) -> None:
            if isinstance(result, dict):
                remember_sheet(str(result.get("spreadsheet_id") or ""))
                finish(
                    f"{int(result.get('rows') or 0)} Sammlungseinträge und "
                    f"{int(result.get('decks') or 0)} Decks zu Google Sheets hochgeladen"
                )
            else:
                finish("Sammlung zu Google Sheets hochgeladen")

        run_task(action, success, "Sammlung wird zu Google Sheets hochgeladen …")

    def download() -> None:
        identifier = current_sheet()
        if not identifier:
            QMessageBox.information(page, "Google Cloud", "Bitte zuerst die Cloud-Datei suchen/erstellen oder eine Sheet-URL einfügen.")
            return

        def action() -> dict[str, Any]:
            service = cloud(False)
            payload = service.download_cloud_payload(identifier)
            cloud_rows = list(payload.get("collection") or [])
            cloud_decks = list(payload.get("decks") or [])
            report = page.database.apply_cloud_collection(cloud_rows)
            deck_report = page.database.apply_cloud_decks(cloud_decks)
            return {
                "rows": len(cloud_rows),
                "decks": len(cloud_decks),
                **report,
                "decks_applied": deck_report.get("applied", 0),
                "decks_skipped": deck_report.get("skipped", 0),
            }

        def success(result: Any) -> None:
            _refresh_collection_windows(page.window())
            if isinstance(result, dict):
                finish(
                    f"Cloud-Sammlung geladen: {int(result.get('applied') or 0)} übernommen, "
                    f"{int(result.get('skipped') or 0)} übersprungen; "
                    f"{int(result.get('decks_applied') or 0)} Decks übernommen"
                )
            else:
                finish("Cloud-Sammlung geladen")

        run_task(action, success, "Cloud-Sammlung wird geladen und lokal zusammengeführt …")

    def synchronize() -> None:
        selected_sort = choose_sort_before_export()
        if selected_sort is None:
            return
        field, direction = selected_sort

        def action() -> dict[str, Any]:
            service = cloud(False)
            identifier = service.find_or_create_spreadsheet(current_sheet())
            local_rows = page.database.export_cloud_collection()
            try:
                payload = service.download_cloud_payload(identifier)
                cloud_rows = list(payload.get("collection") or [])
                cloud_decks = list(payload.get("decks") or [])
            except Exception:
                cloud_rows = []
                cloud_decks = []
            merged = merge_collection_records(local_rows, cloud_rows)
            report = page.database.apply_cloud_collection(merged)
            deck_report = page.database.apply_cloud_decks(cloud_decks)
            decks = page.database.export_cloud_decks()
            upload_result = service.upload_collection(
                identifier,
                merged,
                decks=decks,
                sort_field=field,
                sort_direction=direction,
            )
            return {
                "spreadsheet_id": identifier,
                "merged": len(merged),
                "applied": report.get("applied", 0),
                "skipped": report.get("skipped", 0),
                "decks": upload_result.get("decks", len(decks)),
                "decks_applied": deck_report.get("applied", 0),
                "rows": upload_result.get("rows", len(merged)),
            }

        def success(result: Any) -> None:
            if isinstance(result, dict):
                remember_sheet(str(result.get("spreadsheet_id") or ""))
                _refresh_collection_windows(page.window())
                finish(f"Synchronisiert: {int(result.get('merged') or 0)} Sammlungseinträge")
            else:
                finish("Sammlung synchronisiert")

        run_task(action, success, "Lokale und Google-Sheets-Sammlung werden abgeglichen …")

    def open_sheet() -> None:
        identifier = current_sheet()
        if not identifier:
            QMessageBox.information(page, "Google Cloud", "Noch keine Google-Sheets-Datei verbunden.")
            return
        remember_sheet(identifier)
        webbrowser.open(spreadsheet_url(identifier))

    def save_auto_sync(checked: bool) -> None:
        page.database.set_setting(AUTO_SYNC_SETTING, bool(checked))

    def save_sort_preferences() -> None:
        field, direction = current_sort()
        page.database.set_setting(SORT_FIELD_SETTING, field)
        page.database.set_setting(SORT_DIRECTION_SETTING, direction)

    oauth_select.clicked.connect(select_oauth)
    login_button.clicked.connect(login)
    logout_button.clicked.connect(logout)
    find_button.clicked.connect(find_sheet)
    open_button.clicked.connect(open_sheet)
    upload_button.clicked.connect(upload)
    download_button.clicked.connect(download)
    sync_button.clicked.connect(synchronize)
    sort_field.currentIndexChanged.connect(lambda _index: save_sort_preferences())
    sort_direction.currentIndexChanged.connect(lambda _index: save_sort_preferences())
    auto_sync.toggled.connect(save_auto_sync)

    # Resolve an existing sign-in in the background without opening the browser.
    if default_token_path().exists():
        def account_action() -> Any:
            return cloud(False).account()

        def account_success(account: Any) -> None:
            label = str(getattr(account, "email", "") or getattr(account, "display_name", "") or "Google verbunden")
            account_status.setText(label)
            set_busy(False)

        run_task(account_action, account_success, "Google-Anmeldung wird geprüft …")



def _patch_settings_page() -> None:
    from justincard.ui.settings_page import SettingsPage

    original_init = SettingsPage.__init__

    def page_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        _add_google_cloud_settings(self)

    SettingsPage.__init__ = page_init


def _patch_main_window_auto_sync() -> None:
    from justincard.ui.main_window import MainWindow

    original_init = MainWindow.__init__

    def window_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        if not bool(self.database.get_setting(AUTO_SYNC_SETTING, False)):
            return
        if not default_token_path().exists():
            return
        client_path = str(self.database.get_setting(CLIENT_SECRET_SETTING, "") or "")
        sheet_id = normalize_spreadsheet_id(str(self.database.get_setting(SPREADSHEET_SETTING, "") or ""))
        if not sheet_id:
            return

        def auto_sync() -> None:
            task = _CloudTask(lambda: _auto_sync_database(self.database, client_path, sheet_id))
            self._jic_auto_cloud_task = task

            def done(result: Any) -> None:
                if isinstance(result, dict):
                    self.database.set_setting(LAST_SYNC_SETTING, time.strftime("%Y-%m-%d %H:%M:%S"))
                    _refresh_collection_windows(self)

            task.signals.done.connect(done)
            # Startup sync is intentionally silent on failure so an offline
            # laptop still opens normally. Manual sync shows full errors.
            task.signals.failed.connect(lambda _message: None)
            QThreadPool.globalInstance().start(task)

        QTimer.singleShot(1500, auto_sync)

    MainWindow.__init__ = window_init


def _auto_sync_database(database: Any, client_path: str, spreadsheet_id: str) -> dict[str, Any]:
    service = GoogleSheetsCloud(client_path, default_token_path())
    local_rows = database.export_cloud_collection()
    payload = service.download_cloud_payload(spreadsheet_id)
    cloud_rows = list(payload.get("collection") or [])
    cloud_decks = list(payload.get("decks") or [])
    merged = merge_collection_records(local_rows, cloud_rows)
    report = database.apply_cloud_collection(merged)
    deck_report = database.apply_cloud_decks(cloud_decks)
    decks = database.export_cloud_decks()
    sort_field = str(database.get_setting(SORT_FIELD_SETTING, "name") or "name")
    sort_direction = str(database.get_setting(SORT_DIRECTION_SETTING, "asc") or "asc")
    service.upload_collection(
        spreadsheet_id,
        merged,
        decks=decks,
        sort_field=sort_field,
        sort_direction=sort_direction,
    )
    return {"merged": len(merged), "decks": len(decks), **report, "deck_report": deck_report}


def install_v120_patches() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    install_v110_patches()
    _patch_database()
    _patch_settings_page()
    _patch_main_window_auto_sync()
    _INSTALLED = True


__all__ = [
    "install_v120_patches",
    "CLIENT_SECRET_SETTING",
    "SPREADSHEET_SETTING",
    "AUTO_SYNC_SETTING",
    "LAST_SYNC_SETTING",
    "SORT_FIELD_SETTING",
    "SORT_DIRECTION_SETTING",
]
