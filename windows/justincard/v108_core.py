from __future__ import annotations

import json
from typing import Any, Iterable

VISIBILITY_SETTING_KEY = "card_information_visibility_v108"

# Name is intentionally not configurable: the user explicitly requested that
# card names are always completely visible anywhere a card is shown.
CARD_INFORMATION_FIELDS: tuple[tuple[str, str], ...] = (
    ("passcode", "Passcode"),
    ("set_code", "Set-Code"),
    ("set_name", "Set"),
    ("rarity", "Seltenheit"),
    ("language", "Sprache"),
    ("artwork", "Artwork / Alt Art"),
    ("card_type", "Kartentyp"),
    ("race", "Typ / Rasse"),
    ("attribute", "Attribut"),
    ("atk", "ATK"),
    ("def", "DEF"),
    ("level", "Stufe / Rang"),
    ("scale", "Pendel-Skala"),
    ("link", "Linkwert"),
    ("archetype", "Archetyp"),
    ("effect", "Effekttext"),
    ("quantity", "Menge / Besitz"),
    ("condition", "Zustand"),
    ("market_value", "Geschätzter Marktwert"),
    ("status", "Status"),
    ("price", "Marktpreis"),
    ("sets", "Set-Übersicht"),
)

DEFAULT_VISIBILITY: dict[str, bool] = {key: True for key, _ in CARD_INFORMATION_FIELDS}
# Long text columns are available, but start hidden to keep the first launch
# close to the familiar 1.0.7 layout. They can be enabled with one click.
DEFAULT_VISIBILITY["effect"] = False
DEFAULT_VISIBILITY["archetype"] = False

BASIC_COLLECTION_FIELDS = {
    "set_code",
    "set_name",
    "rarity",
    "language",
    "quantity",
}


def normalize_visibility(value: Any) -> dict[str, bool]:
    result = dict(DEFAULT_VISIBILITY)
    if isinstance(value, dict):
        for key in result:
            if key in value:
                result[key] = bool(value[key])
    elif isinstance(value, (list, tuple, set)):
        enabled = {str(item) for item in value}
        for key in result:
            result[key] = key in enabled
    return result


def visibility_preset(mode: str) -> dict[str, bool]:
    if str(mode).lower() in {"all", "alles", "full"}:
        return {key: True for key, _ in CARD_INFORMATION_FIELDS}
    if str(mode).lower() in {"basic", "basis", "minimal"}:
        return {key: key in BASIC_COLLECTION_FIELDS for key, _ in CARD_INFORMATION_FIELDS}
    if str(mode).lower() in {"none", "off", "aus", "name-only"}:
        return {key: False for key, _ in CARD_INFORMATION_FIELDS}
    return dict(DEFAULT_VISIBILITY)


def placeholder_collection_key(collection_key: str) -> str:
    return f"__placeholder__:{str(collection_key)}"


