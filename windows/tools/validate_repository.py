from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

version_path = ROOT / "justincard/version.py"
if not version_path.exists():
    raise SystemExit("Missing repository file: justincard/version.py")
version_text = version_path.read_text(encoding="utf-8")
match = re.search(r'^APP_VERSION\s*=\s*["\']([^"\']+)["\']', version_text, re.MULTILINE)
if not match:
    raise SystemExit("APP_VERSION could not be resolved from justincard/version.py")
APP_VERSION = match.group(1).strip()
VERSION_TOKEN = APP_VERSION.replace(".", "_")
CHANGELOG_NAME = f"CHANGELOG_v{VERSION_TOKEN}.txt"

REQUIRED = [
    ".github/workflows/build-windows.yml",
    "JustInCard.spec",
    "main.py",
    "requirements.txt",
    "requirements-build.txt",
    "scripts/build_windows.ps1",
    "scripts/build_installer.ps1",
    "installer/JustInCard.iss",
    "justincard/search_core.py",
    "justincard/ui/search_page.py",
    "justincard/version.py",
    "justincard/v108_core.py",
    "justincard/v108_features.py",
    "justincard/v111_core.py",
    "justincard/v111_features.py",
    "justincard/v110_core.py",
    "justincard/v110_features.py",
    "justincard/price_service.py",
    "justincard/cloud_sync.py",
    "justincard/v120_features.py",
    "justincard/v121_core.py",
    "justincard/v121_features.py",
    "justincard/v123_core.py",
    "justincard/v123_features.py",
    "justincard/v128_features.py",
    "justincard/v130_features.py",
    "justincard/account_sync.py",
    "justincard/v132_features.py",
    "justincard/ui/toast.py",
    "assets/google_sheets_template.xlsx",
    "assets/google_oauth_client.json",
    "recovered/PYZ.pyz",
    "tests/test_search_core.py",
    "tests/test_build_configuration.py",
    "tests/test_v108_core.py",
    "tests/test_v111_core.py",
    "tests/test_price_service.py",
    "tests/test_cloud_sync.py",
    "tests/test_v121_core.py",
    "tests/test_v123_core.py",
    CHANGELOG_NAME,
]

missing = [item for item in REQUIRED if not (ROOT / item).exists()]
if missing:
    raise SystemExit(f"Missing repository files: {missing}")

for relative in [
    "main.py",
    "justincard/search_core.py",
    "justincard/ui/search_page.py",
    "justincard/version.py",
    "justincard/v108_core.py",
    "justincard/v108_features.py",
    "justincard/v111_core.py",
    "justincard/v111_features.py",
    "justincard/v110_core.py",
    "justincard/v110_features.py",
    "justincard/price_service.py",
    "justincard/cloud_sync.py",
    "justincard/v120_features.py",
    "justincard/v121_core.py",
    "justincard/v121_features.py",
    "justincard/v123_core.py",
    "justincard/v123_features.py",
    "justincard/v128_features.py",
    "justincard/v130_features.py",
    "justincard/account_sync.py",
    "justincard/v132_features.py",
    "justincard/ui/toast.py",
    "tools/materialize_recovered_modules.py",
    "tools/smoke_imports.py",
]:
    ast.parse((ROOT / relative).read_text(encoding="utf-8"), filename=relative)
    print("OK syntax", relative)

raw = (ROOT / "recovered/PYZ.pyz").read_bytes()
if not raw.startswith(b"PYZ\0"):
    raise SystemExit("Invalid recovered/PYZ.pyz")

# Keep release metadata aligned without hard-coding a previous release.
pyproject_text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
if f'version = "{APP_VERSION}"' not in pyproject_text:
    raise SystemExit(f"pyproject.toml version does not match APP_VERSION {APP_VERSION}")
installer_text = (ROOT / "installer/JustInCard.iss").read_text(encoding="utf-8")
if f'#define AppVersion "{APP_VERSION}"' not in installer_text:
    raise SystemExit(f"Inno Setup fallback version does not match APP_VERSION {APP_VERSION}")

changelogs = sorted(path.name for path in ROOT.glob("CHANGELOG_v*.txt"))
if changelogs != [CHANGELOG_NAME]:
    raise SystemExit(f"Expected only {CHANGELOG_NAME}, found: {changelogs}")

spec_text = (ROOT / "JustInCard.spec").read_text(encoding="utf-8")
if "datas += Tree(" in spec_text:
    raise SystemExit("PyInstaller spec still mixes Tree TOC entries into Analysis(datas=...)")
if 'datas.append((str(tess), "tesseract"))' not in spec_text:
    raise SystemExit("Correct Tesseract (source, destination) data mapping is missing")
