from __future__ import annotations

from pathlib import Path
import hashlib
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
errors: list[str] = []


def need(path: str) -> Path:
    value = ROOT / path
    if not value.is_file():
        errors.append(f"missing {path}")
    return value


required = [
    "android/app/build.gradle.kts",
    "android/app/src/main/AndroidManifest.xml",
    "android/app/src/main/assets/google_sheets_template.xlsx",
    "android/app/src/main/java/org/yugioh/kartenliste/MainActivity.kt",
    "android/app/src/main/java/org/yugioh/kartenliste/data/local/DeckStore.kt",
    "android/app/src/main/java/org/yugioh/kartenliste/data/model/CardLanguages.kt",
    "android/app/src/main/java/org/yugioh/kartenliste/scanner/LiveCardAnalyzer.kt",
    "android/app/src/main/java/org/yugioh/kartenliste/sync/CloudContract.kt",
    "android/app/src/main/java/org/yugioh/kartenliste/sync/GoogleAuthorizationManager.kt",
    "android/app/src/main/java/org/yugioh/kartenliste/sync/GoogleApiClient.kt",
    "android/app/src/main/java/org/yugioh/kartenliste/sync/GoogleSheetsSyncEngine.kt",
    "android/app/src/main/java/org/yugioh/kartenliste/sync/AccountApiClient.kt",
    "android/app/src/main/java/org/yugioh/kartenliste/sync/AccountSyncEngine.kt",
    "android/app/src/main/java/org/yugioh/kartenliste/sync/WindowsCloudCodec.kt",
    "android/app/src/main/java/org/yugioh/kartenliste/sync/WindowsSheetTemplate.kt",
    "android/app/src/main/java/org/yugioh/kartenliste/ui/screens/SettingsScreen.kt",
    "android/app/src/main/java/org/yugioh/kartenliste/ui/screens/SearchScreen.kt",
    "android/app/src/main/java/org/yugioh/kartenliste/ui/screens/CollectionScreen.kt",
    "android/app/src/main/java/org/yugioh/kartenliste/ui/screens/DeckScreen.kt",
    "android/ci/justincard-ci-test.keystore",
    "windows/justincard/cloud_sync.py",
    "windows/justincard/version.py",
    "windows/justincard/v128_features.py",
    "windows/justincard/v130_features.py",
    "windows/justincard/account_sync.py",
    "windows/justincard/v132_features.py",
    "windows/assets/google_oauth_client.json",
    ".github/workflows/build-all.yml",
    "shared/cloud-contract.md",
    "shared/account-sync-contract.md",
]
for item in required:
    need(item)

if errors:
    print("\n".join(f"ERROR {error}" for error in errors))
    raise SystemExit(1)

windows_asset = need("windows/assets/google_sheets_template.xlsx")
android_asset = need("android/app/src/main/assets/google_sheets_template.xlsx")
asset_hash = hashlib.sha256(android_asset.read_bytes()).hexdigest()
if asset_hash != "0cb4633fe1abcec31ee5d9fddf533987cdb7fa9f8c84e7b45d282c6a135c7fd7":
    errors.append("Android Google-Sheets template hash changed")
if android_asset.read_bytes() != windows_asset.read_bytes():
    errors.append("Windows/Android google_sheets_template.xlsx differ")

android_cloud = need(
    "android/app/src/main/java/org/yugioh/kartenliste/sync/CloudContract.kt"
).read_text("utf-8")
windows_cloud = need("windows/justincard/cloud_sync.py").read_text("utf-8")
for token in [
    "justincard-google-drive-backup-v4",
    "justincard-cloud-backup-v125.json",
    "collection-template-v1",
    "Monsterkarten",
    "Zauberkarten",
    "Fallenkarten",
]:
    if token not in android_cloud:
        errors.append(f"Android cloud contract missing {token}")
    if token not in windows_cloud:
        errors.append(f"Windows cloud contract missing {token}")

gradle = need("android/app/build.gradle.kts").read_text("utf-8")
for token in [
    'compileSdk = 36',
    'targetSdk = 36',
    'versionCode = 13009',
    'versionName = "13.0.10"',
    'play-services-auth:22.0.0',
    'GOOGLE_DRIVE_API_BASE',
    'GOOGLE_DRIVE_UPLOAD_BASE',
    'GOOGLE_SHEETS_API_BASE',
    'signingConfigs.getByName("ciTest")',
]:
    if token not in gradle:
        errors.append(f"Android build configuration missing {token}")

workflow = need(".github/workflows/build-all.yml").read_text("utf-8")
for token in [
    "build-android:",
    "build-windows:",
    "windows-latest",
    "ubuntu-latest",
    'ANDROID_VERSION: "13.0.10"',
    'sdkmanager "platforms;android-36"',
    'gradle-version: "9.5.0"',
    ":app:testDebugUnitTest :app:lintDebug",
    ":app:assembleCiRelease :app:bundleCiRelease",
]:
    if token not in workflow:
        errors.append(f"unified workflow missing {token}")

