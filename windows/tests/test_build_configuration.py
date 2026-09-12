from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_pyinstaller_tesseract_datas_are_two_field_mapping() -> None:
    text = (ROOT / "JustInCard.spec").read_text(encoding="utf-8")
    assert "datas += Tree(" not in text
    assert "datas.append((str(tess), \"tesseract\"))" in text
    assert "from PyInstaller.building.datastruct import Tree" not in text


def test_smoke_imports_add_repository_root_to_syspath() -> None:
    text = (ROOT / "tools/smoke_imports.py").read_text(encoding="utf-8")
    assert "ROOT = Path(__file__).resolve().parents[1]" in text
    assert "sys.path.insert(0, str(ROOT))" in text


def test_windowed_selftest_uses_explicit_log_file() -> None:
    main_text = (ROOT / "main.py").read_text(encoding="utf-8")
    build_text = (ROOT / "scripts/build_windows.ps1").read_text(encoding="utf-8")
    assert 'os.environ.get("JIC_SELFTEST_LOG"' in main_text
    assert "$env:JIC_SELFTEST_LOG = $SelfTestLog" in build_text
    assert "Assert-LastExitCode \"Packaged EXE self-test\"" in build_text


def test_v108_modules_are_packaged_and_installed_before_window_creation() -> None:
    spec_text = (ROOT / "JustInCard.spec").read_text(encoding="utf-8")
    main_text = (ROOT / "main.py").read_text(encoding="utf-8")
    assert '"justincard.v108_features"' in spec_text
    assert '"justincard.ui.toast"' in spec_text
    assert "install_v108_patches()" in main_text


def test_latest_changelog_is_the_only_version_changelog() -> None:
    import re
    version_text = (ROOT / "justincard/version.py").read_text(encoding="utf-8")
    match = re.search(r'APP_VERSION\s*=\s*["\']([^"\']+)["\']', version_text)
    assert match is not None
    token = match.group(1).replace(".", "_")
    changelogs = sorted(path.name for path in ROOT.glob("CHANGELOG_v*.txt"))
    assert changelogs == [f"CHANGELOG_v{token}.txt"]


def test_pytest_search_stub_keeps_real_package_path_visible() -> None:
    text = (ROOT / "tests/test_search_core.py").read_text(encoding="utf-8")
    assert "pkg.__path__ = [str(ROOT / 'justincard')]" in text


def test_build_forces_repository_pythonpath_and_logs_resolution() -> None:
    build_text = (ROOT / "scripts/build_windows.ps1").read_text(encoding="utf-8")
    pyproject_text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "$env:PYTHONPATH = $Root" in build_text
    assert "python-import-path.txt" in build_text
    assert 'pythonpath = ["."]' in pyproject_text


def test_pyside611_sort_enums_are_not_cast_to_int() -> None:
    text = (ROOT / "justincard/v108_features.py").read_text(encoding="utf-8")
    assert "int(Qt.AscendingOrder)" not in text
    assert "int(Qt.DescendingOrder)" not in text
    assert "Qt.SortOrder(int(direction.currentData()))" not in text
    assert "return int(Qt.AlignCenter)" not in text
    assert 'direction.addItem("Aufsteigend  A→Z / 0→9", "asc")' in text
    assert 'direction.addItem("Absteigend  Z→A / 9→0", "desc")' in text
    assert 'Qt.DescendingOrder if direction_token == "desc" else Qt.AscendingOrder' in text


def test_packaged_ui_startup_selftest_is_enabled() -> None:
    main_text = (ROOT / "main.py").read_text(encoding="utf-8")
    build_text = (ROOT / "scripts/build_windows.ps1").read_text(encoding="utf-8")
    assert 'APP_UI_SELF_TEST_FLAG = "--ui-self-test"' in main_text
    assert "def run_ui_self_test()" in main_text
    assert "MainWindow(database, directories)" in main_text
    assert "& $BuiltExe --ui-self-test" in build_text
    assert "postbuild-ui-selftest.txt" in build_text
    assert 'Assert-LastExitCode "Packaged EXE UI self-test"' in build_text


