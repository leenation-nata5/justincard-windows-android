# Just InCard – Windows Desktop 1.3.4

## Windows 1.3.4 – In-App-Kontoanmeldung ohne Browser

### Änderung 1.3.4

- Die Anmeldung am Just-InCard-/IONOS-Konto erfolgt vollständig innerhalb des Windows-Programms.
- Beim Klick auf **Anmelden** wird kein Chrome-, Edge- oder anderes Browserfenster geöffnet.
- Der Login-Dialog enthält nur Benutzername/E-Mail, Passwort, Abbrechen und Anmelden.
- Die Kontoerstellung bleibt eine Funktion der Webseite; Windows öffnet sie nicht automatisch.
- Nach erfolgreichem Login wird weiterhin zuerst der vorhandene Serverstand geladen, bevor eine Synchronisierung stattfinden darf.

- Beim ersten Start Wahl zwischen **Nur lokal** und **Mit Just InCard Konto**.
- Konto-Login verwendet den bestehenden Account von `https://justincard.de/`.
- Sammlung und Decks werden über `https://justincard.de/api/v1/sync.php` synchronisiert.
- Kartenbilder bleiben auf Windows/Android; auf dem Server werden keine Bilddateien gespeichert.
- Account-Sync beim Start und optional alle fünf Minuten; manueller Abgleich in Einstellungen.
- Die bestehende lokale Datenbank bleibt immer die Offline-Arbeitskopie.
- Google Sheets und lokale Backups bleiben zusätzlich verfügbar.


- Suchdetail: Die Mengenwahl sitzt jetzt direkt vor „Zur Sammlung hinzufügen“ in derselben Zeile und nicht mehr am unteren Rand der Detailansicht.
- Sammlungsvorschau: Das Kartenbild wird dynamisch an den tatsächlich verfügbaren Bereich angepasst und immer vollständig mit beibehaltenem Seitenverhältnis dargestellt.
- Deckbau mit Kartenbild-/Detailvorschau vor dem Hinzufügen.
- Appweite Kartentext-Sprache in den Einstellungen; Suche, Vorschauen, Sammlung und Deckbau verwenden dieselbe Auswahl.
- Sortierwechsel in Sammlung und Deckbau halten Auswahl und Vorschau synchron.
- Manueller Google-Upload und „Jetzt synchronisieren“ sind wieder sichtbar.
- Optionaler Dauerabgleich beim Start und anschließend alle fünf Minuten.

## Google-Sheets-Vorlage

Für die browserlesbare Google-Sheets-Datei wird **ausschließlich** die vom Nutzer bereitgestellte Datei `Yugioh Excel Beispiel(1).xlsx` verwendet. Die Originaldatei liegt unverändert unter `assets/google_sheets_template.xlsx` und wird bei der ersten Cloud-Erstellung direkt nach Google Sheets konvertiert.

Die sichtbare Sammlung enthält exakt diese drei Vorlagen-Reiter:

- **Monsterkarten**: `Sterne | Name | Typ | Element | Kategorie | Set-Code`
- **Zauberkarten**: `Kategorie | Name | Set-Code`
- **Fallenkarten**: `Kategorie | Name | Set-Code`

Es werden **keine** Effekttexte, Preise, Rarities, Zustände, Notizen, Passcodes, Artwork-URLs oder sonstige Zusatzspalten in die sichtbare Google-Sheets-Datei geschrieben. Da die Vorlage keine Mengen-Spalte besitzt, werden mehrere Exemplare als wiederholte Kartenzeilen dargestellt.

Tuner/Empfänger sind **kein eigener Reiter** mehr. Sie stehen im Reiter **Monsterkarten** in der Spalte **Kategorie** mit dem Wert `Empfänger`.

Vor jedem manuellen **Hochladen** und **Synchronisieren** erscheint weiterhin eine Sortierauswahl. Sortiert werden kann nach Name, Kartentyp, Passcode, Set-Code, Typ, Element, Kategorie oder Sterne, jeweils auf- oder absteigend. Der Passcode darf als Sortierkriterium verwendet werden, wird aber nicht als Spalte exportiert, weil er nicht Bestandteil der Vorlage ist.

Jedes gespeicherte Deck behält einen eigenen Reiter mit dem **Decknamen**. Der Reiter verwendet ausschließlich die sechs Spalten der Monsterkarten-Vorlage. Die Abschnitte stehen immer in der Reihenfolge **Monster → Zauber → Fallen → Extra Deck → Side Deck**. Die gewählte Google-Sortierung wirkt innerhalb des jeweiligen Abschnitts. Mengen werden auch dort durch wiederholte Kartenzeilen dargestellt.

### Verlustfreie Cloud-Sicherung trotz schlanker Vorlage

