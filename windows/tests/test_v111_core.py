from justincard.v111_core import DISPLAY_CONTEXTS, normalize_profiles, profile_for, set_profile_field


def test_profiles_are_independent_and_legacy_migrates():
    legacy = {"atk": False, "def": True, "effect": False}
    profiles = normalize_profiles(None, legacy)
    assert len(profiles) == len(DISPLAY_CONTEXTS)
    assert profile_for(profiles, "search_results")["atk"] is False
    assert profile_for(profiles, "collection_table")["atk"] is False

    updated = set_profile_field(profiles, "search_results", "atk", True)
    assert profile_for(updated, "search_results")["atk"] is True
    assert profile_for(updated, "collection_table")["atk"] is False


def test_profile_shape_is_completed():
    profiles = normalize_profiles({"search_results": {"effect": True}})
    assert profile_for(profiles, "search_results")["effect"] is True
    assert "collection_table" in profiles


from justincard.v110_core import artwork_label


def test_artwork_label_variants():
    card = {"card_images": [{"image_url": "https://img/standard.jpg"}, {"image_url": "https://img/alt.jpg"}]}
    assert artwork_label(card, "card") == "2 Artworks"
    collection_row = {"card": card, "artwork_url": "https://img/alt.jpg"}
    assert "Alt Art" in artwork_label(collection_row, "collection")
