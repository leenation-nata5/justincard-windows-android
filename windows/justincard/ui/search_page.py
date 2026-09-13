from __future__ import annotations

from typing import Any

from PySide6.QtCore import QTimer, Qt, QThreadPool, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from justincard.constants import (
    ATTRIBUTES,
    BAN_STATUSES,
    CARD_TYPES,
    CATEGORIES,
    CONDITIONS,
    FORMATS,
    LINK_MARKERS,
    RACES,
    RARITIES,
    SORT_OPTIONS,
)
from justincard.models import SearchFilters
from justincard.search_core import (
    DISPLAY_LANGUAGES,
    effective_language,
    english_set_query,
    is_set_code_query,
    localized_collection_print,
    search_cards,
)
from justincard.workers import BackgroundTask
from justincard.ui.widgets import CardDetailPanel, CardTableModel, PageHeading, Surface
from justincard.ui.toast import show_toast
from justincard.v121_core import MAX_ADD_QUANTITY, normalize_add_quantity


def _combo(pairs: list[tuple[str, str]] | tuple[tuple[str, str], ...], all_label: str | None = "Beliebig") -> QComboBox:
    widget = QComboBox()
    if all_label is not None:
        widget.addItem(all_label, "all")
    for value, label in pairs:
        if value == "all" and all_label is not None:
            continue
        widget.addItem(label, value)
    return widget


def _text_combo(values: list[str] | tuple[str, ...], all_label: str = "Beliebig") -> QComboBox:
    widget = QComboBox()
    widget.addItem(all_label, "all")
    for value in values:
        widget.addItem(value, value)
    return widget


def _nullable_spin(maximum: int, suffix: str = "") -> QSpinBox:
    widget = QSpinBox()
    widget.setRange(-1, maximum)
    widget.setSpecialValueText("Beliebig")
    widget.setValue(-1)
    if suffix:
        widget.setSuffix(suffix)
    return widget


def _nullable_double(maximum: float) -> QDoubleSpinBox:
    widget = QDoubleSpinBox()
    widget.setRange(-1.0, maximum)
    widget.setSpecialValueText("Beliebig")
    widget.setDecimals(2)
    widget.setSuffix(" €")
    widget.setValue(-1.0)
    return widget


