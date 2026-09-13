from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import re
import socket
import sys
from typing import Any, Iterable

from justincard.version import APP_VERSION

# v1.2.6 deliberately uses only Google's per-file / app-data scopes.  The
# Sheets API accepts drive.file for spreadsheets that the app created/opened,
# so the broad/sensitive "spreadsheets" scope is no longer necessary.
SCOPES: tuple[str, ...] = (
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive.appdata",
)

SHEET_TITLE = "Just InCard – Sammlung"
MONSTER_SHEET = "Monsterkarten"
SPELL_SHEET = "Zauberkarten"
TRAP_SHEET = "Fallenkarten"
BASE_TEMPLATE_SHEETS: tuple[str, ...] = (MONSTER_SHEET, SPELL_SHEET, TRAP_SHEET)

# Kept as compatibility aliases for older integrations/tests.  They are NOT
# created inside the Google Sheet anymore.  The browser-visible workbook uses
# only the user's supplied template plus deck tabs.
COLLECTION_SHEET = MONSTER_SHEET
RAW_SHEET = "JustInCard_Data"
DECK_RAW_SHEET = "JustInCard_Decks"
INFO_SHEET = "Info"
TYPE_SHEET_PREFIX = ""
DECK_SHEET_PREFIX = ""
CATEGORY_SHEETS: tuple[str, ...] = BASE_TEMPLATE_SHEETS
OTHER_CATEGORY_SHEET = ""

APP_PROPERTY_KEY = "justincard_cloud_type"
APP_PROPERTY_VALUE = "collection-template-v1"
CLOUD_SCHEMA = "justincard-google-drive-backup-v4"
BACKUP_FILE_NAME = "justincard-cloud-backup-v125.json"
TEMPLATE_ASSET = "google_sheets_template.xlsx"
TEMPLATE_SHA256 = "0cb4633fe1abcec31ee5d9fddf533987cdb7fa9f8c84e7b45d282c6a135c7fd7"

MONSTER_HEADERS: tuple[str, ...] = ("Sterne", "Name", "Typ", "Element", "Kategorie", "Set-Code")
SPELL_HEADERS: tuple[str, ...] = ("Kategorie", "Name", "Set-Code")
TRAP_HEADERS: tuple[str, ...] = ("Kategorie", "Name", "Set-Code")
EXPECTED_TEMPLATE_HEADERS: dict[str, tuple[str, ...]] = {
    MONSTER_SHEET: MONSTER_HEADERS,
    SPELL_SHEET: SPELL_HEADERS,
    TRAP_SHEET: TRAP_HEADERS,
}
VISIBLE_HEADERS: tuple[str, ...] = MONSTER_HEADERS

# Sorting may use card data that is not displayed in the template.  This keeps
# the previously requested "Passcode" sorting without adding a Passcode column.
SORT_FIELDS: tuple[tuple[str, str], ...] = (
    ("name", "Name / Alphabetisch"),
    ("card_type", "Kartentyp"),
    ("passcode", "Passcode"),
    ("set_code", "Set-Code"),
    ("race", "Typ"),
    ("attribute", "Element"),
    ("category", "Kategorie"),
    ("level", "Sterne"),
)

# Legacy serialization helpers stay available for tests/migrations, but their
# rows are no longer written into hidden Google-Sheets tabs.
RAW_HEADERS: tuple[str, ...] = (
    "collection_key", "print_code", "set_name", "rarity", "artwork_url",
    "language", "quantity", "condition", "note", "updated_at", "card_json",
)
DECK_RAW_HEADERS: tuple[str, ...] = ("deck_json",)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def default_cloud_directory() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if base:
        return Path(base) / "Just InCard" / "google"
    return Path.home() / ".justincard" / "google"


def default_token_path() -> Path:
    return default_cloud_directory() / "google_token.json"


def template_asset_path() -> Path:
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        return Path(bundle) / "assets" / TEMPLATE_ASSET
    return Path(__file__).resolve().parents[1] / "assets" / TEMPLATE_ASSET


def normalize_spreadsheet_id(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    match = re.search(r"/spreadsheets/d/([A-Za-z0-9_-]+)", text)
    if match:
        return match.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{20,}", text):
        return text
    return ""


def spreadsheet_url(spreadsheet_id: str) -> str:
    identifier = normalize_spreadsheet_id(spreadsheet_id)
    return f"https://docs.google.com/spreadsheets/d/{identifier}/edit" if identifier else ""


def _card_from_record(record: dict[str, Any]) -> dict[str, Any]:
    card = record.get("card")
    if isinstance(card, dict):
        return dict(card)
    raw = record.get("card_json")
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str) and raw.strip():
        try:
            loaded = json.loads(raw)
            if isinstance(loaded, dict):
                return loaded
        except Exception:
            pass
    return {}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def serialize_collection_record(record: dict[str, Any]) -> dict[str, Any]:
    card = _card_from_record(record)
    return {
        "collection_key": str(record.get("collection_key") or ""),
        "print_code": str(record.get("print_code") or ""),
        "set_name": str(record.get("set_name") or ""),
        "rarity": str(record.get("rarity") or ""),
        "artwork_url": str(record.get("artwork_url") or ""),
        "language": str(record.get("language") or card.get("_language") or ""),
        "quantity": max(0, _safe_int(record.get("quantity"), 0)),
        "condition": str(record.get("condition") or "Unbewertet"),
        "note": str(record.get("note") or ""),
        "updated_at": _safe_float(record.get("updated_at"), 0.0),
        "card": card,
    }


