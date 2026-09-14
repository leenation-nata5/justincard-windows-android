#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
repository_root="$project_root"
workflow_path="$project_root/.github/workflows/build-android.yml"
cd "$project_root"

fail() {
  echo "FEHLER: $*" >&2
  exit 1
}

required=(
  settings.gradle.kts
  build.gradle.kts
  gradle.properties
  app/build.gradle.kts
  app/proguard-rules.pro
  app/src/main/AndroidManifest.xml
  app/src/main/java/org/yugioh/kartenliste/JustInCardApplication.kt
  app/src/main/java/org/yugioh/kartenliste/MainActivity.kt
  app/src/main/java/org/yugioh/kartenliste/ui/screens/SearchScreen.kt
  app/src/main/java/org/yugioh/kartenliste/ui/screens/CollectionScreen.kt
  app/src/main/java/org/yugioh/kartenliste/ui/screens/ScanScreen.kt
  app/src/main/java/org/yugioh/kartenliste/ui/screens/DeckScreen.kt
  app/src/main/java/org/yugioh/kartenliste/ui/screens/SettingsScreen.kt
  app/src/main/java/org/yugioh/kartenliste/data/model/CardLanguages.kt
  app/src/main/java/org/yugioh/kartenliste/sync/CloudContract.kt
  app/src/main/java/org/yugioh/kartenliste/sync/WindowsCloudCodec.kt
  app/src/main/java/org/yugioh/kartenliste/sync/WindowsSheetTemplate.kt
  app/src/main/assets/google_sheets_template.xlsx
  ci/justincard-ci-test.keystore
)

for path in "${required[@]}"; do
  test -f "$path" || fail "Pflichtdatei fehlt: $path"
done
test -f "$workflow_path" || fail "Standalone-Android-Workflow fehlt: $workflow_path"

grep -Fq 'id("com.android.application") version "9.3.2" apply false' build.gradle.kts \
  || fail "Erwartete Android-Gradle-Plugin-Version 9.3.2 fehlt."
grep -Fq 'id("org.jetbrains.kotlin.plugin.compose") version "2.4.10" apply false' build.gradle.kts \
  || fail "Erwartete Compose-Compiler-Version 2.4.10 fehlt."
grep -Fq 'compileSdk = 36' app/build.gradle.kts \
  || fail "compileSdk 36 fehlt."
grep -Fq 'minSdk = 24' app/build.gradle.kts \
  || fail "minSdk 24 fehlt. Google Play Services Auth 22.0.0 benoetigt mindestens API 24."
grep -Fq 'targetSdk = 36' app/build.gradle.kts \
  || fail "targetSdk 36 fehlt."
grep -Fq 'versionCode = 13010' app/build.gradle.kts \
  || fail "Android versionCode 13010 fehlt."
grep -Fq 'versionName = "13.0.11"' app/build.gradle.kts \
  || fail "Android versionName 13.0.11 fehlt."
grep -Fq 'enforcedPlatform("androidx.compose:compose-bom:2026.02.00")' app/build.gradle.kts \
  || fail "Compose BOM 2026.02.00 muss fuer API 36 strikt erzwungen werden."
grep -Fq 'enforcedPlatform("io.coil-kt.coil3:coil-bom:3.5.0")' app/build.gradle.kts \
  || fail "Der Coil BOM muss fuer compileSdk 36 strikt auf 3.5.0 erzwungen werden."
grep -Fq 'io.coil-kt.coil3:coil-compose")' app/build.gradle.kts \
  || fail "Coil Compose fehlt."
grep -Fq 'io.coil-kt.coil3:coil-network-okhttp")' app/build.gradle.kts \
  || fail "Coil Network OkHttp fehlt."
if grep -Fq 'androidx.compose:compose-bom:2026.04.00' app/build.gradle.kts; then
  fail "Compose BOM 2026.04.00 ist nicht veroeffentlicht und kann nicht aufgeloest werden."
fi
if grep -Fq 'androidx.compose:compose-bom:2026.04.01' app/build.gradle.kts; then
  fail "Compose BOM 2026.04.01 zieht Compose 1.12 und benoetigt compileSdk 37."
fi
if grep -REn 'io\.coil-kt\.coil3:[^" ]+:3\.6\.' app --include='*.gradle' --include='*.gradle.kts'; then
  fail "Coil 3.6.x benoetigt compileSdk 37 und darf in diesem API-36-Build nicht verwendet werden."
