from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "android/app/src/main/java/org/yugioh/kartenliste"

expected_live_hashes = {
    "scanner/LiveCardAnalyzer.kt": "4e7b694f11cbfb1f4e28e5647b4e8463188af8c3f4d423defa7bdfb608af185c",
    "scanner/OcrEngine.kt": "dc267856f05ae88dba74154004c34a6adc7ea4a93a61d3cf5709c946fe822d03",
    "scanner/OcrSignalParser.kt": "c1bb3c4bc919dd2774fae1fde6f7d4b08b150782c1549d7ffa79138638560cc5",
    "ui/screens/ScanScreen.kt": "8d0af8fdfb285c7315d80e5250d851554dddc41b56f338b6127c7b19091082a3",
    "ui/components/LiveCameraPreview.kt": "2db04a4124042286c094ca722fc315d5c5fc2d6a99fd86da9faa09a4802e3f74",
    "ui/ScanViewModel.kt": "6b89b4d5b226ca263f5bc18a676637bec5863b7e2fe7033ab667e8db4395ca78",
}
for relative, expected in expected_live_hashes.items():
    actual = hashlib.sha256((SRC / relative).read_bytes()).hexdigest()
    assert actual == expected, f"Livebild source changed: {relative}"

main = (SRC / "MainActivity.kt").read_text("utf-8")
for destination in ["SEARCH", "COLLECTION", "SCAN", "DECKS", "SETTINGS"]:
    assert f"Destination.{destination}" in main
assert "ScanScreen(" in main
assert "SettingsScreen(" in main
assert "googleAuthorization.handleResult(result.data)" in main
assert "result.resultCode" not in main
assert "Activity.RESULT_OK" not in main
assert "authorizeGoogleFor" in main

auth = (SRC / "sync/GoogleAuthorizationManager.kt").read_text("utf-8")
contract = (SRC / "sync/CloudContract.kt").read_text("utf-8")
client = (SRC / "sync/GoogleApiClient.kt").read_text("utf-8")
engine = (SRC / "sync/GoogleSheetsSyncEngine.kt").read_text("utf-8")
codec = (SRC / "sync/WindowsCloudCodec.kt").read_text("utf-8")
template = (SRC / "sync/WindowsSheetTemplate.kt").read_text("utf-8")
settings = (SRC / "ui/SettingsViewModel.kt").read_text("utf-8")

assert "CloudContract.SCOPES.map(::Scope)" in auth
assert "client.getAuthorizationResultFromIntent(data)" in auth
assert "CommonStatusCodes.DEVELOPER_ERROR" in auth
assert "CommonStatusCodes.INTERNAL_ERROR" in auth
assert "AuthorizationRequest.Prompt.SELECT_ACCOUNT" in auth
assert "GoogleApiAvailability" in auth
assert "signingCertificateSha1" in auth
for scope in ["drive.file", "drive.appdata", "https://www.googleapis.com/auth/spreadsheets"]:
    assert scope in contract
assert "drive.metadata.readonly" not in contract
for action in ["suspend fun save(", "suspend fun load(", "suspend fun sync("]:
    assert action in engine
for action in ["saveToGoogle", "loadFromGoogle", "linkSpreadsheet"]:
    assert action in settings
settings_screen = (SRC / "ui/screens/SettingsScreen.kt").read_text("utf-8")
assert "onFreshGoogleToken" in settings_screen
assert "justincard-cloud-backup-v125.json" in contract
assert "appDataFolder" in client
assert "WindowsCloudCodec.encode" in engine
assert "WindowsCloudCodec.decode" in engine
assert "WindowsSheetTemplate.workbook" in engine
assert '"collection_key"' in codec and '"decks"' in codec
assert "Empfänger" in template
assert "JIC_COLLECTION" not in client
assert "JIC_DECKS" not in client
assert "JIC_DEVICES" not in client
assert "awaitSpreadsheetReady" in client
assert "TRANSIENT_RETRY_DELAYS_MS" in client
assert "Google Sheets verweigert den Zugriff" in client


card_languages = (SRC / "data/model/CardLanguages.kt").read_text("utf-8")
for token in ["Deutsch", "Englisch", "Japanisch", "Koreanisch", "remoteCatalogLanguages"]:
    assert token in card_languages

collection_screen = (SRC / "ui/screens/CollectionScreen.kt").read_text("utf-8")
deck_screen = (SRC / "ui/screens/DeckScreen.kt").read_text("utf-8")
settings_screen = (SRC / "ui/screens/SettingsScreen.kt").read_text("utf-8")
assert "Kartentext-Sprache (appweit)" in settings_screen
for token in ["Sortierung", "Aufsteigend", "Absteigend"]:
    assert token in collection_screen
for token in ["CardThumbnail", "Hinzufügen", "Deck sortieren", "Aufsteigend", "Absteigend"]:
    assert token in deck_screen
for label in ["Monster", "Zauber", "Fallen", "Extra Deck", "Side Deck"]:
    assert label in template

deck_store = (SRC / "data/local/DeckStore.kt").read_text("utf-8")
upsert = re.search(
    r"private fun upsertDeck\(.*?(?=\n    private fun)",
    deck_store,
    flags=re.DOTALL,
)
assert upsert is not None
assert 'db.update("decks"' in upsert.group(0)
assert "CONFLICT_REPLACE" not in upsert.group(0)
assert "beginTransaction()" in deck_store
assert "touchDeck(db, deckId, deviceId)" in deck_store

search_screen = (SRC / "ui/screens/SearchScreen.kt").read_text("utf-8")
assert "rememberModalBottomSheetState(skipPartiallyExpanded = true)" in search_screen
assert "sheetGesturesEnabled = false" in search_screen
assert "dragHandle = null" in search_screen

print("Android source contract OK")
