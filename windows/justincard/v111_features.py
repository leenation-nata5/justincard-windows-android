from __future__ import annotations

import re
from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QScrollArea,
    QTableView,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from justincard.price_service import PriceEstimate, estimate_price
from justincard.v108_core import artwork_label
from justincard.v108_core import VISIBILITY_SETTING_KEY
from justincard.v108_features import (_apply_table_visibility, _ensure_name_width, _estimated_market_value_eur, _refresh_detail_panel)
from justincard.v111_core import (
    CARD_INFORMATION_FIELDS,
    DISPLAY_CONTEXTS,
    PROFILE_SETTING_KEY,
    context_label,
    normalize_profiles,
    preset_for_context,
    profile_for,
)

_INSTALLED = False

CONDITIONS: tuple[str, ...] = (
    "Mint",
    "Near Mint",
    "Excellent",
    "Good",
    "Light Played",
    "Played",
    "Poor",
)


def _resolve_widget_layout(widget: QWidget | None) -> QLayout | None:
    """Return a widget layout without assuming ``widget.layout`` is callable.

    Some recovered Just InCard widgets store their QLayout instance directly in
    ``self.layout``.  That shadows QWidget.layout(), so calling ``widget.layout()``
    raises ``TypeError: 'QVBoxLayout' object is not callable``.
    """
    if widget is None:
        return None
    candidate = getattr(widget, "layout", None)
    if isinstance(candidate, QLayout):
        return candidate
    if callable(candidate):
        try:
            resolved = candidate()
        except TypeError:
            return None
        if isinstance(resolved, QLayout):
            return resolved
    return None


def _load_profiles(database: Any) -> dict[str, dict[str, bool]]:
    try:
        raw = database.get_setting(PROFILE_SETTING_KEY, None)
    except Exception:
        raw = None
    try:
        legacy = database.get_setting(VISIBILITY_SETTING_KEY, None)
    except Exception:
        legacy = None
    profiles = normalize_profiles(raw, legacy)
    if raw is None:
        try:
            database.set_setting(PROFILE_SETTING_KEY, profiles)
        except Exception:
            pass
    return profiles


def _save_profiles(database: Any, profiles: dict[str, dict[str, bool]]) -> None:
    database.set_setting(PROFILE_SETTING_KEY, normalize_profiles(profiles))


def _apply_table_profile(table: QTableView, database: Any, context: str) -> None:
    profiles = _load_profiles(database)
    prefs = profile_for(profiles, context)
    table._jic_visibility_profile_context = context  # type: ignore[attr-defined]
    table._jic_local_visibility_override = prefs  # type: ignore[attr-defined]
    _apply_table_visibility(table, prefs, prefs)
    QTimer.singleShot(0, lambda: _ensure_name_width(table))


def _set_detail_profile(detail: Any, database: Any, context: str) -> None:
    profiles = _load_profiles(database)
    prefs = profile_for(profiles, context)
    detail._jic_database = database  # type: ignore[attr-defined]
    detail._jic_visibility_context = context  # type: ignore[attr-defined]
    detail._jic_visibility = prefs  # type: ignore[attr-defined]
    _refresh_detail_panel(detail)
    group = getattr(detail, "_jic_price_group", None)
    if isinstance(group, QWidget):
        group.setVisible(bool(prefs.get("price", True)))


def _refresh_context(window: QWidget, database: Any, context: str) -> None:
    profiles = _load_profiles(database)
    prefs = profile_for(profiles, context)
    for table in window.findChildren(QTableView):
        if getattr(table, "_jic_visibility_profile_context", None) == context:
            table._jic_local_visibility_override = prefs  # type: ignore[attr-defined]
            _apply_table_visibility(table, prefs, prefs)
    try:
        from justincard.ui.widgets import CardDetailPanel
        for detail in window.findChildren(CardDetailPanel):
            if getattr(detail, "_jic_visibility_context", None) == context:
                detail._jic_visibility = prefs  # type: ignore[attr-defined]
                _refresh_detail_panel(detail)
                group = getattr(detail, "_jic_price_group", None)
                if isinstance(group, QWidget):
                    group.setVisible(bool(prefs.get("price", True)))
    except Exception:
        pass
    # Non-CardDetailPanel views (notably the collection's selected-print row)
    # can register a tiny refresh callback for their own context.
    for widget in window.findChildren(QWidget):
        callback = getattr(widget, "_jic_refresh_visibility_context", None)
        if callable(callback):
            try:
                callback(context)
            except Exception:
                pass


