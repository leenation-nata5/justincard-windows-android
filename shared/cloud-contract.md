# Just InCard Cross-Platform Cloud Contract

Windows 1.2.7 and Android 13.0.1 deliberately use the same Google data contract.

- Windows OAuth scopes: `drive.file`, `drive.appdata`
- Android OAuth scopes: `spreadsheets`, `drive.file`, `drive.appdata`, `drive.metadata.readonly`
- Spreadsheet title: `Just InCard – Sammlung`
- Spreadsheet app property: `justincard_cloud_type=collection-template-v1`
- Visible template sheets: `Monsterkarten`, `Zauberkarten`, `Fallenkarten`
- Monster headers: `Sterne | Name | Typ | Element | Kategorie | Set-Code`
- Spell/Trap headers: `Kategorie | Name | Set-Code`
- Tuner/Empfänger is written as `Empfänger` in the Monsterkarten `Kategorie` column.
- Lossless device backup schema: `justincard-google-drive-backup-v4`
- AppData backup file: `justincard-cloud-backup-v125.json`
- Collection identity: `card id | print code | rarity | language | artwork URL`
- Each deck gets its own visible tab named after the deck. Program order is preserved; Main/Extra/Side are separated by section rows.

The browser-visible spreadsheet intentionally follows the user-supplied XLSX template only. Fields needed for lossless restore (rarity, language, quantity, condition, artwork, note, full card JSON and deck metadata) live in the private Drive `appDataFolder` JSON backup instead.