deck_store = need(
    "android/app/src/main/java/org/yugioh/kartenliste/data/local/DeckStore.kt"
).read_text("utf-8")
upsert = re.search(
    r"private fun upsertDeck\(.*?(?=\n    private fun)",
    deck_store,
    flags=re.DOTALL,
)
if not upsert or 'db.update("decks"' not in upsert.group(0):
    errors.append("Deck upsert must update its parent row without replacing it")
if upsert and "CONFLICT_REPLACE" in upsert.group(0):
    errors.append("Deck parent upsert still uses CONFLICT_REPLACE and can cascade-delete cards")
add_card = re.search(
    r"fun addFromCollection\(.*?(?=\n    fun setCardQuantity)",
    deck_store,
    flags=re.DOTALL,
)
for token in ["beginTransaction()", "upsertCard(db, updated)", "touchDeck(db, deckId, deviceId)"]:
    if not add_card or token not in add_card.group(0):
        errors.append(f"transactional deck-card fix missing {token}")

google_api = need(
    "android/app/src/main/java/org/yugioh/kartenliste/sync/GoogleApiClient.kt"
).read_text("utf-8")
for token in [
    "BuildConfig.GOOGLE_DRIVE_API_BASE",
    "BuildConfig.GOOGLE_DRIVE_UPLOAD_BASE",
    "BuildConfig.GOOGLE_SHEETS_API_BASE",
    "appDataFolder",
    "replaceVisibleWorkbook",
]:
    if token not in google_api:
        errors.append(f"Google API integration missing {token}")
if "GOOGLE_API_BASE" in google_api:
    errors.append("Google API client still uses the broken shared Drive/Sheets base URL")
if "stream?.use { it.readBytes() }.orEmpty()" in google_api:
    errors.append("Google API response still calls unsupported ByteArray?.orEmpty()")
if "stream?.use { it.readBytes() } ?: byteArrayOf()" not in google_api:
    errors.append("Google API empty-response fallback is missing")
for token in [
    "awaitSpreadsheetReady",
    "SHEET_READY_RETRY_DELAYS_MS",
    "TRANSIENT_RETRY_DELAYS_MS",
    "Google Sheets verweigert den Zugriff",
]:
    if token not in google_api:
        errors.append(f"Android 13.0.8 Google retry/permission fix missing {token}")

google_auth = need(
    "android/app/src/main/java/org/yugioh/kartenliste/sync/GoogleAuthorizationManager.kt"
).read_text("utf-8")
main_activity = need(
    "android/app/src/main/java/org/yugioh/kartenliste/MainActivity.kt"
).read_text("utf-8")
for token in [
    "client.getAuthorizationResultFromIntent(data)",
    "CommonStatusCodes.DEVELOPER_ERROR",
    "CommonStatusCodes.INTERNAL_ERROR",
    "AuthorizationRequest.Prompt.SELECT_ACCOUNT",
    "GoogleApiAvailability",
    "signingCertificateSha1",
    "completeSuccess(token)",
]:
    if token not in google_auth:
        errors.append(f"Google authorization result handling missing {token}")
if "result.resultCode" in main_activity or "Activity.RESULT_OK" in main_activity:
    errors.append("Google authorization is still incorrectly gated by the Activity result code")
if "googleAuthorization.handleResult(result.data)" not in main_activity:
    errors.append("Google authorization result Intent is not forwarded")
for required_scope in ["drive.file", "drive.appdata", "https://www.googleapis.com/auth/spreadsheets"]:
    if required_scope not in android_cloud:
        errors.append(f"Android OAuth scope missing {required_scope}")
for forbidden_scope in ["drive.metadata.readonly"]:
    if forbidden_scope in android_cloud:
        errors.append(f"Android OAuth scope must not request {forbidden_scope}")
if '"https://www.googleapis.com/auth/drive"' in android_cloud:
    errors.append("Android OAuth scope must not request broad drive")

search_screen = need(
    "android/app/src/main/java/org/yugioh/kartenliste/ui/screens/SearchScreen.kt"
).read_text("utf-8")
for token in [
    "rememberModalBottomSheetState(skipPartiallyExpanded = true)",
    "sheetGesturesEnabled = false",
    "dragHandle = null",
]:
    if token not in search_screen:
        errors.append(f"stable filter sheet configuration missing {token}")

settings = need(
    "android/app/src/main/java/org/yugioh/kartenliste/ui/screens/SettingsScreen.kt"
).read_text("utf-8")
for token in [
    "Google-Sheets-URL oder Tabellen-ID",
    "Cloud speichern",
    "Cloud laden",
    "Jetzt synchronisieren",
    "onFreshGoogleToken",
]:
    if token not in settings:
        errors.append(f"Google synchronization UI missing {token}")


card_languages = need(
    "android/app/src/main/java/org/yugioh/kartenliste/data/model/CardLanguages.kt"
).read_text("utf-8")
for token in ["Deutsch", "Englisch", "Japanisch", "Koreanisch", "remoteCatalogLanguages"]:
    if token not in card_languages:
        errors.append(f"Android global card-language model missing {token}")

