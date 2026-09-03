from justincard.v108_core import (
    DEFAULT_VISIBILITY,
    is_placeholder_item,
    normalize_backup_payload,
    normalize_visibility,
    placeholder_collection_key,
    record_value,
    sortable_value,
    visibility_preset,
)


def test_visibility_presets_and_legacy_list_shape() -> None:
    all_fields = visibility_preset("all")
    assert all(all_fields.values())
    basic = visibility_preset("basic")
    assert basic["set_code"] is True
    assert basic["atk"] is False
    none = visibility_preset("none")
    assert not any(none.values())
    normalized = normalize_visibility(["atk", "def"])
    assert normalized["atk"] is True
    assert normalized["def"] is True
    assert normalized["rarity"] is False
    assert "effect" in DEFAULT_VISIBILITY


def test_placeholder_detection_is_stable() -> None:
    key = placeholder_collection_key("abc")
    assert key == "__placeholder__:abc"
    assert is_placeholder_item({"collection_key": key})
    assert is_placeholder_item({"is_placeholder": 1})
    assert not is_placeholder_item({"collection_key": "abc"})


def test_backup_normalizes_old_android_and_german_field_names() -> None:
    payload = normalize_backup_payload({
        "sammlung": [{
            "id": 46986414,
            "name": "Dunkler Magier",
            "count": "2",
            "set_code": "LOB-G005",
            "set": "Legend of Blue Eyes White Dragon",
            "set_rarity": "Ultra Rare",
            "sprache": "de",
            "zustand": "Near Mint",
        }]
    })
    assert payload["format"] == "justincard-windows-backup-v2"
    assert payload["collection"][0]["quantity"] == 2
    assert payload["collection"][0]["print_code"] == "LOB-G005"
    assert payload["collection"][0]["card"]["name"] == "Dunkler Magier"


def test_record_value_and_sorting_use_nested_card_data() -> None:
    row = {"quantity": 2, "card": {"name": "Tornadodrache", "atk": 2100, "id": 6983839}}
    assert record_value(row, "name", "collection") == "Tornadodrache"
    assert record_value(row, "atk", "collection") == 2100
    assert sortable_value(row, "atk", "collection") == (0, 2100)