for module in ("justincard.v110_core", "justincard.v110_features", "justincard.cloud_sync", "justincard.v120_features", "justincard.v121_core", "justincard.v121_features", "justincard.v123_core", "justincard.v123_features", "justincard.v128_features", "justincard.v130_features", "justincard.account_sync", "justincard.v132_features"):
    if f'"{module}"' not in spec_text:
        raise SystemExit(f"PyInstaller hidden import missing: {module}")

smoke_text = (ROOT / "tools/smoke_imports.py").read_text(encoding="utf-8")
if "sys.path.insert(0, str(ROOT))" not in smoke_text:
    raise SystemExit("smoke_imports.py does not add the repository root to sys.path")

workflow = (ROOT / ".github/workflows/build-windows.yml").read_text(encoding="utf-8")
for token in [
    "windows-latest",
    "actions/upload-artifact@v4",
    "build_windows.ps1",
    "Build Windows Desktop",
    "Upload build logs",
]:
    if token not in workflow:
        raise SystemExit(f"Workflow token missing: {token}")
for token in ["Verify bundled Google OAuth client", "assets\\google_oauth_client.json"]:
    if token not in workflow:
        raise SystemExit(f"Google OAuth workflow token missing: {token}")
if "GOOGLE_OAUTH_CLIENT_JSON_B64" in workflow:
    raise SystemExit("Build workflow must not override the fixed bundled OAuth client")

gitignore_text = (ROOT / ".gitignore").read_text(encoding="utf-8")
active_ignores = {line.strip() for line in gitignore_text.splitlines() if line.strip() and not line.lstrip().startswith("#")}
if "assets/google_oauth_client.json" in active_ignores:
    raise SystemExit("Fixed Google OAuth client must not be excluded by windows/.gitignore")

build_script = (ROOT / "scripts/build_windows.ps1").read_text(encoding="utf-8")
for token in [
    "--strict",
    "--self-test",
    "repository-validation.txt",
    "prebuild-import-diagnostics.txt",
    "pyinstaller.txt",
    "postbuild-selftest.txt",
    "postbuild-ui-selftest.txt",
    "--ui-self-test",
    "build-exception.txt",
]:
    if token not in build_script:
        raise SystemExit(f"Build-script token missing: {token}")

feature_text = (ROOT / "justincard/v108_features.py").read_text(encoding="utf-8")
for token in [
    "is_placeholder",
    "source_collection_key",
    "Als Platzhalter hinzufügen",
    "Anzeigeoptionen – Karteninformationen",
    "justincard-windows-backup-v2",
    "SQLite-Datenbanken",
]:
    if token not in feature_text:
        raise SystemExit(f"Core feature token missing: {token}")

for forbidden in [
    "int(Qt.AscendingOrder)",
    "int(Qt.DescendingOrder)",
    "Qt.SortOrder(int(direction.currentData()))",
    "return int(Qt.AlignCenter)",
]:
    if forbidden in feature_text:
        raise SystemExit(f"PySide6 6.11 incompatible Qt enum conversion remains: {forbidden}")
for required_sort_token in [
    'direction.addItem("Aufsteigend  A→Z / 0→9", "asc")',
    'direction.addItem("Absteigend  Z→A / 9→0", "desc")',
    'Qt.DescendingOrder if direction_token == "desc" else Qt.AscendingOrder',
]:
    if required_sort_token not in feature_text:
        raise SystemExit(f"PySide6-safe sorting token missing: {required_sort_token}")

v111_text = (ROOT / "justincard/v111_features.py").read_text(encoding="utf-8")
for token in [
    "PROFILE_SETTING_KEY",
    "search_results",
    "collection_table",
    "deck_pool",
    "Spalten auswählen",
    "Preis ermitteln",
    "artwork_label",
]:
    if token not in v111_text:
        raise SystemExit(f"Display/price feature token missing: {token}")

v110_core_text = (ROOT / "justincard/v110_core.py").read_text(encoding="utf-8")
v110_feature_text = (ROOT / "justincard/v110_features.py").read_text(encoding="utf-8")
for token in ["artwork_label", "artwork_urls", "normalize_artwork_url"]:
    if token not in v110_core_text:
        raise SystemExit(f"Alt-art core token missing: {token}")
if "install_v110_patches" not in v110_feature_text:
    raise SystemExit("Alt-art patch installer missing")

price_text = (ROOT / "justincard/price_service.py").read_text(encoding="utf-8")
for token in [
    "YGOPRODECK_URL",
    "FRANKFURTER_RATE_URL",
    "CONDITION_FACTORS",
    "cardmarket_price",
    "set_price",
]:
    if token not in price_text:
        raise SystemExit(f"Price token missing: {token}")

