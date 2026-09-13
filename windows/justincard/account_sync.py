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
            "User-Agent": "JustInCard-Windows/1.3.2",
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

    def put_snapshot(self, token: str, payload: dict[str, Any], revision: int, device_name: str) -> int:
        data = self._request(
            "sync.php",
            method="POST",
            token=token,
            payload={
                "if_revision": int(revision),
                "source_device": device_name,
                "schema": ACCOUNT_SCHEMA,
                "payload": normalize_payload(payload),
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
            l_changed = not _same(l, b)
            r_changed = not _same(r, b)
            if not l_changed and not r_changed: chosen = b
            elif l_changed and not r_changed: chosen = l
            elif r_changed and not l_changed: chosen = r
            else:
                if l is None and r is None: chosen = None
                elif l is None: chosen = r  # concurrent delete/change -> keep changed data
                elif r is None: chosen = l
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
    return {"id": card_id, "name": str(rec.get("card_name") or f"Karte {card_id}"), "_language": language, "card_images": []}


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


def replace_windows_from_payload(database: Any, payload: dict[str, Any]) -> dict[str, Any]:
    collection, decks = _to_windows_cloud(database, payload)
    # Work on a full merged snapshot. Clearing before re-import makes remote
    # deletions deterministic and avoids quantity duplication on repeated sync.
    try:
        with database._write_lock:
            with database.connect() as connection:
                connection.execute("DELETE FROM deck_cards")
                connection.execute("DELETE FROM decks")
                connection.execute("DELETE FROM collection")
    except Exception as exc:
        raise AccountApiError(f"Lokale Daten konnten für den Kontoabgleich nicht vorbereitet werden: {exc}") from exc
    report = database.apply_cloud_collection(collection)
    deck_report = database.apply_cloud_decks(decks)
    return {"collection": report, "decks": deck_report}


def sync_windows_account(
    database: Any,
    token: str,
    *,
    client: JustInCardAccountClient | None = None,
    base_path: Path | None = None,
) -> dict[str, Any]:
    if not token:
        raise AccountApiError("Nicht mit einem Just-InCard-Konto angemeldet.", status=401, code="unauthorized")
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
