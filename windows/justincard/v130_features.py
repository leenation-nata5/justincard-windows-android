from __future__ import annotations

import json
import time
from typing import Any

from PySide6.QtCore import QTimer, Qt, QUrl, QThreadPool
from PySide6.QtGui import QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from justincard.search_core import DISPLAY_LANGUAGES, _decode_row
from justincard.v128_features import _find_artwork_url, install_v128_patches
from justincard.v120_features import (
    AUTO_SYNC_SETTING,
    CLIENT_SECRET_SETTING,
    LAST_SYNC_SETTING,
    SORT_DIRECTION_SETTING,
    SORT_FIELD_SETTING,
    SPREADSHEET_SETTING,
    _CloudTask,
    _auto_sync_database,
)
from justincard.cloud_sync import default_token_path, normalize_spreadsheet_id

_INSTALLED = False
GLOBAL_LANGUAGE_SETTING = "global_card_text_language_v130"
SYNC_INTERVAL_MS = 5 * 60 * 1000

# Every language already understood by the Windows search/database layer.  The
# selected language is global; if a particular local catalog is missing, the
# UI falls back to English (then to the stored card) rather than hiding cards.
GLOBAL_LANGUAGES = [(code, label) for code, label in DISPLAY_LANGUAGES if code not in {"all", "auto"}]


def _widget_layout(widget: QWidget | None) -> Any:
    if widget is None:
        return None
    try:
        return widget.layout()
    except Exception:
        return None


def _global_language(database: Any) -> str:
    value = str(database.get_setting(GLOBAL_LANGUAGE_SETTING, "de") or "de").strip().lower()
    known = {code for code, _label in GLOBAL_LANGUAGES}
    return value if value in known else "de"


def _card_from_record(record: dict[str, Any]) -> dict[str, Any]:
    card = record.get("card")
    if isinstance(card, dict):
        return card
    raw = record.get("card_json")
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            pass
    return {}


def _localized_card(database: Any, card: dict[str, Any], language: str | None = None) -> dict[str, Any]:
    if not isinstance(card, dict) or not card:
        return card if isinstance(card, dict) else {}
    requested = str(language or _global_language(database)).strip().lower()
    try:
        card_id = int(card.get("id") or card.get("card_id") or 0)
    except Exception:
        card_id = 0
    if card_id <= 0:
        return card

    # Exact language first, then English as stable fallback. The original card
    # is kept when neither catalog row is installed locally.
    try:
        with database.connect() as connection:
            for candidate in (requested, "en"):
                row = connection.execute(
                    "SELECT * FROM cards WHERE card_id=? AND LOWER(language)=? ORDER BY card_key LIMIT 1",
                    (card_id, candidate),
                ).fetchone()
                if row is not None:
                    localized = _decode_row(database, row)
                    if isinstance(localized, dict) and localized:
                        # Keep collection-specific artwork selection when the
                        # localized catalog row does not carry it explicitly.
                        if card.get("artwork_url") and not localized.get("artwork_url"):
                            localized["artwork_url"] = card.get("artwork_url")
                        return localized
    except Exception:
        pass
    return card


def _localized_record(database: Any, record: Any) -> Any:
    if not isinstance(record, dict):
        return record
    card = _card_from_record(record)
    if not card:
        return record
    localized = _localized_card(database, card)
    if localized is card:
        return record
    result = dict(record)
    result["card"] = localized
    # Keep compatibility with older models that read card_json.
    try:
        result["card_json"] = json.dumps(localized, ensure_ascii=False)
    except Exception:
        pass
    return result


def _localize_model(model: Any, database: Any, container: str = "items") -> None:
    values = getattr(model, container, None)
    if not isinstance(values, list):
        return
    localized = [_localized_record(database, item) for item in values]
    try:
        model.beginResetModel()
        setattr(model, container, localized)
        model.endResetModel()
    except Exception:
        setattr(model, container, localized)


