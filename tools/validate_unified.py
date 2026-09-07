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
    "android/app/src/main/java/org/yugioh/kartenliste/sync/GoogleApiClient.kt",
    "android/app/src/main/java/org/yugioh/kartenliste/sync/GoogleSheetsSyncEngine.kt",
    "android/app/src/main/java/org/yugioh/kartenliste/sync/WindowsCloudCodec.kt",
    "android/app/src/main/java/org/yugioh/kartenliste/sync/WindowsSheetTemplate.kt",
    "android/app/src/main/java/org/yugioh/kartenliste/ui/screens/SettingsScreen.kt",
    "android/ci/justincard-ci-test.keystore",
    "windows/justincard/cloud_sync.py",
    "windows/justincard/version.py",
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
    'versionName = "13.0.1"',
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
    'ANDROID_VERSION: "13.0.1"',
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

settings = need(
    "android/app/src/main/java/org/yugioh/kartenliste/ui/screens/SettingsScreen.kt"
).read_text("utf-8")
for token in [
    "Google-Sheets-URL oder Tabellen-ID",
    "Cloud speichern",
    "Cloud laden",
    "Jetzt synchronisieren",
]:
    if token not in settings:
        errors.append(f"Google synchronization UI missing {token}")

# Windows must remain byte-for-byte identical to the supplied 1.2.7 source tree.
aggregate = hashlib.sha256()
for path in sorted((ROOT / "windows").rglob("*")):
    if path.is_file():
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        relative = path.relative_to(ROOT).as_posix()
        aggregate.update(f"{digest}  {relative}\n".encode())
if aggregate.hexdigest() != "db6bfd8fa4013a38d59ab121aafc4f0fb1f6fa5cb3dc4f5ab7397d1074d6acc3":
    errors.append("Windows 1.2.7 source tree changed")

if errors:
    print("\n".join(f"ERROR {error}" for error in errors))
    sys.exit(1)
print("Unified repository validation OK")

