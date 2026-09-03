from justincard.cloud_sync import (
    BASE_TEMPLATE_SHEETS,
    CLOUD_SCHEMA,
    MONSTER_HEADERS,
    MONSTER_SHEET,
    RAW_HEADERS,
    SCOPES,
    SPELL_HEADERS,
    SPELL_SHEET,
    TEMPLATE_ASSET,
    TEMPLATE_SHA256,
    TRAP_HEADERS,
    TRAP_SHEET,
    category_sheet_rows,
    deck_sheet_map,
    merge_collection_records,
    monster_category,
    normalize_spreadsheet_id,
    parse_raw_sheet_rows,
    raw_sheet_rows,
    spreadsheet_url,
    template_asset_path,
)


def sample(quantity=1, updated=10.0):
    return {
        "collection_key": "123|TEST-DE001|Common|de|art1",
        "print_code": "TEST-DE001",
        "set_name": "Test Set",
        "rarity": "Common",
        "artwork_url": "https://img.example/art1.jpg",
        "language": "de",
        "quantity": quantity,
        "condition": "Near Mint",
        "note": "Test",
        "updated_at": updated,
        "card": {
            "id": 123,
            "name": "Cloud Test Card",
            "type": "Effect Monster",
            "race": "Dragon",
            "attribute": "DARK",
            "level": 8,
            "desc": "Dieser Effekt darf NICHT in die Google-Sheets-Vorlage gelangen.",
            "card_images": [
                {"image_url": "https://img.example/art1.jpg"},
                {"image_url": "https://img.example/art2.jpg"},
            ],
        },
    }


def test_google_sheet_url_parser_accepts_id_and_browser_url():
    identifier = "abcDEF_12345678901234567890"
    assert normalize_spreadsheet_id(identifier) == identifier
    assert normalize_spreadsheet_id(f"https://docs.google.com/spreadsheets/d/{identifier}/edit#gid=0") == identifier
    assert spreadsheet_url(identifier).endswith(f"/{identifier}/edit")


def test_raw_backup_roundtrip_still_preserves_full_collection_for_private_appdata():
    rows = raw_sheet_rows([sample(quantity=2)])
    assert tuple(rows[0]) == RAW_HEADERS
    parsed = parse_raw_sheet_rows(rows)
    assert len(parsed) == 1
    assert parsed[0]["quantity"] == 2
    assert parsed[0]["card"]["desc"].startswith("Dieser Effekt")


def test_merge_uses_latest_update_and_preserves_rows_missing_on_one_device():
    local_only = sample(updated=5.0)
    local_only["card"] = dict(local_only["card"], id=124, name="Local only")
    local_only["print_code"] = "TEST-DE002"
    local_only["collection_key"] = "legacy-local-only"
    cloud_only = sample(updated=6.0)
    cloud_only["card"] = dict(cloud_only["card"], id=125, name="Cloud only")
    cloud_only["print_code"] = "TEST-DE003"
    cloud_only["collection_key"] = "legacy-cloud-only"
    local = [sample(quantity=1, updated=10.0), local_only]
    cloud = [sample(quantity=3, updated=20.0), cloud_only]
    merged = merge_collection_records(local, cloud)
    by_key = {row["collection_key"]: row for row in merged}
    assert by_key[sample()["collection_key"]]["quantity"] == 3
    # Legacy platform-specific keys are normalized to the shared physical-print
    # identity, while genuinely different cards remain present.
    assert any(row["card"]["id"] == 124 for row in merged)
    assert any(row["card"]["id"] == 125 for row in merged)


def test_cloud_schema_version_is_explicit():
    assert CLOUD_SCHEMA == "justincard-google-drive-backup-v4"


def test_exact_template_is_bundled_unchanged():
    import hashlib

    path = template_asset_path()
    assert path.name == TEMPLATE_ASSET
    assert path.exists()
    assert hashlib.sha256(path.read_bytes()).hexdigest() == TEMPLATE_SHA256


