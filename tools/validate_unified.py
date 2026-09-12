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
    "android/app/src/main/java/org/yugioh/kartenliste/scanner/LiveCardAnalyzer.kt",
    "android/app/src/main/java/org/yugioh/kartenliste/sync/CloudContract.kt",
    "android/app/src/main/java/org/yugioh/kartenliste/sync/GoogleAuthorizationManager.kt",
    "android/app/src/main/java/org/yugioh/kartenliste/sync/GoogleApiClient.kt",
    "android/app/src/main/java/org/yugioh/kartenliste/sync/GoogleSheetsSyncEngine.kt",
    "android/app/src/main/java/org/yugioh/kartenliste/sync/WindowsCloudCodec.kt",
    "android/app/src/main/java/org/yugioh/kartenliste/sync/WindowsSheetTemplate.kt",
    "android/app/src/main/java/org/yugioh/kartenliste/ui/screens/SettingsScreen.kt",
    "android/app/src/main/java/org/yugioh/kartenliste/ui/screens/SearchScreen.kt",
    "android/ci/justincard-ci-test.keystore",
    "windows/justincard/cloud_sync.py",
    "windows/justincard/version.py",
    "windows/justincard/v128_features.py",
    "windows/assets/google_oauth_client.json",
    ".github/workflows/build-all.yml",
    "shared/cloud-contract.md",
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
    'versionCode = 13006',
    'versionName = "13.0.6"',
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
    'ANDROID_VERSION: "13.0.6"',
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
        errors.append(f"Android 13.0.6 Google retry/permission fix missing {token}")

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

# Windows 1.2.9 intentionally extends the previously supplied 1.2.7 tree.
windows_version = need("windows/justincard/version.py").read_text("utf-8")
if 'APP_VERSION = "1.2.9"' not in windows_version:
    errors.append("Windows version is not 1.2.9")
windows_v128 = need("windows/justincard/v128_features.py").read_text("utf-8")
for token in [
    "Backup erstellen",
    "Backup laden",
    "CollectionCardPreview",
    "install_v128_patches",
]:
    if token not in windows_v128:
        errors.append(f"Windows 1.2.9 feature missing {token}")
windows_search = need("windows/justincard/ui/search_page.py").read_text("utf-8")
if "self.detail.set_card(cards[0], self.current_set_query)" not in windows_search:
    errors.append("Windows first-result preview fix missing")

if errors:
    print("\n".join(f"ERROR {error}" for error in errors))
    sys.exit(1)
print("Unified repository validation OK")