def _tile_style() -> str:
    return (
        "QToolButton { min-width: 142px; max-width: 142px; min-height: 40px; max-height: 40px; "
        "padding: 0 8px; border: 1px solid #2a4268; border-radius: 9px; text-align: center; }"
        "QToolButton:checked { background: #2d70c9; color: white; border-color: #5a9bf2; }"
        "QToolButton:hover { border-color: #5a9bf2; }"
    )


def _build_visibility_grid(
    database: Any,
    context: str,
    on_saved: Callable[[str], None] | None = None,
) -> tuple[QWidget, dict[str, QToolButton], Callable[[str], None]]:
    container = QWidget()
    grid = QGridLayout(container)
    grid.setHorizontalSpacing(8)
    grid.setVerticalSpacing(8)
    grid.setContentsMargins(0, 0, 0, 0)
    profiles = _load_profiles(database)
    prefs = profile_for(profiles, context)
    buttons: dict[str, QToolButton] = {}

    def save_field(field: str, enabled: bool) -> None:
        current = _load_profiles(database)
        current.setdefault(context, {})[field] = bool(enabled)
        _save_profiles(database, current)
        if on_saved is not None:
            on_saved(context)

    for index, (key, label) in enumerate(CARD_INFORMATION_FIELDS):
        button = QToolButton()
        button.setText(label)
        button.setCheckable(True)
        button.setChecked(bool(prefs.get(key, True)))
        button.setToolButtonStyle(Qt.ToolButtonTextOnly)
        button.setStyleSheet(_tile_style())
        button.toggled.connect(lambda checked, field=key: save_field(field, checked))
        buttons[key] = button
        row, col = divmod(index, 4)
        grid.addWidget(button, row, col)
    for col in range(4):
        grid.setColumnStretch(col, 1)

    def apply_preset(mode: str) -> None:
        target = preset_for_context(mode)
        current = _load_profiles(database)
        current[context] = dict(target)
        _save_profiles(database, current)
        for key, button in buttons.items():
            old = button.blockSignals(True)
            button.setChecked(bool(target.get(key, True)))
            button.blockSignals(old)
        if on_saved is not None:
            on_saved(context)

    return container, buttons, apply_preset


def _show_visibility_dialog(parent: QWidget, database: Any, context: str) -> None:
    dialog = QDialog(parent)
    dialog.setWindowTitle(f"Anzeige – {context_label(context)}")
    dialog.setMinimumWidth(690)
    layout = QVBoxLayout(dialog)
    title = QLabel(context_label(context))
    title.setStyleSheet("font-size: 18px; font-weight: 700;")
    info = QLabel("Jede Auswahl gilt nur für diesen Bereich. Der Kartenname bleibt immer sichtbar.")
    info.setWordWrap(True)
    info.setObjectName("Muted")
    layout.addWidget(title)
    layout.addWidget(info)

    grid_widget, _buttons, apply_preset = _build_visibility_grid(
        database,
        context,
        on_saved=lambda ctx: _refresh_context(parent.window(), database, ctx),
    )
    layout.addWidget(grid_widget)

    actions = QHBoxLayout()
    for text, mode in (("Alle Infos", "all"), ("Basisansicht", "basic"), ("Nur Namen", "none")):
        button = QPushButton(text)
        button.setProperty("role", "ghost")
        button.setMinimumHeight(36)
        button.clicked.connect(lambda _checked=False, m=mode: apply_preset(m))
        actions.addWidget(button)
    actions.addStretch(1)
    layout.addLayout(actions)
    close_box = QDialogButtonBox(QDialogButtonBox.Close)
    close_box.rejected.connect(dialog.reject)
    close_box.clicked.connect(lambda _button: dialog.accept())
    layout.addWidget(close_box)
    dialog.exec()


def _add_display_button(table: QTableView, database: Any, context: str) -> None:
    if getattr(table, "_jic_v111_display_button", None) is not None:
        return
    parent = table.parentWidget()
    layout = _resolve_widget_layout(parent)
    if not isinstance(layout, QVBoxLayout):
        return
    row = QHBoxLayout()
    label = QLabel("Anzeige")
    label.setObjectName("Muted")
    button = QPushButton("Spalten auswählen")
    button.setProperty("role", "ghost")
    button.setMinimumHeight(34)
    button.clicked.connect(lambda: _show_visibility_dialog(table, database, context))
    row.addWidget(label)
    row.addWidget(button)
    row.addStretch(1)
    idx = layout.indexOf(table)
    layout.insertLayout(max(0, idx), row)
    table._jic_v111_display_button = button  # type: ignore[attr-defined]


class _PriceSignals(QObject):
    done = Signal(object)
    failed = Signal(str)


