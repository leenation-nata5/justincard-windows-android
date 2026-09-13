JUST INCARD WEBSPACE v1.0.0
============================

Diese Version ist für klassisches IONOS Webhosting ausgelegt.
Technik: PHP 8.x + MariaDB + HTML/CSS/JavaScript.

ENTHALTEN
---------
- responsive Just-InCard-Webseite
- Registrierung, Login und Logout
- Passwort-Hashing mit PHP password_hash()
- Benutzer-Dashboard und Kontoverwaltung
- REST-API für spätere Windows-/Android-Anbindung
- API-Tokens pro Gerät
- Sammlung und Decks serverseitig speichern
- KEINE Kartenbilder auf dem Server
- MariaDB-Schema
- Browser-Installationsassistent

IONOS INSTALLATION
------------------
1. In IONOS unter Hosting -> Datenbanken eine MariaDB-Datenbank anlegen.
2. Datenbank-Host, Datenbankname, Benutzer und Passwort notieren.
3. Den kompletten Inhalt des Ordners JustInCard-Webspace-v1.0.0 in das Zielverzeichnis deiner Domain hochladen.
4. In IONOS PHP 8.2 oder neuer einstellen.
5. HTTPS/SSL für die Domain aktivieren.
6. Im Browser öffnen: https://DEINE-DOMAIN.de/install/
7. Die MariaDB-Daten eintragen und Installation ausführen.
8. Danach https://DEINE-DOMAIN.de/register.php öffnen und das erste Konto erstellen.

WICHTIG
-------
- config/local.php wird beim Installer erzeugt und enthält das Datenbankpasswort. Niemals teilen.
- Die .htaccess-Dateien sperren sensible Ordner gegen Browserzugriff.
- Datenschutz und Impressum sind Platzhalter und müssen vor öffentlicher Veröffentlichung angepasst werden.
- Die aktuelle Windows-/Android-App ist mit dieser API noch nicht verdrahtet. Die API ist dafür vorbereitet.

API KURZÜBERSICHT
-----------------
GET  /api/v1/health.php
POST /api/v1/register.php
POST /api/v1/login.php
GET  /api/v1/me.php
POST /api/v1/logout.php
GET/POST /api/v1/collection.php
GET/POST /api/v1/decks.php

Nach Login wird ein Bearer-Token zurückgegeben:
Authorization: Bearer DEIN_TOKEN

Beispiel Login JSON:
{"identity":"name@example.de","password":"DEIN_PASSWORT","device_name":"Windows-PC"}

Beispiel Sammlung:
{"items":[{"sync_id":"uuid","card_id":"46986414","card_name":"Dark Magician","set_code":"LCO1-DE005","rarity":"Ultra Rare","language_code":"de","card_condition":"Near Mint","quantity":2}]}

Beispiel Deck:
{"decks":[{"sync_id":"deck-uuid","name":"Dark Magician","cards":[{"sync_id":"card-uuid","card_id":"46986414","card_name":"Dark Magician","set_code":"LCO1-DE005","quantity":2,"section":"MAIN","sort_order":1}]}]}

UPDATE AUF 1.1.0 / APP-KONTO-SYNC
--------------------------------
Wenn 1.0.0 bereits installiert ist, können die Dateien von 1.1.0 über die alten
Webdateien kopiert werden. config/local.php wird in dieser ZIP weiterhin NICHT
mitgeliefert und dadurch nicht überschrieben. Der vorhandene Account bleibt
bestehen.

Neu ist:
  GET  /api/v1/sync.php
  POST /api/v1/sync.php

Der Endpunkt legt die neue Tabelle account_sync_payloads beim ersten Aufruf
selbst an. Ein erneuter Aufruf des Installers ist für bestehende Installationen
nicht erforderlich.

DASHBOARD NACH APP-SYNC
-----------------------
Ab 1.1.0 liest das Dashboard bevorzugt den gemeinsamen Account-Snapshot. Dadurch
werden die von Windows 1.3.2 bzw. Android 13.0.8 synchronisierten Sammlungs- und
Deckzahlen auch auf der Webseite angezeigt. Kartenbilder bleiben weiterhin auf
den Endgeräten und werden nicht in diesem Snapshot gespeichert.
