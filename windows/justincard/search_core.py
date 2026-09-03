from __future__ import annotations

import json
import re
from typing import Any

from justincard.utils import normalize_text, set_search_parts

# Print-language/region markers that occur in Yu-Gi-Oh! set codes.
# Values are the language keys used by the local Windows database where possible.
SET_LANGUAGE_ALIASES = {
    "DE": "de", "G": "de",
    "EN": "en", "E": "en",
    "FR": "fr", "F": "fr",
    "IT": "it", "I": "it",
    "PT": "pt", "P": "pt",
    "ES": "es", "SP": "es", "S": "es",
    "JP": "ja", "JA": "ja", "J": "ja",
    "KR": "ko", "KO": "ko", "K": "ko",
    "CN": "zh", "SC": "zh", "TC": "zh-tw",
    "NL": "nl", "PL": "pl", "RU": "ru", "TR": "tr",
}


LANGUAGE_TO_SET_MARKER = {
    "de": "DE",
    "en": "EN",
    "fr": "FR",
    "it": "IT",
    "pt": "PT",
    "es": "ES",
    "ja": "JP",
    "ko": "KR",
    "zh": "SC",
    "zh-tw": "TC",
    "nl": "NL",
    "pl": "PL",
    "ru": "RU",
    "tr": "TR",
}

_SET_MARKER_PATTERN = re.compile(
    r"(?:^|-)(DE|EN|FR|IT|PT|ES|SP|JP|JA|KR|KO|CN|SC|TC|NL|PL|RU|TR|[GEFIPSJK])(?=-?\d|$)",
    re.IGNORECASE,
)

DISPLAY_LANGUAGES = [
    ("all", "Alle installierten Sprachen"),
    ("auto", "Automatisch aus Set-Code"),
    ("de", "Deutsch"),
    ("en", "Englisch"),
    ("fr", "Französisch"),
    ("it", "Italienisch"),
    ("pt", "Portugiesisch"),
    ("es", "Spanisch"),
    ("ja", "Japanisch"),
    ("ko", "Koreanisch"),
    ("zh", "Chinesisch (vereinfacht)"),
    ("zh-tw", "Chinesisch (traditionell)"),
    ("nl", "Niederländisch"),
    ("pl", "Polnisch"),
    ("ru", "Russisch"),
    ("tr", "Türkisch"),
]


def _installed_language_codes(database: Any) -> set[str]:
    try:
        rows = database.installed_languages()
    except Exception:
        return set()
    found: set[str] = set()
    for row in rows or []:
        if isinstance(row, dict):
            value = row.get("language")
        else:
            try:
                value = row["language"]
            except Exception:
                value = row[0] if isinstance(row, (tuple, list)) and row else None
        if value:
            found.add(str(value).strip().lower())
    return found


def infer_set_language(value: str) -> str:
    """Infer a print language from canonical and legacy Yu-Gi-Oh! set codes."""
    raw = str(value or "").strip().upper().replace("_", "-")
    if not raw:
        return ""

    # Reuse the application's own parser first. It knows localized/legacy markers.
    try:
        _prefix, parsed_language, _number = set_search_parts(raw)
        parsed_language = str(parsed_language or "").strip().lower()
        if parsed_language:
            return parsed_language
    except Exception:
        pass

    # Canonical forms such as BLMR-DE024, LOB-EN001, ABC-TC012.
    match = re.search(
        r"(?:^|-)(DE|EN|FR|IT|PT|ES|SP|JP|JA|KR|KO|CN|SC|TC|NL|PL|RU|TR)(?=-?\d|$)",
        raw,
    )
    if match:
        return SET_LANGUAGE_ALIASES.get(match.group(1), "")

    # Legacy one-letter language markers such as LOB-G001 / LOB-E001.
    legacy = re.search(r"(?:^|-)([GEFIPSJK])(?=\d{1,5}$)", raw)
    if legacy:
        return SET_LANGUAGE_ALIASES.get(legacy.group(1), "")
    return ""


def _set_marker(value: str) -> str:
    raw = str(value or "").strip().upper().replace("_", "-")
    match = _SET_MARKER_PATTERN.search(raw)
    return str(match.group(1) or "").upper() if match else ""


def is_set_code_query(value: str) -> bool:
    raw, prefix, _language, number = _set_query_parts(value)
    if not raw or not prefix:
        return False
    if re.fullmatch(r"\d+", raw.replace("-", "")):
        return False
    if not re.search(r"[A-Z]", prefix):
        return False
    # A marker or a print number is a strong signal that this is a set code,
    # not a human-readable set name. Plain prefixes such as BLMR are accepted
    # as set-code searches too.
    return bool(_set_marker(raw) or number or re.fullmatch(r"[A-Z0-9]{2,12}", prefix))


