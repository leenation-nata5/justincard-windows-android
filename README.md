# Just InCard – Android 13.0.8 und Windows 1.3.2

Dieses gemeinsame Repository enthält:

- **Android 13.0.8** – native Kotlin-/Compose-Version 13 mit unverändertem Aufbau und unverändertem CameraX-/ML-Kit-Livebild
- **Windows 1.3.2** – Desktop-Version mit Deckvorschau, appweiter Kartentext-Sprache, dauerhafter Google-Synchronisierung sowie korrigierter Mengenposition und vollständig eingepasster Sammlungsvorschau
- einen GitHub-Actions-Workflow, der Android und Windows nach derselben Validierung parallel baut

## Neues Just-InCard-Konto / IONOS-Synchronisierung

Windows 1.3.2 und Android 13.0.8 können jetzt wahlweise **vollständig lokal** oder mit einem Account von `https://justincard.de/` verwendet werden. Im Kontomodus werden ausschließlich Sammlung und Decks als geräteunabhängiger Snapshot über `https://justincard.de/api/v1/sync.php` gespeichert. Kartenbilder werden nicht auf dem Webspace abgelegt.

Beim ersten Start erscheint auf beiden Plattformen eine Auswahl zwischen **Nur lokal verwenden** und **Mit Just InCard Konto anmelden**. Die lokale Datenbank bleibt auch im Kontomodus die Offline-Arbeitskopie. Automatischer Abgleich erfolgt beim Start und anschließend alle fünf Minuten, zusätzlich gibt es einen manuellen Sync in den Einstellungen. Google Sheets und lokale Backups bleiben parallel verfügbar.

Für den Account-Sync muss auf dem IONOS-Webspace mindestens **JustInCard-Webspace 1.1.0** liegen. Bestehende Webspace-1.0.0-Accounts bleiben gültig; beim Update wird kein neues Konto benötigt.

## Änderungen in Android 13.0.8

Zusätzlich zu den Google-Stabilisierungen aus 13.0.6 wurden Deckbau, Kartentext-Sprache und Sortierung erweitert. Livebild und Scanner-Pipeline bleiben unverändert:


- der Deckbau zeigt bei der Auswahl aus der Sammlung jetzt Kartenbilder und eine größere Vorschau vor dem Hinzufügen
- Sammlung und Deckbau besitzen zusätzliche Sortierfunktionen mit auf-/absteigender Richtung
- eine appweite Kartentext-Sprache steuert Suche, Vorschauen, Sammlung, Deckbau und Scannerergebnisse
- EN/DE/FR/IT/PT können über die aktuelle Android-Katalogquelle geladen werden; weitere auswählbare Sprachen nutzen lokal/synchronisiert vorhandene Daten und fallen andernfalls auf Englisch zurück
- Decks werden in Google Sheets als eigene Reiter gespeichert; Reihenfolge: Monster, Zauber, Fallen, Extra Deck, Side Deck
- Android fordert jetzt zusätzlich zu `drive.file` und `drive.appdata` den expliziten Google-Sheets-Scope `https://www.googleapis.com/auth/spreadsheets` an
- dadurch kann eine bereits unter Windows verwendete Google-Tabelle über die Sheets API vollständig gelesen und bearbeitet werden, sofern das angemeldete Konto Bearbeitungsrechte besitzt
- nach dem Update wird beim nächsten Verbinden eine neue Google-Freigabe für den Sheets-Scope angefordert
- neu erstellte XLSX-Vorlagen werden nach der Drive-Konvertierung erst weiterverarbeitet, wenn die Sheets API die Tabelle tatsächlich bereitstellt
- vorübergehende HTTP-429-/5xx-Fehler werden mit begrenztem Backoff automatisch erneut versucht
- jede Cloud-Aktion holt still ein frisches Access-Token über `AuthorizationClient`, sodass abgelaufene Kurzzeit-Tokens nicht weiterverwendet werden
- 401/403/404-Fehler unterscheiden jetzt zwischen abgelaufener Anmeldung, fehlender Sheets-Berechtigung, Drive-Dateirechten und nicht freigegebenen Tabellen
- der bisherige Status-8-Fallback der Android-OAuth-Anmeldung bleibt erhalten
- die gemeinsame private Sicherung im Drive-`appDataFolder` bleibt kompatibel; die Deck-Reiter verwenden jetzt auf beiden Plattformen dieselbe feste Abschnittsreihenfolge

Die Validierung prüft weiterhin die Livebild-/OCR-Quelldateien gegen die Original-Prüfsummen der gelieferten Android-13-Version.

## Gemeinsame Google-Sammlung

Windows und Android verwenden weiterhin denselben Datenvertrag und dieselbe Tabelle. Die OAuth-Scopes sind absichtlich nicht mehr vollständig identisch: Windows 1.3.2 bleibt bei `drive.file` + `drive.appdata`; Android 13.0.8 ergänzt `spreadsheets`, damit bestehende gemeinsame Sheets zuverlässig gelesen und bearbeitet werden können.

- Google-Sheets-Reiter `Monsterkarten`, `Zauberkarten`, `Fallenkarten`
- je ein sichtbarer Reiter pro Deck
- private Sicherung `justincard-cloud-backup-v125.json` im Drive-`appDataFolder`
- Schema `justincard-google-drive-backup-v4`
- Kartenidentität aus Passcode, Set-Code, Seltenheit, Sprache und Artwork-URL

Die Android-Einrichtung ist in `android/docs/GOOGLE_SHEETS_SETUP.md` beschrieben.

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
android/    Android-13.0.8-Quellprojekt
windows/    Windows-1.3.2-Quellprojekt
shared/     gemeinsamer Cloud-Datenvertrag
tools/      gemeinsame Regressionstests
.github/    paralleler Android-/Windows-Build
```
