# Just InCard – gemeinsames Android-/Windows-Repository

Dieses Repository baut beide Plattformen parallel:

- **Android 14.1.1** – native Kotlin/Jetpack-Compose-App mit CameraX-Livebild und ML-Kit-Scanner
- **Windows Desktop 1.2.7** – aktuelle Windows-App auf Basis der bisherigen 1.2.6

Die vom Nutzer bereitgestellte Android-Datei `JustInCard-Android-ci-release-3885c55.zip` enthielt nur fertig kompilierte APK-/AAB-Artefakte, keinen Quellcode. Deshalb ist der Android-Teil hier als neues, vollständig editierbares natives Quellprojekt aufgebaut. Die Kotlin-Namespace-Struktur bleibt `org.yugioh.kartenliste`; die Produktions-Paket-ID ist `org.yugioh.kartenliste.yugiohkartenliste` und die CI-Variante wie im Upload `org.yugioh.kartenliste.yugiohkartenliste.ci`. Die technische Basis verwendet Jetpack Compose, CameraX, ML Kit und Google-Login.

## Gemeinsame Google-Cloud-Sammlung

Windows und Android nutzen denselben Cloud-Vertrag:

- gleiche Google-Sheets-Vorlage
- gleiche sichtbaren Reiter `Monsterkarten`, `Zauberkarten`, `Fallenkarten`
- gleiche Deck-Reiter
- gleiches privates Drive-AppData-Backup `justincard-cloud-backup-v125.json`
- gleiches Schema `justincard-google-drive-backup-v4`
- gleiche kanonische Kartenidentität aus Passcode + Set-Code + Rarity + Sprache + Artwork

Dadurch kann dieselbe Sammlung auf Windows synchronisiert und danach auf Android geladen werden – oder umgekehrt. Die browserlesbare Sheet-Datei bleibt exakt auf die vorgegebene Vorlage beschränkt; vollständige Wiederherstellungsdaten liegen getrennt im privaten `appDataFolder`.

## Google Cloud einmalig konfigurieren

Für echte Windows-/Android-Synchronisation sollten beide OAuth-Clients **im selben Google-Cloud-Projekt** liegen.

1. Google Drive API und Google Sheets API aktivieren.
2. OAuth Consent Screen konfigurieren.
3. Einen **Desktop OAuth Client** für Windows erstellen. Dessen JSON kann als GitHub-Secret `GOOGLE_OAUTH_CLIENT_JSON_B64` eingebettet werden.
4. Einen **Android OAuth Client** erstellen:
   - Package: `org.yugioh.kartenliste.yugiohkartenliste`
   - SHA-1 der Produktionssignatur hinterlegen.
5. Für Test-Builds kann zusätzlich ein zweiter Android OAuth Client registriert werden:
   - Package: `org.yugioh.kartenliste.yugiohkartenliste.ci`
   - SHA-1: `67:AF:0E:5D:FD:32:27:03:EB:15:43:E8:19:2B:BE:90:05:6A:F8:6C`

Jeder Benutzer meldet sich mit seinem eigenen Google-Konto an. Dadurch besitzt jeder Benutzer seine eigene Sheet-/AppData-Sicherung. Meldet sich derselbe Benutzer auf Windows und Android mit demselben Konto an, sehen beide Apps denselben Cloud-Stand.

## Android-Funktionen

- native responsive Oberfläche für Smartphone/Tablet
- Live-Scanner bleibt als vollwertige CameraX-Vorschau erhalten
- ML-Kit-OCR mit Set-Code-Priorität vor Passcode
- Galeriebilder können ebenfalls ausgelesen werden
- Set-Code-Suche arbeitet intern immer über die EN-Referenz, speichert aber die tatsächliche Sprache/den ursprünglichen Set-Code
- Mengenwahl vor dem Hinzufügen, danach Rücksetzung auf 1
- Sammlung mit Zustand, Menge, Alt-Art/Artwork und geschätztem Marktwert
- keine Wunschlisten-/Tauschfunktion
- Deckbuilder mit maximal 50 Decks
- Fusion/Synchro/Xyz/Link automatisch ins Extra Deck
- normale Karten automatisch ins Main Deck
- nur Side Deck wird manuell gewählt
- Platzhalter bei fehlenden Sammlungsexemplaren
- Google-Cloud Upload, Download und bidirektionaler Sync
- getrennte Anzeigeprofile für Suche, Sammlung, Scanner und Decks

## GitHub Actions

Die Datei `.github/workflows/build-all.yml` startet Android und Windows als **zwei parallele Jobs**.

Android erzeugt:

- Debug APK
- Release APK
- Release AAB
- SHA-256-Datei
- Test-/Buildlogs

Windows erzeugt:

- Portable ZIP
- Installer EXE
- SHA-256-Dateien
- Buildlogs

### Android Produktionssignierung

Optional diese Secrets setzen:

- `ANDROID_KEYSTORE_BASE64`
- `ANDROID_KEYSTORE_PASSWORD`
- `ANDROID_KEY_ALIAS`
- `ANDROID_KEY_PASSWORD`

Ohne diese Secrets verwendet Android den mitgelieferten CI-Testschlüssel. Dieser ist nur für Entwicklung/Tests gedacht.

### Windows Google OAuth

Optional:

- `GOOGLE_OAUTH_CLIENT_JSON_B64`

Ohne Secret kann die Desktop-OAuth-JSON weiterhin zur Laufzeit ausgewählt werden.

## Ordner

```text
android/    natives Android-Quellprojekt
windows/    Windows-Desktop-Projekt
shared/     dokumentierter gemeinsamer Cloud-Vertrag
tools/      gemeinsame Validierung
.github/    paralleler Build-Workflow
```


## Android 14.1.1 Build-Hotfix

Der gemeinsame Workflow baut bei jedem Push und bei jedem manuellen Start automatisch **Android und Windows**. Eine separate Release-Auswahl ist nicht mehr nötig. Android bleibt auf `compileSdk 35`; deshalb sind `androidx.core` und `androidx.activity` bewusst auf API-35-kompatible Versionen festgesetzt. Der Workflow installiert Android SDK 35 und Build Tools 35.0.0 ausdrücklich vor dem Gradle-Build.