def english_set_query(value: str) -> str:
    """Normalize any Yu-Gi-Oh! set-code query to its EN reference form.

    Examples: BLMR-DE001 -> BLMR-EN001, CORI-FR -> CORI-EN.
    Non set-code text (for example a card/set name) is returned unchanged.
    """
    raw, prefix, language, number = _set_query_parts(value)
    if not raw or not prefix or not is_set_code_query(raw):
        return str(value or "").strip()
    if number:
        return f"{prefix}-EN{number}"
    # Prefix-only set searches are intentionally pinned to the EN row.
    return f"{prefix}-EN"


def requested_collection_language(value: str) -> str:
    """Language that should be stored in the collection for a set query."""
    if not is_set_code_query(value):
        return ""
    return infer_set_language(value) or "en"


def localized_collection_print(
    card: dict[str, Any],
    print_item: dict[str, Any] | None,
    original_set_query: str,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Return collection-safe copies after an EN reference search.

    Search results always come from the English card row.  When the user typed
    a localized set code, we keep that requested language for the physical
    collection entry without mutating the shared search result object.
    """
    card_copy = dict(card or {})
    selected = dict(print_item) if isinstance(print_item, dict) else None
    language = requested_collection_language(original_set_query)
    if not language:
        return card_copy, selected

    card_copy["_language"] = language
    card_copy["_reference_language"] = "en"

    if selected is None:
        return card_copy, None

    selected_code = str(selected.get("set_code") or "").strip().upper()
    _selected_raw, selected_prefix, _selected_language, selected_number = _set_query_parts(selected_code)
    query_raw, query_prefix, _query_language, query_number = _set_query_parts(original_set_query)
    marker = _set_marker(query_raw) or LANGUAGE_TO_SET_MARKER.get(language, "EN")

    if selected_prefix:
        # Full input codes retain the user's exact language marker. Prefix-only
        # inputs apply that marker to the selected English print number.
        number = selected_number or query_number
        if number:
            selected["set_code"] = f"{selected_prefix}-{marker}{number}"
        elif query_prefix:
            selected["set_code"] = f"{selected_prefix}-{marker}"
    selected["_language"] = language
    selected["_reference_set_code"] = selected_code
    return card_copy, selected


def effective_language(database: Any, filters: Any) -> tuple[str, str]:
    """Return (effective language, explanatory note).

    Set-code searches always use the English card row as the canonical
    reference.  The originally typed language is preserved separately when the
    card is added to the collection.  Non set-code searches keep the normal
    language-filter behavior.
    """
    installed = _installed_language_codes(database)
    requested = str(getattr(filters, "language", "all") or "all").strip().lower()
    set_query = str(getattr(filters, "set_query", "") or "").strip()
    quick = str(getattr(filters, "quick_text", "") or "").strip()

    code_query = set_query if is_set_code_query(set_query) else (quick if is_set_code_query(quick) else "")
    if code_query:
        original_language = infer_set_language(code_query) or "en"
        if not installed or "en" in installed:
            return "en", (
                f"Set-Code wird über EN referenziert; Sammlungs-Sprache bleibt {original_language.upper()}."
            )
        # Extremely defensive fallback for an incomplete local database.
        return "all", (
            "Englische Referenzdaten sind lokal nicht installiert; "
            "die Set-Suche wird ersatzweise sprachübergreifend ausgeführt."
        )

    if requested in ("", "all", "auto"):
        return "all", ""
    if installed and requested not in installed:
        return "all", (
            f"Sprache {requested.upper()} ist nicht lokal installiert; "
            "es wird über alle vorhandenen Sprachdaten gesucht."
        )
    return requested, ""

def _like(value: str) -> str:
    value = str(value or "")
    value = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{value}%"


def _set_query_parts(value: str) -> tuple[str, str, str, str]:
    """Return (raw, prefix, language, number) for loose set searches.

    The desktop database can contain localized card rows whose ``card_sets``
    payload still uses another print-language marker.  Therefore a query such
    as ``CORI-DE`` must be treated as *set CORI + German card row*, not only as
    the literal text ``CORI-DE``.  Full codes such as ``CORI-DE005`` are also
    reduced to a language-neutral prefix/number signature.
    """
    raw = str(value or "").strip().upper().replace("_", "-").replace("/", "-")
    raw = re.sub(r"\s+", "", raw)
    raw = re.sub(r"-+", "-", raw)
    if not raw:
        return "", "", "", ""

    prefix = language = number = ""
    try:
        parsed_prefix, parsed_language, parsed_number = set_search_parts(raw)
        prefix = str(parsed_prefix or "").strip().upper()
        language = str(parsed_language or "").strip().lower()
        number = str(parsed_number or "").strip().upper()
    except Exception:
        pass

    # Defensive parser for recovered/older utility implementations.
    if not prefix:
        match = re.fullmatch(
            r"([A-Z0-9]{2,12})(?:-(DE|EN|FR|IT|PT|ES|SP|JP|JA|KR|KO|CN|SC|TC|NL|PL|RU|TR|[GEFIPSJK]))?(?:-?([A-Z]{0,2}\d{1,5}[A-Z]?))?",
            raw,
        )
        if match:
            prefix = match.group(1) or ""
            marker = match.group(2) or ""
            number = match.group(3) or ""
            language = SET_LANGUAGE_ALIASES.get(marker, language)

    # ``set_search_parts`` may include non-numeric decorations in the number.
    # Keep them because some product codes contain leading letters.
    return raw, prefix, language, number


def _set_match(database: Any, value: str, alias: str = "c") -> tuple[str, list[Any]]:
    """Build a language-neutral, prefix-aware set matcher.

    Important behavior:
    - ``CORI-DE`` matches every German CORI card, even if the API payload on
      the German row stores ``CORI-ENxxx`` as its card-set code.
    - ``CORI-DE005`` matches via the language-neutral print signature and can
      therefore resolve the same physical print number across localized rows.
    - Set names continue to work through ``set_blob``.
    - Search is case-insensitive and accepts partial prefixes.

    We intentionally do not delegate exclusively to the recovered database
    helper here: older builds required a complete print number in several
    language-code paths, which is exactly why prefix queries like CORI-DE
    could return no result.
    """
    search_value = english_set_query(value) if is_set_code_query(value) else value
    raw, prefix, _language, number = _set_query_parts(search_value)
    normalized = normalize_text(value)

    parts: list[str] = []
    params: list[Any] = []

    # Literal search first. This preserves set-name searches and exact codes.
    if raw:
        literal = _like(raw)
        parts.extend([
            f"UPPER({alias}.set_codes) LIKE ? ESCAPE '\\'",
            f"UPPER({alias}.set_blob) LIKE ? ESCAPE '\\'",
        ])
        params.extend([literal, literal])

    # Human-readable set names in set_blob are not canonical set codes.
    if normalized:
        parts.append(f"LOWER({alias}.set_blob) LIKE ? ESCAPE '\\'")
        params.append(_like(normalized))

    if prefix:
        prefix_upper = prefix.upper()
        if number:
            # Canonical language-neutral signatures used by current builds are
            # PREFIX:NUMBER.  Older/recovered databases may use PREFIX-NUMBER,
            # so support both plus a conservative set-code fallback.
            signature_colon = _like(f"{prefix_upper}:{number}")
            signature_dash = _like(f"{prefix_upper}-{number}")
            code_number = f"%{prefix_upper}-%{number}%"
            parts.extend([
                f"UPPER({alias}.set_signatures) LIKE ? ESCAPE '\\'",
                f"UPPER({alias}.set_signatures) LIKE ? ESCAPE '\\'",
                f"UPPER({alias}.set_codes) LIKE ? ESCAPE '\\'",
                f"UPPER({alias}.set_blob) LIKE ? ESCAPE '\\'",
            ])
            params.extend([signature_colon, signature_dash, code_number, code_number])
        else:
            # Prefix-only queries (CORI, CORI-DE, CORI-EN, ...) must not depend
            # on the language marker contained in card_sets.  The row-language
            # restriction is applied separately by effective_language().
            code_prefix = _like(f"{prefix_upper}-")
            signature_prefix_colon = _like(f"{prefix_upper}:")
            signature_prefix_dash = _like(f"{prefix_upper}-")
            parts.extend([
                f"UPPER({alias}.set_codes) LIKE ? ESCAPE '\\'",
                f"UPPER({alias}.set_signatures) LIKE ? ESCAPE '\\'",
                f"UPPER({alias}.set_signatures) LIKE ? ESCAPE '\\'",
                f"UPPER({alias}.set_blob) LIKE ? ESCAPE '\\'",
            ])
            params.extend([code_prefix, signature_prefix_colon, signature_prefix_dash, code_prefix])

    # Keep the old helper only as an additional compatibility route.
    helper = getattr(database, "_set_match_any_language_sql", None)
    if callable(helper):
        try:
            helper_sql, helper_params = helper(value, alias)
            if helper_sql:
                parts.append(f"({str(helper_sql)})")
                params.extend(list(helper_params))
        except Exception:
            # Search must keep working even if an older helper cannot parse a
            # new/current set code.
            pass

    if not parts:
        return "0=1", []
    return "(" + " OR ".join(parts) + ")", params


def _decode_row(database: Any, row: Any) -> dict[str, Any]:
    decoder = getattr(database, "_decode_card_row", None)
    if callable(decoder):
        return decoder(row)
    data = dict(row)
    payload = json.loads(data.get("raw_json") or "{}")
    payload["_card_key"] = data.get("card_key", "")
    payload["_language"] = data.get("language", "")
    payload["_owned"] = int(data.get("owned") or 0)
    payload["_price_min"] = data.get("price_min")
    return payload


def search_cards(database: Any, filters: Any) -> tuple[list[dict[str, Any]], str]:
    """Run one deterministic SQL search where every UI filter is applied.

    All active filters are AND-combined. Text fields are partial and
    case-insensitive through normalized database columns. Set queries are
    language-neutral and can override the displayed card language based on the
    language encoded in the print code.
    """
    clauses: list[str] = ["1=1"]
    params: list[Any] = []

    language, language_note = effective_language(database, filters)
    if language != "all":
        clauses.append("LOWER(c.language)=?")
        params.append(language.lower())

    quick = str(getattr(filters, "quick_text", "") or "").strip()
    if quick:
        digits = re.sub(r"\D", "", quick)
        if len(digits) == 8 and re.fullmatch(r"[\d\s-]+", quick):
            clauses.append("c.card_id=?")
            params.append(int(digits))
        else:
            qn = normalize_text(quick)
            set_sql, set_params = _set_match(database, quick, "c")
            clauses.append(
                "(c.name_norm LIKE ? ESCAPE '\\' "
                "OR c.effect_norm LIKE ? ESCAPE '\\' "
                "OR c.archetype_norm LIKE ? ESCAPE '\\' "
                "OR LOWER(c.rarity_blob) LIKE LOWER(?) ESCAPE '\\' "
                f"OR {set_sql})"
            )
            params.extend([_like(qn), _like(qn), _like(qn), _like(quick)])
            params.extend(set_params)

    text_fields = (
        ("name", "c.name_norm", True),
        ("effect", "c.effect_norm", True),
        ("archetype", "c.archetype_norm", True),
        ("rarity", "c.rarity_blob", False),
    )
    for attr, column, normalized in text_fields:
        value = str(getattr(filters, attr, "") or "").strip()
        if value:
            if normalized:
                clauses.append(f"{column} LIKE ? ESCAPE '\\'")
                params.append(_like(normalize_text(value)))
            else:
                clauses.append(f"LOWER({column}) LIKE LOWER(?) ESCAPE '\\'")
                params.append(_like(value))

    passcode = re.sub(r"\D", "", str(getattr(filters, "passcode", "") or ""))
    if passcode:
        if len(passcode) == 8:
            clauses.append("c.card_id=?")
            params.append(int(passcode))
        else:
            clauses.append("CAST(c.card_id AS TEXT) LIKE ?")
            params.append(f"%{passcode}%")

    set_query = str(getattr(filters, "set_query", "") or "").strip()
    if set_query:
        set_sql, set_params = _set_match(database, set_query, "c")
        clauses.append(set_sql)
        params.extend(set_params)

    category = str(getattr(filters, "category", "all") or "all").lower()
    category_sql = {
        "monster": "c.card_type LIKE '%Monster%'",
        "spell": "c.card_type='Spell Card'",
        "trap": "c.card_type='Trap Card'",
        "extra": "(c.card_type LIKE '%Fusion%' OR c.card_type LIKE '%Synchro%' OR c.card_type LIKE '%XYZ%' OR c.card_type LIKE '%Xyz%' OR c.card_type LIKE '%Link%')",
        "pendulum": "(c.card_type LIKE '%Pendulum%' OR c.scale IS NOT NULL)",
        "skill": "c.card_type='Skill Card'",
        "token": "c.card_type='Token'",
    }
    if category in category_sql:
        clauses.append(category_sql[category])

    for attr, column in (
        ("card_type", "c.card_type"),
        ("race", "c.race"),
        ("attribute", "c.attribute"),
    ):
        value = str(getattr(filters, attr, "all") or "all").strip()
        if value and value.lower() != "all":
            clauses.append(f"LOWER({column})=LOWER(?)")
            params.append(value)

    format_name = str(getattr(filters, "format_name", "all") or "all").strip()
    if format_name and format_name.lower() != "all":
        clauses.append("LOWER(c.formats) LIKE LOWER(?) ESCAPE '\\'")
        params.append(_like(format_name))

    ban_status = str(getattr(filters, "ban_status", "all") or "all").strip()
    if ban_status and ban_status.lower() != "all":
        if ban_status == "allowed":
            clauses.append("COALESCE(c.ban_tcg, '')='' ")
        else:
            clauses.append("LOWER(COALESCE(c.ban_tcg,''))=LOWER(?)")
            params.append(ban_status)

    for prefix, column in (
        ("atk", "c.atk"),
        ("def", "c.def"),
        ("level", "c.level"),
        ("scale", "c.scale"),
        ("link", "c.linkval"),
    ):
        minimum = getattr(filters, f"{prefix}_min", None)
        maximum = getattr(filters, f"{prefix}_max", None)
        if minimum is not None:
            clauses.append(f"{column}>=?")
            params.append(minimum)
        if maximum is not None:
            clauses.append(f"{column}<=?")
            params.append(maximum)

    for marker in tuple(getattr(filters, "link_markers", ()) or ()):
        clauses.append("c.linkmarkers LIKE ? ESCAPE '\\'")
        params.append(_like(str(marker)))

    if bool(getattr(filters, "pendulum_only", False)):
        clauses.append("(c.card_type LIKE '%Pendulum%' OR c.scale IS NOT NULL)")
    if bool(getattr(filters, "alternative_artwork_only", False)):
        clauses.append("c.artwork_count>1")

    price_min = getattr(filters, "price_min", None)
    price_max = getattr(filters, "price_max", None)
    if price_min is not None:
        clauses.append("c.price_min>=?")
        params.append(price_min)
    if price_max is not None:
        clauses.append("c.price_min<=?")
        params.append(price_max)

    owned_state = str(getattr(filters, "owned_state", "all") or "all")
    if owned_state == "owned":
        clauses.append("COALESCE(o.owned,0)>0")
    elif owned_state == "missing":
        clauses.append("COALESCE(o.owned,0)=0")

    condition = str(getattr(filters, "condition", "all") or "all")
    if condition and condition.lower() != "all":
        clauses.append("EXISTS(SELECT 1 FROM collection cc WHERE cc.card_id=c.card_id AND LOWER(cc.condition)=LOWER(?))")
        params.append(condition)

    min_quantity = getattr(filters, "min_quantity", None)
    if min_quantity is not None:
        clauses.append("COALESCE(o.owned,0)>=?")
        params.append(min_quantity)

    order_map = {
        "name_asc": "c.name_norm ASC, c.language ASC",
        "name_desc": "c.name_norm DESC, c.language ASC",
        "atk_desc": "c.atk IS NULL, c.atk DESC, c.name_norm ASC",
        "def_desc": "c.def IS NULL, c.def DESC, c.name_norm ASC",
        "level_desc": "c.level IS NULL, c.level DESC, c.name_norm ASC",
        "type_asc": "c.card_type ASC, c.name_norm ASC",
        "newest": "c.updated_at DESC, c.name_norm ASC",
        "owned_desc": "owned DESC, c.name_norm ASC",
        "price_asc": "c.price_min IS NULL, c.price_min ASC, c.name_norm ASC",
        "price_desc": "c.price_min IS NULL, c.price_min DESC, c.name_norm ASC",
    }
    sort_by = str(getattr(filters, "sort_by", "name_asc") or "name_asc")
    order_by = order_map.get(sort_by, order_map["name_asc"])
    limit = max(1, min(5000, int(getattr(filters, "limit", 250) or 250)))

    sql = f"""
        SELECT c.*, COALESCE(o.owned, 0) AS owned
        FROM cards c
        LEFT JOIN (
            SELECT card_id, SUM(quantity) AS owned
            FROM collection
            GROUP BY card_id
        ) o ON o.card_id=c.card_id
        WHERE {' AND '.join(clauses)}
        ORDER BY {order_by}
        LIMIT ?
    """
    params.append(limit)

    with database.connect() as connection:
        rows = connection.execute(sql, params).fetchall()
    return [_decode_row(database, row) for row in rows], language_note