main_text = (ROOT / "main.py").read_text(encoding="utf-8")
for installer in ("install_v128_patches()", "install_v130_patches()", "install_v132_patches()"):
    if installer not in main_text:
        raise SystemExit(f"Current v{APP_VERSION} feature patch missing from main.py: {installer}")

v130_text = (ROOT / "justincard/v130_features.py").read_text(encoding="utf-8")
for token in (
    "GLOBAL_LANGUAGE_SETTING",
    "SYNC_INTERVAL_MS",
    "Sammlung + Decks hochladen",
    "Dauerhaft automatisch synchronisieren",
    "install_v130_patches",
):
    if token not in v130_text:
        raise SystemExit(f"v1.3.0 feature token missing: {token}")

v132_text = (ROOT / "justincard/v132_features.py").read_text(encoding="utf-8")
account_sync_text = (ROOT / "justincard/account_sync.py").read_text(encoding="utf-8")
for token in (
    "Just InCard Konto (IONOS)",
    "Nur lokal verwenden",
    "Mit Just InCard Konto anmelden",
    "install_v132_patches",
):
    if token not in v132_text:
        raise SystemExit(f"v1.3.4 account UI token missing: {token}")
for token in (
    "justincard-account-sync-v1",
    "sync_windows_account",
    "merge_payloads",
    "replace_windows_from_payload",
):
    if token not in account_sync_text:
        raise SystemExit(f"v1.3.4 account sync token missing: {token}")

v128_text = (ROOT / "justincard/v128_features.py").read_text(encoding="utf-8")
for token in (
    "SearchAddActionRow",
    "_AdaptiveCollectionPreview",
    "Qt.KeepAspectRatio",
    "move_quantity_to_add_button",
):
    if token not in v128_text:
        raise SystemExit(f"v1.3.4 UI hotfix token missing: {token}")
for token in [
    'APP_UI_SELF_TEST_FLAG = "--ui-self-test"',
    "def run_ui_self_test()",
    "MainWindow(database, directories)",
]:
    if token not in main_text:
        raise SystemExit(f"Packaged UI startup self-test token missing: {token}")

search_page_text = (ROOT / "justincard/ui/search_page.py").read_text(encoding="utf-8")
for token in ["show_toast", "self.filters.reset()", "self.filters.quick.setFocus"]:
    if token not in search_page_text:
        raise SystemExit(f"Search UX token missing: {token}")
for token in ["self.add_quantity = QSpinBox()", "normalize_add_quantity(self.add_quantity.value())", "self.add_quantity.setValue(1)"]:
    if token not in search_page_text:
        raise SystemExit(f"Search quantity token missing: {token}")

v121_text = (ROOT / "justincard/v121_features.py").read_text(encoding="utf-8")
for token in ["ScannerAddQuantity", "accept_current", "accept_all_safe", "spin.setValue(1)"]:
    if token not in v121_text:
        raise SystemExit(f"Scanner quantity token missing: {token}")

v123_core_text = (ROOT / "justincard/v123_core.py").read_text(encoding="utf-8")
v123_feature_text = (ROOT / "justincard/v123_features.py").read_text(encoding="utf-8")
for token in ["card_requires_extra_deck", "resolved_deck_zone", "collection_sheet_category", "main_deck_section"]:
    if token not in v123_core_text:
        raise SystemExit(f"v1.2.3 deck/category token missing: {token}")
for token in ["+ Automatisch (Main / Extra)", "+ Side Deck", "button.hide()", "install_v123_patches"]:
    if token not in v123_feature_text:
        raise SystemExit(f"v1.2.3 deck UI token missing: {token}")
if "resolved_deck_zone" not in feature_text:
    raise SystemExit("Deck database auto-routing is missing")

test_search_text = (ROOT / "tests/test_search_core.py").read_text(encoding="utf-8")
if "pkg.__path__ = [str(ROOT / 'justincard')]" not in test_search_text:
    raise SystemExit("Search regression test still hides the real justincard package path")

if 'pythonpath = ["."]' not in pyproject_text:
    raise SystemExit("pytest repository pythonpath is not pinned")
if '$env:PYTHONPATH = $Root' not in build_script:
    raise SystemExit("Build script does not force repository root onto PYTHONPATH")
if "python-import-path.txt" not in build_script:
    raise SystemExit("Build script does not write Python import diagnostics")