def test_repository_validator_resolves_current_version_dynamically() -> None:
    text = (ROOT / "tools/validate_repository.py").read_text(encoding="utf-8")
    assert "APP_VERSION = match.group(1).strip()" in text
    assert 'CHANGELOG_NAME = f"CHANGELOG_v{VERSION_TOKEN}.txt"' in text
    assert 'CHANGELOG_v1_0_11.txt' not in text
    assert 'APP_VERSION = "1.0.11"' not in text
    assert '"justincard/v110_core.py"' in text
    assert '"justincard/v110_features.py"' in text


def test_release_metadata_matches_current_version() -> None:
    import re
    version_text = (ROOT / "justincard/version.py").read_text(encoding="utf-8")
    match = re.search(r'APP_VERSION\s*=\s*["\']([^"\']+)["\']', version_text)
    assert match is not None
    version = match.group(1)
    assert f'version = "{version}"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert f'#define AppVersion "{version}"' in (ROOT / "installer/JustInCard.iss").read_text(encoding="utf-8")


def test_price_panel_layout_resolution_handles_shadowed_layout_attribute() -> None:
    text = (ROOT / "justincard/v111_features.py").read_text(encoding="utf-8")
    assert "def _resolve_widget_layout" in text
    assert "isinstance(candidate, QLayout)" in text
    assert "layout = _resolve_widget_layout(host)" in text
    assert "layout = host.layout()" not in text



def test_collection_trade_wishlist_and_purchase_price_are_removed() -> None:
    search_text = (ROOT / "justincard/ui/search_page.py").read_text(encoding="utf-8")
    feature_text = (ROOT / "justincard/v108_features.py").read_text(encoding="utf-8")
    profile_text = (ROOT / "justincard/v108_core.py").read_text(encoding="utf-8")
    ui_text = (ROOT / "justincard/v111_features.py").read_text(encoding="utf-8")
    assert '("wishlist", "Wunschliste")' not in search_text
    assert '("trade", "Tauschbar")' not in search_text
    assert '("market_value", "Geschätzter Marktwert")' in feature_text
    assert '("purchase_price", "Kaufpreis")' not in feature_text
    assert '("flags", "Status")' not in feature_text
    assert '("market_value", "Geschätzter Marktwert")' in profile_text
    assert "def _disable_removed_collection_controls" in ui_text
    assert '"wunsch" in text' in ui_text
    assert '"tausch" in text' in ui_text


def test_collection_none_selection_is_guarded_before_item_get() -> None:
    text = (ROOT / "justincard/v111_features.py").read_text(encoding="utf-8")
    marker = 'if not isinstance(item, dict):\n            _set_collection_estimate(self, None)\n            return'
    assert marker in text
    assert 'wanted = str(item.get("condition") or "Near Mint")' in text


def test_market_value_is_estimated_from_card_print_and_condition() -> None:
    text = (ROOT / "justincard/v108_features.py").read_text(encoding="utf-8")
    assert "def _estimated_market_value_eur" in text
    assert "estimate_price(" in text
    assert 'live=False' in text
    assert '("market_value", "Geschätzter Marktwert")' in text



def test_google_cloud_modules_are_packaged_and_dependencies_present() -> None:
    spec_text = (ROOT / "JustInCard.spec").read_text(encoding="utf-8")
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    main_text = (ROOT / "main.py").read_text(encoding="utf-8")
    validator = (ROOT / "tools/validate_repository.py").read_text(encoding="utf-8")
    for module in ("justincard.cloud_sync", "justincard.v120_features", "justincard.v121_core", "justincard.v121_features", "justincard.v123_core", "justincard.v123_features", "justincard.v128_features"):
        assert f'"{module}"' in spec_text
    for package in ("google-api-python-client", "google-auth", "google-auth-oauthlib"):
        assert package in requirements
    assert "install_v128_patches()" in main_text
    assert '"justincard/cloud_sync.py"' in validator
    assert '"justincard/v120_features.py"' in validator
    assert '"justincard/v121_features.py"' in validator


def test_google_cloud_uses_non_sensitive_per_file_and_appdata_scopes() -> None:
    text = (ROOT / "justincard/cloud_sync.py").read_text(encoding="utf-8")
    assert "https://www.googleapis.com/auth/drive.file" in text
    assert "https://www.googleapis.com/auth/drive.appdata" in text
    assert "https://www.googleapis.com/auth/spreadsheets" not in text
    assert '"https://www.googleapis.com/auth/drive"' not in text
    assert "run_local_server" in text
    assert 'host="127.0.0.1"' in text


