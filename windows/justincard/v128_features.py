from __future__ import annotations

from datetime import datetime
from pathlib import Path
import os
import time
from typing import Any

from PySide6.QtCore import QEvent, QObject, QTimer, Qt, QUrl
from PySide6.QtGui import QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from justincard.v123_features import install_v123_patches

_INSTALLED = False


def _widget_layout(widget: QWidget | None) -> Any:
    if widget is None:
        return None
    candidate = getattr(widget, "layout", None)
    if callable(candidate):
        try:
            return candidate()
        except TypeError:
            return None
    return candidate


def _patch_collection_added_date() -> None:
    """Persist a stable first-added timestamp without disturbing updated_at."""
    from justincard.database import CardDatabase

    if getattr(CardDatabase, "_jic_v128_added_date", False):
        return

    original_init = CardDatabase.__init__
    original_add = CardDatabase.add_to_collection

    def ensure_schema(self: Any) -> None:
        with self._write_lock:
            with self.connect() as connection:
                columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(collection)").fetchall()}
                if "added_at" not in columns:
                    connection.execute("ALTER TABLE collection ADD COLUMN added_at REAL")
                connection.execute(
                    "UPDATE collection SET added_at=COALESCE(NULLIF(added_at, 0), updated_at, ?) "
                    "WHERE added_at IS NULL OR added_at=0",
                    (time.time(),),
                )

    def db_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        ensure_schema(self)

    def add_to_collection(
        self: Any,
        card: Any,
        print_item: Any = None,
        quantity: int = 1,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        ensure_schema(self)
        artwork_url = ""
        if len(args) >= 2:
            artwork_url = str(args[1] or "")
        elif "artwork_url" in kwargs:
            artwork_url = str(kwargs.get("artwork_url") or "")
        try:
            key = self.collection_key(card, print_item, artwork_url)
        except Exception:
            key = ""
        existed = False
        if key:
            try:
                with self.connect() as connection:
                    row = connection.execute(
                        "SELECT added_at FROM collection WHERE collection_key=? LIMIT 1", (key,)
                    ).fetchone()
                    existed = row is not None
            except Exception:
                pass
        result = original_add(self, card, print_item, quantity, *args, **kwargs)
        if key:
            with self._write_lock:
                with self.connect() as connection:
                    if existed:
                        connection.execute(
                            "UPDATE collection SET added_at=COALESCE(NULLIF(added_at,0), updated_at, ?) "
                            "WHERE collection_key=?",
                            (time.time(), key),
                        )
                    else:
                        connection.execute(
                            "UPDATE collection SET added_at=? WHERE collection_key=?",
                            (time.time(), key),
                        )
        return result

    CardDatabase.__init__ = db_init
    CardDatabase.add_to_collection = add_to_collection
    CardDatabase._jic_v128_added_date = True


def _find_artwork_url(item: dict[str, Any]) -> str:
    direct = str(item.get("artwork_url") or "").strip()
    if direct:
        return direct
    card = item.get("card") if isinstance(item.get("card"), dict) else {}
    images = card.get("card_images") if isinstance(card, dict) else []
    if isinstance(images, list):
        for image in images:
            if not isinstance(image, dict):
                continue
            for key in ("image_url_small", "image_url", "image_url_cropped"):
                value = str(image.get(key) or "").strip()
                if value:
                    return value
    return ""


def _patch_collection_preview() -> None:
    from justincard.ui.collection_page import CollectionPage

    original_init = CollectionPage.__init__
    original_show_item = CollectionPage._show_item

    def page_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        host = self.selected_print.parentWidget() if hasattr(self, "selected_print") else None
        layout = _widget_layout(host)
        if not isinstance(layout, QVBoxLayout):
            return

        preview = QLabel("Karte auswählen", host)
        preview.setObjectName("CollectionCardPreview")
        preview.setAlignment(Qt.AlignCenter)
        preview.setMinimumSize(150, 210)
        preview.setMaximumSize(220, 310)
        preview.setStyleSheet(
            "QLabel#CollectionCardPreview { border: 1px solid #2a4268; border-radius: 10px; "
            "background: #08101f; color: #9fb1cb; padding: 6px; }"
        )
        index = layout.indexOf(getattr(self, "selected_name", None))
        layout.insertWidget(max(0, index if index >= 0 else 0), preview, 0, Qt.AlignHCenter)
        self._jic_collection_preview = preview
        self._jic_preview_generation = 0
        self._jic_preview_manager = QNetworkAccessManager(self)

    def show_item(self: Any, item: Any) -> None:
        original_show_item(self, item)
        preview = getattr(self, "_jic_collection_preview", None)
        manager = getattr(self, "_jic_preview_manager", None)
        if not isinstance(preview, QLabel) or not isinstance(manager, QNetworkAccessManager):
            return
        self._jic_preview_generation = int(getattr(self, "_jic_preview_generation", 0)) + 1
        generation = self._jic_preview_generation
        if not isinstance(item, dict):
            preview.clear()
            preview.setText("Karte auswählen")
            return
        url = _find_artwork_url(item)
        if not url:
            preview.clear()
            preview.setText("Kein Vorschaubild")
            return
        preview.clear()
        preview.setText("Bild wird geladen …")
        request = QNetworkRequest(QUrl(url))
        request.setRawHeader(b"User-Agent", b"JustInCard/1.2.8")
        reply = manager.get(request)

        def finished() -> None:
            if generation != getattr(self, "_jic_preview_generation", -1):
                reply.deleteLater()
                return
            if reply.error() != QNetworkReply.NoError:
                preview.clear()
                preview.setText("Vorschaubild nicht verfügbar")
                reply.deleteLater()
                return
            pixmap = QPixmap()
            if not pixmap.loadFromData(reply.readAll()):
                preview.clear()
                preview.setText("Vorschaubild nicht verfügbar")
            else:
                preview.setText("")
                preview.setPixmap(
                    pixmap.scaled(preview.maximumSize(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )
            reply.deleteLater()

        reply.finished.connect(finished)

    CollectionPage.__init__ = page_init
    CollectionPage._show_item = show_item


def _patch_search_quantity_position() -> None:
    from justincard.ui.search_page import SearchPage

    original_init = SearchPage.__init__

    def page_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)

        def move_quantity() -> None:
            spin = getattr(self, "add_quantity", None)
            label = getattr(self, "_quantity_label", None)
            if not isinstance(spin, QSpinBox) or not isinstance(label, QLabel):
                return
            detail = getattr(self, "detail", None)
            if not isinstance(detail, QWidget):
                return

            # Find the print/set selector. The price-condition combo lives in a
            # QGroupBox named "Marktpreis" and is therefore excluded.
            target: QComboBox | None = None
            for combo in detail.findChildren(QComboBox):
                parent: QWidget | None = combo.parentWidget()
                in_price_group = False
                while parent is not None and parent is not detail:
                    if isinstance(parent, QGroupBox) and "marktpreis" in str(parent.title() or "").casefold():
                        in_price_group = True
                        break
                    parent = parent.parentWidget()
                if not in_price_group:
                    target = combo
                    break
            if target is None:
                return

            parent = target.parentWidget()
            parent_layout = _widget_layout(parent)
            if isinstance(parent_layout, QHBoxLayout):
                parent_layout.removeWidget(label)
                parent_layout.removeWidget(spin)
                position = parent_layout.indexOf(target)
                parent_layout.insertWidget(position + 1, label)
                parent_layout.insertWidget(position + 2, spin)
                return

            if isinstance(parent_layout, QFormLayout):
                row, role = parent_layout.getWidgetPosition(target)
                if row < 0:
                    return
                # Replace only the field slot with a compact row containing set
                # selection + amount. This keeps labels and all other controls intact.
                parent_layout.removeWidget(target)
                container = QWidget(parent)
                compact = QHBoxLayout(container)
                compact.setContentsMargins(0, 0, 0, 0)
                compact.setSpacing(8)
                target.setParent(container)
                label.setParent(container)
                spin.setParent(container)
                compact.addWidget(target, 1)
                compact.addWidget(label)
                compact.addWidget(spin)
                parent_layout.setWidget(row, QFormLayout.FieldRole, container)
                self._jic_set_quantity_container = container
                return

            if isinstance(parent_layout, QGridLayout):
                idx = parent_layout.indexOf(target)
                if idx >= 0:
                    row, col, row_span, col_span = parent_layout.getItemPosition(idx)
                    parent_layout.addWidget(label, row, col + col_span)
                    parent_layout.addWidget(spin, row, col + col_span + 1)

        QTimer.singleShot(0, move_quantity)

    SearchPage.__init__ = page_init


class _RapidNavigationGuard(QObject):
    """Drops accidental rapid-fire navigation clicks before expensive page work starts."""

    def __init__(self, parent: QObject) -> None:
        super().__init__(parent)
        self._last_click_ms = 0.0

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() == QEvent.MouseButtonPress:
            now = time.monotonic() * 1000.0
            if now - self._last_click_ms < 115.0:
                return True
            self._last_click_ms = now
        return False


def _patch_navigation_performance() -> None:
    from justincard.ui.main_window import MainWindow

    original_init = MainWindow.__init__

    def window_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        guard = _RapidNavigationGuard(self)
        self._jic_navigation_guard = guard
        nav_words = {"suche", "sammlung", "livebild", "scanner", "decks", "einstellungen", "start"}
        for button in self.findChildren(QAbstractButton):
            text = " ".join(str(button.text() or "").strip().casefold().split())
            if any(word == text or word in text for word in nav_words):
                button.installEventFilter(guard)
        # Cap worker oversubscription. OCR/image/network tasks stay concurrent,
        # but tab changes no longer compete with an excessive thread count.
        try:
            from PySide6.QtCore import QThreadPool
            pool = QThreadPool.globalInstance()
            ideal = max(2, min(8, int(os.cpu_count() or 4)))
            pool.setMaxThreadCount(ideal)
        except Exception:
            pass

    MainWindow.__init__ = window_init


def _patch_settings_page() -> None:
    from justincard.paths import resource_path
    from justincard.ui.settings_page import SettingsPage

    original_init = SettingsPage.__init__

    def page_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        scroll = self.findChild(QScrollArea)
        content = scroll.widget() if scroll is not None else None
        layout = _widget_layout(content)
        if not isinstance(layout, QVBoxLayout):
            return

        # --- local backup -------------------------------------------------
        backup_group = QGroupBox("Lokale Sicherung", self)
        backup_layout = QVBoxLayout(backup_group)
        backup_info = QLabel(
            "Erstellt eine lokale ZIP-Sicherung von Sammlung, Decks und Einstellungen. "
            "Eine vorhandene Sicherung kann jederzeit wieder geladen werden.",
            backup_group,
        )
        backup_info.setWordWrap(True)
        backup_info.setObjectName("Muted")
        backup_layout.addWidget(backup_info)
        row = QHBoxLayout()
        save_button = QPushButton("Backup erstellen", backup_group)
        save_button.setProperty("role", "primary")
        load_button = QPushButton("Backup laden", backup_group)
        load_button.setProperty("role", "ghost")
        row.addWidget(save_button)
        row.addWidget(load_button)
        row.addStretch(1)
        backup_layout.addLayout(row)

        google_group = next(
            (group for group in self.findChildren(QGroupBox) if "google cloud" in str(group.title() or "").casefold()),
            None,
        )
        insert_index = layout.indexOf(google_group) if isinstance(google_group, QWidget) else max(0, layout.count() - 1)
        layout.insertWidget(max(0, insert_index), backup_group)
        self._jic_local_backup_group = backup_group

        def default_backup_dir() -> Path:
            base = Path.home() / "Documents" / "Just InCard" / "Backups"
            base.mkdir(parents=True, exist_ok=True)
            return base

        def create_backup() -> None:
            target = default_backup_dir() / f"JustInCard-Backup-{datetime.now():%Y-%m-%d_%H-%M-%S}.zip"
            filename, _ = QFileDialog.getSaveFileName(
                self,
                "Lokales Just InCard Backup speichern",
                str(target),
                "Just InCard Backup (*.zip)",
            )
            if not filename:
                return
            if not filename.lower().endswith(".zip"):
                filename += ".zip"
            try:
                created = self.database.create_backup(filename)
            except Exception as exc:
                QMessageBox.critical(self, "Backup fehlgeschlagen", str(exc))
                return
            QMessageBox.information(self, "Backup erstellt", f"Lokales Backup wurde gespeichert:\n{created}")

        def load_backup() -> None:
            filename, _ = QFileDialog.getOpenFileName(
                self,
                "Lokales Just InCard Backup laden",
                str(default_backup_dir()),
                "Just InCard Backup (*.zip *.json *.sqlite3 *.sqlite *.db)",
            )
            if not filename:
                return
            try:
                report = self.database.import_backup_file(filename)
            except Exception as exc:
                QMessageBox.critical(self, "Backup konnte nicht geladen werden", str(exc))
                return
            # Refresh all pages without restarting the application.
            window = self.window()
            for widget in window.findChildren(QWidget):
                refresh = getattr(widget, "refresh", None)
                if callable(refresh):
                    try:
                        refresh()
                    except Exception:
                        pass
            QMessageBox.information(
                self,
                "Backup geladen",
                f"{int(report.get('imported', 0))} Sammlungseinträge und "
                f"{int(report.get('decks', 0))} Decks wurden geladen.",
            )

        save_button.clicked.connect(create_backup)
        load_button.clicked.connect(load_backup)

        # --- fixed Google OAuth UI ---------------------------------------
        if isinstance(google_group, QGroupBox):
            try:
                bundled = str(Path(resource_path("assets/google_oauth_client.json")))
                self.database.set_setting("google_cloud_client_secret_path_v120", "")
            except Exception:
                bundled = ""

            for edit in google_group.findChildren(QLineEdit):
                placeholder = str(edit.placeholderText() or "").casefold()
                if "oauth" in placeholder or "client" in placeholder:
                    edit.setText(bundled)
                    edit.setReadOnly(True)
                    edit.hide()
                elif "sheet" in placeholder:
                    edit.hide()

            for label in google_group.findChildren(QLabel):
                text = str(label.text() or "").strip().casefold()
                if "oauth desktop-json" in text or text == "google sheet":
                    label.hide()
                elif "einmalig erforderlich" in text:
                    label.setText(
                        "Die Google-Anmeldedatei ist fest in Just InCard integriert. "
                        "Für die Nutzung müssen nur Google Drive API und Google Sheets API im zugehörigen Cloud-Projekt aktiv sein."
                    )

            for button in google_group.findChildren(QPushButton):
                text = str(button.text() or "").strip().casefold()
                if "json auswählen" in text or "suchen / erstellen" in text or "browser öffnen" in text:
                    button.hide()
                elif "sammlung hochladen" in text or "synchronisieren" in text:
                    button.hide()
                elif "cloud laden" in text:
                    button.setText("Sammlung aus Google laden")
                    button.setProperty("role", "primary")

            for combo in google_group.findChildren(QComboBox):
                combo.hide()
            for checkbox in google_group.findChildren(QWidget):
                # Hide the auto-sync checkbox without importing its concrete type.
                if checkbox.metaObject().className() == "QCheckBox":
                    checkbox.hide()

            google_group.setTitle("Google-Konto und Sammlung")

    SettingsPage.__init__ = page_init


def install_v128_patches() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    install_v123_patches()
    _patch_collection_added_date()
    _patch_collection_preview()
    _patch_search_quantity_position()
    _patch_navigation_performance()
    _patch_settings_page()
    _INSTALLED = True


__all__ = ["install_v128_patches"]
