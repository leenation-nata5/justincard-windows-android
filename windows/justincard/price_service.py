from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import re
import threading
import time
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

YGOPRODECK_URL = "https://db.ygoprodeck.com/api/v7/cardinfo.php"
FRANKFURTER_RATE_URL = "https://api.frankfurter.dev/v2/rate/USD/EUR?providers=ECB"

# YGOPRODeck exposes translated endpoints for exactly these languages.
YGOPRODECK_LANGUAGES = {"en", "de", "fr", "it", "pt"}

# Conditions follow the Cardmarket scale.  YGOPRODeck does not provide
# condition-specific market prices, so these values deliberately remain a
# transparent estimate around the selected print's live/reference price.
CONDITION_FACTORS: dict[str, float] = {
    "mint": 1.04,
    "m": 1.04,
    "near mint": 1.00,
    "nm": 1.00,
    "excellent": 0.90,
    "ex": 0.90,
    "good": 0.80,
    "gd": 0.80,
    "light played": 0.70,
    "light-played": 0.70,
    "lp": 0.70,
    "played": 0.55,
    "pl": 0.55,
    "poor": 0.35,
    "po": 0.35,
    "unbewertet": 1.00,
    "": 1.00,
}

_CACHE_LOCK = threading.Lock()
_CARD_CACHE: dict[tuple[int, str], tuple[float, dict[str, Any]]] = {}
_RATE_CACHE: tuple[float, float] | None = None
CACHE_SECONDS = 6 * 60 * 60


@dataclass(frozen=True)
class PriceEstimate:
    amount_eur: float | None
    print_price_usd: float | None
    cardmarket_floor_eur: float | None
    condition_factor: float
    requested_language: str
    resolved_language: str
    print_code: str
    rarity: str
    condition: str
    source: str
    note: str
    timestamp: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "amount_eur": self.amount_eur,
            "print_price_usd": self.print_price_usd,
            "cardmarket_floor_eur": self.cardmarket_floor_eur,
            "condition_factor": self.condition_factor,
            "requested_language": self.requested_language,
            "resolved_language": self.resolved_language,
            "print_code": self.print_code,
            "rarity": self.rarity,
            "condition": self.condition,
            "source": self.source,
            "note": self.note,
            "timestamp": self.timestamp,
        }


def _float(value: Any) -> float | None:
    try:
        result = float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _canonical_print(value: str) -> tuple[str, str]:
    text = str(value or "").strip().upper().replace("_", "-")
    # PREFIX-DE123, PREFIX-EN123, PREFIX-123 -> (PREFIX, 123)
    match = re.match(r"^([A-Z0-9]{2,12})-(?:(?:EN|DE|FR|IT|PT|ES|JP|JA|KO|KR|TC|SC)-?)?([A-Z0-9]+)$", text)
    if match:
        return match.group(1), match.group(2)
    match = re.match(r"^([A-Z0-9]{2,12})-(?:EN|DE|FR|IT|PT|ES|JP|JA|KO|KR|TC|SC)([A-Z0-9]+)$", text)
    if match:
        return match.group(1), match.group(2)
    parts = text.split("-", 1)
    return (parts[0], parts[1] if len(parts) > 1 else "")


def _print_match_score(candidate: str, requested: str) -> int:
    cand = str(candidate or "").strip().upper()
    req = str(requested or "").strip().upper()
    if not cand or not req:
        return 0
    if cand == req:
        return 100
    cp, cn = _canonical_print(cand)
    rp, rn = _canonical_print(req)
    if cp == rp and cn and rn and cn == rn:
        return 90
    if cp == rp and req.startswith(rp + "-"):
        return 60
    return 0


def _language_code(value: str) -> tuple[str, str]:
    requested = str(value or "en").strip().lower().replace("_", "-")
    aliases = {
        "german": "de", "deutsch": "de", "ger": "de",
        "english": "en", "englisch": "en",
        "french": "fr", "französisch": "fr", "franzoesisch": "fr",
        "italian": "it", "italienisch": "it",
        "portuguese": "pt", "portugiesisch": "pt",
        "spanish": "es", "spanisch": "es",
        "japanese": "ja", "japanisch": "ja", "jp": "ja",
        "korean": "ko", "koreanisch": "ko",
    }
    requested = aliases.get(requested, requested.split("-")[0])
    resolved = requested if requested in YGOPRODECK_LANGUAGES else "en"
    return requested, resolved


def _condition_factor(condition: str) -> float:
    key = str(condition or "").strip().casefold()
    return CONDITION_FACTORS.get(key, 1.00)


def _request_json(url: str, timeout: float = 7.5) -> Any:
    request = Request(url, headers={"User-Agent": "JustInCard-Windows/1.2.6"})
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed trusted HTTPS endpoints
        return json.loads(response.read().decode("utf-8"))


def _fetch_card(card_id: int, language: str) -> dict[str, Any]:
    requested, resolved = _language_code(language)
    key = (int(card_id), resolved)
    now = time.time()
    with _CACHE_LOCK:
        cached = _CARD_CACHE.get(key)
        if cached and now - cached[0] < CACHE_SECONDS:
            return dict(cached[1])
    params = {"id": str(int(card_id))}
    if resolved != "en":
        params["language"] = resolved
    payload = _request_json(f"{YGOPRODECK_URL}?{urlencode(params)}")
    rows = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
        raise RuntimeError("YGOPRODeck lieferte keine Kartendaten.")
    card = dict(rows[0])
    with _CACHE_LOCK:
        _CARD_CACHE[key] = (now, card)
    return card


