from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QGroupBox, QHBoxLayout, QLabel, QSpinBox

from justincard.v111_features import _resolve_widget_layout
from justincard.v120_features import install_v120_patches
from justincard.v121_core import MAX_ADD_QUANTITY, normalize_add_quantity

_INSTALLED = False


def _patch_scanner_quantity() -> None:
    from justincard.ui.scanner_page import ScannerPage

    original_init = ScannerPage.__init__
    original_accept_current = ScannerPage.accept_current
    original_accept_all_safe = ScannerPage.accept_all_safe

    def page_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        if getattr(self, "_jic_add_quantity", None) is not None:
            return

        quantity = QSpinBox(self)
        quantity.setObjectName("ScannerAddQuantity")
        quantity.setRange(1, MAX_ADD_QUANTITY)
        quantity.setValue(1)
        quantity.setMinimumWidth(92)
        quantity.setToolTip("Anzahl der erkannten Karte, die der Sammlung hinzugefügt wird.")
        self._jic_add_quantity = quantity

        group = QGroupBox("Zur Sammlung hinzufügen", self)
        group.setObjectName("ScannerQuantityGroup")
        row = QHBoxLayout(group)
        label = QLabel("Menge", group)
        label.setObjectName("Muted")
        row.addWidget(label)
        row.addWidget(quantity)
        row.addStretch(1)

        host = getattr(self, "card_detail", None)
        layout = _resolve_widget_layout(host)
        if layout is None:
            layout = _resolve_widget_layout(self)
        if layout is not None:
            layout.addWidget(group)
        else:
            group.setParent(self)
            group.hide()

    def accept_current(self: Any) -> Any:
        spin = getattr(self, "_jic_add_quantity", None)
        if not isinstance(spin, QSpinBox):
            return original_accept_current(self)

        quantity = normalize_add_quantity(spin.value())
        database = getattr(self, "database", None)
        original_add = getattr(database, "add_to_collection", None)
        if not callable(original_add):
            return original_accept_current(self)

        try:
            row = int(self.result_list.currentRow())
        except Exception:
            row = -1
        accepted_before = row in getattr(self, "_accepted_results", set())

        def add_with_selected_quantity(
            card: Any,
            print_item: Any = None,
            _quantity: int = 1,
            *args: Any,
            **kwargs: Any,
        ) -> Any:
            return original_add(card, print_item, quantity, *args, **kwargs)

        # ScannerPage.accept_current is synchronous. Replacing this single
        # instance method for the duration of the call lets the unchanged
        # legacy scan workflow keep its logging, exact-print selection and UI
        # feedback while using the user-selected quantity.
        database.add_to_collection = add_with_selected_quantity
        try:
            result = original_accept_current(self)
        finally:
            database.add_to_collection = original_add

        accepted_after = row in getattr(self, "_accepted_results", set())
        if accepted_after and not accepted_before and not bool(getattr(self, "_jic_bulk_accept", False)):
            spin.setValue(1)
        return result

    def accept_all_safe(self: Any) -> Any:
        spin = getattr(self, "_jic_add_quantity", None)
        self._jic_bulk_accept = True
        try:
            return original_accept_all_safe(self)
        finally:
            self._jic_bulk_accept = False
            if isinstance(spin, QSpinBox):
                spin.setValue(1)

    ScannerPage.__init__ = page_init
    ScannerPage.accept_current = accept_current
    ScannerPage.accept_all_safe = accept_all_safe


def install_v121_patches() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    install_v120_patches()
    _patch_scanner_quantity()
    _INSTALLED = True


__all__ = ["install_v121_patches"]
