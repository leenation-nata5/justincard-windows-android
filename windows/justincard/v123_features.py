from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QPushButton

from justincard.v121_features import install_v121_patches

_INSTALLED = False


def _patch_deck_buttons() -> None:
    from justincard.ui.decks_page import DecksPage

    original_init = DecksPage.__init__

    def page_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        for button in self.findChildren(QPushButton):
            text = str(button.text() or "").strip().casefold().replace("deck", "")
            compact = " ".join(text.split())
            if "main" in compact and compact.startswith("+"):
                button.setText("+ Automatisch (Main / Extra)")
                button.setToolTip(
                    "Just InCard erkennt automatisch, ob die Karte ins Main Deck oder Extra Deck gehört."
                )
            elif "extra" in compact and compact.startswith("+"):
                # Extra Deck is now derived from the card type. Keeping this
                # button would allow an illegal manual zone choice.
                button.hide()
            elif "side" in compact and compact.startswith("+"):
                button.setText("+ Side Deck")
                button.setToolTip("Nur das Side Deck wird weiterhin manuell gewählt.")

    DecksPage.__init__ = page_init


def install_v123_patches() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    install_v121_patches()
    _patch_deck_buttons()
    _INSTALLED = True


__all__ = ["install_v123_patches"]