Die sichtbare Tabelle soll exakt die Vorlage bleiben. Für den Gerätewechsel speichert Just InCard die vollständigen Wiederherstellungsdaten deshalb **nicht** in versteckten Zusatz-Reitern, sondern getrennt im privaten Google-Drive-Bereich `appDataFolder`. Dieser Bereich ist nicht als normale Drive-Datei im Browser sichtbar, gehört aber zum jeweils angemeldeten Google-Konto. Dadurch kann ein zweites Gerät weiterhin Menge, Zustand, Alt Art, vollständige Kartendaten und Decks verlustfrei laden, ohne die Google-Sheets-Vorlage mit zusätzlichen Spalten oder versteckten Tabellen zu verändern.

## Google-Konto und mehrere Benutzer

Just InCard verwendet pro angemeldetem Google-Konto dessen eigene OAuth-Freigabe. Eine neu erstellte `Just InCard – Sammlung` gehört deshalb dem **jeweils angemeldeten Benutzer** und wird in dessen eigenem Google Drive angelegt. Mehrere Benutzer verwenden denselben Desktop-OAuth-Client der App, erhalten aber voneinander getrennte Google-Sheets-Dateien und getrennte private Backups.

Für die Veröffentlichung gibt es zwei sinnvolle Google-Konfigurationen:

- **Internal**: nur Benutzer derselben Google-Workspace-/Cloud-Identity-Organisation können die App autorisieren. Das eignet sich, wenn alle Benutzer zu deinem Unternehmen gehören.
- **External**: Benutzer mit normalen Google-Konten können die App autorisieren. Im Status **Testing** müssen sie als Testnutzer eingetragen werden; für eine breitere Verteilung sollte die App auf **In production** gestellt werden.

Seit 1.3.0 fordert Just InCard nur noch `drive.file` und `drive.appdata` an. Der frühere breite `spreadsheets`-Scope wird nicht mehr benötigt. Nach dem Update ist deshalb einmaliges erneutes Google-Anmelden erforderlich.

### Einmalige Google-Cloud-Einrichtung

1. In der Google Cloud Console ein Projekt anlegen oder auswählen.
2. **Google Sheets API** und **Google Drive API** aktivieren.
3. Unter Google Auth Platform die gewünschte Zielgruppe **Internal** oder **External** festlegen.
4. Der mitgelieferte OAuth-Client vom Typ **Desktop-App** liegt fest unter `assets/google_oauth_client.json` und wird beim Build unverändert eingebettet.
5. **Mit Google anmelden** anklicken.
6. **Sammlung + Decks aus Google laden**, **Sammlung + Decks hochladen** oder **Jetzt synchronisieren** verwenden dieselbe Just-InCard-Tabelle. Optional kann der Dauerabgleich aktiviert werden.

Die OAuth-Datei kann in der Windows-Oberfläche nicht ausgetauscht werden. Der GitHub-Workflow prüft lediglich, dass die fest eingebundene Datei vorhanden ist.

## Weitere Änderungen aus 1.2.x

- Mengenwahl in Suche und Scanner, Standardwert nach dem Hinzufügen wieder `1`.
- Keine Wunschlisten-/Tauschfunktion in der Sammlung.
- Geschätzter Sammlungswert statt erfasster Kaufwertsumme; Cardmarket-Referenzpreise werden über die öffentliche YGOPRODeck-API verwendet.
- Alt-Art-Unterstützung und getrennte Anzeigeprofile bleiben erhalten.
- Fusion-, Synchro-, Xyz- und Linkmonster werden beim Deckbau automatisch ins Extra Deck gelegt; nur Side Deck wird manuell gewählt.

## Bestehende Suchverbesserungen

Die Verbesserungen aus 1.0.7 bleiben vollständig enthalten:

- alle Suchfilter einzeln und kombiniert nutzbar
- alle lokal installierten Sprachen durchsuchbar
- Set-Code-Suchen verwenden immer die englische EN-Referenz (`BLMR-DE001` → Suche nach `BLMR-EN001`)
- die ursprünglich eingegebene Drucksprache wird beim Hinzufügen in die Sammlung wiederhergestellt
- Präfixsuche wie `CORI-DE` verwendet intern `CORI-EN`
- vollständige Suche wie `CORI-DE005` verwendet intern `CORI-EN005`
- der Sprachfilter wird nur bei Set-Code-Suchen von der EN-Referenz übersteuert; normale Namens-/Kartensuchen bleiben mehrsprachig
- exakte und partielle Passcode-Suche
- Enter und Numpad-Enter starten die Suche im gesamten Suchreiter

## GitHub Actions

Workflow: `.github/workflows/build-windows.yml`

Der Workflow läuft auf `windows-latest` mit **Python 3.11** und erledigt automatisch:

1. Python-Abhängigkeiten installieren
2. Tesseract OCR und Inno Setup installieren
3. unveränderte Legacy-Module aus `recovered/PYZ.pyz` materialisieren
4. Such-, Build- und v1.0.8–1.3.4-Regressionsprüfungen ausführen
5. Vorab-Importdiagnose ausführen und protokollieren
6. Windows-App mit PyInstaller als `onedir` bauen
7. die erzeugte `JustInCard.exe --self-test` ausführen
8. portable ZIP erzeugen
9. Windows-Installer erzeugen
10. SHA-256-Prüfsummen erzeugen
11. Build-Dateien und Logs separat als Artifacts hochladen
12. bei einem Tag wie `v1.3.4` zusätzlich einen GitHub Release erstellen

### Build auf GitHub starten

1. Repository auf GitHub erstellen bzw. den bisherigen Inhalt ersetzen.
2. **Den kompletten Inhalt dieses Ordners inklusive `.github` hochladen.**
3. Auf GitHub `Actions` öffnen.
4. `Build Windows Desktop` auswählen.
5. `Run workflow` anklicken.
6. Nach erfolgreichem Build unter `Artifacts` herunterladen:
   - `JustInCard-Windows-<RunNumber>` – portable ZIP + Installer
   - `JustInCard-Windows-Logs-<RunNumber>` – komplette Build-Logs

## Lokaler Windows-Build

Benötigt:

- Windows 10/11 x64
- Python 3.11 x64
- Tesseract OCR unter `C:\Program Files\Tesseract-OCR`
- optional Inno Setup 6 für den Installer

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -r requirements-build.txt
.\scripts\build_windows.ps1
.\scripts\build_installer.ps1
```

## Projektstruktur

```text
.github/workflows/build-windows.yml    GitHub-Actions-Build
assets/                                App-Icon, Logo, Navigation-Icons
installer/JustInCard.iss               Inno-Setup-Konfiguration
justincard/search_core.py              Filter-/Sprach-Suchlogik
justincard/ui/search_page.py           Suche, Enter-Workflow, Toast/Autofokus
justincard/ui/toast.py                 zentrale temporäre Meldungen
justincard/v108_core.py                Anzeige-, Sortier- und Backup-Normalisierung
justincard/v108_features.py            v1.0.8 UI-/DB-Kompatibilitätslayer
justincard/v111_core.py                getrennte Anzeigeprofile je Bereich
justincard/v111_features.py            Anzeigeprofile und Preisoberfläche
justincard/v110_core.py                Alt-Art-Hilfslogik
justincard/v110_features.py            Alt-Art-UI-Patches
justincard/price_service.py             Preisermittlung / Sprach- und Zustandslogik
justincard/cloud_sync.py                Google OAuth/Sheets/Drive Cloud-Kern
justincard/v120_features.py             Cloud-Einstellungen, Geräteabgleich, Auto-Sync
justincard/v121_core.py                 sichere Mengenvalidierung beim Hinzufügen
justincard/v121_features.py             Scanner-Mengenwahl und Reset auf 1
justincard/v123_core.py                 Deck-Zonen- und Google-Kategorienlogik
justincard/v123_features.py             Automatische Main-/Extra-Deck-UI
justincard/v130_features.py             Deckvorschau, globale Kartensprache, Sortier-/Dauer-Sync-Patches
justincard/account_sync.py               IONOS-Account-API und geräteübergreifender Snapshot-Abgleich
justincard/v132_features.py              Kontoauswahl, Login-UI und automatischer Account-Sync
assets/google_oauth_client.example.json OAuth-Desktop-Beispielkonfiguration
justincard/version.py                  Version 1.3.4
recovered/PYZ.pyz                      Recovery-Basis unveränderter Legacy-Module
scripts/build_windows.ps1              PyInstaller/Portable-Build
scripts/build_installer.ps1            Installer-Build
tests/test_search_core.py              Filter-/Sprachtests
tests/test_v108_core.py                v1.0.8–1.0.10-Regressionsprüfungen
tests/test_v111_core.py                Anzeigeprofil-Regressionsprüfungen
tests/test_price_service.py             Preislogik-Regressionsprüfungen
tests/test_cloud_sync.py                Google-Sheets-/Merge-Regressionsprüfungen
tools/materialize_recovered_modules.py Recovery-Builder
tools/smoke_imports.py                 Kompatibilitätsprüfung
JustInCard.spec                         PyInstaller-Spezifikation
```

## Hinweis zur Recovery-Basis

Der ursprüngliche Windows-Upload 1.0.3 enthielt die bereits kompilierte portable Anwendung und den Installer, aber nicht das ursprüngliche Python-Repository. Die unveränderten Altmodule werden deshalb weiterhin reproduzierbar aus dem extrahierten Python-3.11-PYZ wiederhergestellt. Die Suchverbesserungen sowie die UI-/Backup-Erweiterungen ab 1.0.8 und die neueren Anzeige-, Preis-, Alt-Art- und Google-Cloud-Funktionen bis 1.3.4 liegen offen und editierbar im Repository.