class _PriceTask(QRunnable):
    def __init__(self, card: dict[str, Any], print_code: str, rarity: str, language: str, condition: str) -> None:
        super().__init__()
        self.card = dict(card)
        self.print_code = print_code
        self.rarity = rarity
        self.language = language
        self.condition = condition
        self.signals = _PriceSignals()

    def run(self) -> None:
        try:
            result = estimate_price(
                self.card,
                print_code=self.print_code,
                rarity=self.rarity,
                language=self.language,
                condition=self.condition,
                live=True,
            )
        except Exception as exc:
            self.signals.failed.emit(f"{type(exc).__name__}: {exc}")
            return
        self.signals.done.emit(result)


def _infer_print_language(print_code: str, fallback: str = "en") -> str:
    match = re.search(r"-(DE|EN|FR|IT|PT|ES|JP|JA|KO|KR|TC|SC)(?=[A-Z0-9-]*$)", str(print_code or "").upper())
    if not match:
        return str(fallback or "en").lower()
    return {
        "DE": "de", "EN": "en", "FR": "fr", "IT": "it", "PT": "pt", "ES": "es",
        "JP": "ja", "JA": "ja", "KO": "ko", "KR": "ko", "TC": "zh-tw", "SC": "zh-cn",
    }.get(match.group(1), str(fallback or "en").lower())


def _format_price_result(result: PriceEstimate) -> tuple[str, str]:
    if result.amount_eur is None:
        primary = "Kein Marktpreis verfügbar"
    else:
        primary = f"Geschätzter Marktpreis: {result.amount_eur:.2f} €".replace(".", ",")
    details: list[str] = []
    if result.print_code:
        details.append(result.print_code)
    if result.rarity:
        details.append(result.rarity)
    if result.requested_language:
        details.append(result.requested_language.upper())
    details.append(result.condition)
    if result.cardmarket_floor_eur is not None:
        details.append(f"Cardmarket Karten-Floor {result.cardmarket_floor_eur:.2f} €".replace(".", ","))
    return primary, " • ".join(details) + "\n" + result.note


def _attach_price_panel(
    host: QWidget,
    *,
    card_provider: Callable[[], dict[str, Any] | None],
    print_provider: Callable[[], tuple[str, str]],
    language_provider: Callable[[], str],
    condition_provider: Callable[[], str] | None = None,
) -> QGroupBox | None:
    if getattr(host, "_jic_price_group", None) is not None:
        return getattr(host, "_jic_price_group")
    layout = _resolve_widget_layout(host)
    if not isinstance(layout, QVBoxLayout):
        return None
    group = QGroupBox("Marktpreis")
    box = QVBoxLayout(group)
    row = QHBoxLayout()
    condition = QComboBox()
    for value in CONDITIONS:
        condition.addItem(value, value)
    condition.setCurrentText("Near Mint")
    condition.setMinimumWidth(150)
    button = QPushButton("Preis ermitteln")
    button.setProperty("role", "primary")
    button.setMinimumHeight(36)
    row.addWidget(QLabel("Zustand"))
    row.addWidget(condition)
    row.addWidget(button)
    row.addStretch(1)
    result_label = QLabel("Noch nicht ermittelt")
    result_label.setWordWrap(True)
    result_label.setStyleSheet("font-size: 16px; font-weight: 700;")
    detail_label = QLabel("Set-/Raritätsabhängige Schätzung mit Live-Daten; Zustand wird transparent modelliert.")
    detail_label.setWordWrap(True)
    detail_label.setObjectName("Muted")
    box.addLayout(row)
    box.addWidget(result_label)
    box.addWidget(detail_label)
    layout.addWidget(group)
    host._jic_price_group = group  # type: ignore[attr-defined]
    host._jic_price_result = result_label  # type: ignore[attr-defined]
    host._jic_price_detail = detail_label  # type: ignore[attr-defined]
    host._jic_price_condition = condition  # type: ignore[attr-defined]

    def start() -> None:
        card = card_provider()
        if not isinstance(card, dict) or not card:
            result_label.setText("Keine Karte ausgewählt")
            return
        code, rarity = print_provider()
        fallback_condition = condition_provider() if condition_provider is not None else condition.currentText()
        if fallback_condition in CONDITIONS:
            condition.setCurrentText(fallback_condition)
        chosen_condition = condition.currentText()
        language = _infer_print_language(code, language_provider())
        button.setEnabled(False)
        result_label.setText("Preis wird ermittelt …")
        detail_label.setText("YGOPRODeck und Wechselkurs werden im Hintergrund abgefragt.")
        task = _PriceTask(card, code, rarity, language, chosen_condition)
        host._jic_price_task = task  # type: ignore[attr-defined]

        def done(value: object) -> None:
            button.setEnabled(True)
            if isinstance(value, PriceEstimate):
                primary, details = _format_price_result(value)
                result_label.setText(primary)
                detail_label.setText(details)
                detail_label.setToolTip(value.note)

        def failed(message: str) -> None:
            button.setEnabled(True)
            result_label.setText("Preis konnte nicht ermittelt werden")
            detail_label.setText(message)

        task.signals.done.connect(done)
        task.signals.failed.connect(failed)
        QThreadPool.globalInstance().start(task)

    button.clicked.connect(start)
    return group


