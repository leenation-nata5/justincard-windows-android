from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import socket
import ssl
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import uuid

import certifi

ACCOUNT_SCHEMA = "justincard-account-sync-v1"
DEFAULT_API_BASE = "https://justincard.de/api/v1/"
DEFAULT_WEBSITE = "https://justincard.de/"

MODE_SETTING = "account_storage_mode_v132"  # "local" | "account"
TOKEN_SETTING = "account_api_token_v132"
USER_SETTING = "account_user_v132"
DEVICE_ID_SETTING = "account_device_id_v132"
AUTO_SYNC_SETTING = "account_auto_sync_v132"
LAST_SYNC_SETTING = "account_last_sync_v132"
RESTORE_READY_SETTING = "account_restore_ready_v135"


def _now_ms() -> int:
    return int(time.time() * 1000)


def _clean_base(url: str) -> str:
    return (url or DEFAULT_API_BASE).strip().rstrip("/") + "/"


class AccountApiError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None, code: str = "") -> None:
        super().__init__(message)
        self.status = status
        self.code = code


class JustInCardAccountClient:
    def __init__(self, base_url: str = DEFAULT_API_BASE, timeout: float = 20.0) -> None:
        self.base_url = _clean_base(base_url)
        self.timeout = timeout
        self.ssl_context = ssl.create_default_context(cafile=certifi.where())

    def _request(
        self,
        path: str,
        *,
        method: str = "GET",
        token: str = "",
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body = None
        headers = {
            "Accept": "application/json",
            "User-Agent": "JustInCard-Windows/1.3.6",
        }
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = Request(self.base_url + path.lstrip("/"), data=body, method=method, headers=headers)
        try:
            with urlopen(req, timeout=self.timeout, context=self.ssl_context) as response:
                raw = response.read().decode("utf-8", errors="replace")
                data = json.loads(raw) if raw.strip() else {}
        except HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                data = json.loads(raw) if raw.strip() else {}
            except Exception:
                data = {}
            code = str(data.get("error") or "") if isinstance(data, dict) else ""
            message = str(data.get("message") or code or f"HTTP {exc.code}") if isinstance(data, dict) else f"HTTP {exc.code}"
            raise AccountApiError(message, status=exc.code, code=code) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise AccountApiError(f"Just-InCard-Server nicht erreichbar: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise AccountApiError("Der Just-InCard-Server hat keine gültige JSON-Antwort geliefert.") from exc
        if not isinstance(data, dict):
            raise AccountApiError("Ungültige Serverantwort.")
        if data.get("ok") is False:
            raise AccountApiError(str(data.get("message") or data.get("error") or "Serverfehler"), code=str(data.get("error") or ""))
        return data

    def health(self) -> dict[str, Any]:
        return self._request("health.php")

    def login(self, identity: str, password: str, device_name: str) -> dict[str, Any]:
        return self._request(
            "login.php",
            method="POST",
            payload={"identity": identity.strip(), "password": password, "device_name": device_name.strip()},
        )

    def me(self, token: str) -> dict[str, Any]:
        return self._request("me.php", token=token)

    def logout(self, token: str) -> None:
        if token:
            self._request("logout.php", method="POST", token=token, payload={})

    def get_snapshot(self, token: str) -> tuple[int, dict[str, Any]]:
        data = self._request("sync.php", token=token)
        payload = data.get("payload") if isinstance(data.get("payload"), dict) else {}
        return int(data.get("revision") or 0), normalize_payload(payload)

    def put_snapshot(self, token: str, payload: dict[str, Any], revision: int, device_name: str, *, force_replace: bool = False) -> int:
        data = self._request(
            "sync.php",
            method="POST",
            token=token,
            payload={
                "if_revision": int(revision),
                "source_device": device_name,
                "schema": ACCOUNT_SCHEMA,
                "payload": normalize_payload(payload),
                "force_replace": bool(force_replace),
            },
        )
        return int(data.get("revision") or (revision + 1))


def stable_device_id(database: Any) -> str:
    value = str(database.get_setting(DEVICE_ID_SETTING, "") or "").strip()
    if value:
        return value
    value = str(uuid.uuid4())
    database.set_setting(DEVICE_ID_SETTING, value)
    return value


def windows_device_name() -> str:
    return socket.gethostname().strip() or os.environ.get("COMPUTERNAME", "Windows-PC") or "Windows-PC"


def _to_ms(value: Any) -> int:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return 0
    if number <= 0:
        return 0
    return int(number if number >= 10_000_000_000 else number * 1000)


def _to_seconds(value: Any) -> float:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return time.time()
    return number / 1000.0 if number >= 10_000_000_000 else number


def _artwork_id(url: str, card_id: int) -> int:
    matches = re.findall(r"(?<!\d)(\d{5,12})(?!\d)", str(url or ""))
    if matches:
        try:
            return int(matches[-1])
        except ValueError:
            pass
    return card_id


def _artwork_url(artwork_id: int) -> str:
    return f"https://images.ygoprodeck.com/images/cards/{artwork_id}.jpg" if artwork_id > 0 else ""


def collection_identity(card_id: Any, artwork_id: Any, set_code: str, rarity: str, condition: str, language: str) -> str:
    raw = "|".join([
        str(card_id or "0"), str(artwork_id or card_id or "0"), str(set_code or "").upper().strip(),
        str(rarity or "").lower().strip(), str(condition or "").lower().strip(), str(language or "").lower().strip(),
    ])
    return "collection:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def deck_identity(name: str) -> str:
    return "deck:" + hashlib.sha256(str(name or "Deck").strip().lower().encode("utf-8")).hexdigest()


def deck_card_identity(deck_sync_id: str, card_id: Any, artwork_id: Any, set_code: str, section: str) -> str:
    raw = "|".join([
        deck_sync_id, str(card_id or "0"), str(artwork_id or card_id or "0"),
        str(set_code or "").upper().strip(), str(section or "MAIN").upper().strip(),
    ])
    return "deckcard:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def normalize_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    source = payload if isinstance(payload, dict) else {}
    collection = [dict(row) for row in source.get("collection", []) if isinstance(row, dict)]
    decks = []
    for raw in source.get("decks", []):
        if not isinstance(raw, dict):
            continue
        deck = dict(raw)
        deck["cards"] = [dict(card) for card in deck.get("cards", []) if isinstance(card, dict)]
        decks.append(deck)
    return {"schema": ACCOUNT_SCHEMA, "collection": collection, "decks": decks}


def windows_snapshot(database: Any) -> dict[str, Any]:
    device_id = stable_device_id(database)
    collection: list[dict[str, Any]] = []
    for raw in database.export_cloud_collection():
        if not isinstance(raw, dict):
            continue
        card = raw.get("card") if isinstance(raw.get("card"), dict) else {}
        try:
            card_id = int(card.get("id") or 0)
        except (TypeError, ValueError):
            card_id = 0
        art_id = _artwork_id(str(raw.get("artwork_url") or ""), card_id)
        sync_id = collection_identity(card_id, art_id, str(raw.get("print_code") or ""), str(raw.get("rarity") or ""), str(raw.get("condition") or ""), str(raw.get("language") or card.get("_language") or ""))
        collection.append({
            "sync_id": sync_id,
            "card_id": card_id,
            "artwork_id": art_id,
            "card_name": str(card.get("name") or ""),
            "set_code": str(raw.get("print_code") or ""),
            "set_name": str(raw.get("set_name") or ""),
            "rarity": str(raw.get("rarity") or ""),
            "language": str(raw.get("language") or card.get("_language") or "en"),
            "condition": str(raw.get("condition") or "Near Mint"),
            "quantity": max(0, int(raw.get("quantity") or 0)),
            "notes": str(raw.get("note") or ""),
            "added_at_ms": _to_ms(raw.get("added_at")) or _to_ms(raw.get("updated_at")) or _now_ms(),
            "updated_at_ms": _to_ms(raw.get("updated_at")) or _now_ms(),
            "device_id": str(raw.get("device_id") or device_id),
        })

    decks: list[dict[str, Any]] = []
    for raw_deck in database.export_cloud_decks():
        if not isinstance(raw_deck, dict):
            continue
        name = str(raw_deck.get("name") or "Deck").strip() or "Deck"
        deck_sync = deck_identity(name)
        cards: list[dict[str, Any]] = []
        for item in raw_deck.get("cards") or []:
            if not isinstance(item, dict):
                continue
            card = item.get("card") if isinstance(item.get("card"), dict) else {}
            try:
                card_id = int(card.get("id") or item.get("card_id") or 0)
            except (TypeError, ValueError):
                card_id = 0
            art_id = _artwork_id(str(item.get("artwork_url") or ""), card_id)
            section = str(item.get("zone") or item.get("section") or "main").upper()
            section = "EXTRA" if section.startswith("EXTRA") else ("SIDE" if section.startswith("SIDE") else "MAIN")
            set_code = str(item.get("print_code") or item.get("set_code") or "")
            cards.append({
                "sync_id": deck_card_identity(deck_sync, card_id, art_id, set_code, section),
                "card_id": card_id,
                "artwork_id": art_id,
                "language": str(item.get("language") or card.get("_language") or "en"),
                "card_name": str(card.get("name") or item.get("card_name") or ""),
                "set_code": set_code,
                "section": section,
                "quantity": max(0, int(item.get("quantity") or 1)),
                "updated_at_ms": _to_ms(item.get("updated_at") or raw_deck.get("updated_at")) or _now_ms(),
                "device_id": str(item.get("device_id") or device_id),
            })
        decks.append({
            "sync_id": deck_sync,
            "name": name,
            "notes": str(raw_deck.get("description") or raw_deck.get("notes") or ""),
            "favorite": bool(raw_deck.get("favorite")),
            "updated_at_ms": _to_ms(raw_deck.get("updated_at")) or max([c["updated_at_ms"] for c in cards], default=_now_ms()),
            "device_id": str(raw_deck.get("device_id") or device_id),
            "cards": cards,
        })
    return normalize_payload({"collection": collection, "decks": decks})


def _strip_runtime(record: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in record.items() if k not in {"updated_at_ms", "device_id"}}


def _same(a: dict[str, Any] | None, b: dict[str, Any] | None) -> bool:
    if a is None or b is None:
        return a is b
    return _strip_runtime(a) == _strip_runtime(b)


def _winner(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    ta, tb = int(a.get("updated_at_ms") or 0), int(b.get("updated_at_ms") or 0)
    if ta != tb:
        return a if ta > tb else b
    return a if str(a.get("device_id") or "") >= str(b.get("device_id") or "") else b


def _merge_record_map(
    base_items: list[dict[str, Any]],
    local_items: list[dict[str, Any]],
    remote_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    base = {str(x.get("sync_id") or ""): x for x in base_items if x.get("sync_id")}
    local = {str(x.get("sync_id") or ""): x for x in local_items if x.get("sync_id")}
    remote = {str(x.get("sync_id") or ""): x for x in remote_items if x.get("sync_id")}
    out: list[dict[str, Any]] = []
    for key in sorted(set(base) | set(local) | set(remote)):
        b, l, r = base.get(key), local.get(key), remote.get(key)
        if b is None:
            if l is None: chosen = r
            elif r is None: chosen = l
            else: chosen = l if _same(l, r) else _winner(l, r)
        else:
            # A missing row is NOT treated as a deletion.  Older Just-InCard
            # builds could fail to materialize a downloaded snapshot locally;
            # interpreting the resulting empty local database as a deletion
            # erased the valid server snapshot on the next automatic sync.
            # Until explicit tombstones are present, data safety wins: a row
            # that still exists on either side is retained.
            if l is None and r is None:
                chosen = None
            elif l is None:
                chosen = r
            elif r is None:
                chosen = l
            else:
                l_changed = not _same(l, b)
                r_changed = not _same(r, b)
                if not l_changed and not r_changed: chosen = b
                elif l_changed and not r_changed: chosen = l
                elif r_changed and not l_changed: chosen = r
                else: chosen = _winner(l, r)
        if chosen is not None:
            out.append(dict(chosen))
    return out


def merge_payloads(base_payload: dict[str, Any], local_payload: dict[str, Any], remote_payload: dict[str, Any]) -> dict[str, Any]:
    base = normalize_payload(base_payload)
    local = normalize_payload(local_payload)
    remote = normalize_payload(remote_payload)
    merged_collection = _merge_record_map(base["collection"], local["collection"], remote["collection"])

    base_decks = {str(d.get("sync_id") or ""): d for d in base["decks"] if d.get("sync_id")}
    local_decks = {str(d.get("sync_id") or ""): d for d in local["decks"] if d.get("sync_id")}
    remote_decks = {str(d.get("sync_id") or ""): d for d in remote["decks"] if d.get("sync_id")}
    merged_decks: list[dict[str, Any]] = []
    for key in sorted(set(base_decks) | set(local_decks) | set(remote_decks)):
        b, l, r = base_decks.get(key), local_decks.get(key), remote_decks.get(key)
        b_meta = None if b is None else {k: v for k, v in b.items() if k != "cards"}
        l_meta = None if l is None else {k: v for k, v in l.items() if k != "cards"}
        r_meta = None if r is None else {k: v for k, v in r.items() if k != "cards"}
        chosen_meta_list = _merge_record_map(
            [b_meta] if b_meta else [], [l_meta] if l_meta else [], [r_meta] if r_meta else []
        )
        if not chosen_meta_list:
            continue
        chosen = dict(chosen_meta_list[0])
        chosen["cards"] = _merge_record_map(
            (b or {}).get("cards") or [], (l or {}).get("cards") or [], (r or {}).get("cards") or []
        )
        if chosen["cards"]:
            chosen["updated_at_ms"] = max(int(chosen.get("updated_at_ms") or 0), max(int(c.get("updated_at_ms") or 0) for c in chosen["cards"]))
        merged_decks.append(chosen)
    return normalize_payload({"collection": merged_collection, "decks": merged_decks})


def _load_base(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return normalize_payload(data if isinstance(data, dict) else {})
    except Exception:
        return normalize_payload({})


def _save_base(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(normalize_payload(payload), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)


def default_base_path() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / ".local" / "share")) / "Just InCard"
    return root / "account_sync_base_v1.json"


def _local_card(database: Any, rec: dict[str, Any]) -> dict[str, Any]:
    card_id = int(rec.get("card_id") or 0)
    language = str(rec.get("language") or "en").lower()
    try:
        from justincard.search_core import _decode_row
        with database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM cards WHERE card_id=? AND LOWER(language)=? ORDER BY card_key LIMIT 1",
                (card_id, language),
            ).fetchone()
            if row is None and language != "en":
                row = connection.execute(
                    "SELECT * FROM cards WHERE card_id=? AND LOWER(language)='en' ORDER BY card_key LIMIT 1",
                    (card_id,),
                ).fetchone()
        if row is not None:
            card = _decode_row(database, row)
            if isinstance(card, dict):
                return card
    except Exception:
        pass
    art_id = int(rec.get("artwork_id") or card_id or 0)
    image = _artwork_url(art_id)
    return {
        "id": card_id,
        "name": str(rec.get("card_name") or f"Karte {card_id}"),
        "desc": "",
        "type": "",
        "frameType": "",
        "race": "",
        "attribute": "",
        "_language": language,
        "card_images": ([{"id": art_id, "image_url": image, "image_url_small": image}] if image else []),
    }


def _to_windows_cloud(database: Any, payload: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    collection: list[dict[str, Any]] = []
    for rec in normalize_payload(payload)["collection"]:
        card = _local_card(database, rec)
        art_id = int(rec.get("artwork_id") or rec.get("card_id") or 0)
        artwork_url = _artwork_url(art_id)
        if artwork_url:
            card = dict(card)
            card["artwork_url"] = artwork_url
        collection.append({
            "collection_key": str(rec.get("sync_id") or ""),
            "print_code": str(rec.get("set_code") or ""),
            "set_name": str(rec.get("set_name") or ""),
            "rarity": str(rec.get("rarity") or ""),
            "artwork_url": artwork_url,
            "language": str(rec.get("language") or "en"),
            "quantity": max(0, int(rec.get("quantity") or 0)),
            "condition": str(rec.get("condition") or "Near Mint"),
            "note": str(rec.get("notes") or ""),
            "added_at": _to_seconds(rec.get("added_at_ms")),
            "updated_at": _to_seconds(rec.get("updated_at_ms")),
            "card": card,
        })

    decks: list[dict[str, Any]] = []
    for deck in normalize_payload(payload)["decks"]:
        cards = []
        for rec in deck.get("cards") or []:
            card = _local_card(database, rec)
            art_id = int(rec.get("artwork_id") or rec.get("card_id") or 0)
            artwork_url = _artwork_url(art_id)
            cards.append({
                "collection_key": "",  # placeholder-safe import if matching collection key cannot be reconstructed here
                "source_collection_key": "",
                "print_code": str(rec.get("set_code") or ""),
                "set_code": str(rec.get("set_code") or ""),
                "artwork_url": artwork_url,
                "language": str(rec.get("language") or "en"),
                "quantity": max(1, int(rec.get("quantity") or 1)),
                "zone": str(rec.get("section") or "MAIN").lower(),
                "updated_at": _to_seconds(rec.get("updated_at_ms")),
                "card": card,
            })
        decks.append({
            "deck_id": str(deck.get("sync_id") or ""),
            "name": str(deck.get("name") or "Deck"),
            "description": str(deck.get("notes") or ""),
            "favorite": bool(deck.get("favorite")),
            "updated_at": _to_seconds(deck.get("updated_at_ms")),
            "cards": cards,
        })
    return collection, decks


def _collection_key_index(database: Any) -> dict[tuple[int, str, int], str]:
    """Map imported cloud records back to the application's native collection keys.

    Deck cards reference collection rows by the native collection_key.  The
    account protocol intentionally uses its own stable sync_id, so after a
    collection restore we resolve those stable records to the freshly-created
    local keys before importing decks.
    """
    index: dict[tuple[int, str, int], str] = {}
    for item in database.collection_items(""):
        if not isinstance(item, dict):
            continue
        card = item.get("card") if isinstance(item.get("card"), dict) else {}
        try:
            card_id = int(card.get("id") or 0)
        except (TypeError, ValueError):
            card_id = 0
        if card_id <= 0:
            continue
        set_code = str(item.get("print_code") or "").strip().upper()
        art_id = _artwork_id(str(item.get("artwork_url") or ""), card_id)
        key = str(item.get("collection_key") or "").strip()
        if key:
            index[(card_id, set_code, art_id)] = key
            index.setdefault((card_id, set_code, card_id), key)
            index.setdefault((card_id, "", art_id), key)
    return index


def _bind_decks_to_collection(database: Any, decks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    index = _collection_key_index(database)
    bound: list[dict[str, Any]] = []
    for raw_deck in decks:
        if not isinstance(raw_deck, dict):
            continue
        deck = dict(raw_deck)
        cards: list[dict[str, Any]] = []
        for raw in deck.get("cards") or []:
            if not isinstance(raw, dict):
                continue
            item = dict(raw)
            card = item.get("card") if isinstance(item.get("card"), dict) else {}
            try:
                card_id = int(card.get("id") or item.get("card_id") or 0)
            except (TypeError, ValueError):
                card_id = 0
            set_code = str(item.get("print_code") or item.get("set_code") or "").strip().upper()
            art_id = _artwork_id(str(item.get("artwork_url") or ""), card_id)
            key = (
                index.get((card_id, set_code, art_id))
                or index.get((card_id, set_code, card_id))
                or index.get((card_id, "", art_id))
                or ""
            )
            if key:
                item["source_collection_key"] = key
                item["collection_key"] = key
            cards.append(item)
        deck["cards"] = cards
        bound.append(deck)
    return bound


def _native_collection_key(database: Any, rec: dict[str, Any]) -> tuple[str, dict[str, Any], dict[str, Any] | None, str]:
    card = _local_card(database, rec)
    art_id = int(rec.get("artwork_id") or rec.get("card_id") or 0)
    artwork_url = _artwork_url(art_id)
    if artwork_url:
        card = dict(card)
        card["artwork_url"] = artwork_url
    print_item: dict[str, Any] | None = {
        "set_code": str(rec.get("set_code") or ""),
        "set_name": str(rec.get("set_name") or ""),
        "set_rarity": str(rec.get("rarity") or ""),
    }
    if not any(print_item.values()):
        print_item = None
    key = str(database.collection_key(card, print_item, artwork_url) or "")
    return key, card, print_item, artwork_url


def _direct_restore_collection(database: Any, payload: dict[str, Any]) -> tuple[set[str], dict[str, int]]:
    """Materialise the account collection directly into the native SQLite table.

    The generic Google-cloud importer intentionally swallows malformed rows.  For
    account restore this is too dangerous: a skipped restore followed by auto-sync
    used to look like an intentional local deletion.  This importer writes the
    application's native schema explicitly and raises if even one server row
    cannot be materialised.
    """
    wanted: set[str] = set()
    applied = 0
    normalized = normalize_payload(payload)
    with database._write_lock:
        with database.connect() as connection:
            columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(collection)").fetchall()}
            for rec in normalized["collection"]:
                key, card, print_item, artwork_url = _native_collection_key(database, rec)
                if not key:
                    raise AccountApiError(f"Konto-Karte konnte nicht lokal zugeordnet werden: {rec.get('card_name') or rec.get('card_id')}")
                wanted.add(key)
                quantity = max(0, int(rec.get("quantity") or 0))
                added_at = _to_seconds(rec.get("added_at_ms"))
                updated_at = _to_seconds(rec.get("updated_at_ms"))
                card_id = int(rec.get("card_id") or card.get("id") or 0)
                row = {
                    "collection_key": key,
                    "card_key": str(card.get("_card_key") or card.get("card_key") or ""),
                    "card_id": card_id,
                    "print_code": str(rec.get("set_code") or ""),
                    "set_name": str(rec.get("set_name") or ""),
                    "rarity": str(rec.get("rarity") or ""),
                    "artwork_url": artwork_url,
                    "language": str(rec.get("language") or card.get("_language") or "en"),
                    "quantity": quantity,
                    "condition": str(rec.get("condition") or "Near Mint"),
                    "purchase_price": None,
                    "note": str(rec.get("notes") or ""),
                    "wishlist": 0,
                    "trade": 0,
                    "card_json": database._json(card),
                    "created_at": added_at if added_at > 0 else updated_at,
                    "added_at": added_at if added_at > 0 else updated_at,
                    "updated_at": updated_at,
                }
                usable = {k: v for k, v in row.items() if k in columns}
                names = list(usable)
                placeholders = ",".join("?" for _ in names)
                updates = ",".join(f"{name}=excluded.{name}" for name in names if name not in {"collection_key", "created_at"})
                sql = (
                    f"INSERT INTO collection({','.join(names)}) VALUES({placeholders}) "
                    f"ON CONFLICT(collection_key) DO UPDATE SET {updates}"
                )
                connection.execute(sql, tuple(usable[name] for name in names))
                applied += 1
    return wanted, {"applied": applied, "skipped": 0}


def _verify_remote_materialized(database: Any, payload: dict[str, Any]) -> tuple[list[str], list[str]]:
    remote = normalize_payload(payload)
    local = windows_snapshot(database)
    local_collection = {str(item.get("sync_id") or "") for item in local["collection"]}
    local_decks = {str(item.get("sync_id") or ""): item for item in local["decks"]}
    missing_collection = [
        str(item.get("sync_id") or item.get("card_name") or item.get("card_id") or "?")
        for item in remote["collection"]
        if str(item.get("sync_id") or "") not in local_collection
    ]
    missing_decks: list[str] = []
    for deck in remote["decks"]:
        sync_id = str(deck.get("sync_id") or "")
        local_deck = local_decks.get(sync_id)
        if local_deck is None:
            missing_decks.append(str(deck.get("name") or sync_id or "Deck"))
            continue
        local_cards = {str(card.get("sync_id") or "") for card in local_deck.get("cards") or []}
        for card in deck.get("cards") or []:
            card_sync = str(card.get("sync_id") or "")
            if card_sync and card_sync not in local_cards:
                missing_decks.append(f"{deck.get('name') or 'Deck'} / {card.get('card_name') or card_sync}")
    return missing_collection, missing_decks


def _prune_local_to_remote(database: Any, payload: dict[str, Any], wanted_collection_keys: set[str]) -> None:
    """Only prune after every remote row has been verified locally."""
    remote = normalize_payload(payload)
    remote_deck_names = {str(d.get("name") or "").strip().casefold() for d in remote["decks"]}
    with database._write_lock:
        with database.connect() as connection:
            if wanted_collection_keys:
                marks = ",".join("?" for _ in wanted_collection_keys)
                connection.execute(
                    f"DELETE FROM collection WHERE collection_key NOT IN ({marks})",
                    tuple(sorted(wanted_collection_keys)),
                )
            else:
                connection.execute("DELETE FROM collection")
            deck_rows = connection.execute("SELECT deck_id, name FROM decks").fetchall()
            for row in deck_rows:
                name = str(row["name"] if hasattr(row, "keys") else row[1]).strip().casefold()
                if name not in remote_deck_names:
                    deck_id = str(row["deck_id"] if hasattr(row, "keys") else row[0])
                    connection.execute("DELETE FROM deck_cards WHERE deck_id=?", (deck_id,))
                    connection.execute("DELETE FROM decks WHERE deck_id=?", (deck_id,))


def replace_windows_from_payload(database: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """Restore a server snapshot without ever turning an import failure into deletion.

    Remote rows are first materialised alongside existing local data.  Only when
    every collection row, deck and deck card can be read back through the normal
    application export path are unrelated local rows pruned.  Therefore a parser
    or catalogue problem cannot leave an empty database that auto-sync then sends
    back to the server.
    """
    normalized = normalize_payload(payload)
    wanted_keys, collection_report = _direct_restore_collection(database, normalized)

    # Deck import can now resolve server cards against the native keys just
    # materialised above.  Existing helper also handles placeholders when a deck
    # contains more copies than the collection owns.
    _, decks = _to_windows_cloud(database, normalized)
    bound_decks = _bind_decks_to_collection(database, decks)
    deck_report = database.apply_cloud_decks(bound_decks)

    missing_collection, missing_decks = _verify_remote_materialized(database, normalized)
    if missing_collection or missing_decks:
        details = []
        if missing_collection:
            details.append(f"{len(missing_collection)} Sammlungseinträge")
        if missing_decks:
            details.append(f"{len(missing_decks)} Deck-/Deckkarteneinträge")
        raise AccountApiError(
            "Der Serverstand wurde heruntergeladen, konnte aber nicht vollständig in die lokale Datenbank übernommen werden "
            f"({', '.join(details)}). Aus Sicherheitsgründen wird NICHT zum Server zurück synchronisiert."
        )

    _prune_local_to_remote(database, normalized, wanted_keys)
    # Verify once more after the authoritative prune.
    missing_collection, missing_decks = _verify_remote_materialized(database, normalized)
    if missing_collection or missing_decks:
        raise AccountApiError(
            "Lokale Prüfung nach dem Konto-Import ist fehlgeschlagen. Der Serverstand bleibt unverändert; automatische Synchronisierung wurde blockiert."
        )
    return {"collection": collection_report, "decks": deck_report}

def load_windows_account(
    database: Any,
    token: str,
    *,
    client: JustInCardAccountClient | None = None,
    base_path: Path | None = None,
) -> dict[str, Any]:
    """Restore the account snapshot immediately after login.

    A populated server snapshot is downloaded *before* any local upload can
    happen. This prevents a fresh Windows installation or an unrelated local
    database from overwriting the user's account on first login. If the server
    account is completely empty, the current local collection/decks are used as
    the initial account snapshot instead.
    """
    if not token:
        raise AccountApiError("Nicht mit einem Just-InCard-Konto angemeldet.", status=401, code="unauthorized")
    api = client or JustInCardAccountClient()
    path = base_path or default_base_path()
    database.set_setting(RESTORE_READY_SETTING, False)
    revision, remote = api.get_snapshot(token)
    remote = normalize_payload(remote)
    has_remote = bool(remote["collection"] or remote["decks"])

    if has_remote:
        report = replace_windows_from_payload(database, remote)
        _save_base(path, remote)
        database.set_setting(RESTORE_READY_SETTING, True)
        database.set_setting(LAST_SYNC_SETTING, time.strftime("%Y-%m-%d %H:%M:%S"))
        return {
            "revision": revision,
            "collection": len(remote["collection"]),
            "decks": len(remote["decks"]),
            "report": report,
            "mode": "downloaded",
        }

    local = windows_snapshot(database)
    # A brand-new empty account should not erase useful local data. Seed the
    # server from the device only when the remote account has no data at all.
    if local["collection"] or local["decks"]:
        new_revision = api.put_snapshot(token, local, revision, windows_device_name())
        _save_base(path, local)
        database.set_setting(RESTORE_READY_SETTING, True)
        database.set_setting(LAST_SYNC_SETTING, time.strftime("%Y-%m-%d %H:%M:%S"))
        return {
            "revision": new_revision,
            "collection": len(local["collection"]),
            "decks": len(local["decks"]),
            "report": {"collection": {"applied": 0, "skipped": 0}, "decks": {"applied": 0, "skipped": 0}},
            "mode": "seeded",
        }

    _save_base(path, remote)
    database.set_setting(RESTORE_READY_SETTING, True)
    database.set_setting(LAST_SYNC_SETTING, time.strftime("%Y-%m-%d %H:%M:%S"))
    return {
        "revision": revision,
        "collection": 0,
        "decks": 0,
        "report": {"collection": {"applied": 0, "skipped": 0}, "decks": {"applied": 0, "skipped": 0}},
        "mode": "empty",
    }


def sync_windows_account(
    database: Any,
    token: str,
    *,
    client: JustInCardAccountClient | None = None,
    base_path: Path | None = None,
) -> dict[str, Any]:
    if not token:
        raise AccountApiError("Nicht mit einem Just-InCard-Konto angemeldet.", status=401, code="unauthorized")
    if not bool(database.get_setting(RESTORE_READY_SETTING, False)):
        raise AccountApiError(
            "Der Konto-Stand wurde auf diesem Gerät noch nicht sicher geladen. Bitte zuerst 'Konto laden' bzw. erneut anmelden; es wird nichts zum Server hochgeladen.",
            code="restore_required",
        )
    api = client or JustInCardAccountClient()
    path = base_path or default_base_path()
    local = windows_snapshot(database)
    base = _load_base(path)
    revision, remote = api.get_snapshot(token)
    merged = merge_payloads(base, local, remote)
    try:
        new_revision = api.put_snapshot(token, merged, revision, windows_device_name())
    except AccountApiError as exc:
        if exc.status != 409:
            raise
        # One bounded retry against the newest server revision.
        revision, remote = api.get_snapshot(token)
        merged = merge_payloads(base, local, remote)
        new_revision = api.put_snapshot(token, merged, revision, windows_device_name())
    report = replace_windows_from_payload(database, merged)
    _save_base(path, merged)
    database.set_setting(LAST_SYNC_SETTING, time.strftime("%Y-%m-%d %H:%M:%S"))
    return {
        "revision": new_revision,
        "collection": len(merged["collection"]),
        "decks": len(merged["decks"]),
        "report": report,
    }

def force_upload_windows_account(
    database: Any,
    token: str,
    *,
    client: JustInCardAccountClient | None = None,
    base_path: Path | None = None,
) -> dict[str, Any]:
    """Replace the complete remote account snapshot with this device's local state.

    This is deliberately destructive and is only called from an explicit UI
    action that requires user confirmation. Unlike normal synchronisation,
    rows/decks missing locally are intentionally removed from the server.
    """
    if not token:
        raise AccountApiError("Nicht mit einem Just-InCard-Konto angemeldet.", status=401, code="unauthorized")
    api = client or JustInCardAccountClient()
    path = base_path or default_base_path()
    local = normalize_payload(windows_snapshot(database))
    revision, _remote = api.get_snapshot(token)
    try:
        new_revision = api.put_snapshot(
            token, local, revision, windows_device_name(), force_replace=True
        )
    except AccountApiError as exc:
        if exc.status != 409:
            raise
        # If another device changed the snapshot between GET and PUT, refresh
        # the revision exactly once. The explicit action still means: local
        # state is authoritative.
        revision, _remote = api.get_snapshot(token)
        new_revision = api.put_snapshot(
            token, local, revision, windows_device_name(), force_replace=True
        )

    _save_base(path, local)
    database.set_setting(RESTORE_READY_SETTING, True)
    database.set_setting(LAST_SYNC_SETTING, time.strftime("%Y-%m-%d %H:%M:%S"))
    return {
        "revision": new_revision,
        "collection": len(local["collection"]),
        "decks": len(local["decks"]),
        "mode": "force_uploaded",
    }

