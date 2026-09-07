# Google-Synchronisation einrichten

Die Google-Anbindung ist optional. Suche, Sammlung, Livebild, Decks, lokale Backups und CSV funktionieren weiterhin ohne Google-Konfiguration.

## 1. Google-Cloud-Projekt vorbereiten

1. In der Google Cloud Console ein Projekt auswählen oder erstellen.
2. **Google Drive API** und **Google Sheets API** aktivieren.
3. Den OAuth-Zustimmungsbildschirm konfigurieren. Solange die App im Testmodus ist, alle verwendeten Google-Konten als Testnutzer eintragen.
4. Für Windows und Android dasselbe Cloud-Projekt verwenden. Dadurch können beide Apps dieselbe Tabelle und dasselbe Cloudformat nutzen.

## 2. Android-OAuth-Clients anlegen

Unter **APIs & Dienste → Anmeldedaten → Anmeldedaten erstellen → OAuth-Client-ID** jeweils den Typ **Android** wählen. Android benötigt keine heruntergeladene Client-JSON und kein Client-Secret im Projekt.

| Build | Paketname | Zertifikat |
|---|---|---|
| Produktion | `org.yugioh.kartenliste.yugiohkartenliste` | SHA-1 des privaten Release-Keystores |
| CI-Release | `org.yugioh.kartenliste.yugiohkartenliste.ci` | `67:AF:0E:5D:FD:32:27:03:EB:15:43:E8:19:2B:BE:90:05:6A:F8:6C` |
| Lokal Debug | `org.yugioh.kartenliste.yugiohkartenliste.debug` | SHA-1 des lokalen Debug-Keystores |

Fingerabdruck eines eigenen Schlüssels anzeigen:

```bash
keytool -list -v -keystore /pfad/zu/justincard-release.jks -alias DEIN_ALIAS
```

Für produktive GitHub-Builds werden diese Secrets unterstützt:

- `JIC_KEYSTORE_BASE64`
- `JIC_KEYSTORE_PASSWORD`
- `JIC_KEY_ALIAS`
- `JIC_KEY_PASSWORD`

Die bisherigen gleichnamigen `ANDROID_…`-Secrets bleiben im gemeinsamen Workflow ebenfalls kompatibel. Der mitgelieferte CI-Schlüssel ist ausschließlich eine öffentliche Testsignatur und darf nicht für Play-Store- oder Produktionsupdates verwendet werden.

## 3. Windows-OAuth im selben Projekt

Für Windows zusätzlich eine OAuth-Client-ID vom Typ **Desktop-App** erstellen. Die heruntergeladene JSON-Datei kann in der Windows-App ausgewählt oder im GitHub-Build über `GOOGLE_OAUTH_CLIENT_JSON_B64` eingebettet werden.

## 4. In Android verbinden

1. **Einstellungen → Gemeinsame Google-Tabelle → Google-Konto verbinden** öffnen und den Zugriff bestätigen.
2. Eine gefundene Tabelle antippen, eine neue Just-InCard-Tabelle erstellen oder eine Google-Sheets-URL/ID einfügen.
3. Danach eine der klar getrennten Aktionen verwenden:
   - **Cloud speichern**: lokalen Stand zu Google übertragen.
   - **Cloud laden**: Cloud-Daten lokal zusammenführen.
   - **Jetzt synchronisieren**: beide Stände zusammenführen und anschließend lokal sowie in Google speichern.
4. Unter Windows dieselbe Google-Sheets-URL wählen.

Die sichtbare Tabelle behält die Reiter `Monsterkarten`, `Zauberkarten`, `Fallenkarten` und je einen Reiter pro Deck. Vollständige Felder wie Druck, Seltenheit, Sprache, Zustand, Menge, Notizen und Deck-Metadaten liegen verlustfrei im privaten Drive-`appDataFolder`-Backup `justincard-cloud-backup-v125.json`. Dieses Format ist identisch zu Windows 1.2.7.

## Angeforderte OAuth-Scopes

- `https://www.googleapis.com/auth/spreadsheets`
- `https://www.googleapis.com/auth/drive.file`
- `https://www.googleapis.com/auth/drive.appdata`
- `https://www.googleapis.com/auth/drive.metadata.readonly`

Das kurzlebige Google-Zugriffstoken wird nur im Arbeitsspeicher gehalten und nicht dauerhaft in der App gespeichert.

