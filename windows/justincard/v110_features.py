from __future__ import annotations

from typing import Any

from justincard.v108_core import artwork_label
from justincard.v111_features import install_v111_patches

_INSTALLED = False


def install_v110_patches() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    install_v111_patches()
    try:
        from justincard.ui.collection_page import CollectionPage

        original_show_item = CollectionPage._show_item

        def show_item(self: Any, item: Any) -> None:
            original_show_item(self, item)
            label = getattr(self, "selected_print", None)
            if not isinstance(item, dict) or label is None:
                return
            current_text = str(label.text() or "").strip()
            art = artwork_label(item, "collection")
            if art and art != "–" and art not in current_text:
                label.setText((current_text + " • " + art).strip(" •"))

        CollectionPage._show_item = show_item
    except Exception:
        pass
    _INSTALLED = True


__all__ = ["install_v110_patches"]
