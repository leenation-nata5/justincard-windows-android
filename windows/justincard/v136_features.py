from __future__ import annotations

from typing import Any

from PySide6.QtCore import QTimer, Qt, QUrl
from PySide6.QtGui import QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStyledItemDelegate,
    QTableView,
    QTextEdit,
    QThreadPool,
    QVBoxLayout,
    QWidget,
)

from justincard.account_sync import force_upload_windows_account
from justincard.v120_features import _CloudTask
from justincard.v130_features import (
    _card_from_record,
    _find_artwork_url,
    _localized_record,
)
from justincard.v132_features import (
    _account_token,
    _refresh_data_pages,
    install_v132_patches,
)

_INSTALLED = False


def _deck_usage(page: Any) -> dict[str, int]:
    deck_id = str(getattr(page, "current_deck_id", "") or "").strip()
    if not deck_id:
        return {}
    totals: dict[str, int] = {}
    try:
        rows = page.database.deck_cards(deck_id) or []
    except Exception:
        rows = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = str(row.get("collection_key") or "").strip()
        if not key:
            continue
        try:
            quantity = max(0, int(row.get("quantity") or 0))
        except Exception:
            quantity = 0
        totals[key] = totals.get(key, 0) + quantity
    return totals


def _remaining_for_item(item: Any, usage: dict[str, int]) -> int:
    if not isinstance(item, dict):
        return 0
    key = str(item.get("collection_key") or "").strip()
    try:
        owned = max(0, int(item.get("quantity") or 0))
    except Exception:
        owned = 0
    return max(0, owned - usage.get(key, 0))