fi
grep -Fq 'org.gradle.configuration-cache=false' gradle.properties \
  || fail "Der Gradle-Konfigurationscache muss fuer den stabilen AGP-CI-Build deaktiviert sein."
grep -Fq 'applicationId = "org.yugioh.kartenliste.yugiohkartenliste"' app/build.gradle.kts \
  || fail "Release-Application-ID stimmt nicht."
grep -Fq 'create("ciRelease")' app/build.gradle.kts \
  || fail "Der optimierte CI-Release-Buildtyp fehlt."
grep -Fq 'applicationIdSuffix = ".ci"' app/build.gradle.kts \
  || fail "Der CI-Release muss eine getrennte .ci-Paket-ID verwenden."
grep -Fq 'signingConfig = signingConfigs.getByName("ciTest")' app/build.gradle.kts \
  || fail "Der installierbare CI-Release muss mit der stabilen Android-Testsignatur gebaut werden."
grep -Fq 'gradle-version: "9.5.0"' "$workflow_path" \
  || fail "Gradle 9.5.0 fehlt im Android-Workflow."
grep -Fq ':app:assembleCiRelease :app:bundleCiRelease' "$workflow_path" \
  || fail "CI-Release APK/AAB fehlen im Android-Workflow."
grep -Fq 'android.permission.CAMERA' app/src/main/AndroidManifest.xml \
  || fail "CAMERA-Berechtigung fehlt."
grep -Fq 'android.permission.INTERNET' app/src/main/AndroidManifest.xml \
  || fail "INTERNET-Berechtigung fehlt."

grep -Fq 'import androidx.activity.compose.setContent' app/src/main/java/org/yugioh/kartenliste/MainActivity.kt \
  || fail "MainActivity importiert androidx.activity.compose.setContent nicht."
grep -Fq 'toOkioPath()' app/src/main/java/org/yugioh/kartenliste/JustInCardApplication.kt \
  || fail "Coil-DiskCache muss den Cache-Pfad als Okio Path uebergeben."
grep -Fq 'import androidx.camera.core.ExperimentalGetImage' app/src/main/java/org/yugioh/kartenliste/scanner/LiveCardAnalyzer.kt \
  || fail "CameraX ExperimentalGetImage-Import fehlt im LiveCardAnalyzer."
grep -Fq '@ExperimentalGetImage' app/src/main/java/org/yugioh/kartenliste/scanner/LiveCardAnalyzer.kt \
  || fail "CameraX ImageProxy.image muss direkt mit ExperimentalGetImage markiert sein."
if grep -Fq '@OptIn(ExperimentalGetImage::class)' app/src/main/java/org/yugioh/kartenliste/scanner/LiveCardAnalyzer.kt; then
  fail "Kotlin-OptIn ist fuer die CameraX-Java-Annotation wirkungslos; @ExperimentalGetImage direkt verwenden."
fi
grep -Fq 'import androidx.lifecycle.compose.LocalLifecycleOwner' app/src/main/java/org/yugioh/kartenliste/ui/components/LiveCameraPreview.kt \
  || fail "LocalLifecycleOwner muss aus lifecycle-runtime-compose importiert werden."
if grep -RInF 'androidx.compose.ui.platform.LocalLifecycleOwner' app/src/main/java; then
  fail "Der veraltete Compose-UI-Import fuer LocalLifecycleOwner darf nicht verwendet werden."
fi
if grep -RInE '^import androidx\.compose\.material\.icons\.filled\.(ArrowBack|ArrowForward)$' app/src/main/java; then
  fail "Richtungssymbole muessen die AutoMirrored-Varianten fuer RTL verwenden."
fi
if grep -Fq 'android:screenOrientation=' app/src/main/AndroidManifest.xml; then
  fail "Eine feste bzw. redundante Bildschirmausrichtung verhindert das adaptive Android-Layout."
fi
if grep -RInE '^import androidx\.compose\.foundation\.layout\.(weight|matchParentSize)$' app/src/main/java; then
  fail "Compose-Scope-Funktionen weight/matchParentSize duerfen mit der festgelegten Compose-Linie nicht als Top-Level-Import eingebunden werden."
fi

if grep -RInE 'http://' app/src/main/java; then
  fail "Unsichere Klartext-URL im App-Code gefunden."
