from __future__ import annotations

from typing import Any

EXTRA_DECK_TOKENS = ("fusion", "synchro", "xyz", "link")


def card_requires_extra_deck(card: Any) -> bool:
    """Return True for cards that legally start in the Extra Deck.

    Yu-Gi-Oh! Fusion, Synchro, Xyz and Link monsters belong to the Extra Deck.
    Hybrid Pendulum variants are handled as Extra Deck cards when their type or
    frame also identifies one of those mechanics. Ritual/Pendulum/Main-Deck
    monsters remain Main Deck cards. Tokens/Skills are not treated as Extra.
    """
    if not isinstance(card, dict):
        return False
    tokens = " ".join(
        str(card.get(key) or "").casefold()
        for key in ("type", "frameType", "frame_type")
    )
    return any(token in tokens for token in EXTRA_DECK_TOKENS)


def resolved_deck_zone(card: Any, requested_zone: str = "main") -> str:
    requested = str(requested_zone or "main").strip().casefold()
    if requested == "side":
        return "side"
    return "extra" if card_requires_extra_deck(card) else "main"


def collection_sheet_category(card: Any) -> str:
    """Map API card types to the user-facing Google-Sheets categories."""
    if not isinstance(card, dict):
        return "Sonstige"
    card_type = str(card.get("type") or "").casefold()
    frame = str(card.get("frameType") or card.get("frame_type") or "").casefold()
    combined = f"{card_type} {frame}"
    if "spell" in combined:
        return "Zauberkarten"
    if "trap" in combined:
        return "Fallenkarten"
    if "tuner" in combined:
        return "Empfänger"
    if "monster" in combined or any(token in combined for token in EXTRA_DECK_TOKENS) or frame in {
        "normal", "effect", "ritual", "pendulum", "ritual_pendulum"
    }:
        return "Monster"
    return "Sonstige"


def main_deck_section(card: Any) -> str:
    """Category label used inside a deck sheet's Main Deck sections."""
    if not isinstance(card, dict):
        return "Monsterkarten"
    text = " ".join(
        str(card.get(key) or "").casefold()
        for key in ("type", "frameType", "frame_type")
    )
    if "spell" in text:
        return "Zauberkarten"
    if "trap" in text:
        return "Fallenkarten"
    return "Monsterkarten"


__all__ = [
    "EXTRA_DECK_TOKENS",
    "card_requires_extra_deck",
    "resolved_deck_zone",
    "collection_sheet_category",
    "main_deck_section",
]