def _sync_search_language(page: Any) -> None:
    combo = getattr(getattr(page, "filters", None), "language", None)
    if not isinstance(combo, QComboBox):
        return
    requested = _global_language(page.database)
    # Search only in a catalog language that is installed. Missing global
    # language catalogs fall back to EN; details/collection use the same rule.
    installed: set[str] = set()
    try:
        for row in page.database.installed_languages() or []:
            if isinstance(row, dict):
                value = row.get("language")
            else:
                try:
                    value = row["language"]
                except Exception:
                    value = row[0] if isinstance(row, (tuple, list)) and row else None
            if value:
                installed.add(str(value).strip().lower())
    except Exception:
        pass
    effective = requested if not installed or requested in installed else ("en" if "en" in installed else requested)
    index = combo.findData(effective)
    if index >= 0:
        blocked = combo.blockSignals(True)
        combo.setCurrentIndex(index)
        combo.blockSignals(blocked)
    combo.setEnabled(False)
    combo.setToolTip("Die Kartentext-Sprache gilt appweit und wird unter Einstellungen geändert.")


def _refresh_language_pages(window: QWidget) -> None:
    try:
        from justincard.ui.search_page import SearchPage
        for page in window.findChildren(SearchPage):
            _sync_search_language(page)
    except Exception:
        pass
    for class_name in ("CollectionPage", "DecksPage"):
        for page in window.findChildren(QWidget):
            if type(page).__name__ != class_name:
                continue
            if class_name == "CollectionPage":
                refresh = getattr(page, "refresh", None)
                if callable(refresh):
                    try:
                        refresh()
                    except Exception:
                        pass
            else:
                for name in ("refresh_collection", "refresh_deck_cards"):
                    refresh = getattr(page, name, None)
                    if callable(refresh):
                        try:
                            refresh()
                        except Exception:
                            pass


def _patch_global_language() -> None:
    from justincard.ui.search_page import SearchPage
    from justincard.ui.collection_page import CollectionPage
    from justincard.ui.decks_page import DecksPage
    from justincard.ui.settings_page import SettingsPage

    # Search: the filter is still visible as context, but global and read-only.
    original_search_init = SearchPage.__init__
    original_start_search = SearchPage.start_search

    def search_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_search_init(self, *args, **kwargs)
        _sync_search_language(self)

    def start_search(self: Any) -> None:
        _sync_search_language(self)
        original_start_search(self)

    SearchPage.__init__ = search_init
    SearchPage.start_search = start_search

    # Collection: localize both table records and the selected-detail card.
    original_collection_refresh = CollectionPage.refresh
    original_collection_show = CollectionPage._show_item

    def collection_refresh(self: Any) -> None:
        original_collection_refresh(self)
        model = getattr(self, "model", None)
        if model is not None:
            _localize_model(model, self.database, "items")

    def collection_show(self: Any, item: Any) -> None:
        original_collection_show(self, _localized_record(self.database, item))

    CollectionPage.refresh = collection_refresh
    CollectionPage._show_item = collection_show

    # Deck builder: localize both selectable collection cards and deck rows.
    original_refresh_collection = DecksPage.refresh_collection
    original_refresh_deck = DecksPage.refresh_deck_cards

    def refresh_collection(self: Any) -> None:
        original_refresh_collection(self)
        model = getattr(self, "collection_model", None)
        if model is not None:
            _localize_model(model, self.database, "items")

    def refresh_deck(self: Any) -> None:
        original_refresh_deck(self)
        model = getattr(self, "deck_model", None)
        if model is not None:
            _localize_model(model, self.database, "items")

    DecksPage.refresh_collection = refresh_collection
    DecksPage.refresh_deck_cards = refresh_deck

    # Settings: one app-wide card-text language selector.
    original_settings_init = SettingsPage.__init__

    def settings_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_settings_init(self, *args, **kwargs)
        scroll = self.findChild(QScrollArea)
        content = scroll.widget() if scroll is not None else None
        layout = _widget_layout(content)
        if not isinstance(layout, QVBoxLayout):
            return
        group = QGroupBox("Kartentext-Sprache", self)
        group_layout = QVBoxLayout(group)
        info = QLabel(
            "Diese Einstellung gilt für Suche, Vorschauen, Sammlung und Deckbau. "
            "Name, Effekt-/Beschreibungstext und weitere lokalisierte Kartendaten werden in der gewählten Sprache angezeigt. "
            "Ist eine Sprache lokal noch nicht installiert, wird Englisch als Fallback verwendet.",
            group,
        )
        info.setWordWrap(True)
        info.setObjectName("Muted")
        combo = QComboBox(group)
        for code, label in GLOBAL_LANGUAGES:
            combo.addItem(label, code)
        current = combo.findData(_global_language(self.database))
        if current >= 0:
            combo.setCurrentIndex(current)
        group_layout.addWidget(info)
        group_layout.addWidget(combo)
        layout.insertWidget(0, group)
        self._jic_global_language_group = group
        self._jic_global_language_combo = combo

        def changed(_index: int) -> None:
            language = str(combo.currentData() or "de")
            self.database.set_setting(GLOBAL_LANGUAGE_SETTING, language)
            _refresh_language_pages(self.window())

        combo.currentIndexChanged.connect(changed)

    SettingsPage.__init__ = settings_init