def _detail_print(detail: Any) -> tuple[str, str]:
    preferred = str(getattr(detail, "_jic_preferred_set_code", "") or "")
    for combo in detail.findChildren(QComboBox):
        text = str(combo.currentText() or "").strip()
        match = re.match(r"^([A-Z0-9]{2,12}-(?:[A-Z]{1,3})?[A-Z0-9]+)\s*(?:[•|]\s*(.*?))?(?:\s*[•|]|$)", text, re.I)
        if match:
            code = match.group(1).strip()
            rest = str(match.group(2) or "").strip()
            rarity = rest.split("•")[-1].strip() if rest else ""
            return code, rarity
    card = getattr(detail, "card", None)
    if isinstance(card, dict):
        for item in card.get("card_sets") or []:
            if not isinstance(item, dict):
                continue
            code = str(item.get("set_code") or "")
            if preferred and code.upper() == preferred.upper():
                return code, str(item.get("set_rarity") or "")
        if card.get("card_sets"):
            first = card["card_sets"][0]
            if isinstance(first, dict):
                return str(first.get("set_code") or preferred), str(first.get("set_rarity") or "")
    return preferred, ""


def _patch_card_detail_panel() -> None:
    from justincard.ui.widgets import CardDetailPanel

    original_set_card = CardDetailPanel.set_card

    def set_card(self: Any, card: dict[str, Any] | None, preferred_set_code: str = "") -> None:
        self._jic_preferred_set_code = preferred_set_code  # type: ignore[attr-defined]
        original_set_card(self, card, preferred_set_code)
        database = getattr(self, "_jic_database", None)
        context = getattr(self, "_jic_visibility_context", None)
        if database is not None and context:
            _set_detail_profile(self, database, str(context))

    CardDetailPanel.set_card = set_card


def _patch_search_page() -> None:
    from justincard.ui.search_page import SearchPage

    original_init = SearchPage.__init__
    original_show_results = SearchPage._show_results

    def page_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        _apply_table_profile(self.table, self.database, "search_results")
        _add_display_button(self.table, self.database, "search_results")
        _set_detail_profile(self.detail, self.database, "search_detail")
        _attach_price_panel(
            self.detail,
            card_provider=lambda: getattr(self.detail, "card", None),
            print_provider=lambda: _detail_print(self.detail),
            language_provider=lambda: str((getattr(self.detail, "card", {}) or {}).get("_language") or "en"),
        )
        price_group = getattr(self.detail, "_jic_price_group", None)
        if isinstance(price_group, QWidget):
            price_group.setVisible(profile_for(_load_profiles(self.database), "search_detail").get("price", True))

    def show_results(self: Any, result: object) -> None:
        original_show_results(self, result)
        _apply_table_profile(self.table, self.database, "search_results")

    SearchPage.__init__ = page_init
    SearchPage._show_results = show_results


def _disable_removed_collection_controls(page: QWidget) -> None:
    """Remove legacy Wishlist/Trade/Purchase-price controls from collection UI."""
    for check in page.findChildren(QCheckBox):
        text = str(check.text() or "").casefold()
        if "wunsch" in text or "tausch" in text or "trade" in text or "wishlist" in text:
            check.blockSignals(True)
            check.setChecked(False)
            check.setEnabled(False)
            check.hide()
    # The recovered collection page used a QDoubleSpinBox only for Kaufpreis.
    for spin in page.findChildren(QDoubleSpinBox):
        spin.setEnabled(False)
        spin.hide()
    for label in page.findChildren(QLabel):
        text = str(label.text() or "").strip().casefold()
        if "kaufpreis" in text or text == "€":
            label.hide()