def test_google_cloud_ui_has_manual_and_automatic_sync_controls() -> None:
    text = (ROOT / "justincard/v120_features.py").read_text(encoding="utf-8")
    for token in (
        "Google Cloud-Sammlung",
        "Mit Google anmelden",
        "Sammlung hochladen",
        "Cloud laden",
        "Synchronisieren",
        "Beim App-Start automatisch synchronisieren",
        "Im Browser öffnen",
    ):
        assert token in text


def test_search_and_scanner_quantity_controls_are_packaged() -> None:
    search_text = (ROOT / "justincard/ui/search_page.py").read_text(encoding="utf-8")
    scanner_text = (ROOT / "justincard/v121_features.py").read_text(encoding="utf-8")
    main_text = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "self.add_quantity = QSpinBox()" in search_text
    assert "self.add_quantity.setValue(1)" in search_text
    assert "normalize_add_quantity(self.add_quantity.value())" in search_text
    assert "ScannerAddQuantity" in scanner_text
    assert "spin.setValue(1)" in scanner_text
    assert "install_v128_patches()" in main_text


def test_google_cloud_uses_exact_user_template_and_private_backup():
    import hashlib
    cloud_text = (ROOT / "justincard/cloud_sync.py").read_text(encoding="utf-8")
    ui_text = (ROOT / "justincard/v120_features.py").read_text(encoding="utf-8")
    template = ROOT / "assets/google_sheets_template.xlsx"
    assert template.exists()
    assert hashlib.sha256(template.read_bytes()).hexdigest() == "0cb4633fe1abcec31ee5d9fddf533987cdb7fa9f8c84e7b45d282c6a135c7fd7"
    for token in (
        'MONSTER_HEADERS: tuple[str, ...] = ("Sterne", "Name", "Typ", "Element", "Kategorie", "Set-Code")',
        'SPELL_HEADERS: tuple[str, ...] = ("Kategorie", "Name", "Set-Code")',
        'TRAP_HEADERS: tuple[str, ...] = ("Kategorie", "Name", "Set-Code")',
        'TEMPLATE_ASSET = "google_sheets_template.xlsx"',
        'MediaFileUpload',
        'parents": ["appDataFolder"]',
        'def deck_sheet_map(',
        'def download_cloud_payload(',
        'return "Empfänger"',
    ):
        assert token in cloud_text
    assert '"Effekttext"' not in cloud_text
    assert 'CATEGORY_SHEETS: tuple[str, ...] = BASE_TEMPLATE_SHEETS' in cloud_text
    for token in (
        "Standard-Sortierung für Google Sheets",
        "SORT_FIELD_SETTING",
        "SORT_DIRECTION_SETTING",
        "export_cloud_decks",
        "apply_cloud_decks",
        "Google Sheets – Sortierung festlegen",
    ):
        assert token in ui_text


def test_v125_template_keeps_receiver_as_monster_category_and_deck_order_note():
    cloud_text = (ROOT / "justincard/cloud_sync.py").read_text(encoding="utf-8")
    ui_text = (ROOT / "justincard/v120_features.py").read_text(encoding="utf-8")
    assert 'CLOUD_SCHEMA = "justincard-google-drive-backup-v4"' in cloud_text
    assert 'BASE_TEMPLATE_SHEETS: tuple[str, ...] = (MONSTER_SHEET, SPELL_SHEET, TRAP_SHEET)' in cloud_text
    assert 'if "tuner" in text:' in cloud_text
    assert 'return "Empfänger"' in cloud_text
    assert '"Main Deck"' in cloud_text
    assert '"Extra Deck"' in cloud_text
    assert '"Side Deck"' in cloud_text
    assert 'def choose_sort_before_export()' in ui_text
    assert 'Deck-Reiter behalten unabhängig davon exakt die Reihenfolge aus dem Deckbuilder.' in ui_text