def _patch_deck_preview() -> None:
    from justincard.ui.decks_page import DecksPage

    original_init = DecksPage.__init__

    def page_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        table = getattr(self, "collection_table", None)
        model = getattr(self, "collection_model", None)
        if not isinstance(table, QTableView) or model is None:
            return
        parent = table.parentWidget()
        layout = _widget_layout(parent)
        if not isinstance(layout, QVBoxLayout):
            return

        preview_host = QWidget(parent)
        preview_layout = QHBoxLayout(preview_host)
        preview_layout.setContentsMargins(0, 6, 0, 6)
        image = QLabel("Karte auswählen", preview_host)
        image.setAlignment(Qt.AlignCenter)
        image.setMinimumSize(120, 170)
        image.setMaximumSize(170, 238)
        image.setStyleSheet(
            "QLabel { border: 1px solid #2a4268; border-radius: 10px; background: #08101f; "
            "color: #9fb1cb; padding: 5px; }"
        )
        details = QLabel(
            "Wähle links eine Karte aus. Hier werden Artwork, Kartenname, Set und Effekttext angezeigt, bevor du sie dem Deck hinzufügst.",
            preview_host,
        )
        details.setWordWrap(True)
        details.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        details.setObjectName("Muted")
        preview_layout.addWidget(image, 0, Qt.AlignTop)
        preview_layout.addWidget(details, 1)
        index = layout.indexOf(table)
        layout.insertWidget(index + 1 if index >= 0 else layout.count(), preview_host)

        self._jic_deck_preview_host = preview_host
        self._jic_deck_preview_image = image
        self._jic_deck_preview_details = details
        self._jic_deck_preview_manager = QNetworkAccessManager(self)
        self._jic_deck_preview_generation = 0

        def update_preview() -> None:
            rows = table.selectionModel().selectedRows()
            if not rows:
                image.clear(); image.setText("Karte auswählen")
                details.setText("Wähle eine Karte aus der Sammlung aus.")
                return
            try:
                item = model.item_at(rows[0].row())
            except Exception:
                return
            item = _localized_record(self.database, item)
            if not isinstance(item, dict):
                return
            card = _card_from_record(item)
            name = str(card.get("name") or "Unbekannte Karte")
            set_code = str(item.get("print_code") or item.get("set_code") or "")
            set_name = str(item.get("set_name") or "")
            rarity = str(item.get("rarity") or "")
            desc = str(card.get("desc") or card.get("effect") or "").strip()
            header = " • ".join(part for part in (set_code, set_name, rarity) if part)
            details.setText(f"{name}\n{header}\n\n{desc}".strip())

            self._jic_deck_preview_generation += 1
            generation = self._jic_deck_preview_generation
            url = _find_artwork_url(item)
            if not url:
                image.clear(); image.setText("Kein Vorschaubild")
                return
            image.clear(); image.setText("Bild wird geladen …")
            request = QNetworkRequest(QUrl(url))
            request.setRawHeader(b"User-Agent", b"JustInCard/1.3.1")
            reply = self._jic_deck_preview_manager.get(request)

            def finished() -> None:
                if generation != getattr(self, "_jic_deck_preview_generation", -1):
                    reply.deleteLater(); return
                if reply.error() != QNetworkReply.NoError:
                    image.clear(); image.setText("Vorschaubild nicht verfügbar")
                    reply.deleteLater(); return
                pixmap = QPixmap()
                if pixmap.loadFromData(reply.readAll()):
                    image.setText("")
                    image.setPixmap(pixmap.scaled(image.maximumSize(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
                else:
                    image.clear(); image.setText("Vorschaubild nicht verfügbar")
                reply.deleteLater()

            reply.finished.connect(finished)

        table.selectionModel().selectionChanged.connect(lambda *_args: update_preview())

    DecksPage.__init__ = page_init


def _patch_sort_selection_sync() -> None:
    """Keep the selected logical row + preview together after a sort."""
    from justincard.ui.collection_page import CollectionPage
    from justincard.ui.decks_page import DecksPage

    def install_for_table(page: Any, table: QTableView, model: Any, key_names: tuple[str, ...], preview: Any = None) -> None:
        if getattr(table, "_jic_v130_selection_sync", False):
            return
        state: dict[str, str] = {"key": ""}

        def identity(item: Any) -> str:
            if not isinstance(item, dict):
                return ""
            for key in key_names:
                value = item.get(key)
                if value not in (None, ""):
                    return f"{key}:{value}"
            card = _card_from_record(item)
            return f"card:{card.get('id', '')}:{item.get('print_code', '')}"

        def before() -> None:
            rows = table.selectionModel().selectedRows()
            if rows:
                try:
                    state["key"] = identity(model.item_at(rows[0].row()))
                except Exception:
                    state["key"] = ""

        def after() -> None:
            target = state.get("key", "")
            selected_item: Any = None
            if target:
                try:
                    for row in range(model.rowCount()):
                        candidate = model.item_at(row)
                        if identity(candidate) == target:
                            table.selectRow(row)
                            selected_item = candidate
                            break
                except Exception:
                    pass
            if selected_item is None:
                rows = table.selectionModel().selectedRows()
                if rows:
                    try:
                        selected_item = model.item_at(rows[0].row())
                    except Exception:
                        pass
            if callable(preview) and selected_item is not None:
                try:
                    preview(selected_item)
                except Exception:
                    pass

        try:
            model.layoutAboutToBeChanged.connect(before)
            model.layoutChanged.connect(lambda: QTimer.singleShot(0, after))
            table._jic_v130_selection_sync = True
        except Exception:
            pass

    original_collection_init = CollectionPage.__init__
    def collection_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_collection_init(self, *args, **kwargs)
        table = getattr(self, "table", None); model = getattr(self, "model", None)
        if isinstance(table, QTableView) and model is not None:
            install_for_table(self, table, model, ("collection_key", "id"), getattr(self, "_show_item", None))
    CollectionPage.__init__ = collection_init

    original_decks_init = DecksPage.__init__
    def decks_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_decks_init(self, *args, **kwargs)
        for table_name, model_name, keys in (
            ("collection_table", "collection_model", ("collection_key", "id")),
            ("deck_table", "deck_model", ("deck_card_id", "id", "collection_key")),
        ):
            table = getattr(self, table_name, None); model = getattr(self, model_name, None)
            if isinstance(table, QTableView) and model is not None:
                install_for_table(self, table, model, keys)
    DecksPage.__init__ = decks_init


def _patch_google_sync_controls_and_periodic_sync() -> None:
    from justincard.paths import resource_path
    from justincard.ui.settings_page import SettingsPage
    from justincard.ui.main_window import MainWindow

    # v1.2.8 intentionally hid upload/sync/sort. Restore the useful controls
    # while keeping OAuth JSON and manual Sheet-path internals locked down.
    original_settings_init = SettingsPage.__init__
    def settings_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_settings_init(self, *args, **kwargs)
        google_group = next(
            (group for group in self.findChildren(QGroupBox) if "google-konto" in str(group.title() or "").casefold()
             or "google cloud" in str(group.title() or "").casefold()),
            None,
        )
        if not isinstance(google_group, QGroupBox):
            return
        for button in google_group.findChildren(QPushButton):
            text = str(button.text() or "").strip().casefold()
            if "sammlung hochladen" in text:
                button.setText("Sammlung + Decks hochladen")
                button.show()
            elif "synchronisieren" in text:
                button.setText("Jetzt synchronisieren")
                button.show()
            elif "sammlung aus google laden" in text or "cloud laden" in text:
                button.setText("Sammlung + Decks aus Google laden")
                button.show()
        for combo in google_group.findChildren(QComboBox):
            combo.show()
        for checkbox in google_group.findChildren(QCheckBox):
            checkbox.setText("Dauerhaft automatisch synchronisieren (beim Start + alle 5 Minuten)")
            checkbox.show()
        google_group.setTitle("Google-Konto, Sammlung und Decks")
        for label in google_group.findChildren(QLabel):
            text = str(label.text() or "")
            if "Die Google-Anmeldedatei ist fest" in text:
                label.setText(
                    "Die Google-Anmeldedatei ist fest integriert. Sammlung und Decks werden in derselben "
                    "Google-Sheets-Datei zwischen Windows und Android abgeglichen."
                )

    SettingsPage.__init__ = settings_init

    original_window_init = MainWindow.__init__
    def window_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_window_init(self, *args, **kwargs)
        # v1.2.8 hid the OAuth path and cleared its legacy setting. Keep the
        # bundled path internally so the existing startup-sync worker can use
        # the same fixed client as manual and periodic sync.
        try:
            self.database.set_setting(CLIENT_SECRET_SETTING, str(resource_path("assets/google_oauth_client.json")))
        except Exception:
            pass
        timer = QTimer(self)
        timer.setInterval(SYNC_INTERVAL_MS)
        self._jic_periodic_cloud_timer = timer
        self._jic_periodic_cloud_busy = False

        def tick() -> None:
            if getattr(self, "_jic_periodic_cloud_busy", False):
                return
            if not bool(self.database.get_setting(AUTO_SYNC_SETTING, False)):
                return
            if not default_token_path().exists():
                return
            sheet_id = normalize_spreadsheet_id(str(self.database.get_setting(SPREADSHEET_SETTING, "") or ""))
            if not sheet_id:
                return
            try:
                client_path = str(resource_path("assets/google_oauth_client.json"))
            except Exception:
                client_path = str(self.database.get_setting(CLIENT_SECRET_SETTING, "") or "")
            self._jic_periodic_cloud_busy = True
            task = _CloudTask(lambda: _auto_sync_database(self.database, client_path, sheet_id))
            self._jic_periodic_cloud_task = task

            def finish(_result: Any = None) -> None:
                self._jic_periodic_cloud_busy = False
                if isinstance(_result, dict):
                    self.database.set_setting(LAST_SYNC_SETTING, time.strftime("%Y-%m-%d %H:%M:%S"))
                    for widget in self.findChildren(QWidget):
                        if type(widget).__name__ == "CollectionPage":
                            refresh = getattr(widget, "refresh", None)
                            if callable(refresh):
                                try: refresh()
                                except Exception: pass
                        elif type(widget).__name__ == "DecksPage":
                            for name in ("refresh_collection", "refresh_deck_cards"):
                                refresh = getattr(widget, name, None)
                                if callable(refresh):
                                    try: refresh()
                                    except Exception: pass

            task.signals.done.connect(finish)
            task.signals.failed.connect(lambda _message: finish(None))
            QThreadPool.globalInstance().start(task)

        timer.timeout.connect(tick)
        timer.start()
        # v1.2.8 cleared the hidden client-path setting while building the
        # Settings page, so the older one-shot startup sync can legitimately
        # skip. Trigger this v1.3.0 worker once shortly after startup as well.
        QTimer.singleShot(1500, tick)

    MainWindow.__init__ = window_init


def install_v130_patches() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    install_v128_patches()
    _patch_global_language()
    _patch_deck_preview()
    _patch_sort_selection_sync()
    _patch_google_sync_controls_and_periodic_sync()
    _INSTALLED = True


__all__ = ["GLOBAL_LANGUAGE_SETTING", "install_v130_patches"]