fi
if grep -q 'usesCleartextTraffic="true"' app/src/main/AndroidManifest.xml; then
  fail "Cleartext-Traffic ist im AndroidManifest aktiviert."
fi

# Nur die dokumentierte, nicht produktive CI-Testsignatur darf im Repository liegen.
if find . -path './.git' -prune -o -type f \( -iname '*.jks' -o -iname '*.keystore' \) \
  ! -path './ci/justincard-ci-test.keystore' -print | grep -q .; then
  fail "Unerwartete Keystore-Datei gefunden. Produktionsschlüssel nur über GitHub Secrets verwenden."
fi
echo "0cb4633fe1abcec31ee5d9fddf533987cdb7fa9f8c84e7b45d282c6a135c7fd7  app/src/main/assets/google_sheets_template.xlsx" \
  | sha256sum -c -
grep -Fq 'CloudContract.SCOPES.map(::Scope)' app/src/main/java/org/yugioh/kartenliste/sync/GoogleAuthorizationManager.kt \
  || fail "Google-Autorisierung verwendet nicht den gemeinsamen Cloud-Vertrag."
grep -Fq 'GOOGLE_SHEETS_API_BASE' app/src/main/java/org/yugioh/kartenliste/sync/GoogleApiClient.kt \
  || fail "Google Sheets API-Endpunkt fehlt."
grep -Fq 'GOOGLE_DRIVE_UPLOAD_BASE' app/src/main/java/org/yugioh/kartenliste/sync/GoogleApiClient.kt \
  || fail "Google Drive Upload-Endpunkt fehlt."
grep -Fq 'touchDeck(db, deckId, deviceId)' app/src/main/java/org/yugioh/kartenliste/data/local/DeckStore.kt \
  || fail "Transaktionale Deckkarten-Korrektur fehlt."
grep -Fq 'remoteCatalogLanguages' app/src/main/java/org/yugioh/kartenliste/data/model/CardLanguages.kt \
  || fail "Appweite Kartentext-Sprachen fehlen."
grep -Fq 'CardThumbnail' app/src/main/java/org/yugioh/kartenliste/ui/screens/DeckScreen.kt \
  || fail "Deckbau-Kartenvorschau fehlt."
grep -Fq 'DeckFixedPreview' app/src/main/java/org/yugioh/kartenliste/ui/screens/DeckScreen.kt \
  || fail "Feste Deckbau-Vorschau fehlt."
grep -Fq 'Nicht verfügbare Karten ausblenden' app/src/main/java/org/yugioh/kartenliste/ui/screens/DeckScreen.kt \
  || fail "Filter fuer vollstaendig verwendete Sammlungskarten fehlt."
grep -Fq 'forceReplace = true' app/src/main/java/org/yugioh/kartenliste/sync/AccountSyncEngine.kt \
  || fail "Expliziter vollstaendiger Account-Upload fehlt."
grep -Fq 'Sammlung + Decks vollständig hochladen' app/src/main/java/org/yugioh/kartenliste/ui/screens/SettingsScreen.kt \
  || fail "UI fuer vollstaendigen Account-Upload fehlt."
grep -Fq 'Extra Deck' app/src/main/java/org/yugioh/kartenliste/sync/WindowsSheetTemplate.kt \
  || fail "Deck-Sheets-Sortierung fehlt."

if compgen -G 'windows/reference/JustInCard-Windows-7.zip.part-*' >/dev/null; then
  expected_parts=(00 01 02 03)
  for part in "${expected_parts[@]}"; do
    test -f "windows/reference/JustInCard-Windows-7.zip.part-$part" \
      || fail "Windows-Referenzteil fehlt: part-$part"
  done

  # Erst jeden Block einzeln prüfen. So ist bei beschädigten Uploads sofort
  # sichtbar, welcher Teil betroffen ist, statt nur die Gesamtsumme zu melden.
  (
    cd windows/reference
    grep 'zip\.part-' SHA256SUMS.txt | sha256sum -c -
  )

  temp_dir="$(mktemp -d)"
  trap 'rm -rf "$temp_dir"' EXIT
  cat windows/reference/JustInCard-Windows-7.zip.part-* > "$temp_dir/JustInCard-Windows-7.zip"
  echo "f65d18840a7d82b82f1263a5ff5bc2b3e8162355dffa155f182329019a7ee18c  $temp_dir/JustInCard-Windows-7.zip" | sha256sum -c -
fi

echo "Vorabprüfung erfolgreich."
