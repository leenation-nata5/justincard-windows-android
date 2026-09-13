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


def test_missing_local_row_never_erases_unchanged_server_row():
    base_row = {"sync_id": "x", "quantity": 1, "updated_at_ms": 100, "device_id": "a"}
    result = merge_payloads(payload([base_row]), payload([]), payload([base_row]))
    assert result["collection"] == [base_row]


def test_missing_remote_row_never_erases_local_row_without_tombstone():
    base_row = {"sync_id": "x", "quantity": 1, "updated_at_ms": 100, "device_id": "a"}
    result = merge_payloads(payload([base_row]), payload([base_row]), payload([]))
    assert result["collection"] == [base_row]


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


def test_account_restore_materializes_collection_rows_without_generic_cloud_import(tmp_path):
    import json
    import sqlite3
    import threading
    from justincard.account_sync import replace_windows_from_payload

    class FakeDatabase:
        def __init__(self, path):
            self.path = str(path)
            self._write_lock = threading.RLock()
            self.settings = {}
            with self.connect() as connection:
                connection.executescript(
                    """
                    CREATE TABLE collection(
                        collection_key TEXT PRIMARY KEY, card_key TEXT NOT NULL DEFAULT '', card_id INTEGER,
                        print_code TEXT NOT NULL DEFAULT '', set_name TEXT NOT NULL DEFAULT '', rarity TEXT NOT NULL DEFAULT '',
                        artwork_url TEXT NOT NULL DEFAULT '', language TEXT NOT NULL DEFAULT '', quantity INTEGER NOT NULL,
                        condition TEXT NOT NULL DEFAULT 'Near Mint', purchase_price REAL, note TEXT NOT NULL DEFAULT '',
                        wishlist INTEGER NOT NULL DEFAULT 0, trade INTEGER NOT NULL DEFAULT 0, card_json TEXT NOT NULL,
                        created_at REAL NOT NULL, updated_at REAL NOT NULL, added_at REAL
                    );
                    CREATE TABLE decks(deck_id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', favorite INTEGER NOT NULL DEFAULT 0, created_at REAL NOT NULL DEFAULT 0, updated_at REAL NOT NULL DEFAULT 0);
                    CREATE TABLE deck_cards(deck_id TEXT NOT NULL, collection_key TEXT NOT NULL, card_id INTEGER, zone TEXT NOT NULL, quantity INTEGER NOT NULL, card_json TEXT NOT NULL, is_placeholder INTEGER NOT NULL DEFAULT 0, source_collection_key TEXT NOT NULL DEFAULT '');
                    """
                )

        def connect(self):
            connection = sqlite3.connect(self.path)
            connection.row_factory = sqlite3.Row
            return connection

        def get_setting(self, key, default=None):
            return self.settings.get(key, default)

        def set_setting(self, key, value):
            self.settings[key] = value

        def collection_key(self, card, print_item, artwork_url):
            return f"{int(card.get('id') or 0)}|{(print_item or {}).get('set_code', '')}|{artwork_url}"

        def _json(self, value):
            return json.dumps(value)

        def collection_items(self, _query):
            with self.connect() as connection:
                rows = connection.execute("SELECT * FROM collection").fetchall()
            result = []
            for row in rows:
                item = dict(row)
                item["card"] = json.loads(item["card_json"])
                result.append(item)
            return result

        def export_cloud_collection(self):
            return self.collection_items("")

        def list_decks(self):
            return []

        def export_cloud_decks(self):
            return []

        def apply_cloud_decks(self, decks):
            return {"applied": len(decks), "skipped": 0}

    database = FakeDatabase(tmp_path / "account.db")
    row = {
        "card_id": 46986414,
        "artwork_id": 46986414,
        "card_name": "Dark Magician",
        "set_code": "LCO1-DE005",
        "set_name": "Legendary Collection",
        "rarity": "Ultra Rare",
        "language": "de",
        "condition": "Near Mint",
        "quantity": 2,
        "notes": "",
        "added_at_ms": 1_700_000_000_000,
        "updated_at_ms": 1_700_000_000_000,
        "device_id": "server",
    }
    row["sync_id"] = collection_identity(46986414, 46986414, "LCO1-DE005", "Ultra Rare", "Near Mint", "de")
    report = replace_windows_from_payload(database, payload([row]))
    assert report["collection"]["applied"] == 1
    restored = database.collection_items("")
    assert len(restored) == 1
    assert restored[0]["quantity"] == 2
    assert restored[0]["card"]["name"] == "Dark Magician"
