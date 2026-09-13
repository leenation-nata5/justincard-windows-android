# Just InCard – Android 13.0.10 und Windows 1.3.5

Dieses gemeinsame GitHub-Repository enthält ausschließlich die beiden Programme:

- **Android 13.0.10** – native Kotlin-/Compose-Version mit Livebild, Scanner, Sammlung, Decks, Google-Synchronisierung und Just-InCard-Konto.
- **Windows 1.3.5** – Desktop-Version mit Suche, Galerie-Scanner, Sammlung, Decks, Google-Synchronisierung und Just-InCard-Konto.

Der IONOS-Webspace wird ab dieser Version **nicht mehr in diesem ZIP mitgeführt**. Er wird als separates Webspace-ZIP ausgeliefert, damit App-Quellcode und Server-Dateien unabhängig aktualisiert werden können.
Für den neuen Fail-Safe wird **Just InCard Webspace 1.2.1** empfohlen; dort blockiert `sync.php` zusätzlich leere destruktive Snapshots und archiviert die vorherige Serverrevision.

## Konto-Sync Hotfix 1.3.5 / 13.0.10

Der IONOS-Kontoabgleich ist jetzt fail-safe: Ein Gerät darf erst hochladen, nachdem der vorhandene Serverstand vollständig in Sammlung und Decks übernommen und lokal wieder verifiziert wurde. Ein fehlender lokaler Datensatz wird nicht mehr automatisch als Löschung interpretiert. Dadurch kann ein fehlerhafter/leer gebliebener lokaler Import den Serverstand nicht mehr leeren.


## Windows 1.3.5 – Kontoanmeldung ohne Browser

Die Anmeldung am Just-InCard-Konto erfolgt vollständig im Windows-Programm. Der Nutzer gibt Benutzername/E-Mail und Passwort in den integrierten Dialog ein. Windows sendet die Anmeldung direkt per HTTPS an `https://justincard.de/api/v1/login.php`; beim Anmelden wird **kein Chrome-, Edge- oder anderes Browserfenster geöffnet**.

Nach erfolgreichem Login wird weiterhin zuerst der vorhandene IONOS-Kontostand geladen. Erst danach darf ein normaler Abgleich stattfinden. Sammlung und Decks bleiben zusätzlich lokal auf dem jeweiligen Gerät verfügbar.

Die Kontoerstellung bleibt auf der Webseite möglich, wird von Windows jedoch nicht automatisch geöffnet.

## Android 13.0.10

Android 13.0.10 erhält denselben Fail-Safe wie Windows: Nach Login wird der Serverstand zuerst lokal geladen und geprüft; erst danach darf ein Upload erfolgen. Bei fehlgeschlagenem Restore bleibt der Serverstand unangetastet.

## GitHub Actions

`.github/workflows/build-all.yml` validiert das gemeinsame Repository und baut Android und Windows getrennt:

- Android: Unit-Tests, Lint, Debug-/CI-Release-APK und AAB, optional produktive Signierung.
- Windows: Python-Tests, Portable-ZIP und Installer.

## Struktur

```text
android/    Android-13.0.10-Quellprojekt
windows/    Windows-1.3.5-Quellprojekt
shared/     gemeinsamer Cloud-/Account-Datenvertrag
tools/      plattformübergreifende Repository-Prüfungen
.github/    gemeinsamer Android-/Windows-Build
```

Der passende IONOS-Webspace wird separat bereitgestellt.
