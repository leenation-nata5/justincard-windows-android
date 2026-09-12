# Just InCard – Android 13.0.4 und Windows 1.2.8

Dieses gemeinsame Repository enthält:

- **Android 13.0.4** – die bereitgestellte native Kotlin-/Compose-Version 13 mit unverändertem Aufbau und unverändertem CameraX-/ML-Kit-Livebild
- **Windows 1.2.8** – vollständig und bytegleich aus der bereitgestellten gemeinsamen Version
- einen GitHub-Actions-Workflow, der Android und Windows nach derselben Validierung parallel baut

## Änderungen in Android 13.0.4

Nur die angeforderten Bereiche wurden ergänzt beziehungsweise korrigiert:

- Google-Konto-Autorisierung über die moderne Android `AuthorizationClient`-API, jetzt mit explizitem Google-Play-Services-Check, festem Kontoauswahldialog und direkter Diagnose von Paketname/SHA-1
- Android fordert exakt dieselben minimalen Google-Berechtigungen wie Windows 1.2.8 an (`drive.file` und `drive.appdata`)
- vorhandene Google-Sheets-Datei über Liste, URL oder Tabellen-ID verbinden
- getrennte Aktionen **Cloud speichern**, **Cloud laden** und **Jetzt synchronisieren**
- identischer sichtbarer Tabellenaufbau und identisches privates Drive-AppData-Backup wie Windows 1.2.8
- Korrektur im Deck-Reiter: Das Hinzufügen einer Sammlungskarte bleibt nun tatsächlich im Deck gespeichert und wird sofort angezeigt
- stabile, installierbare CI-Release-Signatur mit eigener `.ci`-Paket-ID
- Kotlin-Buildfehler beim Lesen einer leeren Google-API-Antwort korrigiert
- das erweiterte Filterfenster bleibt beim Scrollen vollständig geöffnet und kann die Liste nicht mehr durch eigene Ziehgesten versetzen
- die Antwort der Google-Autorisierung wird nach der Kontoauswahl direkt aus dem Ergebnis-Intent gelesen, statt vorzeitig als Abbruch verworfen zu werden
- Status 8/`INTERNAL_ERROR` zeigt nun die exakte installierte Paket-ID und SHA-1-Signatur an, damit der passende Android-OAuth-Client ohne Rätselraten angelegt werden kann
- die Windows-Desktop-OAuth-JSON wird absichtlich nicht als Android-Client missbraucht; Android verwendet Googles unterstützte Paketname+SHA-1-Identität
- verständliche Hinweise für fehlende OAuth-Konfiguration, Netzwerkfehler und echte Abbrüche ergänzt

Livebild, Scannerlogik, Navigation, Suchlogik, Sammlung und die übrige UI wurden nicht umgebaut. Die Validierung prüft die Livebild-/OCR-Quelldateien gegen die Original-Prüfsummen der gelieferten Android-13-Version.

## Gemeinsame Google-Sammlung

Beide Plattformen verwenden denselben Datenvertrag:

- Google-Sheets-Reiter `Monsterkarten`, `Zauberkarten`, `Fallenkarten`
- je ein sichtbarer Reiter pro Deck
- private Sicherung `justincard-cloud-backup-v125.json` im Drive-`appDataFolder`
- Schema `justincard-google-drive-backup-v4`
- Kartenidentität aus Passcode, Set-Code, Seltenheit, Sprache und Artwork-URL

Die sichtbare Tabelle bleibt damit lesbar und vorlagentreu. Mengen, Zustand, Sprache, Seltenheit, Notizen, vollständige Kartendaten und Deck-Metadaten werden verlustfrei in der privaten Sicherung gehalten.

Die Android-Einrichtung ist in [android/docs/GOOGLE_SHEETS_SETUP.md](android/docs/GOOGLE_SHEETS_SETUP.md) beschrieben.

## GitHub Actions

`.github/workflows/build-all.yml` startet nach den gemeinsamen Prüfungen zwei parallele Jobs:

- Android: Unit-Tests, Lint, Debug-APK, optimierte CI-Release-APK und AAB; optional produktiv signierte APK/AAB
- Windows: Tests, Portable-ZIP und Installer

Produktionssignierung für Android:

- `JIC_KEYSTORE_BASE64`
- `JIC_KEYSTORE_PASSWORD`
- `JIC_KEY_ALIAS`
- `JIC_KEY_PASSWORD`

Die bisherigen `ANDROID_…`-Varianten dieser vier Secrets werden ebenfalls akzeptiert. Ohne Produktions-Secrets entsteht weiterhin ein installierbarer, aber ausschließlich für Tests bestimmter `.ci`-Build.

## Struktur

```text
android/    Android-13.0.4-Quellprojekt
windows/    Windows-1.2.8-Quellprojekt
shared/     gemeinsamer Cloud-Datenvertrag
tools/      gemeinsame Regressionstests
.github/    paralleler Android-/Windows-Build
```
