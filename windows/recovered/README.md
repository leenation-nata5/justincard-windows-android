# Recovery-Basis

Die vom Nutzer bereitgestellte Windows-Version 1.0.3 enthielt **keinen ursprünglichen Python-Quellcode**, sondern nur eine bereits mit PyInstaller gebaute EXE.

`PYZ.pyz` ist der aus dieser EXE extrahierte Python-3.11-Modulcontainer. Der Build erzeugt daraus nur die unveränderten Legacy-Module als `.pyc`.

Offen und editierbar sind die seitdem überarbeiteten Bereiche, insbesondere:

- `justincard/search_core.py`
- `justincard/ui/search_page.py`
- `justincard/ui/toast.py`
- `justincard/v108_core.py`
- `justincard/v108_features.py`
- `justincard/version.py`

Version 1.0.8 legt die neuen Sammlungs-/Deck-/Anzeige-/Backup-Funktionen als Kompatibilitätslayer über die unveränderten Legacy-Klassen. Dadurch bleibt die bisherige Funktionalität erhalten, während die neuen Bereiche wartbar im Quellcode liegen.

`tools/materialize_recovered_modules.py` prüft die Python-Version und erzeugt die unveränderten Module für den Build.
