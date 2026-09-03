# Just InCard Android 14.1.1

Native Kotlin/Jetpack-Compose source rebuild of the supplied Android release.

## Important Google OAuth setup

The app uses the Android OAuth client registered for:

- package: `org.yugioh.kartenliste.yugiohkartenliste`
- signing SHA-1: your production certificate

For CI/testing create a second Android OAuth client for package
`org.yugioh.kartenliste.yugiohkartenliste.ci`. The repository test key SHA-1 is:

`67:AF:0E:5D:FD:32:27:03:EB:15:43:E8:19:2B:BE:90:05:6A:F8:6C`

Register the Android OAuth client in the **same Google Cloud project as the Windows Desktop OAuth client**. Drive API and Sheets API must both be enabled.

## Cloud compatibility

Android reads/writes the same:

- `Just InCard – Sammlung` spreadsheet
- template XLSX
- `drive.file` / `drive.appdata` scopes
- `justincard-cloud-backup-v125.json`
- `justincard-google-drive-backup-v4`

The same Google user can therefore switch between Windows and Android without manual CSV/XLSX transfers.

## Local build

Requires Java 17 and Android SDK 35.

```bash
gradle :app:testDebugUnitTest
gradle :app:assembleDebug
gradle :app:assembleRelease :app:bundleRelease
```