def serialize_collection(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [serialize_collection_record(record) for record in records if isinstance(record, dict)]


def _record_key(record: dict[str, Any]) -> str:
    # Cross-platform canonical key shared by Windows and Android.  Existing
    # database-specific collection_key values are intentionally not preferred
    # when enough print metadata exists, otherwise the same physical print can
    # appear twice after a Windows <-> Android merge.
    card = _card_from_record(record)
    canonical = "|".join((
        str(card.get("id") or "").strip(),
        str(record.get("print_code") or "").strip().upper(),
        str(record.get("rarity") or "").strip().casefold(),
        str(record.get("language") or "").strip().lower(),
        str(record.get("artwork_url") or "").strip(),
    ))
    if str(card.get("id") or "").strip() or str(record.get("print_code") or "").strip():
        return canonical
    return str(record.get("collection_key") or "").strip()


def merge_collection_records(
    local_records: Iterable[dict[str, Any]],
    cloud_records: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for source in (local_records, cloud_records):
        for raw in source:
            if not isinstance(raw, dict):
                continue
            record = serialize_collection_record(raw)
            key = _record_key(record)
            if not key:
                continue
            current = merged.get(key)
            if current is None or _safe_float(record.get("updated_at")) >= _safe_float(current.get("updated_at")):
                record["collection_key"] = str(record.get("collection_key") or key)
                merged[key] = record
    return sorted(
        merged.values(),
        key=lambda item: (
            str(_card_from_record(item).get("name") or "").casefold(),
            str(item.get("print_code") or "").casefold(),
            str(item.get("rarity") or "").casefold(),
        ),
    )


def _card_text(card: dict[str, Any]) -> str:
    return " ".join(
        str(card.get(key) or "").casefold()
        for key in ("type", "frameType", "frame_type", "race")
    )


def template_family(card: dict[str, Any]) -> str:
    text = _card_text(card)
    if "spell" in text:
        return SPELL_SHEET
    if "trap" in text:
        return TRAP_SHEET
    return MONSTER_SHEET


def monster_category(card: dict[str, Any]) -> str:
    text = _card_text(card)
    # User explicitly requested "Empfänger" as a value of the Monsterkarten
    # category column, not as a separate worksheet.
    if "tuner" in text:
        return "Empfänger"
    for token, label in (
        ("fusion", "Fusion"),
        ("synchro", "Synchro"),
        ("xyz", "Xyz"),
        ("link", "Link"),
        ("ritual", "Ritual"),
        ("pendulum", "Pendel"),
        ("normal", "Normal"),
        ("effect", "Effekt"),
        ("token", "Token"),
    ):
        if token in text:
            return label
    return "Monster"


def spell_trap_category(card: dict[str, Any]) -> str:
    race = str(card.get("race") or "").strip()
    normalized = race.casefold()
    mapping = {
        "normal": "Normal",
        "continuous": "Permanent",
        "quick-play": "Schnellzauber",
        "quick play": "Schnellzauber",
        "field": "Spielfeld",
        "equip": "Ausrüstung",
        "ritual": "Ritual",
        "counter": "Konter",
    }
    return mapping.get(normalized, race or "Normal")


def template_category(record: dict[str, Any]) -> str:
    card = _card_from_record(record)
    if template_family(card) == MONSTER_SHEET:
        return monster_category(card)
    return spell_trap_category(card)


def record_sort_value(record: dict[str, Any], field: str) -> tuple[int, Any]:
    normalized = serialize_collection_record(record)
    card = _card_from_record(normalized)
    values: dict[str, Any] = {
        "name": card.get("name"),
        "card_type": card.get("type"),
        "passcode": card.get("id"),
        "set_code": normalized.get("print_code"),
        "race": card.get("race"),
        "attribute": card.get("attribute"),
        "category": template_category(normalized),
        "level": card.get("level", card.get("rank")),
    }
    value = values.get(str(field or "name"), values["name"])
    if value in (None, ""):
        return (2, "")
    if isinstance(value, (int, float)):
        return (0, float(value))
    try:
        return (0, float(str(value).replace(",", ".")))
    except (TypeError, ValueError):
        return (1, str(value).casefold())


def sort_collection_records(
    records: Iterable[dict[str, Any]], sort_field: str = "name", sort_direction: str = "asc"
) -> list[dict[str, Any]]:
    values = [serialize_collection_record(record) for record in records if isinstance(record, dict)]
    values.sort(
        key=lambda record: record_sort_value(record, sort_field),
        reverse=str(sort_direction).lower() == "desc",
    )
    return values


def monster_template_row(record: dict[str, Any]) -> list[Any]:
    normalized = serialize_collection_record(record)
    card = _card_from_record(normalized)
    return [
        card.get("level", card.get("rank", "")),
        str(card.get("name") or ""),
        str(card.get("race") or ""),
        str(card.get("attribute") or ""),
        monster_category(card),
        str(normalized.get("print_code") or ""),
    ]


def spell_template_row(record: dict[str, Any]) -> list[Any]:
    normalized = serialize_collection_record(record)
    card = _card_from_record(normalized)
    return [
        spell_trap_category(card),
        str(card.get("name") or ""),
        str(normalized.get("print_code") or ""),
    ]


def trap_template_row(record: dict[str, Any]) -> list[Any]:
    return spell_template_row(record)


def _repeat_quantity(record: dict[str, Any]) -> int:
    return max(0, _safe_int(record.get("quantity"), 0))


def category_sheet_rows(
    records: Iterable[dict[str, Any]], sort_field: str = "name", sort_direction: str = "asc"
) -> dict[str, list[list[Any]]]:
    """Return exactly the three tables from the uploaded workbook template."""
    grouped: dict[str, list[dict[str, Any]]] = {title: [] for title in BASE_TEMPLATE_SHEETS}
    for record in sort_collection_records(records, sort_field, sort_direction):
        family = template_family(_card_from_record(record))
        if family in grouped:
            grouped[family].append(record)

    result: dict[str, list[list[Any]]] = {
        MONSTER_SHEET: [list(MONSTER_HEADERS)],
        SPELL_SHEET: [list(SPELL_HEADERS)],
        TRAP_SHEET: [list(TRAP_HEADERS)],
    }
    row_builders = {
        MONSTER_SHEET: monster_template_row,
        SPELL_SHEET: spell_template_row,
        TRAP_SHEET: trap_template_row,
    }
    for title in BASE_TEMPLATE_SHEETS:
        builder = row_builders[title]
        for record in grouped[title]:
            for _ in range(_repeat_quantity(record)):
                result[title].append(builder(record))
    return result


def type_sheet_rows(
    records: Iterable[dict[str, Any]], sort_field: str = "name", sort_direction: str = "asc"
) -> dict[str, list[list[Any]]]:
    return category_sheet_rows(records, sort_field, sort_direction)


def visible_sheet_rows(
    records: Iterable[dict[str, Any]], sort_field: str = "name", sort_direction: str = "asc"
) -> list[list[Any]]:
    """Compatibility helper: return the Monsterkarten template table."""
    return category_sheet_rows(records, sort_field, sort_direction)[MONSTER_SHEET]


def full_record_row(record: dict[str, Any]) -> list[Any]:
    return monster_template_row(record)


def sanitize_sheet_title(value: str, prefix: str = "") -> str:
    text = re.sub(r"[:\\/?*\[\]]", "-", str(value or "").strip())
    text = re.sub(r"\s+", " ", text).strip() or "Ohne Namen"
    candidate = f"{prefix}{text}"[:100]
    if candidate in BASE_TEMPLATE_SHEETS:
        suffix = " (Deck)"
        candidate = candidate[:100 - len(suffix)] + suffix
    return candidate


def serialize_deck(deck: dict[str, Any]) -> dict[str, Any]:
    cards = deck.get("cards") or deck.get("deck_cards") or []
    return {
        "deck_id": str(deck.get("deck_id") or deck.get("id") or ""),
        "name": str(deck.get("name") or "Unbenanntes Deck"),
        "description": str(deck.get("description") or ""),
        "favorite": bool(deck.get("favorite")),
        "updated_at": _safe_float(deck.get("updated_at"), 0.0),
        "cards": [dict(item) for item in cards if isinstance(item, dict)] if isinstance(cards, list) else [],
    }


def _deck_card_record(item: dict[str, Any]) -> dict[str, Any]:
    card = _card_from_record(item)
    return {
        "collection_key": str(item.get("collection_key") or item.get("source_collection_key") or ""),
        "print_code": str(item.get("print_code") or ""),
        "set_name": str(item.get("set_name") or ""),
        "rarity": str(item.get("rarity") or ""),
        "artwork_url": str(item.get("artwork_url") or ""),
        "language": str(item.get("language") or card.get("_language") or ""),
        "quantity": max(0, _safe_int(item.get("quantity"), 0)),
        "condition": str(item.get("condition") or ""),
        "note": str(item.get("note") or ""),
        "updated_at": _safe_float(item.get("updated_at"), 0.0),
        "card": card,
    }


def deck_template_row(item: dict[str, Any]) -> list[Any]:
    record = _deck_card_record(item)
    card = _card_from_record(record)
    family = template_family(card)
    if family == MONSTER_SHEET:
        return monster_template_row(record)
    # A deck tab is a duplicate of the Monsterkarten template so all cards use
    # those six existing columns. Spell/Trap-only monster fields remain empty.
    return [
        "",
        str(card.get("name") or ""),
        "",
        "",
        spell_trap_category(card),
        str(record.get("print_code") or ""),
    ]


def deck_sheet_rows(
    deck: dict[str, Any], sort_field: str = "name", sort_direction: str = "asc"
) -> list[list[Any]]:
    """Write deck tabs in the cross-platform order requested by the UI.

    Main-deck cards are split into Monster -> Spell -> Trap.  Extra Deck and
    Side Deck follow afterwards.  The selected Google-Sheets sort is applied
    inside each block without ever moving a card into another deck zone.
    """
    normalized = serialize_deck(deck)
    items = [dict(item) for item in normalized["cards"]]

    def zone(item: dict[str, Any]) -> str:
        return str(item.get("zone") or item.get("section") or "main").strip().casefold()

    def family(item: dict[str, Any]) -> str:
        return template_family(_card_from_record(_deck_card_record(item)))

    def sorted_section(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(
            values,
            key=lambda item: record_sort_value(_deck_card_record(item), sort_field),
            reverse=str(sort_direction).lower() == "desc",
        )

    main = [item for item in items if zone(item) in {"main", "main deck", "main_deck"}]
    sections: list[tuple[str, list[dict[str, Any]]]] = [
        ("Monster", sorted_section([item for item in main if family(item) == MONSTER_SHEET])),
        ("Zauber", sorted_section([item for item in main if family(item) == SPELL_SHEET])),
        ("Fallen", sorted_section([item for item in main if family(item) == TRAP_SHEET])),
        ("Extra Deck", sorted_section([item for item in items if zone(item) in {"extra", "extra deck", "extra_deck"}])),
        ("Side Deck", sorted_section([item for item in items if zone(item) in {"side", "side deck", "side_deck"}])),
    ]

    rows: list[list[Any]] = [list(MONSTER_HEADERS)]
    first = True
    for label, section in sections:
        if not section:
            continue
        if not first:
            rows.append(["", "", "", "", "", ""])
        rows.append(["", label, "", "", "", ""])
        for item in section:
            count = max(1, _safe_int(item.get("quantity"), 1))
            row = deck_template_row(item)
            rows.extend([list(row) for _ in range(count)])
        first = False
    return rows


def deck_sheet_map(
    decks: Iterable[dict[str, Any]], sort_field: str = "name", sort_direction: str = "asc"
) -> dict[str, list[list[Any]]]:
    result: dict[str, list[list[Any]]] = {}
    used: set[str] = set(BASE_TEMPLATE_SHEETS)
    for raw in decks:
        if not isinstance(raw, dict):
            continue
        deck = serialize_deck(raw)
        base = sanitize_sheet_title(deck["name"])
        title = base
        counter = 2
        while title in used:
            suffix = f" ({counter})"
            title = base[:100 - len(suffix)] + suffix
            counter += 1
        used.add(title)
        result[title] = deck_sheet_rows(deck, sort_field, sort_direction)
    return result


def raw_sheet_rows(records: Iterable[dict[str, Any]]) -> list[list[Any]]:
    rows: list[list[Any]] = [list(RAW_HEADERS)]
    for raw in records:
        record = serialize_collection_record(raw)
        rows.append([
            record.get("collection_key", ""), record.get("print_code", ""),
            record.get("set_name", ""), record.get("rarity", ""),
            record.get("artwork_url", ""), record.get("language", ""),
            record.get("quantity", 0), record.get("condition", ""),
            record.get("note", ""), record.get("updated_at", 0.0),
            json.dumps(record.get("card") or {}, ensure_ascii=False, separators=(",", ":")),
        ])
    return rows


def parse_raw_sheet_rows(values: list[list[Any]]) -> list[dict[str, Any]]:
    if not values:
        return []
    header = [str(value) for value in values[0]]
    indices = {name: index for index, name in enumerate(header)}
    missing = [name for name in RAW_HEADERS if name not in indices]
    if missing:
        raise ValueError(f"Cloud-Tabelle besitzt ein unbekanntes Datenformat. Fehlend: {', '.join(missing)}")
    records: list[dict[str, Any]] = []
    for row in values[1:]:
        def cell(name: str, default: Any = "") -> Any:
            index = indices[name]
            return row[index] if index < len(row) else default
        try:
            card = json.loads(str(cell("card_json", "{}") or "{}"))
        except Exception:
            card = {}
        if not isinstance(card, dict):
            card = {}
        record = {
            "collection_key": str(cell("collection_key") or ""),
            "print_code": str(cell("print_code") or ""),
            "set_name": str(cell("set_name") or ""),
            "rarity": str(cell("rarity") or ""),
            "artwork_url": str(cell("artwork_url") or ""),
            "language": str(cell("language") or ""),
            "quantity": max(0, _safe_int(cell("quantity"), 0)),
            "condition": str(cell("condition") or "Unbewertet"),
            "note": str(cell("note") or ""),
            "updated_at": _safe_float(cell("updated_at"), 0.0),
            "card": card,
        }
        if record["collection_key"] or card.get("id") or card.get("name"):
            records.append(record)
    return records


def raw_deck_sheet_rows(decks: Iterable[dict[str, Any]]) -> list[list[Any]]:
    rows: list[list[Any]] = [list(DECK_RAW_HEADERS)]
    for deck in decks:
        if isinstance(deck, dict):
            rows.append([json.dumps(serialize_deck(deck), ensure_ascii=False, separators=(",", ":"))])
    return rows


def parse_raw_deck_sheet_rows(values: list[list[Any]]) -> list[dict[str, Any]]:
    if not values:
        return []
    result: list[dict[str, Any]] = []
    for row in values[1:]:
        if not row:
            continue
        try:
            payload = json.loads(str(row[0] or "{}"))
        except Exception:
            continue
        if isinstance(payload, dict) and (payload.get("name") or payload.get("deck_id")):
            result.append(serialize_deck(payload))
    return result


@dataclass(frozen=True)
class CloudAccount:
    display_name: str = ""
    email: str = ""


class GoogleSheetsCloud:
    def __init__(self, client_secret_path: str | Path, token_path: str | Path | None = None) -> None:
        self.client_secret_path = Path(client_secret_path).expanduser()
        self.token_path = Path(token_path or default_token_path()).expanduser()
        self._credentials: Any = None
        self._sheets: Any = None
        self._drive: Any = None

    def _imports(self) -> tuple[Any, Any, Any, Any]:
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                "Google-Bibliotheken fehlen. Bitte die GitHub-Version mit den aktuellen requirements bauen."
            ) from exc
        return Request, Credentials, InstalledAppFlow, build

    def load_credentials(self, interactive: bool = False) -> Any:
        Request, Credentials, InstalledAppFlow, _build = self._imports()
        credentials = None
        if self.token_path.exists():
            try:
                token_info = json.loads(self.token_path.read_text(encoding="utf-8"))
                stored_scopes = set(token_info.get("scopes") or ()) if isinstance(token_info, dict) else set()
                if stored_scopes and not set(SCOPES).issubset(stored_scopes):
                    credentials = None
                else:
                    credentials = Credentials.from_authorized_user_file(str(self.token_path), list(SCOPES))
                    granted = set(getattr(credentials, "granted_scopes", None) or getattr(credentials, "scopes", None) or ())
                    if granted and not set(SCOPES).issubset(granted):
                        credentials = None
            except Exception:
                credentials = None
        if credentials is not None and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        if credentials is None or not credentials.valid:
            if not interactive:
                raise RuntimeError(
                    "Google-Anmeldung fehlt oder benötigt wegen der neuen sicheren Cloud-Berechtigungen eine erneute Anmeldung."
                )
            if not self.client_secret_path.exists():
                raise FileNotFoundError(
                    "OAuth-Client-JSON nicht gefunden. Wählen Sie zuerst die Desktop-OAuth-JSON-Datei aus."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(self.client_secret_path), list(SCOPES))
            credentials = flow.run_local_server(
                host="127.0.0.1",
                port=0,
                open_browser=True,
                access_type="offline",
                prompt="consent",
                success_message="Just InCard wurde mit Google verbunden. Sie können dieses Browserfenster schließen.",
            )
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        self.token_path.write_text(credentials.to_json(), encoding="utf-8")
        try:
            os.chmod(self.token_path, 0o600)
        except Exception:
            pass
        self._credentials = credentials
        return credentials

    def services(self, interactive: bool = False) -> tuple[Any, Any]:
        _Request, _Credentials, _InstalledAppFlow, build = self._imports()
        credentials = self.load_credentials(interactive=interactive)
        if self._sheets is None:
            self._sheets = build("sheets", "v4", credentials=credentials, cache_discovery=False)
        if self._drive is None:
            self._drive = build("drive", "v3", credentials=credentials, cache_discovery=False)
        return self._sheets, self._drive

    def account(self) -> CloudAccount:
        _sheets, drive = self.services(interactive=False)
        try:
            result = drive.about().get(fields="user(displayName,emailAddress)").execute()
            user = result.get("user") or {}
            return CloudAccount(str(user.get("displayName") or ""), str(user.get("emailAddress") or ""))
        except Exception:
            return CloudAccount()

    def logout(self) -> None:
        self._credentials = None
        self._sheets = None
        self._drive = None
        try:
            self.token_path.unlink(missing_ok=True)
        except Exception:
            pass

    def _find_spreadsheet(self) -> str:
        _sheets, drive = self.services(interactive=False)
        query = (
            "trashed=false and mimeType='application/vnd.google-apps.spreadsheet' "
            f"and appProperties has {{ key='{APP_PROPERTY_KEY}' and value='{APP_PROPERTY_VALUE}' }}"
        )
        response = drive.files().list(
            q=query, spaces="drive", pageSize=20, orderBy="modifiedTime desc",
            fields="files(id,name,modifiedTime,webViewLink)",
        ).execute()
        for item in response.get("files") or []:
            identifier = str(item.get("id") or "")
            if identifier and self._is_template_spreadsheet(identifier):
                return identifier
        return ""

    def verify_spreadsheet(self, spreadsheet_id: str) -> str:
        identifier = normalize_spreadsheet_id(spreadsheet_id)
        if not identifier:
            raise ValueError("Ungültige Google-Sheets-ID oder URL.")
        sheets, _drive = self.services(interactive=False)
        sheets.spreadsheets().get(spreadsheetId=identifier, fields="spreadsheetId").execute()
        return identifier

    def _sheet_ids(self, spreadsheet_id: str) -> dict[str, int]:
        sheets, _drive = self.services(interactive=False)
        result = sheets.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            fields="sheets(properties(sheetId,title,hidden))",
        ).execute()
        return {
            str(item.get("properties", {}).get("title") or ""): int(item.get("properties", {}).get("sheetId") or 0)
            for item in result.get("sheets") or []
        }

    def _is_template_spreadsheet(self, spreadsheet_id: str) -> bool:
        try:
            sheets, _drive = self.services(interactive=False)
            ids = self._sheet_ids(spreadsheet_id)
            if not set(BASE_TEMPLATE_SHEETS).issubset(ids):
                return False
            ranges = [f"'{title}'!A1:{'F1' if title == MONSTER_SHEET else 'C1'}" for title in BASE_TEMPLATE_SHEETS]
            result = sheets.spreadsheets().values().batchGet(
                spreadsheetId=spreadsheet_id, ranges=ranges, majorDimension="ROWS"
            ).execute()
            value_ranges = result.get("valueRanges") or []
            if len(value_ranges) != len(BASE_TEMPLATE_SHEETS):
                return False
            for title, entry in zip(BASE_TEMPLATE_SHEETS, value_ranges):
                values = entry.get("values") or []
                header = tuple(str(value) for value in (values[0] if values else []))
                if header != EXPECTED_TEMPLATE_HEADERS[title]:
                    return False
            return True
        except Exception:
            return False

    def _create_from_template(self) -> str:
        _sheets, drive = self.services(interactive=False)
        template = template_asset_path()
        if not template.exists():
            raise FileNotFoundError(f"Google-Sheets-Vorlage fehlt: {template}")
        try:
            from googleapiclient.http import MediaFileUpload
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("Google Drive Upload-Komponente fehlt.") from exc
        media = MediaFileUpload(
            str(template),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            resumable=False,
        )
        result = drive.files().create(
            body={
                "name": SHEET_TITLE,
                "mimeType": "application/vnd.google-apps.spreadsheet",
                "appProperties": {APP_PROPERTY_KEY: APP_PROPERTY_VALUE},
            },
            media_body=media,
            fields="id,webViewLink",
        ).execute()
        identifier = str(result.get("id") or "")
        if not identifier:
            raise RuntimeError("Google Drive hat keine Tabellen-ID zurückgegeben.")
        if not self._is_template_spreadsheet(identifier):
            raise RuntimeError("Die hochgeladene Google-Sheets-Datei entspricht nicht der Just-InCard-Vorlage.")
        return identifier

    def find_or_create_spreadsheet(self, preferred_id: str = "") -> str:
        preferred = normalize_spreadsheet_id(preferred_id)
        if preferred:
            try:
                self.verify_spreadsheet(preferred)
                if self._is_template_spreadsheet(preferred):
                    return preferred
            except Exception:
                pass
        linked = self._linked_spreadsheet_from_backup()
        if linked:
            try:
                self.verify_spreadsheet(linked)
                if self._is_template_spreadsheet(linked):
                    return linked
            except Exception:
                pass
        found = self._find_spreadsheet()
        if found:
            return found
        return self._create_from_template()

    def _sync_deck_sheets(self, spreadsheet_id: str, desired_titles: Iterable[str]) -> dict[str, int]:
        sheets, _drive = self.services(interactive=False)
        ids = self._sheet_ids(spreadsheet_id)
        if MONSTER_SHEET not in ids:
            raise RuntimeError("Vorlage besitzt keinen Monsterkarten-Reiter.")
        desired = {str(title) for title in desired_titles if str(title).strip()}
        existing_decks = set(ids) - set(BASE_TEMPLATE_SHEETS)
        requests: list[dict[str, Any]] = []
        for title in sorted(existing_decks - desired):
            requests.append({"deleteSheet": {"sheetId": ids[title]}})
        for title in sorted(desired - set(ids)):
            requests.append({
                "duplicateSheet": {
                    "sourceSheetId": ids[MONSTER_SHEET],
                    "newSheetName": title,
                }
            })
        if requests:
            sheets.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id, body={"requests": requests}
            ).execute()
        return self._sheet_ids(spreadsheet_id)

    def _find_backup_file(self) -> str:
        _sheets, drive = self.services(interactive=False)
        response = drive.files().list(
            spaces="appDataFolder",
            q=f"name='{BACKUP_FILE_NAME}' and trashed=false",
            pageSize=10,
            fields="files(id,name,modifiedTime)",
            orderBy="modifiedTime desc",
        ).execute()
        files = response.get("files") or []
        return str(files[0].get("id") or "") if files else ""

    def _linked_spreadsheet_from_backup(self) -> str:
        """Resolve the same cross-device Sheet before creating a new one."""
        _sheets, drive = self.services(interactive=False)
        file_id = self._find_backup_file()
        if not file_id:
            return ""
        try:
            raw = drive.files().get_media(fileId=file_id).execute()
            if isinstance(raw, str):
                raw = raw.encode("utf-8")
            payload = json.loads(bytes(raw).decode("utf-8"))
        except Exception:
            return ""
        if not isinstance(payload, dict):
            return ""
        return normalize_spreadsheet_id(str(payload.get("spreadsheet_id") or ""))

    def _save_backup_payload(
        self,
        spreadsheet_id: str,
        collection: list[dict[str, Any]],
        decks: list[dict[str, Any]],
        device_name: str = "",
    ) -> None:
        _sheets, drive = self.services(interactive=False)
        payload = {
            "schema": CLOUD_SCHEMA,
            "app_version": APP_VERSION,
            "updated_at": utc_now_iso(),
            "device": device_name or socket.gethostname(),
            "spreadsheet_id": spreadsheet_id,
            "collection": collection,
            "decks": decks,
        }
        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        try:
            from googleapiclient.http import MediaIoBaseUpload
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("Google Drive Backup-Komponente fehlt.") from exc
        media = MediaIoBaseUpload(io.BytesIO(data), mimetype="application/json", resumable=False)
        existing = self._find_backup_file()
        if existing:
            drive.files().update(fileId=existing, media_body=media, fields="id").execute()
        else:
            drive.files().create(
                body={"name": BACKUP_FILE_NAME, "parents": ["appDataFolder"], "mimeType": "application/json"},
                media_body=media,
                fields="id",
            ).execute()

    def _load_backup_payload(self, spreadsheet_id: str = "") -> dict[str, Any]:
        _sheets, drive = self.services(interactive=False)
        file_id = self._find_backup_file()
        if not file_id:
            return {"collection": [], "decks": []}
        raw = drive.files().get_media(fileId=file_id).execute()
        if isinstance(raw, str):
            raw = raw.encode("utf-8")
        try:
            payload = json.loads(bytes(raw).decode("utf-8"))
        except Exception as exc:
            raise RuntimeError("Google-Cloud-Backup konnte nicht gelesen werden.") from exc
        if not isinstance(payload, dict):
            return {"collection": [], "decks": []}
        linked = normalize_spreadsheet_id(str(payload.get("spreadsheet_id") or ""))
        requested = normalize_spreadsheet_id(spreadsheet_id)
        if requested and linked and requested != linked:
            return {"collection": [], "decks": []}
        return {
            "collection": serialize_collection(payload.get("collection") or []),
            "decks": [serialize_deck(deck) for deck in (payload.get("decks") or []) if isinstance(deck, dict)],
        }

    def _legacy_sheet_backup(self, spreadsheet_id: str) -> dict[str, Any]:
        """Best-effort migration path for v1.2.0-v1.2.4 cloud files."""
        sheets, _drive = self.services(interactive=False)
        try:
            collection_values = sheets.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=f"'{RAW_SHEET}'!A:K",
                majorDimension="ROWS",
            ).execute().get("values") or []
        except Exception:
            collection_values = []
        try:
            deck_values = sheets.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=f"'{DECK_RAW_SHEET}'!A:A",
                majorDimension="ROWS",
            ).execute().get("values") or []
        except Exception:
            deck_values = []
        return {
            "collection": parse_raw_sheet_rows(collection_values) if collection_values else [],
            "decks": parse_raw_deck_sheet_rows(deck_values) if deck_values else [],
        }

    def upload_collection(
        self,
        spreadsheet_id: str,
        records: Iterable[dict[str, Any]],
        device_name: str = "",
        *,
        decks: Iterable[dict[str, Any]] | None = None,
        sort_field: str = "name",
        sort_direction: str = "asc",
    ) -> dict[str, Any]:
        identifier = self.find_or_create_spreadsheet(spreadsheet_id)
        sheets, _drive = self.services(interactive=False)
        serialized = serialize_collection(records)
        serialized_decks = [serialize_deck(deck) for deck in (decks or []) if isinstance(deck, dict)]

        tabs = category_sheet_rows(serialized, sort_field, sort_direction)
        deck_tabs = deck_sheet_map(serialized_decks, sort_field, sort_direction)
        self._sync_deck_sheets(identifier, deck_tabs.keys())

        clear_ranges = [
            f"'{MONSTER_SHEET}'!A2:F",
            f"'{SPELL_SHEET}'!A2:C",
            f"'{TRAP_SHEET}'!A2:C",
        ] + [f"'{title}'!A2:F" for title in deck_tabs]
        sheets.spreadsheets().values().batchClear(
            spreadsheetId=identifier,
            body={"ranges": clear_ranges},
        ).execute()

        data: list[dict[str, Any]] = []
        for title in BASE_TEMPLATE_SHEETS:
            values = tabs[title][1:]
            if values:
                data.append({"range": f"'{title}'!A2", "values": values})
        for title, rows in deck_tabs.items():
            values = rows[1:]
            if values:
                data.append({"range": f"'{title}'!A2", "values": values})
        if data:
            sheets.spreadsheets().values().batchUpdate(
                spreadsheetId=identifier,
                body={"valueInputOption": "RAW", "data": data},
            ).execute()

        # Full restore data is intentionally stored outside the visible Sheet
        # in the appData folder. This keeps the Sheet 1:1 to the supplied
        # template while still allowing lossless sync on another device.
        self._save_backup_payload(identifier, serialized, serialized_decks, device_name)
        return {
            "spreadsheet_id": identifier,
            "url": spreadsheet_url(identifier),
            "rows": len(serialized),
            "decks": len(serialized_decks),
            "category_sheets": len(BASE_TEMPLATE_SHEETS),
            "type_sheets": len(BASE_TEMPLATE_SHEETS),
            "deck_sheets": len(deck_tabs),
        }

    def download_cloud_payload(self, spreadsheet_id: str) -> dict[str, Any]:
        identifier = self.verify_spreadsheet(spreadsheet_id)
        payload = self._load_backup_payload(identifier)
        if payload.get("collection") or payload.get("decks"):
            return payload
        legacy = self._legacy_sheet_backup(identifier)
        return legacy

    def download_collection(self, spreadsheet_id: str) -> list[dict[str, Any]]:
        return list(self.download_cloud_payload(spreadsheet_id).get("collection") or [])

    def download_decks(self, spreadsheet_id: str) -> list[dict[str, Any]]:
        return list(self.download_cloud_payload(spreadsheet_id).get("decks") or [])