def test_google_sheet_uses_only_the_three_template_tabs_and_columns():
    tabs = category_sheet_rows([sample(quantity=2)])
    assert tuple(tabs) == BASE_TEMPLATE_SHEETS
    assert tuple(tabs[MONSTER_SHEET][0]) == MONSTER_HEADERS
    assert tuple(tabs[SPELL_SHEET][0]) == SPELL_HEADERS
    assert tuple(tabs[TRAP_SHEET][0]) == TRAP_HEADERS
    # Quantity is represented by repeated rows because the user's template has
    # no quantity column.
    assert len(tabs[MONSTER_SHEET]) == 3
    assert tabs[MONSTER_SHEET][1] == [8, "Cloud Test Card", "Dragon", "DARK", "Effekt", "TEST-DE001"]
    flattened = [str(cell) for rows in tabs.values() for row in rows for cell in row]
    assert not any("Effekt darf NICHT" in cell for cell in flattened)
    assert "Geschätzter Marktwert" not in " ".join(flattened)
    assert "Seltenheit" not in " ".join(flattened)


def test_receiver_is_monster_category_not_separate_sheet():
    tuner = sample()
    tuner["card"] = dict(tuner["card"], type="Tuner Monster")
    tabs = category_sheet_rows([tuner])
    assert "Empfänger" not in tabs
    assert tabs[MONSTER_SHEET][1][4] == "Empfänger"
    assert monster_category(tuner["card"]) == "Empfänger"


def test_spell_and_trap_follow_template_headers_only():
    spell = sample()
    spell["collection_key"] = "spell"
    spell["card"] = dict(spell["card"], type="Spell Card", race="Quick-Play", name="Schnellzauber")
    trap = sample()
    trap["collection_key"] = "trap"
    trap["card"] = dict(trap["card"], type="Trap Card", race="Counter", name="Konterfalle")
    tabs = category_sheet_rows([spell, trap])
    assert tabs[SPELL_SHEET][1] == ["Schnellzauber", "Schnellzauber", "TEST-DE001"]
    assert tabs[TRAP_SHEET][1] == ["Konter", "Konterfalle", "TEST-DE001"]


def test_sorting_can_use_name_type_passcode_or_template_fields_without_exporting_them():
    alpha = sample()
    alpha["collection_key"] = "a"
    alpha["card"] = dict(alpha["card"], id=999, name="Alpha")
    beta = sample()
    beta["collection_key"] = "b"
    beta["card"] = dict(beta["card"], id=111, name="Beta")
    by_name = category_sheet_rows([beta, alpha], "name", "asc")[MONSTER_SHEET]
    by_passcode = category_sheet_rows([alpha, beta], "passcode", "asc")[MONSTER_SHEET]
    assert by_name[1][1] == "Alpha"
    assert by_passcode[1][1] == "Beta"
    assert "Passcode" not in MONSTER_HEADERS


def test_each_deck_receives_own_template_only_sheet_and_preserves_program_order():
    monster = {**sample(), "collection_key": "m", "zone": "main", "quantity": 2}
    monster["card"] = dict(monster["card"], type="Effect Monster", name="Monster Eins")
    extra = {**sample(), "collection_key": "e", "zone": "extra", "quantity": 1}
    extra["card"] = dict(extra["card"], type="Link Monster", name="Extra Eins", level=None)
    side = {**sample(), "collection_key": "d", "zone": "side", "quantity": 1}
    side["card"] = dict(side["card"], type="Trap Card", race="Counter", name="Side Eins")
    deck = {"deck_id": "deck-1", "name": "Drachen Deck", "cards": [monster, extra, side]}
    sheets = deck_sheet_map([deck], sort_field="name", sort_direction="desc")
    assert "Drachen Deck" in sheets
    rows = sheets["Drachen Deck"]
    assert tuple(rows[0]) == MONSTER_HEADERS
    assert all(len(row) == len(MONSTER_HEADERS) for row in rows)
    names = [row[1] for row in rows if len(row) > 1]
    assert names.index("Monster Eins") < names.index("Extra Eins") < names.index("Side Eins")
    assert names.count("Monster Eins") == 2
    assert "Main Deck" in names and "Extra Deck" in names and "Side Deck" in names


def test_oauth_scopes_are_non_sensitive_per_file_and_appdata_only():
    assert SCOPES == (
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive.appdata",
    )
    assert not any(scope.endswith("/spreadsheets") for scope in SCOPES)
