# Just InCard Account Sync Contract v1

Windows 1.3.2 and Android 13.0.8 use the same IONOS account contract.

- Website/account base: `https://justincard.de/`
- API base: `https://justincard.de/api/v1/`
- Login: `POST login.php`
- Snapshot: `GET/POST sync.php`
- Schema: `justincard-account-sync-v1`
- Server stores metadata for collection and decks only; no card-image bytes are uploaded.
- Each client keeps a local offline database and a private last-sync base snapshot for three-way reconciliation.
- Collection identities are derived from card id, artwork id, set code, rarity, condition and language.
- Deck identities are derived from the normalized deck name; deck-card identities additionally include section and print identity.
- `if_revision` is used for optimistic concurrency; clients retry one revision conflict against the newest server state.
- Local mode requires no account and disables account synchronization without disabling any app feature.
