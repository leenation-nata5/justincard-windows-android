# Just InCard Android 13.0.9

Standalone Android project for Just InCard.

## Account mode
- First start: choose **local only** or **Just InCard account**.
- When logging into an existing account, the server snapshot is downloaded first.
- A remote account that already contains collection/deck data is never overwritten by the pre-login local database.
- If the remote account is truly empty, existing local data may initialize it.
- Card images remain on the device; account sync stores collection/deck metadata only.

## GitHub build
The included workflow `.github/workflows/build-android.yml` builds debug, CI release APK/AAB and optionally a production-signed release when signing secrets are configured.