__all__ = [
    "SCOPES", "SHEET_TITLE", "MONSTER_SHEET", "SPELL_SHEET", "TRAP_SHEET",
    "BASE_TEMPLATE_SHEETS", "COLLECTION_SHEET", "RAW_SHEET", "DECK_RAW_SHEET",
    "INFO_SHEET", "TYPE_SHEET_PREFIX", "DECK_SHEET_PREFIX", "CATEGORY_SHEETS",
    "OTHER_CATEGORY_SHEET", "CLOUD_SCHEMA", "BACKUP_FILE_NAME", "TEMPLATE_ASSET",
    "TEMPLATE_SHA256", "MONSTER_HEADERS", "SPELL_HEADERS", "TRAP_HEADERS",
    "EXPECTED_TEMPLATE_HEADERS", "VISIBLE_HEADERS", "RAW_HEADERS", "DECK_RAW_HEADERS",
    "SORT_FIELDS", "CloudAccount", "GoogleSheetsCloud", "default_token_path",
    "template_asset_path", "normalize_spreadsheet_id", "spreadsheet_url",
    "serialize_collection_record", "serialize_collection", "merge_collection_records",
    "template_family", "monster_category", "spell_trap_category", "template_category",
    "record_sort_value", "sort_collection_records", "monster_template_row",
    "spell_template_row", "trap_template_row", "visible_sheet_rows", "type_sheet_rows",
    "category_sheet_rows", "full_record_row", "sanitize_sheet_title", "serialize_deck",
    "deck_template_row", "deck_sheet_rows", "deck_sheet_map", "raw_sheet_rows",
    "parse_raw_sheet_rows", "raw_deck_sheet_rows", "parse_raw_deck_sheet_rows",
]
