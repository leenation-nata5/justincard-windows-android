from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'android/app/src/main/java/org/yugioh/kartenliste'
app=(SRC/'ui/App.kt').read_text('utf-8')
cloud=(SRC/'cloud/GoogleCloudRepository.kt').read_text('utf-8')
mapper=(SRC/'cloud/CloudMapper.kt').read_text('utf-8')
scanner=(SRC/'scanner/LiveScanner.kt').read_text('utf-8')
ygo=(SRC/'network/YgoApi.kt').read_text('utf-8')
db=(SRC/'data/Database.kt').read_text('utf-8')

assert 'Tausch' not in app
assert 'Wunschliste' not in app
assert 'LiveScanner' in app and 'PreviewView' in scanner
assert 'ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST' in scanner
assert 'originalCode' in ygo and 'englishReference' in ygo
assert 'requestedPrintCode = requestedCode' in (SRC/'ui/JustInCardViewModel.kt').read_text('utf-8')
assert 'DeckRules.allowedZone' in db
assert 'syncBidirectional' in cloud
assert 'appDataFolder' in cloud
assert 'google_sheets_template.xlsx' in cloud
assert 'CloudMapper.mergeCollection' in cloud
assert 'CloudMapper.mergeDecks' in cloud
assert 'drive.file' in (SRC/'core/CloudContract.kt').read_text('utf-8')
assert 'drive.appdata' in (SRC/'core/CloudContract.kt').read_text('utf-8')
print('Android source contract OK')
