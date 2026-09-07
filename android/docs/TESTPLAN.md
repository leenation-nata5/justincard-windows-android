# Testplan

## Automatisch bei Pull Request und Push

- JVM-Unit-Tests für Set-Code-Normalisierung, OCR-Signale und den Windows-kompatiblen Cloud-Roundtrip
- kombinierte SQL-Filtererzeugung
- CSV-, JSON-, Google-Sheets- und YDK-Roundtrips
- Android Lint für Debug
- Debug-APK-Build
- optimierter CI-Release als APK und AAB bei Läufen ohne Produktions-Secrets
- Signaturprüfung der erzeugten APK und Kontrolle der AAB-JAR-Signatur
- statische Projekt-/Manifest-/Workflow-Prüfung über `scripts/preflight.sh`

## Vor einem Release auf echten Geräten

Mindestens testen:

- kleines Telefon, 360 dp Breite
- großes Telefon, Querformat
- Tablet/Foldable ab 700 dp Breite
- Android 7 als Mindestversion und aktuelle Android-Version
- Light-, Dark- und System-Theme; große Systemschrift
- Suche mit jedem Filter einzeln sowie mindestens fünf Filtern gleichzeitig
- 200+ Treffer schnell vor/zurück scrollen; Flugmodus danach erneut öffnen (Bildcache)
- Live-OCR bei guter/schwacher Beleuchtung; Set-Code, Passcode-Fallback und falscher Treffer
- direkte Kameraaufnahme, ein Galeriebild und 20 Galeriebilder als Stapel
- Sammlung: gleicher Kartenname aus zwei Sets; getrennte Mengen und Set-Anzeige
- JSON-Backup exportieren, App-Daten leeren, Backup importieren
- CSV mit Komma, Anführungszeichen und Zeilenumbruch in Notizen
- dieselbe Google-Tabelle unter Windows und Android verbinden
- Cloud speichern, App-Daten auf einem zweiten Gerät leeren und Cloud laden
- parallele Änderung unter Windows/Android und anschließend beidseitig synchronisieren
- Sammlungsmengen, Zustände, Notizen sowie Main-/Extra-/Side-Decks nach dem Roundtrip vergleichen
- Deck-Reiter: Karte aus der Sammlung hinzufügen, Dialog schließen und gespeicherte Karte/Menge prüfen

## Signierter Release

- CI-Release nur als getrennte Test-App mit `.ci`-Paket-ID verwenden
- `apksigner verify --verbose --print-certs app-release.apk`
- Upgrade von der bisherigen Release-App mit gleicher Application-ID und Signatur
- APK auf mindestens einem ARM64-Gerät installieren
- AAB mit `bundletool` prüfen oder internen Play-Test verwenden
