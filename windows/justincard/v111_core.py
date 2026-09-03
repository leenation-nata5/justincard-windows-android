from __future__ import annotations

from typing import Any

from justincard.v108_core import (
    CARD_INFORMATION_FIELDS,
    DEFAULT_VISIBILITY,
    normalize_visibility,
    visibility_preset,
)

PROFILE_SETTING_KEY = "card_information_visibility_profiles_v111"

DISPLAY_CONTEXTS: tuple[tuple[str, str], ...] = (
    ("search_results", "Suche – Ergebnisliste"),
    ("search_detail", "Suche – Kartendetails"),
    ("collection_table", "Sammlung – Tabelle"),
    ("collection_detail", "Sammlung – Kartendetails"),
    ("deck_pool", "Decks – Sammlungsliste"),
    ("deck_table", "Decks – Deckliste"),
    ("scanner_detail", "Scanner – Kartendetails"),
)

DEFAULT_PROFILES: dict[str, dict[str, bool]] = {
    key: dict(DEFAULT_VISIBILITY) for key, _label in DISPLAY_CONTEXTS
}

# Compact table defaults are intentionally different from detail views.  This
# is exactly why v1.0.11 stores profiles per place instead of globally.
for context in ("search_results", "collection_table", "deck_pool", "deck_table"):
    DEFAULT_PROFILES[context]["effect"] = False
    DEFAULT_PROFILES[context]["archetype"] = False

# Set-related fields are useful in lists but usually duplicate the print chooser
# in card detail panes.
for context in ("search_detail", "collection_detail", "scanner_detail"):
    DEFAULT_PROFILES[context]["sets"] = True


def normalize_profiles(value: Any, legacy: Any = None) -> dict[str, dict[str, bool]]:
    """Return a complete, independent visibility profile per UI location.

    Older 1.0.8-1.0.10 installations only had one global visibility dictionary.
    If no v1.0.11 profiles exist, that legacy dictionary seeds every profile so
    existing user choices are preserved rather than discarded.
    """
    result = {key: dict(prefs) for key, prefs in DEFAULT_PROFILES.items()}
    if isinstance(value, dict):
        # New shape: {context: {field: bool}}
        nested = any(isinstance(value.get(context), dict) for context, _ in DISPLAY_CONTEXTS)
        if nested:
            for context, _label in DISPLAY_CONTEXTS:
                if context in value:
                    result[context] = normalize_visibility(value.get(context))
            return result
        # Tolerate an accidentally stored old/flat shape under the new key.
        if value:
            seeded = normalize_visibility(value)
            return {context: dict(seeded) for context, _label in DISPLAY_CONTEXTS}

    if legacy is not None:
        seeded = normalize_visibility(legacy)
        return {context: dict(seeded) for context, _label in DISPLAY_CONTEXTS}
    return result


def profile_for(profiles: dict[str, dict[str, bool]], context: str) -> dict[str, bool]:
    return normalize_visibility(profiles.get(context, DEFAULT_PROFILES.get(context, DEFAULT_VISIBILITY)))


def set_profile_field(
    profiles: dict[str, dict[str, bool]], context: str, field: str, enabled: bool
) -> dict[str, dict[str, bool]]:
    updated = {name: dict(values) for name, values in profiles.items()}
    updated.setdefault(context, dict(DEFAULT_VISIBILITY))
    updated[context][field] = bool(enabled)
    return normalize_profiles(updated)


def preset_for_context(mode: str) -> dict[str, bool]:
    return visibility_preset(mode)


def context_label(context: str) -> str:
    return dict(DISPLAY_CONTEXTS).get(context, context)


__all__ = [
    "CARD_INFORMATION_FIELDS",
    "DISPLAY_CONTEXTS",
    "PROFILE_SETTING_KEY",
    "DEFAULT_PROFILES",
    "normalize_profiles",
    "profile_for",
    "set_profile_field",
    "preset_for_context",
    "context_label",
]