class FilterPanel(QScrollArea):
    search_requested = Signal()
    reset_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setObjectName("PageScroll")
        self.setFrameShape(QScrollArea.NoFrame)

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(10)

        self.quick = QLineEdit()
        self.quick.setPlaceholderText("Name, Set-Code, Passcode oder Text")
        layout.addWidget(self._group("Schnellsuche", [("Suchbegriff", self.quick)]))

        self.name = QLineEdit(); self.name.setPlaceholderText("z. B. Blauäugiger w. Drache")
        self.passcode = QLineEdit(); self.passcode.setPlaceholderText("8-stelliger Karten-Passcode"); self.passcode.setMaxLength(12)
        self.effect = QLineEdit(); self.effect.setPlaceholderText("Begriff aus dem Kartentext")
        self.archetype = QLineEdit(); self.archetype.setPlaceholderText("Thema / Archetyp")
        self.set_query = QLineEdit(); self.set_query.setPlaceholderText("Setname oder Kürzel: CORI-DE, LOB-DE001, BLMR-EN024")
        self.set_query.setToolTip("Groß-/Kleinschreibung ist egal. Auch Sprach-Präfixe ohne Kartennummer wie CORI-DE werden erkannt.")
        layout.addWidget(self._group("Text und Identität", [
            ("Kartenname", self.name),
            ("Passcode", self.passcode),
            ("Effekttext", self.effect),
            ("Archetyp", self.archetype),
            ("Set / Set-Code", self.set_query),
        ]))

        self.rarity = QComboBox(); self.rarity.setEditable(True); self.rarity.addItem("Beliebig", "all")
        for rarity in RARITIES:
            self.rarity.addItem(rarity, rarity)
        self.language = _combo(DISPLAY_LANGUAGES, None)
        self.language.setCurrentIndex(max(0, self.language.findData("all")))
        self.language.setToolTip(
            "Alle = keine Sprachsperre. CORI-DE oder CORI-DE005 wählen automatisch deutsche Kartendaten."
        )
        layout.addWidget(self._group("Druckauflage", [
            ("Seltenheit", self.rarity),
            ("Kartensprache", self.language),
        ]))

        self.category = _combo(CATEGORIES)
        self.card_type = _text_combo(CARD_TYPES)
        self.race = _text_combo(sorted(set(RACES)))
        self.attribute = _combo(ATTRIBUTES)
        self.format_name = _text_combo(FORMATS)
        self.ban_status = _combo(BAN_STATUSES, None)
        layout.addWidget(self._group("Klassifizierung", [
            ("Kategorie", self.category),
            ("Kartentyp", self.card_type),
            ("Monster-/Zaubertyp", self.race),
            ("Attribut", self.attribute),
            ("Format", self.format_name),
            ("TCG-Status", self.ban_status),
        ]))

        self.atk_min = _nullable_spin(99999); self.atk_max = _nullable_spin(99999)
        self.def_min = _nullable_spin(99999); self.def_max = _nullable_spin(99999)
        self.level_min = _nullable_spin(13); self.level_max = _nullable_spin(13)
        self.scale_min = _nullable_spin(13); self.scale_max = _nullable_spin(13)
        self.link_min = _nullable_spin(8); self.link_max = _nullable_spin(8)
        stats_group = QGroupBox("Wertebereiche")
        stats_layout = QGridLayout(stats_group)
        stats_layout.addWidget(QLabel("Wert"), 0, 0)
        stats_layout.addWidget(QLabel("Minimum"), 0, 1)
        stats_layout.addWidget(QLabel("Maximum"), 0, 2)
        for row, (label, minimum, maximum) in enumerate((
            ("ATK", self.atk_min, self.atk_max),
            ("DEF", self.def_min, self.def_max),
            ("Stufe/Rang", self.level_min, self.level_max),
            ("Pendel-Skala", self.scale_min, self.scale_max),
            ("Linkwert", self.link_min, self.link_max),
        ), start=1):
            stats_layout.addWidget(QLabel(label), row, 0)
            stats_layout.addWidget(minimum, row, 1)
            stats_layout.addWidget(maximum, row, 2)
        layout.addWidget(stats_group)

        link_group = QGroupBox("Linkpfeile")
        link_layout = QGridLayout(link_group)
        self.link_checks: dict[str, QCheckBox] = {}
        for index, (value, symbol) in enumerate(LINK_MARKERS):
            check = QCheckBox(f"{symbol} {value}")
            self.link_checks[value] = check
            link_layout.addWidget(check, index // 2, index % 2)
        layout.addWidget(link_group)

        self.pendulum_only = QCheckBox("Nur Pendelmonster")
        self.alternative_artwork_only = QCheckBox("Nur Karten mit alternativem Artwork")
        self.owned_state = QComboBox()
        for value, label in (
            ("all", "Beliebig"), ("owned", "In Sammlung"), ("missing", "Nicht in Sammlung"),
        ):
            self.owned_state.addItem(label, value)
        self.condition = _text_combo(CONDITIONS)
        self.min_quantity = _nullable_spin(9999)
        self.price_min = _nullable_double(999999.0); self.price_max = _nullable_double(999999.0)
        layout.addWidget(self._group("Spezialfilter", [
            ("Pendel", self.pendulum_only),
            ("Alternative Artworks", self.alternative_artwork_only),
            ("Sammlungsstatus", self.owned_state),
            ("Zustand", self.condition),
            ("Mindestmenge", self.min_quantity),
            ("Preis minimum", self.price_min),
            ("Preis maximum", self.price_max),
        ]))

        self.sort_by = _combo(SORT_OPTIONS, None)
        self.sort_by.setCurrentIndex(max(0, self.sort_by.findData("name_asc")))
        self.limit = QSpinBox(); self.limit.setRange(1, 5000); self.limit.setSingleStep(50); self.limit.setValue(250)
        layout.addWidget(self._group("Ausgabe", [("Sortierung", self.sort_by), ("Trefferlimit", self.limit)]))

        buttons = QHBoxLayout()
        reset = QPushButton("Filter löschen"); reset.setProperty("role", "ghost"); reset.clicked.connect(self.reset)
        search = QPushButton("Suche starten"); search.setProperty("role", "primary"); search.clicked.connect(self.search_requested.emit)
        buttons.addWidget(reset); buttons.addWidget(search)
        layout.addLayout(buttons)
        layout.addStretch(1)
        self.setWidget(root)

    @staticmethod
    def _group(title: str, rows: list[tuple[str, QWidget]]) -> QGroupBox:
        group = QGroupBox(title)
        form = QFormLayout(group)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        for label, widget in rows:
            form.addRow(label, widget)
        return group

    @staticmethod
    def _nullable_value(widget: QSpinBox | QDoubleSpinBox) -> int | float | None:
        value = widget.value()
        return None if value < 0 else value

    @staticmethod
    def _data(combo: QComboBox) -> str:
        data = combo.currentData()
        if data is None:
            return str(combo.currentText()).strip()
        return str(data)

    def filters(self) -> SearchFilters:
        rarity_data = self.rarity.currentData()
        rarity = "" if rarity_data == "all" else str(rarity_data or self.rarity.currentText()).strip()
        return SearchFilters(
            quick_text=self.quick.text().strip(),
            name=self.name.text().strip(),
            passcode=self.passcode.text().strip(),
            effect=self.effect.text().strip(),
            archetype=self.archetype.text().strip(),
            set_query=self.set_query.text().strip(),
            rarity=rarity,
            language=self._data(self.language),
            category=self._data(self.category),
            card_type=self._data(self.card_type),
            race=self._data(self.race),
            attribute=self._data(self.attribute),
            format_name=self._data(self.format_name),
            ban_status=self._data(self.ban_status),
            atk_min=self._nullable_value(self.atk_min), atk_max=self._nullable_value(self.atk_max),
            def_min=self._nullable_value(self.def_min), def_max=self._nullable_value(self.def_max),
            level_min=self._nullable_value(self.level_min), level_max=self._nullable_value(self.level_max),
            scale_min=self._nullable_value(self.scale_min), scale_max=self._nullable_value(self.scale_max),
            link_min=self._nullable_value(self.link_min), link_max=self._nullable_value(self.link_max),
            link_markers=tuple(value for value, check in self.link_checks.items() if check.isChecked()),
            pendulum_only=self.pendulum_only.isChecked(),
            alternative_artwork_only=self.alternative_artwork_only.isChecked(),
            owned_state=self._data(self.owned_state),
            condition=self._data(self.condition),
            min_quantity=self._nullable_value(self.min_quantity),
            price_min=self._nullable_value(self.price_min), price_max=self._nullable_value(self.price_max),
            sort_by=self._data(self.sort_by),
            limit=self.limit.value(),
        )

    def set_quick_text(self, text: str) -> None:
        self.quick.setText(text)

    def reset(self) -> None:
        for edit in (self.quick, self.name, self.passcode, self.effect, self.archetype, self.set_query):
            edit.clear()
        for combo in (
            self.rarity, self.language, self.category, self.card_type, self.race, self.attribute,
            self.format_name, self.ban_status, self.owned_state, self.condition, self.sort_by,
        ):
            combo.setCurrentIndex(0)
        self.language.setCurrentIndex(max(0, self.language.findData("all")))
        self.sort_by.setCurrentIndex(max(0, self.sort_by.findData("name_asc")))
        for spin in (
            self.atk_min, self.atk_max, self.def_min, self.def_max, self.level_min, self.level_max,
            self.scale_min, self.scale_max, self.link_min, self.link_max, self.min_quantity,
            self.price_min, self.price_max,
        ):
            spin.setValue(-1)
        for check in self.link_checks.values():
            check.setChecked(False)
        self.pendulum_only.setChecked(False)
        self.alternative_artwork_only.setChecked(False)
        self.limit.setValue(250)
        self.reset_requested.emit()


class SearchPage(QWidget):
    status_message = Signal(str)
    collection_changed = Signal()

    def __init__(self, database: Any, image_cache: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Page")
        self.database = database
        self.thread_pool = QThreadPool.globalInstance()
        self.active_task: BackgroundTask | None = None
        self.current_set_query = ""
        self.current_original_set_query = ""
        self._last_language_note = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        heading_row = QHBoxLayout()
        heading_row.addWidget(PageHeading(
            "Kartensuche",
            "Jeder Filter ist einzeln nutzbar. Set-Code-Sprachen werden automatisch erkannt; Enter startet die Suche im gesamten Suchreiter.",
        ), 1)
        self.reset_button = QPushButton("Filter löschen"); self.reset_button.setProperty("role", "ghost")
        self.search_button = QPushButton("Suche starten"); self.search_button.setProperty("role", "primary")
        heading_row.addWidget(self.reset_button); heading_row.addWidget(self.search_button)
        root.addLayout(heading_row)

        splitter = QSplitter(Qt.Horizontal)
        self.filters = FilterPanel()
        self.filters.setMinimumWidth(330); self.filters.setMaximumWidth(520)
        splitter.addWidget(self.filters)

        results_surface = Surface()
        results_layout = QVBoxLayout(results_surface)
        result_header = QHBoxLayout()
        self.result_label = QLabel("Noch keine Suche ausgeführt"); self.result_label.setObjectName("Muted")
        self.loading_label = QLabel(""); self.loading_label.setObjectName("Gold")
        result_header.addWidget(self.result_label, 1); result_header.addWidget(self.loading_label)
        results_layout.addLayout(result_header)
        self.model = CardTableModel([])
        self.table = QTableView(); self.table.setModel(self.model)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setSortingEnabled(False)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(34)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        if self.model.columnCount() > 1:
            header.setSectionResizeMode(1, QHeaderView.Stretch)
        results_layout.addWidget(self.table, 1)
        splitter.addWidget(results_surface)

        detail_surface = Surface()
        detail_layout = QVBoxLayout(detail_surface)
        self.detail = CardDetailPanel(image_cache)
        detail_layout.addWidget(self.detail)

        quantity_row = QHBoxLayout()
        self._quantity_row = quantity_row
        quantity_label = QLabel("Menge")
        self._quantity_label = quantity_label
        quantity_label.setObjectName("Muted")
        self.add_quantity = QSpinBox()
        self.add_quantity.setRange(1, MAX_ADD_QUANTITY)
        self.add_quantity.setValue(1)
        self.add_quantity.setMinimumWidth(92)
        self.add_quantity.setToolTip("Anzahl der ausgewählten Karte, die der Sammlung hinzugefügt wird.")
        quantity_row.addWidget(quantity_label)
        quantity_row.addWidget(self.add_quantity)
        quantity_row.addStretch(1)
        detail_layout.addLayout(quantity_row)
        splitter.addWidget(detail_surface)
        splitter.setSizes([390, 820, 420])
        splitter.setStretchFactor(1, 2); splitter.setStretchFactor(2, 1)
        root.addWidget(splitter, 1)

        self.filters.search_requested.connect(self.start_search)
        self.search_button.clicked.connect(self.start_search)
        self.filters.reset_requested.connect(self._reset_results)
        self.reset_button.clicked.connect(self.filters.reset)
        self.table.selectionModel().selectionChanged.connect(self._selection_changed)
        self.detail.add_requested.connect(self._add_to_collection)

        # Enter/Numpad-Enter works from every child widget while this page is active.
        self._enter_shortcuts: list[QShortcut] = []
        for key in (Qt.Key_Return, Qt.Key_Enter):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.setContext(Qt.WidgetWithChildrenShortcut)
            shortcut.activated.connect(self.start_search)
            self._enter_shortcuts.append(shortcut)

    def _reset_results(self) -> None:
        self.current_set_query = ""
        self.current_original_set_query = ""
        self._last_language_note = ""
        self.model.set_cards([])
        self.detail.set_card(None)
        self.result_label.setText("Filter zurückgesetzt")

    def search_quick(self, text: str) -> None:
        self.filters.set_quick_text(text)
        self.start_search()

    def start_search(self) -> None:
        if self.active_task is not None:
            self.active_task.cancel()
        if self.database.card_count() <= 0:
            QMessageBox.information(
                self,
                "Kartendatenbank fehlt",
                "Bitte laden Sie zuerst unter Einstellungen die Kartendatenbank. Danach stehen alle Detailfilter zur Verfügung.",
            )
            return

        filters = self.filters.filters()
        candidate_query = str(filters.set_query or filters.quick_text or "").strip()
        self.current_original_set_query = candidate_query if is_set_code_query(candidate_query) else ""
        self.current_set_query = (
            english_set_query(candidate_query)
            if self.current_original_set_query
            else candidate_query
        )
        _, note = effective_language(self.database, filters)
        self._last_language_note = note
        self.search_button.setEnabled(False)
        self.loading_label.setText("Suche läuft …")

        def execute(*, progress, cancelled):
            if cancelled():
                return []
            cards, note_from_search = search_cards(self.database, filters)
            self._last_language_note = note_from_search
            return cards

        task = BackgroundTask(execute)
        self.active_task = task
        task.signals.result.connect(self._show_results)
        task.signals.error.connect(self._show_error)
        task.signals.finished.connect(self._search_finished)
        self.thread_pool.start(task)

    def _show_results(self, result: object) -> None:
        cards = result if isinstance(result, list) else []
        self.model.set_cards(cards)
        self.result_label.setText(f"{len(cards):,} Treffer".replace(",", "."))
        if cards:
            # CardTableModel may re-apply the user's previous table sort with a
            # zero-delay timer after set_cards(). Selecting cards[0] immediately
            # can therefore show a different card than the row that becomes
            # visually first. Select *after* that deferred sort and read the
            # first card back from the model, so list row 1 and preview always
            # describe the same card.
            self.table.clearSelection()

            def select_visible_first() -> None:
                if self.model.rowCount() <= 0:
                    self.detail.set_card(None)
                    return
                self.table.selectRow(0)
                first = self.model.card_at(0)
                self.detail.set_card(first, self.current_set_query)
                try:
                    self.table.scrollToTop()
                except Exception:
                    pass

            QTimer.singleShot(0, select_visible_first)
        else:
            self.detail.set_card(None)
        message = f"Suche abgeschlossen: {len(cards)} Treffer"
        if self._last_language_note:
            message += f" • {self._last_language_note}"
        self.status_message.emit(message)

    def _show_error(self, message: str, trace: str) -> None:
        self.result_label.setText("Suche fehlgeschlagen")
        QMessageBox.critical(self, "Fehler bei der Suche", str(message))
        self.status_message.emit(f"Fehler bei der Suche: {message}")

    def _search_finished(self) -> None:
        self.search_button.setEnabled(True)
        self.loading_label.clear()
        self.active_task = None

    def _selection_changed(self, *_args) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            self.detail.set_card(None)
            return
        card = self.model.card_at(rows[0].row())
        self.detail.set_card(card, self.current_set_query)

    def _add_to_collection(self, card: object, print_item: object) -> None:
        if not isinstance(card, dict):
            return
        selected = print_item if isinstance(print_item, dict) else None
        collection_card, collection_print = localized_collection_print(
            card, selected, self.current_original_set_query
        )
        quantity = normalize_add_quantity(self.add_quantity.value())
        self.database.add_to_collection(collection_card, collection_print, quantity)
        self.collection_changed.emit()
        set_code = str((collection_print or {}).get("set_code") or "ohne Setangabe")
        card_name = str(card.get("name") or "Karte")
        amount_text = f"{quantity}× " if quantity != 1 else ""
        message = f"✓ {amount_text}{card_name} ({set_code}) zur Sammlung hinzugefügt"
        self.add_quantity.setValue(1)
        self.status_message.emit(message)
        show_toast(self, message, 1150)

        # v1.0.8: after a successful add, immediately prepare the search page
        # for the next card.  This deliberately resets *all* filters so a set,
        # rarity or language filter cannot accidentally affect the next search.
        self.filters.reset()

        def focus_next_search() -> None:
            self.filters.quick.setFocus(Qt.ShortcutFocusReason)
            self.filters.quick.selectAll()

        QTimer.singleShot(0, focus_next_search)