# v1.1.3: collection is no longer a trade/wishlist ledger and uses estimated market value.
search_page_text = (ROOT / "justincard/ui/search_page.py").read_text(encoding="utf-8")
search_core_text = (ROOT / "justincard/search_core.py").read_text(encoding="utf-8")
if '("wishlist", "Wunschliste")' in search_page_text or '("trade", "Tauschbar")' in search_page_text:
    raise SystemExit("Removed wishlist/trade search options are still visible")
if 'owned_state == "wishlist"' in search_core_text or 'owned_state == "trade"' in search_core_text:
    raise SystemExit("Removed wishlist/trade search backend remains active")
if '("market_value", "Geschätzter Marktwert")' not in feature_text:
    raise SystemExit("Estimated collection market-value column is missing")
if '("purchase_price", "Kaufpreis")' in feature_text or '("flags", "Status")' in feature_text:
    raise SystemExit("Legacy purchase/trade collection columns are still visible")
if "def _disable_removed_collection_controls" not in v111_text:
    raise SystemExit("Legacy collection trade/wishlist controls are not disabled")
if 'if not isinstance(item, dict):' not in v111_text or '_set_collection_estimate(self, None)' not in v111_text:
    raise SystemExit("Collection None-selection guard is missing")


# v1.2.4: collection summary no longer exposes trade/purchase totals.
for token in (
    "def _collection_estimated_total_eur",
    "total += float(unit_value) * quantity",
    "Geschätzter Sammlungswert:",
    'database.collection_items("")',
):
    if token not in v111_text:
        raise SystemExit(f"v1.2.4 collection summary token missing: {token}")
if 'flags.append("Tausch")' in (ROOT / "justincard/v108_core.py").read_text(encoding="utf-8"):
    raise SystemExit("Legacy trade flag is still exposed by record_value")


# v1.2.6: exact user-supplied Google-Sheets template + private appData backup.
requirements_text = (ROOT / "requirements.txt").read_text(encoding="utf-8")
for dependency in ("google-api-python-client", "google-auth", "google-auth-oauthlib"):
    if dependency not in requirements_text:
        raise SystemExit(f"Google cloud dependency missing: {dependency}")
cloud_text = (ROOT / "justincard/cloud_sync.py").read_text(encoding="utf-8")
v120_text = (ROOT / "justincard/v120_features.py").read_text(encoding="utf-8")
for token in (
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive.appdata",
    "InstalledAppFlow",
    'TEMPLATE_ASSET = "google_sheets_template.xlsx"',
    'MONSTER_HEADERS: tuple[str, ...] = ("Sterne", "Name", "Typ", "Element", "Kategorie", "Set-Code")',
    'SPELL_HEADERS: tuple[str, ...] = ("Kategorie", "Name", "Set-Code")',
    'TRAP_HEADERS: tuple[str, ...] = ("Kategorie", "Name", "Set-Code")',
    'if "tuner" in text:',
    'return "Empfänger"',
    "MediaFileUpload",
    'parents": ["appDataFolder"]',
    "merge_collection_records",
    "find_or_create_spreadsheet",
):
    if token not in cloud_text:
        raise SystemExit(f"Google template/cloud token missing: {token}")
if "https://www.googleapis.com/auth/spreadsheets" in cloud_text:
    raise SystemExit("Sensitive spreadsheets scope must not be requested in v1.2.6")
for token in (
    "Google Cloud-Sammlung",
    "Mit Google anmelden",
    "Sammlung hochladen",
    "Cloud laden",
    "Synchronisieren",
    "install_v120_patches",
    "Google Sheets – Sortierung festlegen",
):
    if token not in v120_text:
        raise SystemExit(f"Google cloud UI token missing: {token}")
if not (ROOT / "assets/google_oauth_client.example.json").exists():
    raise SystemExit("Google OAuth client example JSON missing")
import hashlib
expected_template_hash = "0cb4633fe1abcec31ee5d9fddf533987cdb7fa9f8c84e7b45d282c6a135c7fd7"
actual_template_hash = hashlib.sha256((ROOT / "assets/google_sheets_template.xlsx").read_bytes()).hexdigest()
if actual_template_hash != expected_template_hash:
    raise SystemExit("Google Sheets template differs from the user-supplied workbook")

# v1.2.3+: pre-export sort prompt and legal deck zoning stay active.
for token in (
    'def choose_sort_before_export()',
    'Google Sheets – Sortierung festlegen',
    'Deck-Reiter werden fest in Monster, Zauber, Fallen, Extra Deck und Side Deck gegliedert;',
):
    if token not in v120_text:
        raise SystemExit(f"pre-export sorting token missing: {token}")

print(f"Repository structure validated for Just InCard {APP_VERSION}.")