collection_screen = need(
    "android/app/src/main/java/org/yugioh/kartenliste/ui/screens/CollectionScreen.kt"
).read_text("utf-8")
deck_screen = need(
    "android/app/src/main/java/org/yugioh/kartenliste/ui/screens/DeckScreen.kt"
).read_text("utf-8")
for token in ["Sortierung", "Aufsteigend", "Absteigend"]:
    if token not in collection_screen:
        errors.append(f"Android collection sorting UI missing {token}")
for token in ["CardThumbnail", "Hinzufügen", "Sortierung", "Aufsteigend", "Absteigend"]:
    if token not in deck_screen:
        errors.append(f"Android deck preview/sorting UI missing {token}")
windows_sheet = need(
    "android/app/src/main/java/org/yugioh/kartenliste/sync/WindowsSheetTemplate.kt"
).read_text("utf-8")
for token in ["Monster", "Zauber", "Fallen", "Extra Deck", "Side Deck"]:
    if token not in windows_sheet:
        errors.append(f"Android deck sheet ordering missing {token}")

# Windows 1.3.5 keeps the IONOS account path and performs account login fully in-app.
windows_version = need("windows/justincard/version.py").read_text("utf-8")
if 'APP_VERSION = "1.3.5"' not in windows_version:
    errors.append("Windows version is not 1.3.5")
windows_v128 = need("windows/justincard/v128_features.py").read_text("utf-8")
for token in [
    "Backup erstellen",
    "Backup laden",
    "CollectionCardPreview",
    "install_v128_patches",
]:
    if token not in windows_v128:
        errors.append(f"Windows 1.3.5 feature missing {token}")
for token in [
    "SearchAddActionRow",
    "_AdaptiveCollectionPreview",
    "Qt.KeepAspectRatio",
    "move_quantity_to_add_button",
]:
    if token not in windows_v128:
        errors.append(f"Windows 1.3.5 UI hotfix missing {token}")
windows_v130 = need("windows/justincard/v130_features.py").read_text("utf-8")
for token in [
    "GLOBAL_LANGUAGE_SETTING",
    "SYNC_INTERVAL_MS",
    "Sammlung + Decks hochladen",
    "Dauerhaft automatisch synchronisieren",
    "install_v130_patches",
]:
    if token not in windows_v130:
        errors.append(f"Windows 1.3.5 feature missing {token}")
for token in ["Monster", "Zauber", "Fallen", "Extra Deck", "Side Deck"]:
    if token not in windows_cloud:
        errors.append(f"Windows deck sheet ordering missing {token}")

account_client = need(
    "android/app/src/main/java/org/yugioh/kartenliste/sync/AccountApiClient.kt"
).read_text("utf-8")
for token in ["JIC_ACCOUNT_API_BASE", "login.php", "sync.php", "revision_conflict", "justincard-account-sync-v1"]:
    if token not in account_client:
        errors.append(f"Android account API missing {token}")
account_engine = need(
    "android/app/src/main/java/org/yugioh/kartenliste/sync/AccountSyncEngine.kt"
).read_text("utf-8")
for token in ["account_sync_base_v1.json", "mergePayloads", "collectionIdentity", "replaceAll", "suspend fun sync()"]:
    if token not in account_engine:
        errors.append(f"Android account sync missing {token}")
for token in ["Wie möchtest du Just InCard verwenden?", "syncAccount(silent = true)"]:
    if token not in main_activity:
        errors.append(f"Android local/account startup choice missing {token}")
for token in ["Just InCard Konto", "Nur lokal verwenden", "Konto jetzt synchronisieren"]:
    if token not in settings:
        errors.append(f"Android account settings UI missing {token}")

windows_account = need("windows/justincard/account_sync.py").read_text("utf-8")
for token in ["justincard-account-sync-v1", "sync_windows_account", "merge_payloads", "replace_windows_from_payload"]:
    if token not in windows_account:
        errors.append(f"Windows account sync missing {token}")
windows_v132 = need("windows/justincard/v132_features.py").read_text("utf-8")
for token in ["Just InCard Konto (IONOS)", "Nur lokal verwenden", "Mit Just InCard Konto anmelden", "install_v132_patches"]:
    if token not in windows_v132:
        errors.append(f"Windows 1.3.5 account UI missing {token}")
windows_search = need("windows/justincard/ui/search_page.py").read_text("utf-8")
for token in ["select_visible_first", "self.table.selectRow(0)", "self.model.card_at(0)", "QTimer.singleShot(0, select_visible_first)"]:
    if token not in windows_search:
        errors.append(f"Windows visible-first-result preview fix missing {token}")

# Windows account login must never launch a browser. Account creation remains on the webspace,
# but signing in is performed only through the HTTPS API from the in-app credential dialog.
if "webbrowser" in windows_v132 or "DEFAULT_WEBSITE" in windows_v132 or 'QPushButton("Konto erstellen"' in windows_v132:
    errors.append("Windows account login still contains external-browser integration")
for token in ["JustInCardAccountClient().login", "es wird kein Browser geöffnet"]:
    if token not in windows_v132:
        errors.append(f"Windows in-app account login missing {token}")

if errors:
    print("\n".join(f"ERROR {error}" for error in errors))
    sys.exit(1)
print("Unified repository validation OK")