def _collection_items_for_summary(page: Any) -> list[dict[str, Any]]:
    # The headline is the value of the complete collection, not only the rows
    # currently visible through the collection search/filter field.
    database = getattr(page, "database", None)
    if database is not None:
        try:
            values = database.collection_items("")
            if isinstance(values, list):
                return [item for item in values if isinstance(item, dict)]
        except Exception:
            pass
    table = getattr(page, "table", None)
    try:
        model = table.model() if table is not None else None
    except Exception:
        model = None
    items = getattr(model, "items", None)
    if isinstance(items, list):
        return [item for item in items if isinstance(item, dict)]
    return []


def _collection_estimated_total_eur(page: Any) -> tuple[float, int]:
    """Return quantity-aware estimated collection value and unknown quantity."""
    total = 0.0
    unknown_quantity = 0
    cache = getattr(page, "_jic_market_value_cache", None)
    if not isinstance(cache, dict):
        cache = {}
        page._jic_market_value_cache = cache

    for item in _collection_items_for_summary(page):
        try:
            quantity = max(0, int(item.get("quantity") or 0))
        except (TypeError, ValueError):
            quantity = 0
        if quantity <= 0:
            continue
        cache_key = (
            str(item.get("collection_key") or ""),
            str(item.get("updated_at") or ""),
            str(item.get("print_code") or ""),
            str(item.get("rarity") or ""),
            str(item.get("language") or ""),
            str(item.get("condition") or ""),
        )
        if cache_key in cache:
            unit_value = cache[cache_key]
        else:
            unit_value = _estimated_market_value_eur(item)
            cache[cache_key] = unit_value
        if unit_value is None:
            unknown_quantity += quantity
            continue
        total += float(unit_value) * quantity
    return total, unknown_quantity


def _format_collection_total(total: float, unknown_quantity: int = 0) -> tuple[str, str]:
    value_text = f"{total:.2f} €".replace(".", ",")
    tooltip = "Summe der geschätzten Marktwerte aller vorhandenen Exemplare inklusive Stückzahl."
    if unknown_quantity:
        tooltip += f" Für {unknown_quantity} Exemplar(e) war kein Marktwert verfügbar."
    return value_text, tooltip


def _label_visual_size(label: QLabel) -> float:
    score = float(label.font().pointSizeF() or 0.0)
    match = re.search(r"font-size\s*:\s*(\d+(?:\.\d+)?)px", str(label.styleSheet() or ""), re.I)
    if match:
        try:
            score = max(score, float(match.group(1)))
        except ValueError:
            pass
    return score


def _find_market_summary_container(page: Any) -> QWidget | None:
    """Find the legacy purchase-value statistic card without relying on class names."""
    markers = ("kaufwert", "kaufpreis", "investiert", "geschätzter sammlungswert")
    for label in page.findChildren(QLabel):
        folded = str(label.text() or "").strip().casefold()
        if not any(marker in folded for marker in markers):
            continue
        parent = label.parentWidget()
        for _depth in range(4):
            if parent is None:
                break
            labels = parent.findChildren(QLabel)
            numeric = [
                item for item in labels
                if re.fullmatch(r"\s*[0-9][0-9.,\s]*\s*€?\s*", str(item.text() or ""))
            ]
            # Statistic cards normally contain a title, one large numeric value
            # and an optional subtitle. Pick the smallest ancestor matching that.
            if 2 <= len(labels) <= 8 and numeric:
                return parent
            parent = parent.parentWidget()
    return None


def _render_market_summary_card(page: Any, value_text: str, tooltip: str) -> bool:
    container = _find_market_summary_container(page)
    if not isinstance(container, QWidget):
        return False
    labels = container.findChildren(QLabel)
    if not labels:
        return False

    numeric = [
        label for label in labels
        if re.fullmatch(r"\s*[0-9][0-9.,\s]*\s*€?\s*", str(label.text() or ""))
    ]
    if not numeric:
        return False
    value_label = max(numeric, key=_label_visual_size)

    descriptive = [
        label for label in labels
        if label is not value_label and any(
            token in str(label.text() or "").casefold()
            for token in ("kauf", "investiert", "geschätzter sammlungswert", "marktwert")
        )
    ]
    title_label = descriptive[0] if descriptive else None

    if isinstance(title_label, QLabel):
        title_label.setText("Geschätzter Sammlungswert")
        title_label.setToolTip(tooltip)
        title_label.show()

    value_label.setText(value_text)
    value_label.setToolTip(tooltip)
    # Keep the recovered dashboard's large-number typography. If it had no
    # explicit size, ensure the collection value is still clearly prominent.
    if _label_visual_size(value_label) < 20:
        value_label.setStyleSheet((value_label.styleSheet() or "") + "; font-size: 28px; font-weight: 700;")
    value_label.show()

    # Remove duplicated subtitles/values such as the 1.2.6 screenshot's
    # "Geschätzter Sammlungswert: …" above and below a stale large 0,00 €.
    for label in labels:
        if label is value_label or label is title_label:
            continue
        folded = str(label.text() or "").strip().casefold()
        if (
            "kauf" in folded
            or "investiert" in folded
            or "geschätzter sammlungswert" in folded
            or re.fullmatch(r"\s*[0-9][0-9.,\s]*\s*€?\s*", str(label.text() or ""))
        ):
            label.hide()
    return True


