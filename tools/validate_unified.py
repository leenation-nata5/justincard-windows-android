from pathlib import Path
import hashlib
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
errors=[]

def need(path):
    p=ROOT/path
    if not p.exists(): errors.append(f"missing {path}")
    return p

required=[
    'android/app/build.gradle.kts','android/app/src/main/AndroidManifest.xml',
    'android/app/src/main/java/org/yugioh/kartenliste/MainActivity.kt',
    'android/app/src/main/java/org/yugioh/kartenliste/scanner/LiveScanner.kt',
    'android/app/src/main/java/org/yugioh/kartenliste/cloud/GoogleCloudRepository.kt',
    'android/app/src/main/java/org/yugioh/kartenliste/cloud/SheetTemplate.kt',
    'android/app/src/main/java/org/yugioh/kartenliste/core/SetCode.kt',
    'android/app/src/main/java/org/yugioh/kartenliste/core/DeckRules.kt',
    'windows/justincard/cloud_sync.py','windows/justincard/version.py',
    '.github/workflows/build-all.yml','shared/cloud-contract.md',
]
for x in required: need(x)

wa=need('windows/assets/google_sheets_template.xlsx')
aa=need('android/app/src/main/assets/google_sheets_template.xlsx')
if wa.exists() and aa.exists() and hashlib.sha256(wa.read_bytes()).digest()!=hashlib.sha256(aa.read_bytes()).digest():
    errors.append('Windows/Android google_sheets_template.xlsx differ')

android_cloud=need('android/app/src/main/java/org/yugioh/kartenliste/core/CloudContract.kt').read_text('utf-8')
windows_cloud=need('windows/justincard/cloud_sync.py').read_text('utf-8')
for token in ['justincard-google-drive-backup-v4','justincard-cloud-backup-v125.json','collection-template-v1','Monsterkarten','Zauberkarten','Fallenkarten']:
    if token not in android_cloud: errors.append(f'Android cloud contract missing {token}')
    if token not in windows_cloud: errors.append(f'Windows cloud contract missing {token}')

setcode=need('android/app/src/main/java/org/yugioh/kartenliste/core/SetCode.kt').read_text('utf-8')
if 'englishReference' not in setcode or 'EN' not in setcode: errors.append('Android EN reference set-code contract missing')
deck=need('android/app/src/main/java/org/yugioh/kartenliste/core/DeckRules.kt').read_text('utf-8')
for token in ['fusion','synchro','xyz','link','SIDE']:
    if token.lower() not in deck.lower(): errors.append(f'Android deck routing missing {token}')
scanner=need('android/app/src/main/java/org/yugioh/kartenliste/scanner/LiveScanner.kt').read_text('utf-8')
for token in ['PreviewView','ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST','TextRecognition','FocusMeteringAction']:
    if token not in scanner: errors.append(f'Live scanner missing {token}')

manifest=need('android/app/src/main/AndroidManifest.xml').read_text('utf-8')
if 'android.permission.CAMERA' not in manifest: errors.append('CAMERA permission missing')
if 'org.yugioh.kartenliste' not in need('android/app/build.gradle.kts').read_text('utf-8'): errors.append('Android package id changed')

wf=need('.github/workflows/build-all.yml').read_text('utf-8')
for token in ['build-android','build-windows','windows-latest','ubuntu-latest']:
    if token not in wf: errors.append(f'unified workflow missing {token}')

if errors:
    print('\n'.join('ERROR '+e for e in errors)); sys.exit(1)
print('Unified repository validation OK')
