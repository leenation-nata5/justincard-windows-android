from justincard.v123_core import (
    card_requires_extra_deck,
    collection_sheet_category,
    main_deck_section,
    resolved_deck_zone,
)


def test_main_extra_zone_is_automatic_and_side_remains_manual():
    fusion = {"type": "Fusion Effect Monster", "frameType": "fusion"}
    synchro = {"type": "Synchro Tuner Monster", "frameType": "synchro"}
    xyz = {"type": "XYZ Monster", "frameType": "xyz"}
    link = {"type": "Link Monster", "frameType": "link"}
    normal = {"type": "Effect Monster", "frameType": "effect"}
    ritual = {"type": "Ritual Effect Monster", "frameType": "ritual"}

    for card in (fusion, synchro, xyz, link):
        assert card_requires_extra_deck(card)
        assert resolved_deck_zone(card, "main") == "extra"
    assert resolved_deck_zone(normal, "extra") == "main"
    assert resolved_deck_zone(ritual, "extra") == "main"
    assert resolved_deck_zone(link, "side") == "side"
    assert resolved_deck_zone(normal, "side") == "side"


def test_google_collection_categories_include_tuner_receiver_tab():
    assert collection_sheet_category({"type": "Effect Monster"}) == "Monster"
    assert collection_sheet_category({"type": "Tuner Monster"}) == "Empfänger"
    assert collection_sheet_category({"type": "Synchro Tuner Monster"}) == "Empfänger"
    assert collection_sheet_category({"type": "Spell Card"}) == "Zauberkarten"
    assert collection_sheet_category({"type": "Trap Card"}) == "Fallenkarten"


def test_deck_main_sections_keep_tuners_with_monsters():
    assert main_deck_section({"type": "Tuner Monster"}) == "Monsterkarten"
    assert main_deck_section({"type": "Spell Card"}) == "Zauberkarten"
    assert main_deck_section({"type": "Trap Card"}) == "Fallenkarten"