def _update_collection_summary(page: Any) -> None:
    """Show one clean quantity-aware market total and remove legacy trade stats."""
    total, unknown_quantity = _collection_estimated_total_eur(page)
    value_text, tooltip = _format_collection_total(total, unknown_quantity)

    for group in page.findChildren(QGroupBox):
        title = str(group.title() or "").casefold()
        if "tausch" in title or "trade" in title:
            group.hide()

    for label in page.findChildren(QLabel):
        folded = str(label.text() or "").strip().casefold()
        if "tausch" in folded or "trade" in folded or "wunsch" in folded or "wishlist" in folded:
            label.hide()

    if _render_market_summary_card(page, value_text, tooltip):
        extra = getattr(page, "_jic_market_total_label", None)
        if isinstance(extra, QLabel):
            extra.hide()
        return

    # Defensive fallback for layouts without the legacy statistics card.
    summary = getattr(page, "_jic_market_total_label", None)
    if not isinstance(summary, QLabel):
        summary = QLabel(page)
        summary.setObjectName("CollectionEstimatedTotal")
        summary.setStyleSheet("font-size: 28px; font-weight: 700;")
        table = getattr(page, "table", None)
        parent = table.parentWidget() if table is not None else page
        layout = _resolve_widget_layout(parent)
        if isinstance(layout, QVBoxLayout) and table is not None:
            index = layout.indexOf(table)
            layout.insertWidget(max(0, index), summary)
        else:
            root_layout = _resolve_widget_layout(page)
            if isinstance(root_layout, QVBoxLayout):
                root_layout.addWidget(summary)
        page._jic_market_total_label = summary
    summary.setText(value_text)
    summary.setToolTip(tooltip)
    summary.show()


def _set_collection_estimate(page: Any, item: dict[str, Any] | None) -> None:
    group = getattr(page, "_jic_collection_price_group", None)
    if not isinstance(group, QWidget):
        return
    host = group.parentWidget()
    result_label = getattr(host, "_jic_price_result", None) if host is not None else None
    detail_label = getattr(host, "_jic_price_detail", None) if host is not None else None
    if not isinstance(item, dict):
        if isinstance(result_label, QLabel):
            result_label.setText("Keine Karte ausgewählt")
        if isinstance(detail_label, QLabel):
            detail_label.setText("")
        return
    card = item.get("card") if isinstance(item.get("card"), dict) else None
    if card is None and isinstance(item.get("card_json"), dict):
        card = item.get("card_json")
    if card is None and isinstance(item.get("card_json"), str):
        try:
            import json as _json
            loaded = _json.loads(item.get("card_json") or "{}")
            if isinstance(loaded, dict):
                card = loaded
        except Exception:
            card = None
    if not isinstance(card, dict):
        return
    try:
        estimate = estimate_price(
            card,
            print_code=str(item.get("print_code") or ""),
            rarity=str(item.get("rarity") or ""),
            language=_infer_print_language(str(item.get("print_code") or ""), str(item.get("language") or "en")),
            condition=str(item.get("condition") or "Near Mint"),
            live=False,
        )
    except Exception:
        return
    if isinstance(result_label, QLabel):
        result_label.setText(
            "Kein Marktpreis verfügbar" if estimate.amount_eur is None
            else f"Geschätzter Marktwert: {estimate.amount_eur:.2f} €".replace(".", ",")
        )
    if isinstance(detail_label, QLabel):
        _primary, details = _format_price_result(estimate)
        detail_label.setText(details)


