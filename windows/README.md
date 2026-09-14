# Just InCard – Windows Desktop 1.3.6

## Neu in 1.3.6

### Deckbau

- Die linke Deckauswahl ist kompakter.
- Direkt unter der Deckauswahl befindet sich ein fester Bereich **Kartenvorschau**.
- Dieselbe Vorschau wird verwendet, egal ob du eine Karte aus der Sammlung oder eine bereits im Deck befindliche Karte auswählst.
- Angezeigt werden Kartenbild, Name, Set-/Druckinformationen und lokalisierter Effekt-/Beschreibungstext.
- Die alte zusätzliche Vorschau unter der Sammlung wird ausgeblendet, damit nicht mehrere unterschiedliche Karten gleichzeitig angezeigt werden.
- Sammlungskarten werden ausgegraut, sobald ihre verfügbaren Exemplare im aktuellen Deck vollständig verbraucht sind.
- Über **Nicht verfügbare Karten ausblenden** können diese Zeilen vollständig verborgen werden.

### Just-InCard-Konto

Der normale Account-Sync bleibt absichtlich konservativ: Ein fehlerhaft leer geladener lokaler Stand darf weiterhin keine gefüllte Serverdatenbank löschen.

Zusätzlich gibt es in den Einstellungen jetzt die ausdrücklich destruktive Aktion:

**Sammlung + Decks vollständig hochladen**

Nach einer Sicherheitsabfrage wird der aktuelle lokale Stand als allein gültiger Serverstand gespeichert. Karten oder Decks, die lokal nicht mehr vorhanden sind, werden damit auch auf dem Server entfernt. Der Webspace archiviert die vorherige Serverrevision als Sicherung.

Die Just-InCard-Kontoanmeldung bleibt vollständig innerhalb des Windows-Programms und öffnet keinen Browser. Google-OAuth kann separat weiterhin einen Browser verwenden.

## Weiterhin enthalten

- lokale/offline Nutzung ohne Konto
- IONOS-Account-Synchronisation
- Google-Sheets-Synchronisation und privates Drive-Backup
- lokale Backups
- detaillierte Suche und Scanner/Galerie-Funktionen
- appweite Kartentext-Sprache
- Sammlungs- und Decksortierungen

## GitHub Actions

Workflow: `.github/workflows/build-windows.yml`

Der Workflow verwendet Python 3.11, materialisiert die unveränderten Legacy-Module aus `recovered/PYZ.pyz`, führt Tests und Repository-Prüfungen aus und erstellt anschließend Portable-ZIP und Installer.

Für einen Release-Tag kann z. B. `v1.3.6` verwendet werden.
