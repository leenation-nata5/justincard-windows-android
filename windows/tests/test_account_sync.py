from __future__ import annotations

from justincard.account_sync import (
    ACCOUNT_SCHEMA,
    collection_identity,
    deck_card_identity,
    deck_identity,
    merge_payloads,
    normalize_payload,
)


def payload(collection=None, decks=None):
    return normalize_payload({"collection": collection or [], "decks": decks or []})


def test_identity_is_normalized_and_stable():
    a = collection_identity(46986414, 46986414, " lco1-de005 ", "Ultra Rare", "Near Mint", "DE")
    b = collection_identity(46986414, 46986414, "LCO1-DE005", " ultra rare ", " near mint ", "de")
    assert a == b
    assert a.startswith("collection:")
    deck = deck_identity(" Dark Magician ")
    assert deck == deck_identity("dark magician")
    assert deck_card_identity(deck, 46986414, 46986414, " lco1-de005 ", "main") == deck_card_identity(
        deck, 46986414, 46986414, "LCO1-DE005", "MAIN"
    )


def test_local_change_wins_when_remote_is_unchanged_from_base():
    base_row = {"sync_id": "x", "quantity": 1, "updated_at_ms": 100, "device_id": "a"}
    local_row = {"sync_id": "x", "quantity": 2, "updated_at_ms": 200, "device_id": "a"}
    result = merge_payloads(payload([base_row]), payload([local_row]), payload([base_row]))
    assert result["collection"][0]["quantity"] == 2


def test_remote_change_wins_when_local_is_unchanged_from_base():
    base_row = {"sync_id": "x", "quantity": 1, "updated_at_ms": 100, "device_id": "a"}
    remote_row = {"sync_id": "x", "quantity": 3, "updated_at_ms": 300, "device_id": "b"}
    result = merge_payloads(payload([base_row]), payload([base_row]), payload([remote_row]))
    assert result["collection"][0]["quantity"] == 3


def test_deletion_propagates_when_other_side_is_unchanged():
    base_row = {"sync_id": "x", "quantity": 1, "updated_at_ms": 100, "device_id": "a"}
    result = merge_payloads(payload([base_row]), payload([]), payload([base_row]))
    assert result["collection"] == []


def test_concurrent_changes_use_latest_timestamp_and_keep_deck_cards():
    base_card = {"sync_id": "c", "quantity": 1, "updated_at_ms": 100, "device_id": "a"}
    local_card = {"sync_id": "c", "quantity": 2, "updated_at_ms": 250, "device_id": "a"}
    remote_card = {"sync_id": "c", "quantity": 3, "updated_at_ms": 300, "device_id": "b"}
    base_deck = {"sync_id": "d", "name": "Deck", "updated_at_ms": 100, "device_id": "a", "cards": [base_card]}
    local_deck = {"sync_id": "d", "name": "Deck", "updated_at_ms": 250, "device_id": "a", "cards": [local_card]}
    remote_deck = {"sync_id": "d", "name": "Deck", "updated_at_ms": 300, "device_id": "b", "cards": [remote_card]}
    result = merge_payloads(payload(decks=[base_deck]), payload(decks=[local_deck]), payload(decks=[remote_deck]))
    assert result["schema"] == ACCOUNT_SCHEMA
    assert result["decks"][0]["cards"][0]["quantity"] == 3