def _patch_collection_page() -> None:
    from justincard.ui.collection_page import CollectionPage

    original_init = CollectionPage.__init__
    original_refresh = CollectionPage.refresh
    original_show_item = CollectionPage._show_item

    def page_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        _disable_removed_collection_controls(self)
        _update_collection_summary(self)
        _apply_table_profile(self.table, self.database, "collection_table")
        _add_display_button(self.table, self.database, "collection_table")
        self._jic_selected_collection_item = None
        # v1.0.8 had three temporary local presets.  v1.0.11 replaces them by
        # persistent, per-location profiles, so hide the old controls.
        for attr in ("_jic_all_info_button", "_jic_basic_info_button", "_jic_name_only_button"):
            old_button = getattr(self, attr, None)
            if isinstance(old_button, QWidget):
                old_button.hide()

        host = self.selected_print.parentWidget() if hasattr(self, "selected_print") else None
        if isinstance(host, QWidget):
            _attach_price_panel(
                host,
                card_provider=lambda: (
                    (self._jic_selected_collection_item or {}).get("card")
                    if isinstance(self._jic_selected_collection_item, dict)
                    else None
                ),
                print_provider=lambda: (
                    str((self._jic_selected_collection_item or {}).get("print_code") or ""),
                    str((self._jic_selected_collection_item or {}).get("rarity") or ""),
                ),
                language_provider=lambda: str((self._jic_selected_collection_item or {}).get("language") or "en"),
                condition_provider=lambda: str((self._jic_selected_collection_item or {}).get("condition") or "Near Mint"),
            )
            group = getattr(host, "_jic_price_group", None)
            self._jic_collection_price_group = group
            if isinstance(group, QWidget):
                group.setVisible(profile_for(_load_profiles(self.database), "collection_detail").get("price", True))

        def refresh_visibility_context(context: str) -> None:
            if context == "collection_table":
                _apply_table_profile(self.table, self.database, "collection_table")
            elif context == "collection_detail" and isinstance(self._jic_selected_collection_item, dict):
                show_item(self, self._jic_selected_collection_item)
        self._jic_refresh_visibility_context = refresh_visibility_context

    def refresh(self: Any) -> None:
        original_refresh(self)
        _disable_removed_collection_controls(self)
        _update_collection_summary(self)
        _apply_table_profile(self.table, self.database, "collection_table")

    def show_item(self: Any, item: Any) -> None:
        self._jic_selected_collection_item = item if isinstance(item, dict) else None
        original_show_item(self, item)
        _disable_removed_collection_controls(self)
        prefs = profile_for(_load_profiles(self.database), "collection_detail")
        if not isinstance(item, dict):
            _set_collection_estimate(self, None)
            return
        if hasattr(self, "selected_print"):
            parts: list[str] = []
            if prefs.get("set_code", True):
                parts.append(str(item.get("print_code") or "Kein Set-Code"))
            if prefs.get("set_name", True) and item.get("set_name"):
                parts.append(str(item.get("set_name")))
            if prefs.get("rarity", True) and item.get("rarity"):
                parts.append(str(item.get("rarity")))
            if prefs.get("language", True) and item.get("language"):
                parts.append(str(item.get("language")).upper())
            if prefs.get("artwork", True):
                art = artwork_label(item, "collection")
                if art and art != "–":
                    parts.append(art)
            self.selected_print.setText(" • ".join(parts))
            self.selected_print.setVisible(bool(parts))
        _set_collection_estimate(self, item)
        group = getattr(self, "_jic_collection_price_group", None)
        if isinstance(group, QWidget):
            group.setVisible(bool(prefs.get("price", True)))
            condition = getattr(group.parentWidget(), "_jic_price_condition", None)
            if isinstance(condition, QComboBox):
                wanted = str(item.get("condition") or "Near Mint")
                if condition.findText(wanted) >= 0:
                    condition.setCurrentText(wanted)

    CollectionPage.__init__ = page_init
    CollectionPage.refresh = refresh
    CollectionPage._show_item = show_item


def _patch_decks_page() -> None:
    from justincard.ui.decks_page import DecksPage

    original_init = DecksPage.__init__
    original_refresh_collection = DecksPage.refresh_collection
    original_refresh_deck_cards = DecksPage.refresh_deck_cards

    def page_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        _apply_table_profile(self.collection_table, self.database, "deck_pool")
        _apply_table_profile(self.deck_table, self.database, "deck_table")
        _add_display_button(self.collection_table, self.database, "deck_pool")
        _add_display_button(self.deck_table, self.database, "deck_table")

    def refresh_collection(self: Any) -> None:
        original_refresh_collection(self)
        _apply_table_profile(self.collection_table, self.database, "deck_pool")

    def refresh_deck_cards(self: Any) -> None:
        original_refresh_deck_cards(self)
        _apply_table_profile(self.deck_table, self.database, "deck_table")

    DecksPage.__init__ = page_init
    DecksPage.refresh_collection = refresh_collection
    DecksPage.refresh_deck_cards = refresh_deck_cards


