# Just InCard – Windows 1.3.6 / Android 13.0.11

Gemeinsames GitHub-Projekt für die Windows- und Android-Version von Just InCard.

## Windows 1.3.6

- fester Vorschauplatz im linken Bereich des Deckbauers
- Vorschau für Sammlungskarten und bereits im Deck befindliche Karten
- Bild, Kartenname, Setdaten und Effekt-/Beschreibungstext in derselben Vorschau
- vollständig verbrauchte Sammlungskarten werden im Deckbau ausgegraut
- nicht verfügbare Karten können ausgeblendet werden
- expliziter manueller Voll-Upload von Sammlung + Decks zum Just-InCard-Account
- normaler Account-Sync bleibt gegen versehentliches Löschen geschützt
- lokale Nutzung, IONOS-Account, Google Sheets und lokale Backups bleiben parallel nutzbar

## Android 13.0.11

- feste Deckbau-Vorschau mit Bild und lokalisiertem Effekttext
- Vorschau aus Deckliste und Sammlungsauswahl
- ausgegraute/versteckbare nicht verfügbare Sammlungskarten
- Verfügbarkeit nach konkretem Kartendruck/Set-Code plus Drei-Kopien-Regel
- expliziter manueller Voll-Upload von Sammlung + Decks zum Just-InCard-Account
- normaler Account-Sync bleibt gegen unbeabsichtigtes Leeren geschützt
- Livebild, Scanner, Suche, Sammlung, Decks, Google-Synchronisierung und lokaler Modus bleiben erhalten

## Projektstruktur

```text
android/    Android-13.0.11-Quellprojekt
windows/    Windows-1.3.6-Quellprojekt
tools/      gemeinsame Repository-Prüfungen
.github/    GitHub-Actions-Workflows
```

Der IONOS-Webspace wird getrennt ausgeliefert und ist nicht Bestandteil dieses ZIPs.