def test_v123_deck_auto_zone_is_installed_and_manual_extra_button_hidden():
    core_text = (ROOT / "justincard/v123_core.py").read_text(encoding="utf-8")
    feature_text = (ROOT / "justincard/v123_features.py").read_text(encoding="utf-8")
    database_patch = (ROOT / "justincard/v108_features.py").read_text(encoding="utf-8")
    main_text = (ROOT / "main.py").read_text(encoding="utf-8")
    spec_text = (ROOT / "JustInCard.spec").read_text(encoding="utf-8")
    assert "def resolved_deck_zone" in core_text
    assert "+ Automatisch (Main / Extra)" in feature_text
    assert "+ Side Deck" in feature_text
    assert "button.hide()" in feature_text
    assert "resolved_deck_zone" in database_patch
    assert "install_v128_patches()" in main_text
    assert '"justincard.v123_core"' in spec_text
    assert '"justincard.v123_features"' in spec_text


def test_collection_summary_replaces_trade_and_purchase_totals() -> None:
    ui_text = (ROOT / "justincard/v111_features.py").read_text(encoding="utf-8")
    core_text = (ROOT / "justincard/v108_core.py").read_text(encoding="utf-8")
    assert "def _collection_estimated_total_eur" in ui_text
    assert "total += float(unit_value) * quantity" in ui_text
    assert 'title_label.setText("Geschätzter Sammlungswert")' in ui_text
    assert '"tausch" in folded or "trade" in folded' in ui_text
    assert 'database.collection_items("")' in ui_text
    assert 'if key == "flags":' in core_text
    assert 'flags.append("Tausch")' not in core_text


def test_v126_set_code_search_uses_english_reference_and_restores_collection_language() -> None:
    search_core = (ROOT / "justincard/search_core.py").read_text(encoding="utf-8")
    search_page = (ROOT / "justincard/ui/search_page.py").read_text(encoding="utf-8")
    assert "def english_set_query" in search_core
    assert 'return f"{prefix}-EN{number}"' in search_core
    assert 'return "en", (' in search_core
    assert "def localized_collection_print" in search_core
    assert 'card_copy["_language"] = language' in search_core
    assert 'selected["_reference_set_code"] = selected_code' in search_core
    assert "self.current_original_set_query" in search_page
    assert "localized_collection_print(" in search_page
    assert "self.database.add_to_collection(collection_card, collection_print, quantity)" in search_page


def test_v126_collection_market_summary_has_one_large_value() -> None:
    ui_text = (ROOT / "justincard/v111_features.py").read_text(encoding="utf-8")
    assert "def _render_market_summary_card" in ui_text
    assert 'title_label.setText("Geschätzter Sammlungswert")' in ui_text
    assert "value_label.setText(value_text)" in ui_text
    assert "label.hide()" in ui_text
    assert 'value_text = f"{total:.2f} €"' in ui_text
    assert 'text = f"Geschätzter Sammlungswert: {total:.2f} €"' not in ui_text


def test_v126_market_value_uses_cardmarket_reference_as_primary_anchor() -> None:
    price_text = (ROOT / "justincard/price_service.py").read_text(encoding="utf-8")
    assert "if market_floor is not None:" in price_text
    assert "Cardmarket-Referenzpreis (EUR) über YGOPRODeck" in price_text
    assert 'source="Cardmarket-Referenz über YGOPRODeck + Set/Raritäts-Schätzung"' in price_text


def test_v128_fixed_google_backup_preview_sort_and_search_contract() -> None:
    feature = (ROOT / "justincard/v128_features.py").read_text(encoding="utf-8")
    search = (ROOT / "justincard/ui/search_page.py").read_text(encoding="utf-8")
    v108 = (ROOT / "justincard/v108_features.py").read_text(encoding="utf-8")
    v120 = (ROOT / "justincard/v120_features.py").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/build-windows.yml").read_text(encoding="utf-8")
    assert (ROOT / "assets/google_oauth_client.json").exists()
    assert "Backup erstellen" in feature and "Backup laden" in feature
    assert "CollectionCardPreview" in feature
    assert '("added_at", "Hinzugefügt am")' in v108
    assert "self.detail.set_card(cards[0], self.current_set_query)" in search
    assert "application-bundled OAuth desktop" in v120
    assert "Prepare optional Google OAuth client" not in workflow
    assert "Verify bundled Google OAuth client" in workflow
