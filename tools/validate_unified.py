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

# Android compileSdk/dependency compatibility regression guard.
gradle_text=need('android/app/build.gradle.kts').read_text('utf-8')
if 'compileSdk = 35' in gradle_text:
    if 'androidx.core:core-ktx:1.17.0' in gradle_text:
        errors.append('Android compileSdk 35 cannot use androidx.core 1.17.0 (requires API 36)')
    if 'androidx.activity:activity-compose:1.11.0' in gradle_text:
        errors.append('Android compileSdk 35 cannot use androidx.activity 1.11.0 (requires API 36)')
if 'androidx.core:core-ktx:1.16.0' not in gradle_text:
    errors.append('Android core-ktx compatibility pin 1.16.0 missing')
if 'androidx.activity:activity-compose:1.10.1' not in gradle_text:
    errors.append('Android activity-compose compatibility pin 1.10.1 missing')
if 'resolutionStrategy.force' not in gradle_text:
    errors.append('Android API-35 transitive dependency force guard missing')
wf_text=need('.github/workflows/build-all.yml').read_text('utf-8')
if 'inputs.build_release' in wf_text:
    errors.append('Unified workflow must build Android release automatically without user input')
if 'sdkmanager "platforms;android-35"' not in wf_text:
    errors.append('Unified workflow does not install Android API 35 explicitly')

# Android 14.1.2 Kotlin compiler regression guards.
if 'com.google.android.gms:play-services-auth:22.0.0' in gradle_text:
    errors.append('play-services-auth 22.0.0 removes legacy GoogleSignIn client entry points used by this source')
if 'com.google.android.gms:play-services-auth:21.4.0' not in gradle_text:
    errors.append('Google Sign-In compatibility pin 21.4.0 missing')
cloud_repo=need('android/app/src/main/java/org/yugioh/kartenliste/cloud/GoogleCloudRepository.kt').read_text('utf-8')
display_prefs=need('android/app/src/main/java/org/yugioh/kartenliste/ui/DisplayPrefs.kt').read_text('utf-8')
if 'private fun JsonArray?.orEmpty()' in cloud_repo:
    errors.append('JsonArray.orEmpty shadows Kotlin String?.orEmpty and breaks type inference')
if 'gson.fromJson<List<Map<String, Any?>>>' not in cloud_repo:
    errors.append('Explicit Gson generic type for cloud collection/decks missing')
if 'gson.fromJson<Map<String, Map<String, Boolean>>>' not in display_prefs:
    errors.append('Explicit Gson generic type for display profiles missing')

if errors:
    print('\n'.join('ERROR '+e for e in errors)); sys.exit(1)
print('Unified repository validation OK')