def is_placeholder_item(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    if bool(item.get("is_placeholder") or item.get("placeholder")):
        return True
    return str(item.get("collection_key") or "").startswith("__placeholder__:")


def _nested_card(record: dict[str, Any]) -> dict[str, Any]:
    card = record.get("card")
    if isinstance(card, dict):
        return card
    raw = record.get("card_json")
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            loaded = json.loads(raw)
            if isinstance(loaded, dict):
                return loaded
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
    return record


def record_value(record: Any, key: str, context: str = "card") -> Any:
    if not isinstance(record, dict):
        return ""
    card = _nested_card(record)

    direct = record.get(key)
    if direct not in (None, ""):
        return direct

    aliases: dict[str, tuple[str, ...]] = {
        "name": ("name", "card_name", "title"),
        "id": ("id", "card_id", "passcode"),
        "passcode": ("id", "card_id", "passcode"),
        "language": ("language", "_language", "sprache"),
        "type": ("type", "card_type"),
        "card_type": ("type", "card_type"),
        "race": ("race", "monster_type"),
        "attribute": ("attribute",),
        "atk": ("atk",),
        "def": ("def",),
        "level": ("level", "rank"),
        "scale": ("scale",),
        "link": ("linkval", "link"),
        "archetype": ("archetype",),
        "effect": ("desc", "effect", "text"),
        "print_code": ("print_code", "set_code", "code"),
        "set_code": ("print_code", "set_code", "code"),
        "set_name": ("set_name", "set"),
        "rarity": ("rarity", "set_rarity"),
        "quantity": ("quantity", "count", "amount", "menge"),
        "condition": ("condition", "zustand"),
        "purchase_price": ("purchase_price", "kaufpreis", "price_paid"),
        "market_value": ("market_value", "estimated_market_value", "marktwert"),
        "price": ("_price_min", "price_min"),
        "owned": ("_owned", "owned", "quantity"),
        "zone": ("zone",),
        "status": ("status",),
        "artwork": ("artwork_label", "artwork", "art_label"),
    }
    for candidate in aliases.get(key, (key,)):
        if candidate in record and record[candidate] not in (None, ""):
            return record[candidate]
        if candidate in card and card[candidate] not in (None, ""):
            return card[candidate]

    if key == "flags":
        # Wishlist/trade functionality was removed from the Windows app.
        # Keep the legacy key readable for old backups without exposing status.
        return ""
    if key == "sets":
        sets = card.get("card_sets")
        if isinstance(sets, list):
            return ", ".join(
                str(item.get("set_code") or item.get("set_name") or "")
                for item in sets
                if isinstance(item, dict)
            )
    return ""


def sortable_value(record: Any, key: str, context: str = "card") -> tuple[int, Any]:
    value = record_value(record, key, context)
    if value is None or value == "" or value == "–":
        return (2, "")
    if isinstance(value, bool):
        return (0, int(value))
    if isinstance(value, (int, float)):
        return (0, value)
    text = str(value).strip()
    try:
        return (0, float(text.replace("€", "").replace(",", ".").strip()))
    except (TypeError, ValueError):
        return (1, text.casefold())


def first_present(mapping: dict[str, Any], keys: Iterable[str], default: Any = None) -> Any:
    for key in keys:
        if key in mapping and mapping[key] not in (None, ""):
            return mapping[key]
    return default


def normalize_backup_payload(payload: Any) -> dict[str, Any]:
    """Normalize old Windows/Android backup shapes into one v1.0.8 payload.

    This function is intentionally tolerant: older project versions used
    different names for collection/count/set fields, and some Android exports
    were a bare list instead of an object.
    """
    if isinstance(payload, list):
        payload = {"collection": payload}
    if not isinstance(payload, dict):
        raise ValueError("Die Sicherung enthält keine unterstützte Datenstruktur.")

    if isinstance(payload.get("data"), dict):
        merged = dict(payload["data"])
        for key, value in payload.items():
            if key != "data" and key not in merged:
                merged[key] = value
        payload = merged

    collection = first_present(payload, ("collection", "sammlung", "items", "cards"), [])
    decks = first_present(payload, ("decks", "deck_list", "decklisten"), [])
    deck_cards = first_present(payload, ("deck_cards", "deckCards", "deck_karten"), [])
    settings = first_present(payload, ("settings", "preferences", "einstellungen"), {})

    if isinstance(collection, dict):
        # Some legacy exports keyed entries by collection id.
        collection = list(collection.values())
    if not isinstance(collection, list):
        collection = []
    if isinstance(decks, dict):
        decks = list(decks.values())
    if not isinstance(decks, list):
        decks = []
    if isinstance(deck_cards, dict):
        expanded: list[dict[str, Any]] = []
        for deck_id, values in deck_cards.items():
            if isinstance(values, list):
                for value in values:
                    if isinstance(value, dict):
                        item = dict(value)
                        item.setdefault("deck_id", deck_id)
                        expanded.append(item)
        deck_cards = expanded
    if not isinstance(deck_cards, list):
        deck_cards = []
    if not isinstance(settings, dict):
        settings = {}

    normalized_collection: list[dict[str, Any]] = []
    for raw in collection:
        if not isinstance(raw, dict):
            continue
        card = _nested_card(raw)
        if not isinstance(card, dict):
            card = {}
        # Bare legacy card entries often stored the card itself on the row.
        if not card.get("name") and raw.get("name"):
            card = dict(card)
            for field in (
                "id", "name", "desc", "type", "race", "attribute", "atk", "def",
                "level", "scale", "linkval", "archetype", "card_sets", "card_images",
            ):
                if field in raw:
                    card[field] = raw[field]

        quantity = first_present(raw, ("quantity", "count", "amount", "menge"), 1)
        try:
            quantity = max(0, int(quantity))
        except (TypeError, ValueError):
            quantity = 1
        normalized_collection.append({
            "collection_key": str(first_present(raw, ("collection_key", "key", "id_key"), "") or ""),
            "card": card,
            "print_code": str(first_present(raw, ("print_code", "set_code", "code", "_collection_set_code"), "") or ""),
            "set_name": str(first_present(raw, ("set_name", "set", "_collection_set_name"), "") or ""),
            "rarity": str(first_present(raw, ("rarity", "set_rarity", "_collection_set_rarity"), "") or ""),
            "artwork_url": str(first_present(raw, ("artwork_url", "image_url", "image"), "") or ""),
            "language": str(first_present(raw, ("language", "sprache", "_language"), card.get("_language", "")) or ""),
            "quantity": quantity,
            "condition": str(first_present(raw, ("condition", "zustand"), "Unbewertet") or "Unbewertet"),
            # Legacy purchase/trade/wishlist fields are accepted during import,
            # but intentionally not restored as active collection features.
            "purchase_price": None,
            "note": str(first_present(raw, ("note", "notiz"), "") or ""),
            "wishlist": False,
            "trade": False,
        })

    normalized_decks: list[dict[str, Any]] = [dict(item) for item in decks if isinstance(item, dict)]
    normalized_deck_cards: list[dict[str, Any]] = [dict(item) for item in deck_cards if isinstance(item, dict)]

    return {
        "format": "justincard-windows-backup-v2",
        "source_format": str(payload.get("format") or "legacy/unknown"),
        "created_at": payload.get("created_at"),
        "collection": normalized_collection,
        "decks": normalized_decks,
        "deck_cards": normalized_deck_cards,
        "settings": settings,
    }



def normalize_artwork_url(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text.split("?", 1)[0].rstrip("/").casefold()


def artwork_urls(card: Any) -> list[str]:
    if not isinstance(card, dict):
        return []
    urls: list[str] = []
    seen: set[str] = set()
    for raw in card.get("card_images") or []:
        if not isinstance(raw, dict):
            continue
        for key in ("image_url", "image_url_small", "image_url_cropped", "artwork_url"):
            value = str(raw.get(key) or "").strip()
            normalized = normalize_artwork_url(value)
            if normalized and normalized not in seen:
                seen.add(normalized)
                urls.append(value)
                break
    direct = str(card.get("artwork_url") or card.get("image_url") or "").strip()
    normalized_direct = normalize_artwork_url(direct)
    if normalized_direct and normalized_direct not in seen:
        seen.add(normalized_direct)
        urls.insert(0, direct)
    return urls


def artwork_label(record: Any, context: str = "card") -> str:
    if not isinstance(record, dict):
        return ""
    card = _nested_card(record)
    urls = artwork_urls(card)
    selected = str(record.get("artwork_url") or card.get("artwork_url") or "").strip()
    selected_norm = normalize_artwork_url(selected)

    if not urls:
        return "Standard-Artwork" if selected else "–"

    if selected_norm:
        for index, candidate in enumerate(urls):
            if normalize_artwork_url(candidate) == selected_norm:
                if len(urls) == 1:
                    return "Standard-Artwork"
                if index == 0:
                    return f"Artwork 1/{len(urls)} (Standard)"
                return f"Artwork {index + 1}/{len(urls)} (Alt Art)"

    if len(urls) == 1:
        return "Standard-Artwork"
    if context in {"collection", "deck"}:
        return f"{len(urls)} Artworks verfügbar"
    return f"{len(urls)} Artworks"