def _usd_to_eur() -> float:
    global _RATE_CACHE
    now = time.time()
    with _CACHE_LOCK:
        if _RATE_CACHE and now - _RATE_CACHE[0] < CACHE_SECONDS:
            return _RATE_CACHE[1]
    try:
        payload = _request_json(FRANKFURTER_RATE_URL, timeout=5.0)
        rate = _float(payload.get("rate") if isinstance(payload, dict) else None)
    except Exception:
        rate = None
    if rate is None:
        # Conservative offline fallback used only when the FX endpoint is not
        # reachable.  The UI explicitly labels the result as an estimate.
        rate = 0.88
    with _CACHE_LOCK:
        _RATE_CACHE = (now, rate)
    return rate


def _find_print(card: dict[str, Any], print_code: str, rarity: str = "") -> dict[str, Any] | None:
    candidates = [item for item in (card.get("card_sets") or []) if isinstance(item, dict)]
    if not candidates:
        return None
    requested_rarity = str(rarity or "").strip().casefold()
    ranked: list[tuple[int, dict[str, Any]]] = []
    for item in candidates:
        score = _print_match_score(str(item.get("set_code") or ""), print_code)
        if requested_rarity and str(item.get("set_rarity") or "").strip().casefold() == requested_rarity:
            score += 15
        ranked.append((score, item))
    ranked.sort(key=lambda pair: pair[0], reverse=True)
    return ranked[0][1] if ranked and ranked[0][0] > 0 else None


def estimate_price(
    card: dict[str, Any],
    *,
    print_code: str = "",
    rarity: str = "",
    language: str = "en",
    condition: str = "Near Mint",
    live: bool = True,
) -> PriceEstimate:
    """Estimate the selected physical print's value in EUR.

    The print/rarity reference price comes from YGOPRODeck's set_price.  Their
    API documents that value in USD.  It is converted to EUR with the current
    ECB reference rate through Frankfurter.  Cardmarket's aggregate card floor
    from YGOPRODeck is retained as a reference but is *not* falsely presented as
    print/condition specific.  Condition adjustment is a documented heuristic.
    """
    requested_lang, resolved_lang = _language_code(language)
    source_card = dict(card or {})
    card_id = source_card.get("id") or source_card.get("card_id")
    note_parts: list[str] = []

    if live and card_id:
        try:
            source_card = _fetch_card(int(card_id), requested_lang)
        except Exception as exc:
            note_parts.append(f"Live-Abruf nicht verfügbar ({type(exc).__name__}); lokale Daten verwendet.")

    selected = _find_print(source_card, print_code, rarity)
    print_price_usd = _float(selected.get("set_price")) if selected else None
    selected_code = str((selected or {}).get("set_code") or print_code or "")
    selected_rarity = str((selected or {}).get("set_rarity") or rarity or "")

    prices = source_card.get("card_prices") or []
    market_floor = None
    if isinstance(prices, list) and prices and isinstance(prices[0], dict):
        market_floor = _float(prices[0].get("cardmarket_price"))

    factor = _condition_factor(condition)
    amount_eur = None
    if market_floor is not None:
        # Cardmarket is the primary EUR market anchor. YGOPRODeck exposes this
        # public Cardmarket reference in card_prices. Because that value is a
        # card-wide floor rather than a print-specific quote, retain the
        # selected set/rarity relationship through a transparent relative
        # factor derived from the card's set_price values.
        print_factor = 1.0
        if print_price_usd is not None:
            available_set_prices = [
                price
                for price in (_float(item.get("set_price")) for item in (source_card.get("card_sets") or []) if isinstance(item, dict))
                if price is not None
            ]
            if available_set_prices:
                cheapest_print = min(available_set_prices)
                if cheapest_print > 0:
                    print_factor = max(0.25, min(25.0, print_price_usd / cheapest_print))
        amount_eur = round(market_floor * print_factor * factor, 2)
        note_parts.append(
            "Cardmarket-Referenzpreis (EUR) über YGOPRODeck; Set/Rarität wird relativ zur gewählten Druckausgabe geschätzt."
        )
    elif print_price_usd is not None:
        fx_rate = _usd_to_eur() if live else 0.88
        amount_eur = round(print_price_usd * fx_rate * factor, 2)
        note_parts.append(
            "Cardmarket-Referenz nicht verfügbar; YGOPRODeck set_price (USD) dient als Fallback und wird in EUR umgerechnet."
        )
    else:
        note_parts.append("Für diese Ausgabe wurde kein verwertbarer Preis geliefert.")

    if requested_lang != resolved_lang:
        note_parts.append(
            f"Für Sprache {requested_lang.upper()} bietet YGOPRODeck keine lokalisierte API; EN-Daten dienen als Fallback."
        )
    if factor != 1.0:
        note_parts.append(f"Zustand {condition}: transparenter Schätzfaktor {factor:.2f}.")
    note_parts.append("Zustandspreise sind Schätzwerte, keine einzelnen Live-Angebote von Cardmarket.")

    return PriceEstimate(
        amount_eur=amount_eur,
        print_price_usd=print_price_usd,
        cardmarket_floor_eur=market_floor,
        condition_factor=factor,
        requested_language=requested_lang,
        resolved_language=resolved_lang,
        print_code=selected_code,
        rarity=selected_rarity,
        condition=str(condition or "Near Mint"),
        source="Cardmarket-Referenz über YGOPRODeck + Set/Raritäts-Schätzung",
        note=" ".join(note_parts),
        timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


__all__ = ["PriceEstimate", "estimate_price", "CONDITION_FACTORS", "YGOPRODECK_LANGUAGES"]