def _patch_scanner_page() -> None:
    try:
        from justincard.ui.scanner_page import ScannerPage
        from justincard.ui.widgets import CardDetailPanel
    except Exception:
        return
    original_init = ScannerPage.__init__

    def page_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        database = getattr(self, "database", None)
        if database is None:
            return
        for detail in self.findChildren(CardDetailPanel):
            _set_detail_profile(detail, database, "scanner_detail")

    ScannerPage.__init__ = page_init


def _add_profile_settings(page: Any) -> None:
    scroll = page.findChild(QScrollArea)
    content = scroll.widget() if scroll is not None else None
    layout = _resolve_widget_layout(content)
    if not isinstance(layout, QVBoxLayout):
        return

    # Hide the old global 1.0.8 control.  Its value is retained only as a
    # migration source for users upgrading from 1.0.8-1.0.10.
    for group in content.findChildren(QGroupBox):
        if group.title() == "Anzeigeoptionen – Karteninformationen":
            group.hide()

    group = QGroupBox("Anzeigeoptionen – je Bereich")
    outer = QVBoxLayout(group)
    intro = QLabel(
        "Suche, Sammlung, Deckbuilder und Kartendetails besitzen jetzt getrennte Anzeigeprofile. "
        "Eine Änderung hier wirkt ausschließlich auf den ausgewählten Bereich."
    )
    intro.setWordWrap(True)
    intro.setObjectName("Muted")
    outer.addWidget(intro)

    selector_row = QHBoxLayout()
    selector_row.addWidget(QLabel("Bereich"))
    selector = QComboBox()
    for key, label in DISPLAY_CONTEXTS:
        selector.addItem(label, key)
    selector.setMinimumHeight(36)
    selector.setMinimumWidth(320)
    selector_row.addWidget(selector, 1)
    outer.addLayout(selector_row)

    grid_holder = QVBoxLayout()
    outer.addLayout(grid_holder)
    action_row = QHBoxLayout()
    all_button = QPushButton("Alle Infos")
    basic_button = QPushButton("Basisansicht")
    none_button = QPushButton("Nur Namen")
    for button in (all_button, basic_button, none_button):
        button.setProperty("role", "ghost")
        button.setMinimumHeight(36)
        action_row.addWidget(button)
    action_row.addStretch(1)
    outer.addLayout(action_row)

    state: dict[str, Any] = {"widget": None, "preset": None}

    def saved(context: str) -> None:
        _refresh_context(page.window(), page.database, context)
        try:
            page.status_message.emit(f"Anzeigeprofil gespeichert: {context_label(context)}")
        except Exception:
            pass

    def rebuild() -> None:
        previous = state.get("widget")
        if isinstance(previous, QWidget):
            grid_holder.removeWidget(previous)
            previous.deleteLater()
        context = str(selector.currentData() or "search_results")
        widget, _buttons, preset = _build_visibility_grid(page.database, context, on_saved=saved)
        state["widget"] = widget
        state["preset"] = preset
        grid_holder.addWidget(widget)

    selector.currentIndexChanged.connect(lambda _idx: rebuild())
    all_button.clicked.connect(lambda: state.get("preset") and state["preset"]("all"))
    basic_button.clicked.connect(lambda: state.get("preset") and state["preset"]("basic"))
    none_button.clicked.connect(lambda: state.get("preset") and state["preset"]("none"))
    rebuild()
    layout.insertWidget(max(0, layout.count() - 1), group)


def _patch_settings_page() -> None:
    from justincard.ui.settings_page import SettingsPage

    original_init = SettingsPage.__init__

    def page_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        _add_profile_settings(self)

    SettingsPage.__init__ = page_init


def _patch_main_window() -> None:
    from justincard.ui.main_window import MainWindow

    original_init = MainWindow.__init__

    def window_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        # No global visibility pass here: each page has already been assigned a
        # dedicated context by the v1.0.11 wrappers above.
        for table in self.findChildren(QTableView):
            context = getattr(table, "_jic_visibility_profile_context", None)
            if context:
                _apply_table_profile(table, self.database, str(context))
        try:
            from justincard.ui.widgets import CardDetailPanel
            for detail in self.findChildren(CardDetailPanel):
                context = getattr(detail, "_jic_visibility_context", None)
                if context:
                    _set_detail_profile(detail, self.database, str(context))
        except Exception:
            pass

    MainWindow.__init__ = window_init


def install_v111_patches() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _patch_card_detail_panel()
    _patch_search_page()
    _patch_collection_page()
    _patch_decks_page()
    _patch_scanner_page()
    _patch_settings_page()
    _patch_main_window()
    _INSTALLED = True


__all__ = ["install_v111_patches"]
