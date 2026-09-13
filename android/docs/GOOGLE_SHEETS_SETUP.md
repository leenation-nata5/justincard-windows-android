# Google-Synchronisation einrichten

Die Google-Anbindung ist optional. Suche, Sammlung, Livebild, Decks, lokale Backups und CSV funktionieren weiterhin ohne Google-Konfiguration.

## Wichtig zu Status 8 / INTERNAL_ERROR

Die Windows-Anmeldung und die Android-Anmeldung dürfen im selben Google-Cloud-Projekt liegen, verwenden aber unterschiedliche OAuth-Clienttypen. Das ist eine Vorgabe von Google und keine frei austauschbare App-Einstellung.

- **Windows 1.3.3:** OAuth-Client vom Typ **Desktop-App** und die heruntergeladene `client_secret_....json`.
- **Android 13.0.9:** OAuth-Client vom Typ **Android**. Hier wird keine Desktop-Client-JSON in die APK eingebaut. Google identifiziert die App über **Paketname + SHA-1 der Signatur**.

Die bereitgestellte Desktop-JSON ist daher für Windows korrekt, behebt aber eine Android-Autorisierung mit Status 8 nicht.

## 1. Google-Cloud-Projekt vorbereiten

1. Dasselbe Google-Cloud-Projekt wie für Windows verwenden.
2. **Google Drive API** und **Google Sheets API** aktivieren.
3. Den OAuth-Zustimmungsbildschirm konfigurieren.
4. Solange die App im Testmodus ist, jedes verwendete Google-Konto als Testnutzer eintragen.

## 2. Android-OAuth-Clients anlegen

Unter **Google Cloud Console → Google Auth Platform / APIs & Dienste → Clients → Client erstellen** den Typ **Android** auswählen.

| Build | Paketname | SHA-1 |
|---|---|---|
| GitHub CI-Release aus diesem Repository | `org.yugioh.kartenliste.yugiohkartenliste.ci` | `67:AF:0E:5D:FD:32:27:03:EB:15:43:E8:19:2B:BE:90:05:6A:F8:6C` |
| Produktions-Release | `org.yugioh.kartenliste.yugiohkartenliste` | SHA-1 des privaten Produktions-Keystores |
| Lokaler Debug-Build | `org.yugioh.kartenliste.yugiohkartenliste.debug` | SHA-1 des lokalen Debug-Keystores |

**Für den Build aus dem Screenshot mit `.ci`-Paket ist der erste Eintrag entscheidend.** Wenn genau dieser Android-OAuth-Client fehlt, kann die Kontoauswahl erscheinen und danach trotzdem mit Status 8 oder Status 10 abbrechen.

Eigene Signatur anzeigen:

```bash
keytool -list -v -keystore /pfad/zu/justincard-release.jks -alias DEIN_ALIAS
```

Der GitHub-Workflow schreibt die verwendeten Fingerabdrücke zusätzlich in das Log-Artefakt `oauth-signing-fingerprint.txt`.

## 3. Produktionssignierung in GitHub

Für einen echten Produktionsbuild ohne `.ci`-Suffix werden diese Repository-Secrets unterstützt:

- `JIC_KEYSTORE_BASE64`
- `JIC_KEYSTORE_PASSWORD`
- `JIC_KEY_ALIAS`
- `JIC_KEY_PASSWORD`

Die bisherigen gleichnamigen `ANDROID_…`-Secrets bleiben kompatibel. Ohne diese Secrets erstellt GitHub den installierbaren CI-Release mit `.ci`-Paket und der oben angegebenen öffentlichen CI-Testsignatur.

## 4. Windows-OAuth im selben Projekt

Für Windows wird weiterhin der fest integrierte OAuth-Client vom Typ **Desktop-App** verwendet. Die JSON-Datei liegt unter `windows/assets/google_oauth_client.json` und wird beim GitHub-Build nur geprüft, nicht mehr durch Secrets ersetzt. Diese Datei ist **nicht** der Android-OAuth-Client.

## 5. In Android verbinden

1. **Einstellungen → Gemeinsame Google-Tabelle → Google-Konto verbinden** öffnen.
2. Konto auswählen und die Google-Freigabe bestätigen.
3. Eine gefundene Tabelle antippen, eine neue Just-InCard-Tabelle erstellen oder eine Google-Sheets-URL/ID einfügen.
4. Danach eine Aktion wählen:
   - **Cloud speichern**: lokalen Stand zu Google übertragen.
   - **Cloud laden**: Cloud-Daten lokal zusammenführen.
   - **Jetzt synchronisieren**: beide Stände zusammenführen und anschließend lokal sowie in Google speichern.
5. Unter Windows dieselbe Google-Sheets-URL wählen.

Die sichtbare Tabelle behält die Reiter `Monsterkarten`, `Zauberkarten`, `Fallenkarten` und je einen Reiter pro Deck. In jedem Deck-Reiter ist die Reihenfolge plattformübergreifend `Monster → Zauber → Fallen → Extra Deck → Side Deck`. Vollständige Felder liegen verlustfrei im privaten Drive-`appDataFolder`-Backup `justincard-cloud-backup-v125.json`. Dieses Format ist identisch zu Windows 1.3.3.

## Angeforderte OAuth-Scopes

Windows 1.3.3 bleibt unverändert bei:

- `https://www.googleapis.com/auth/drive.file`
- `https://www.googleapis.com/auth/drive.appdata`

Android 13.0.9 fordert zusätzlich an:

- `https://www.googleapis.com/auth/spreadsheets`

Der zusätzliche Android-Scope ist absichtlich eingebaut: Er erlaubt der Sheets API das vollständige Lesen und Bearbeiten einer bereits vorhandenen gemeinsamen Tabelle, während `drive.file` weiterhin nur den dateibezogenen Drive-Zugriff und `drive.appdata` das private Just-InCard-Backup abdecken. Der breite `https://www.googleapis.com/auth/drive`-Scope wird weiterhin nicht verlangt.

**Nach dem Update:** Das Google-Konto in Just InCard einmal erneut verbinden und die neue Tabellen-Berechtigung bestätigen. Falls Google Auth Platform im Testmodus läuft, muss das verwendete Konto weiterhin als Testnutzer eingetragen sein. Unter Google Auth Platform → Datenzugriff sollte der `spreadsheets`-Scope ebenfalls aufgeführt sein.

## Wenn weiterhin Status 8 erscheint

1. Prüfen, ob **genau der installierte Paketname** als Android-OAuth-Client existiert.
2. Prüfen, ob dessen **SHA-1 exakt zur installierten APK** gehört.
3. Bei `.ci`-Builds nicht versehentlich nur den Produktions-Client ohne `.ci` anlegen.
4. Google Play-Dienste auf dem Gerät aktualisieren.
5. Falls der OAuth-Zustimmungsbildschirm im Testmodus ist: verwendetes Konto als Testnutzer eintragen.
6. Google Drive API und Google Sheets API im selben Cloud-Projekt aktivieren.

Android 13.0.9 startet die Autorisierung zuerst ohne erzwungenen Account-Picker. Falls Google Play-Dienste trotzdem Status 8 liefern, wird genau einmal mit expliziter Kontoauswahl wiederholt. Bleibt Status 8 bestehen, ist die serverseitige Android-OAuth-Registrierung (Paketname + SHA-1) zu prüfen. Paketname und SHA-1 werden direkt in der Fehlermeldung angezeigt.
