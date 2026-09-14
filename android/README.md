# Just InCard Android 13.0.11

## Neu in 13.0.11

### Deckbau

- feste Karten-/Effektvorschau im Deckbereich
- Vorschau sowohl für Karten im Deck als auch für Karten aus der Sammlungsauswahl
- nicht mehr verfügbare Sammlungskarten werden ausgegraut
- **Nicht verfügbare Karten ausblenden** blendet vollständig verbrauchte Drucke aus
- Verfügbarkeit berücksichtigt den konkreten Set-Code/Druck und zusätzlich das Yu-Gi-Oh!-Limit von maximal drei Exemplaren einer Karte

### Just-InCard-Konto

Der normale Account-Sync behält seinen Schutz vor versehentlichem Löschen eines gefüllten Serverstands.

Zusätzlich gibt es in den Einstellungen die bestätigungspflichtige Aktion:

**Sammlung + Decks vollständig hochladen**

Damit wird der lokale Stand absichtlich als vollständiger Serverstand gespeichert. Lokal entfernte Sammlungseinträge oder Decks werden damit auch serverseitig entfernt.

## Weiterhin enthalten

- Wahl zwischen lokalem Modus und Just-InCard-Konto
- Livebild/Scanner
- Suche und Sammlung
- Google-Sheets-/Drive-Synchronisation
- lokale Backups/CSV
- appweite Kartentext-Sprache
- Offline-Arbeitskopie auf dem Gerät

## GitHub-Build

Der enthaltene Workflow `.github/workflows/build-android.yml` erstellt die Android-Artefakte. Version: `13.0.11`, VersionCode: `13010`.