class _AvailabilityDelegate(QStyledItemDelegate):
    def __init__(self, page: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.page = page

    def paint(self, painter: Any, option: Any, index: Any) -> None:
        model = getattr(self.page, "collection_model", None)
        unavailable = False
        try:
            if model is not None:
                item = model.item_at(index.row())
                key = str(item.get("collection_key") or "").strip() if isinstance(item, dict) else ""
                remaining = getattr(self.page, "_jic_remaining_by_collection_key", {}).get(key)
                unavailable = remaining is not None and int(remaining) <= 0
        except Exception:
            unavailable = False
        if unavailable:
            painter.save()
            painter.setOpacity(0.34)
            super().paint(painter, option, index)
            painter.restore()
        else:
            super().paint(painter, option, index)


def _apply_pool_availability(page: Any) -> None:
    table = getattr(page, "collection_table", None)
    model = getattr(page, "collection_model", None)
    if not isinstance(table, QTableView) or model is None:
        return
    usage = _deck_usage(page)
    hide_unavailable = bool(getattr(getattr(page, "_jic_hide_unavailable", None), "isChecked", lambda: False)())
    try:
        count = model.rowCount()
    except Exception:
        count = 0
    remaining_by_key: dict[str, int] = {}
    for row in range(count):
        try:
            item = model.item_at(row)
            key = str(item.get("collection_key") or "").strip() if isinstance(item, dict) else ""
            remaining = _remaining_for_item(item, usage)
            if key:
                remaining_by_key[key] = remaining
            table.setRowHidden(row, hide_unavailable and remaining <= 0)
        except Exception:
            table.setRowHidden(row, False)
    page._jic_remaining_by_collection_key = remaining_by_key
    table.viewport().update()


def _build_fixed_preview(page: Any) -> None:
    deck_list = getattr(page, "deck_list", None)
    if deck_list is None:
        return

    # v1.3.0 placed the preview below the collection table. Keep that widget
    # hidden so the deck builder has exactly one stable preview location.
    old_host = getattr(page, "_jic_deck_preview_host", None)
    if isinstance(old_host, QWidget):
        old_host.hide()
        old_host.setMaximumHeight(0)

    left_surface = deck_list.parentWidget()
    left_layout = left_surface.layout() if left_surface is not None else None
    if not isinstance(left_layout, QVBoxLayout):
        return

    try:
        deck_list.setMinimumHeight(86)
        deck_list.setMaximumHeight(145)
    except Exception:
        pass
    if left_surface is not None:
        left_surface.setMinimumWidth(285)
        left_surface.setMaximumWidth(360)

    group = QGroupBox("Kartenvorschau", left_surface)
    group.setObjectName("JicDeckFixedPreview")
    group_layout = QVBoxLayout(group)
    group_layout.setContentsMargins(10, 10, 10, 10)
    group_layout.setSpacing(7)

    image = QLabel("Karte auswählen", group)
    image.setAlignment(Qt.AlignCenter)
    image.setFixedSize(168, 235)
    image.setStyleSheet(
        "QLabel { border: 1px solid #2a4268; border-radius: 10px; background: #08101f; "
        "color: #9fb1cb; padding: 4px; }"
    )
    image_row = QHBoxLayout()
    image_row.addStretch(1)
    image_row.addWidget(image)
    image_row.addStretch(1)
    group_layout.addLayout(image_row)

    context = QLabel("Sammlung oder Deckkarte auswählen", group)
    context.setObjectName("Muted")
    context.setAlignment(Qt.AlignCenter)
    group_layout.addWidget(context)

    title = QLabel("Noch keine Karte ausgewählt", group)
    title.setWordWrap(True)
    title.setStyleSheet("font-weight: 700; font-size: 14px;")
    group_layout.addWidget(title)

    meta = QLabel("", group)
    meta.setWordWrap(True)
    meta.setObjectName("Muted")
    group_layout.addWidget(meta)

    effect = QTextEdit(group)
    effect.setReadOnly(True)
    effect.setMinimumHeight(110)
    effect.setMaximumHeight(185)
    effect.setPlaceholderText("Effekt-/Beschreibungstext")
    effect.setStyleSheet(
        "QTextEdit { border: 1px solid #203758; border-radius: 8px; background: #08101f; padding: 6px; }"
    )
    group_layout.addWidget(effect)

    # Insert directly below the shortened deck list. This keeps the preview at
    # a fixed location independent from the collection/deck table selection.
    index = left_layout.indexOf(deck_list)
    left_layout.insertWidget(index + 1 if index >= 0 else 1, group, 1)

    manager = QNetworkAccessManager(page)
    page._jic_fixed_preview_manager = manager
    page._jic_fixed_preview_generation = 0
    page._jic_fixed_preview_group = group

    def set_preview(record: Any, source: str) -> None:
        localized = _localized_record(page.database, record)
        if not isinstance(localized, dict):
            return
        card = _card_from_record(localized)
        name = str(card.get("name") or localized.get("card_name") or "Unbekannte Karte")
        desc = str(card.get("desc") or card.get("effect") or localized.get("effect") or "").strip()
        set_code = str(localized.get("print_code") or localized.get("set_code") or "")
        set_name = str(localized.get("set_name") or "")
        rarity = str(localized.get("rarity") or "")
        zone = str(localized.get("zone") or localized.get("section") or "")
        pieces = [part for part in (set_code, set_name, rarity, zone.upper() if zone else "") if part]
        context.setText(source)
        title.setText(name)
        meta.setText(" • ".join(pieces))
        effect.setPlainText(desc or "Für diese Karte ist lokal noch kein Effekt-/Beschreibungstext gespeichert.")

        page._jic_fixed_preview_generation += 1
        generation = page._jic_fixed_preview_generation
        url = _find_artwork_url(localized)
        if not url:
            image.clear()
            image.setText("Kein Vorschaubild")
            return
        image.clear()
        image.setText("Bild wird geladen …")
        request = QNetworkRequest(QUrl(url))
        request.setRawHeader(b"User-Agent", b"JustInCard/1.3.6")
        reply = manager.get(request)

        def finished() -> None:
            if generation != getattr(page, "_jic_fixed_preview_generation", -1):
                reply.deleteLater()
                return
            if reply.error() != QNetworkReply.NoError:
                image.clear()
                image.setText("Vorschaubild nicht verfügbar")
                reply.deleteLater()
                return
            pixmap = QPixmap()
            if pixmap.loadFromData(reply.readAll()):
                image.setText("")
                image.setPixmap(pixmap.scaled(image.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                image.clear()
                image.setText("Vorschaubild nicht verfügbar")
            reply.deleteLater()

        reply.finished.connect(finished)

    page._jic_set_fixed_deck_preview = set_preview

    for table_name, model_name, source in (
        ("collection_table", "collection_model", "Aus Sammlung"),
        ("deck_table", "deck_model", "Im aktuellen Deck"),
    ):
        table = getattr(page, table_name, None)
        model = getattr(page, model_name, None)
        if not isinstance(table, QTableView) or model is None:
            continue

        def on_current(current: Any, _previous: Any, table=table, model=model, source=source) -> None:
            if not current.isValid():
                return
            try:
                set_preview(model.item_at(current.row()), source)
            except Exception:
                pass

        table.selectionModel().currentRowChanged.connect(on_current)

        def on_clicked(index: Any, model=model, source=source) -> None:
            if not index.isValid():
                return
            try:
                set_preview(model.item_at(index.row()), source)
            except Exception:
                pass

        table.clicked.connect(on_clicked)

    splitter = page.findChild(QSplitter)
    if isinstance(splitter, QSplitter):
        try:
            splitter.setStretchFactor(0, 0)
            splitter.setStretchFactor(1, 1)
            splitter.setStretchFactor(2, 1)
            splitter.setSizes([320, 535, 610])
        except Exception:
            pass


def _patch_decks_page() -> None:
    from justincard.ui.decks_page import DecksPage

    original_init = DecksPage.__init__
    original_refresh_collection = DecksPage.refresh_collection
    original_refresh_deck_cards = DecksPage.refresh_deck_cards
    original_deck_selected = DecksPage._deck_selected
    original_add_card = DecksPage.add_card
    original_remove_card = DecksPage.remove_card

    def page_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        _build_fixed_preview(self)

        table = getattr(self, "collection_table", None)
        if isinstance(table, QTableView):
            delegate = _AvailabilityDelegate(self, table)
            table.setItemDelegate(delegate)
            self._jic_availability_delegate = delegate

            parent = table.parentWidget()
            layout = parent.layout() if parent is not None else None
            if isinstance(layout, QVBoxLayout):
                hide = QCheckBox("Nicht verfügbare Karten ausblenden", parent)
                hide.setToolTip(
                    "Karten, deren verfügbare Kopien bereits vollständig im aktuellen Deck verwendet werden, ausblenden."
                )
                hide.setChecked(False)
                index = layout.indexOf(table)
                layout.insertWidget(index if index >= 0 else 0, hide)
                self._jic_hide_unavailable = hide
                hide.toggled.connect(lambda _checked: _apply_pool_availability(self))
        QTimer.singleShot(0, lambda: _apply_pool_availability(self))

    def refresh_collection(self: Any) -> None:
        original_refresh_collection(self)
        QTimer.singleShot(0, lambda: _apply_pool_availability(self))

    def refresh_deck_cards(self: Any) -> None:
        original_refresh_deck_cards(self)
        QTimer.singleShot(0, lambda: _apply_pool_availability(self))

    def deck_selected(self: Any, *args: Any, **kwargs: Any) -> None:
        original_deck_selected(self, *args, **kwargs)
        QTimer.singleShot(0, lambda: _apply_pool_availability(self))

    def add_card(self: Any, *args: Any, **kwargs: Any) -> None:
        original_add_card(self, *args, **kwargs)
        QTimer.singleShot(0, lambda: _apply_pool_availability(self))

    def remove_card(self: Any, *args: Any, **kwargs: Any) -> None:
        original_remove_card(self, *args, **kwargs)
        QTimer.singleShot(0, lambda: _apply_pool_availability(self))

    DecksPage.__init__ = page_init
    DecksPage.refresh_collection = refresh_collection
    DecksPage.refresh_deck_cards = refresh_deck_cards
    DecksPage._deck_selected = deck_selected
    DecksPage.add_card = add_card
    DecksPage.remove_card = remove_card


def _run_force_upload(window: QWidget, database: Any) -> None:
    if getattr(window, "_jic_account_sync_busy", False):
        QMessageBox.information(window, "Just InCard Konto", "Eine Konto-Übertragung läuft bereits.")
        return
    token = _account_token(database)
    if not token:
        QMessageBox.information(window, "Just InCard Konto", "Bitte zuerst mit deinem Just-InCard-Konto anmelden.")
        return

    answer = QMessageBox.warning(
        window,
        "Serverstand vollständig ersetzen",
        "Der aktuelle lokale Stand von Sammlung UND Decks wird als allein gültiger Stand auf justincard.de gespeichert.\n\n"
        "Servereinträge, die lokal nicht mehr existieren, werden dabei bewusst gelöscht. Vorherige Serverrevisionen bleiben als Sicherung in der Server-Historie erhalten.\n\n"
        "Möchtest du wirklich fortfahren?",
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No,
    )
    if answer != QMessageBox.Yes:
        return

    window._jic_account_sync_busy = True
    task = _CloudTask(lambda: force_upload_windows_account(database, token))
    window._jic_force_upload_task = task

    def done(result: Any) -> None:
        window._jic_account_sync_busy = False
        result = result if isinstance(result, dict) else {}
        _refresh_data_pages(window)
        QMessageBox.information(
            window,
            "Serverstand ersetzt",
            "Der lokale Stand wurde vollständig auf den Just-InCard-Server übertragen.\n\n"
            f"Sammlungseinträge: {int(result.get('collection') or 0)}\n"
            f"Decks: {int(result.get('decks') or 0)}",
        )

    def failed(message: str) -> None:
        window._jic_account_sync_busy = False
        friendly = message.split(":", 1)[-1].strip() if ":" in message else message
        QMessageBox.warning(window, "Vollständiger Upload fehlgeschlagen", friendly)

    task.signals.done.connect(done)
    task.signals.failed.connect(failed)
    QThreadPool.globalInstance().start(task)


def _patch_account_force_upload() -> None:
    from justincard.ui.settings_page import SettingsPage

    original_init = SettingsPage.__init__

    def settings_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        group = next(
            (g for g in self.findChildren(QGroupBox) if "just incard konto" in str(g.title() or "").casefold()),
            None,
        )
        if not isinstance(group, QGroupBox):
            return
        layout = group.layout()
        if not isinstance(layout, QVBoxLayout):
            return
        info = QLabel(
            "Manueller Voll-Upload: ersetzt den Serverstand exakt durch diese lokale Sammlung und diese lokalen Decks. "
            "Damit werden auch Einträge auf dem Server gelöscht, die auf diesem Gerät nicht mehr vorhanden sind.",
            group,
        )
        info.setWordWrap(True)
        info.setObjectName("Muted")
        button = QPushButton("Sammlung + Decks vollständig hochladen", group)
        button.setProperty("role", "danger")
        button.clicked.connect(lambda: _run_force_upload(self.window(), self.database))
        layout.addWidget(info)
        layout.addWidget(button)
        self._jic_force_account_upload_button = button

    SettingsPage.__init__ = settings_init


def install_v136_patches() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    install_v132_patches()
    _patch_decks_page()
    _patch_account_force_upload()
    _INSTALLED = True


__all__ = ["install_v136_patches"]
