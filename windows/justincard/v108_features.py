from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import time
import tempfile
import zipfile
from typing import Any, Callable

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableView,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from justincard.version import APP_VERSION
from justincard.v123_core import resolved_deck_zone
from justincard.price_service import estimate_price

from justincard.v108_core import (
    CARD_INFORMATION_FIELDS,
    DEFAULT_VISIBILITY,
    VISIBILITY_SETTING_KEY,
    artwork_label,
    is_placeholder_item,
    normalize_backup_payload,
    normalize_visibility,
    placeholder_collection_key,
    record_value,
    sortable_value,
    visibility_preset,
)

_INSTALLED = False

CARD_COLUMNS = (
    ("name", "Name"),
    ("id", "Passcode"),
    ("language", "Sprache"),
    ("artwork", "Artwork / Alt Art"),
    ("type", "Kartentyp"),
    ("race", "Typ"),
    ("attribute", "Attribut"),
    ("atk", "ATK"),
    ("def", "DEF"),
    ("level", "Stufe/Rang"),
    ("scale", "Pendel-Skala"),
    ("link", "Linkwert"),
    ("sets", "Sets"),
    ("rarity", "Seltenheiten"),
    ("owned", "Besitz"),
    ("price", "Preis ab"),
    ("archetype", "Archetyp"),
    ("effect", "Effekt"),
)

COLLECTION_COLUMNS = (
    ("name", "Name"),
    ("print_code", "Set-Code"),
    ("set_name", "Set"),
    ("rarity", "Seltenheit"),
    ("language", "Sprache"),
    ("artwork", "Artwork / Alt Art"),
    ("quantity", "Menge"),
    ("added_at", "Hinzugefügt am"),
    ("condition", "Zustand"),
    ("market_value", "Geschätzter Marktwert"),
    ("id", "Passcode"),
    ("type", "Kartentyp"),
    ("race", "Typ"),
    ("attribute", "Attribut"),
    ("atk", "ATK"),
    ("def", "DEF"),
    ("level", "Stufe/Rang"),
    ("scale", "Pendel-Skala"),
    ("link", "Linkwert"),
    ("archetype", "Archetyp"),
    ("effect", "Effekt"),
)

DECK_COLUMNS = (
    ("zone", "Zone"),
    ("name", "Karte"),
    ("id", "Passcode"),
    ("quantity", "Anzahl"),
    ("artwork", "Artwork / Alt Art"),
    ("type", "Kartentyp"),
    ("race", "Typ"),
    ("attribute", "Attribut"),
    ("atk", "ATK"),
    ("def", "DEF"),
    ("level", "Stufe/Rang"),
    ("scale", "Pendel-Skala"),
    ("link", "Linkwert"),
    ("status", "Status"),
)

COLUMN_VISIBILITY = {
    "id": "passcode",
    "language": "language",
    "artwork": "artwork",
    "type": "card_type",
    "race": "race",
    "attribute": "attribute",
    "atk": "atk",
    "def": "def",
    "level": "level",
    "scale": "scale",
    "link": "link",
    "sets": "sets",
    "rarity": "rarity",
    "owned": "quantity",
    "price": "price",
    "archetype": "archetype",
    "effect": "effect",
    "print_code": "set_code",
    "set_name": "set_name",
    "quantity": "quantity",
    "condition": "condition",
    "market_value": "market_value",
    "status": "status",
}

NUMERIC_KEYS = {"id", "atk", "def", "level", "scale", "link", "owned", "quantity", "price", "market_value", "added_at"}


def _collection_card(record: dict[str, Any]) -> dict[str, Any]:
    card = record.get("card")
    if isinstance(card, dict):
        return card
    raw = record.get("card_json")
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            loaded = json.loads(raw)
            if isinstance(loaded, dict):
                return loaded
        except Exception:
            pass
    return record


def _estimated_market_value_eur(record: dict[str, Any]) -> float | None:
    if not isinstance(record, dict):
        return None
    card = _collection_card(record)
    if not isinstance(card, dict) or not card:
        return None
    try:
        estimate = estimate_price(
            card,
            print_code=str(record.get("print_code") or ""),
            rarity=str(record.get("rarity") or ""),
            language=str(record.get("language") or card.get("_language") or "en"),
            condition=str(record.get("condition") or "Near Mint"),
            live=False,
        )
        return estimate.amount_eur
    except Exception:
        return None


def _display_value(record: dict[str, Any], key: str, context: str) -> str:
    if context == "deck" and key == "zone":
        return {"main": "Main", "extra": "Extra", "side": "Side"}.get(str(record.get("zone") or "").lower(), str(record.get("zone") or ""))
    if context == "deck" and key == "status":
        return "Fehlt / Platzhalter" if is_placeholder_item(record) else "Vorhanden"
    if key == "artwork":
        return artwork_label(record, context)
    if context == "collection" and key == "market_value":
        value = _estimated_market_value_eur(record)
        return "–" if value is None else f"{value:.2f} €".replace(".", ",")
    if context == "card" and key == "rarity":
        card = record
        values: list[str] = []
        for item in card.get("card_sets") or []:
            if isinstance(item, dict):
                value = str(item.get("set_rarity") or "").strip()
                if value and value not in values:
                    values.append(value)
        return ", ".join(values) if values else "–"
    value = record_value(record, key, context)
    if key == "language":
        return str(value or "–").upper()
    if key in {"price", "market_value"}:
        if value in (None, "", "–"):
            return "–"
        try:
            return f"{float(value):.2f} €".replace(".", ",")
        except (TypeError, ValueError):
            return str(value)
    if key == "sets":
        return str(value or "–")
    if value in (None, ""):
        return "–"
    return str(value)


def _model_data(self: Any, index: Any, role: int, *, context: str, container: str) -> Any:
    if not index.isValid():
        return None
    rows = getattr(self, container, [])
    row = index.row()
    if row < 0 or row >= len(rows):
        return None
    record = rows[row]
    if not isinstance(record, dict):
        return None

    if role == Qt.UserRole:
        return record
    columns = getattr(self, "COLUMNS", ())
    column = index.column()
    if column < 0 or column >= len(columns):
        return None
    key = columns[column][0]

    if role == Qt.DisplayRole:
        return _display_value(record, key, context)
    if role == Qt.ToolTipRole:
        card = record.get("card") if isinstance(record.get("card"), dict) else record
        parts: list[str] = []
        if is_placeholder_item(record):
            parts.append("Platzhalter: Dieses Exemplar fehlt aktuell in der Sammlung.")
        desc = str(card.get("desc") or card.get("effect") or "").strip() if isinstance(card, dict) else ""
        note = str(record.get("note") or "").strip()
        if note:
            parts.append(note)
        if desc:
            parts.append(desc)
        return "\n\n".join(parts) if parts else None
    if role == Qt.TextAlignmentRole and key in NUMERIC_KEYS:
        return Qt.AlignCenter
    if context == "deck" and is_placeholder_item(record):
        if role == Qt.ForegroundRole:
            return QBrush(QColor("#78879d"))
        if role == Qt.FontRole:
            font = QFont()
            font.setItalic(True)
            return font
    return None


def _sort_model(self: Any, column: int, order: Qt.SortOrder, *, context: str, container: str) -> None:
    rows = getattr(self, container, None)
    columns = getattr(self, "COLUMNS", ())
    if not isinstance(rows, list) or not (0 <= int(column) < len(columns)):
        return
    key = columns[int(column)][0]
    self._jic_sort_column = int(column)
    self._jic_sort_order = order
    self.layoutAboutToBeChanged.emit()
    def row_sort_value(item: Any) -> tuple[int, Any]:
        if context == "deck" and key == "zone" and isinstance(item, dict):
            return (0, {"main": 0, "extra": 1, "side": 2}.get(str(item.get("zone") or "").lower(), 9))
        if context == "collection" and key == "market_value" and isinstance(item, dict):
            value = _estimated_market_value_eur(item)
            return (2, "") if value is None else (0, value)
        return sortable_value(item, key, context)

    rows.sort(
        key=row_sort_value,
        reverse=order == Qt.DescendingOrder,
    )
    self.layoutChanged.emit()


def _replace_rows(self: Any, values: Any, *, container: str, context: str) -> None:
    self.beginResetModel()
    setattr(self, container, list(values or []))
    self.endResetModel()
    column = getattr(self, "_jic_sort_column", None)
    order = getattr(self, "_jic_sort_order", Qt.AscendingOrder)
    if isinstance(column, int):
        QTimer.singleShot(0, lambda: _sort_model(self, column, order, context=context, container=container))


def _patch_models() -> None:
    from justincard.ui import widgets

    widgets.CardTableModel.COLUMNS = CARD_COLUMNS
    widgets.CollectionTableModel.COLUMNS = COLLECTION_COLUMNS
    widgets.DeckCardsTableModel.COLUMNS = DECK_COLUMNS

    widgets.CardTableModel.data = lambda self, index, role=Qt.DisplayRole: _model_data(self, index, role, context="card", container="cards")
    widgets.CollectionTableModel.data = lambda self, index, role=Qt.DisplayRole: _model_data(self, index, role, context="collection", container="items")
    widgets.DeckCardsTableModel.data = lambda self, index, role=Qt.DisplayRole: _model_data(self, index, role, context="deck", container="items")

    widgets.CardTableModel.sort = lambda self, column, order=Qt.AscendingOrder: _sort_model(self, column, order, context="card", container="cards")
    widgets.CollectionTableModel.sort = lambda self, column, order=Qt.AscendingOrder: _sort_model(self, column, order, context="collection", container="items")
    widgets.DeckCardsTableModel.sort = lambda self, column, order=Qt.AscendingOrder: _sort_model(self, column, order, context="deck", container="items")

    widgets.CardTableModel.set_cards = lambda self, values: _replace_rows(self, values, container="cards", context="card")
    widgets.CollectionTableModel.set_items = lambda self, values: _replace_rows(self, values, container="items", context="collection")
    widgets.DeckCardsTableModel.set_items = lambda self, values: _replace_rows(self, values, container="items", context="deck")

    original_detail_set_card = widgets.CardDetailPanel.set_card

    def detail_set_card(self: Any, card: dict[str, Any] | None, preferred_set_code: str = "") -> None:
        original_detail_set_card(self, card, preferred_set_code)
        if hasattr(self, "name"):
            self.name.setWordWrap(True)
            self.name.setMinimumWidth(0)
        _refresh_detail_panel(self)

    widgets.CardDetailPanel.set_card = detail_set_card


def _visibility_for_database(database: Any) -> dict[str, bool]:
    try:
        return normalize_visibility(database.get_setting(VISIBILITY_SETTING_KEY, DEFAULT_VISIBILITY))
    except Exception:
        return dict(DEFAULT_VISIBILITY)


def _column_context(model: Any) -> str:
    name = type(model).__name__
    if name == "CollectionTableModel":
        return "collection"
    if name == "DeckCardsTableModel":
        return "deck"
    return "card"


def _ensure_name_width(table: QTableView) -> None:
    model = table.model()
    if model is None:
        return
    columns = getattr(model, "COLUMNS", ())
    name_column = next((idx for idx, (key, _label) in enumerate(columns) if key == "name"), None)
    if name_column is None:
        return
    table.setColumnHidden(name_column, False)
    try:
        suggested = max(280, int(table.sizeHintForColumn(name_column)) + 28)
    except Exception:
        suggested = 320
    current = table.columnWidth(name_column)
    target = max(current, suggested)
    table._jic_min_name_width = target  # type: ignore[attr-defined]
    if current < target:
        table.setColumnWidth(name_column, target)


def _configure_table(table: QTableView, database: Any | None = None) -> None:
    if getattr(table, "_jic_v108_configured", False):
        if database is not None:
            _apply_table_visibility(table, _visibility_for_database(database))
        return
    table._jic_v108_configured = True  # type: ignore[attr-defined]
    table.setSortingEnabled(True)
    table.setTextElideMode(Qt.ElideNone)
    table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
    header = table.horizontalHeader()
    header.setSectionsClickable(True)
    header.setStretchLastSection(False)
    header.setMinimumSectionSize(46)
    header.setMaximumSectionSize(4096)
    header.setSectionResizeMode(QHeaderView.Interactive)

    def guard_name(logical: int, _old: int, new: int) -> None:
        model = table.model()
        columns = getattr(model, "COLUMNS", ()) if model is not None else ()
        if not (0 <= logical < len(columns)) or columns[logical][0] != "name":
            return
        minimum = int(getattr(table, "_jic_min_name_width", 0) or 0)
        if minimum and new < minimum:
            QTimer.singleShot(0, lambda: table.setColumnWidth(logical, minimum))

    header.sectionResized.connect(guard_name)
    if table.model() is not None:
        try:
            table.model().modelReset.connect(lambda: QTimer.singleShot(0, lambda: _ensure_name_width(table)))
        except Exception:
            pass
    QTimer.singleShot(0, lambda: _ensure_name_width(table))
    if database is not None:
        _apply_table_visibility(table, _visibility_for_database(database))


def _apply_table_visibility(table: QTableView, prefs: dict[str, bool], override: dict[str, bool] | None = None) -> None:
    model = table.model()
    if model is None:
        return
    columns = getattr(model, "COLUMNS", ())
    for index, (key, _label) in enumerate(columns):
        # added_at is intentionally a sort-only field. It appears in the
        # collection sort selector, but does not consume horizontal table space.
        if key == "added_at":
            visible = False
        elif key in {"name", "zone"}:
            visible = True
        else:
            setting = COLUMN_VISIBILITY.get(key)
            visible = True if setting is None else bool((override or prefs).get(setting, True))
        table.setColumnHidden(index, not visible)
    QTimer.singleShot(0, lambda: _ensure_name_width(table))


def _refresh_detail_panel(detail: Any) -> None:
    prefs = normalize_visibility(getattr(detail, "_jic_visibility", DEFAULT_VISIBILITY))
    card = getattr(detail, "card", None)
    if hasattr(detail, "name"):
        detail.name.setWordWrap(True)
    if not isinstance(card, dict):
        return
    pieces: list[str] = []
    if prefs.get("artwork", True):
        art_text = artwork_label(card, "card")
        if art_text and art_text != "–":
            pieces.append(art_text)
    if prefs.get("card_type", True) and card.get("type"):
        pieces.append(str(card.get("type")))
    if prefs.get("attribute", True) and card.get("attribute"):
        pieces.append(str(card.get("attribute")))
    if prefs.get("race", True) and card.get("race"):
        pieces.append(str(card.get("race")))
    stats: list[str] = []
    if prefs.get("atk", True) and card.get("atk") is not None:
        stats.append(f"ATK {card.get('atk')}")
    if prefs.get("def", True) and card.get("def") is not None:
        stats.append(f"DEF {card.get('def')}")
    if stats:
        pieces.append(" / ".join(stats))
    if prefs.get("link", True) and card.get("linkval") is not None:
        pieces.append(f"LINK-{card.get('linkval')}")
    elif prefs.get("level", True) and card.get("level") is not None:
        pieces.append(f"Stufe/Rang {card.get('level')}")
    if prefs.get("scale", True) and card.get("scale") is not None:
        pieces.append(f"Pendel-Skala {card.get('scale')}")
    if hasattr(detail, "meta"):
        detail.meta.setText("  •  ".join(pieces))
        detail.meta.setVisible(bool(pieces))
    if hasattr(detail, "effect"):
        show_effect = bool(prefs.get("effect", True))
        detail.effect.setVisible(show_effect)
        for label in detail.findChildren(QLabel):
            if label.text().strip() == "Kartentext":
                label.setVisible(show_effect)


def apply_visibility_to_window(window: QWidget, prefs: dict[str, bool] | None = None) -> None:
    database = getattr(window, "database", None)
    current = normalize_visibility(prefs if prefs is not None else (_visibility_for_database(database) if database is not None else DEFAULT_VISIBILITY))
    from justincard.ui.widgets import CardDetailPanel

    for table in window.findChildren(QTableView):
        model = table.model()
        if model is None or type(model).__name__ not in {"CardTableModel", "CollectionTableModel", "DeckCardsTableModel"}:
            continue
        _configure_table(table, database)
        override = getattr(table, "_jic_local_visibility_override", None)
        _apply_table_visibility(table, current, override)
    for label in window.findChildren(QLabel):
        if label.objectName() == "CardTitle":
            label.setWordWrap(True)
            label.setMinimumWidth(0)
    for detail in window.findChildren(CardDetailPanel):
        detail._jic_visibility = current  # type: ignore[attr-defined]
        _refresh_detail_panel(detail)


def _add_sort_bar(table: QTableView, label: str = "Sortieren") -> None:
    if getattr(table, "_jic_sort_bar", None) is not None:
        return
    parent = table.parentWidget()
    layout = parent.layout() if parent is not None else None
    if not isinstance(layout, QVBoxLayout):
        return
    row = QHBoxLayout()
    caption = QLabel(label)
    caption.setObjectName("Muted")
    combo = QComboBox()
    direction = QComboBox()
    model = table.model()
    for index, (_key, title) in enumerate(getattr(model, "COLUMNS", ())):
        combo.addItem(title, index)
    direction.addItem("Aufsteigend  A→Z / 0→9", "asc")
    direction.addItem("Absteigend  Z→A / 9→0", "desc")
    row.addWidget(caption)
    row.addWidget(combo, 1)
    row.addWidget(direction)
    idx = layout.indexOf(table)
    layout.insertLayout(max(0, idx), row)
    table._jic_sort_bar = (combo, direction)  # type: ignore[attr-defined]

    def apply_sort() -> None:
        column = int(combo.currentData())
        direction_token = str(direction.currentData() or "asc").strip().lower()
        order = Qt.DescendingOrder if direction_token == "desc" else Qt.AscendingOrder
        table.sortByColumn(column, order)

    combo.currentIndexChanged.connect(lambda _idx: apply_sort())
    direction.currentIndexChanged.connect(lambda _idx: apply_sort())


def _read_backup_payload(path: Path) -> Any:
    suffix = path.suffix.lower()
    if suffix in {".sqlite", ".sqlite3", ".db"}:
        connection = sqlite3.connect(path)
        connection.row_factory = sqlite3.Row
        try:
            tables = {str(row[0]) for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            payload: dict[str, Any] = {"format": "legacy-sqlite"}
            if "collection" in tables:
                payload["collection"] = [dict(row) for row in connection.execute("SELECT * FROM collection").fetchall()]
            if "decks" in tables:
                payload["decks"] = [dict(row) for row in connection.execute("SELECT * FROM decks").fetchall()]
            if "deck_cards" in tables:
                payload["deck_cards"] = [dict(row) for row in connection.execute("SELECT * FROM deck_cards").fetchall()]
            if "settings" in tables:
                settings: dict[str, Any] = {}
                for row in connection.execute("SELECT * FROM settings").fetchall():
                    data = dict(row)
                    key = str(data.get("key") or "")
                    raw = data.get("value_json", data.get("value"))
                    if not key:
                        continue
                    try:
                        settings[key] = json.loads(raw) if isinstance(raw, str) else raw
                    except Exception:
                        settings[key] = raw
                payload["settings"] = settings
            return payload
        finally:
            connection.close()
    if suffix == ".zip":
        with zipfile.ZipFile(path, "r") as archive:
            names = archive.namelist()
            preferred = next((name for name in names if name.lower().endswith("backup.json")), None)
            if preferred is None:
                preferred = next((name for name in names if name.lower().endswith("collection.json") or name.lower().endswith("sammlung.json")), None)
            if preferred is None:
                preferred = next((name for name in names if name.lower().endswith(".json")), None)
            if preferred is not None:
                return json.loads(archive.read(preferred).decode("utf-8-sig"))

            sqlite_name = next((
                name for name in names
                if name.lower().endswith((".sqlite3", ".sqlite", ".db"))
            ), None)
            if sqlite_name is not None:
                suffix = Path(sqlite_name).suffix or ".sqlite3"
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
                    handle.write(archive.read(sqlite_name))
                    temporary = Path(handle.name)
                try:
                    return _read_backup_payload(temporary)
                finally:
                    temporary.unlink(missing_ok=True)
            raise ValueError("Die ZIP-Sicherung enthält weder JSON- noch SQLite-Daten.")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _patch_database() -> None:
    from justincard.database import CardDatabase, DatabaseError

    original_init = CardDatabase.__init__
    original_add_deck_card = CardDatabase.add_deck_card
    original_deck_cards = CardDatabase.deck_cards
    original_validate_deck = CardDatabase.validate_deck

    def db_init(self: Any, path: Any) -> None:
        original_init(self, path)
        with self.connect() as connection:
            columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(deck_cards)").fetchall()}
            if "is_placeholder" not in columns:
                connection.execute("ALTER TABLE deck_cards ADD COLUMN is_placeholder INTEGER NOT NULL DEFAULT 0")
            if "source_collection_key" not in columns:
                connection.execute("ALTER TABLE deck_cards ADD COLUMN source_collection_key TEXT NOT NULL DEFAULT ''")
            collection_columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(collection)").fetchall()}
            if "wishlist" in collection_columns:
                connection.execute("UPDATE collection SET wishlist=0 WHERE wishlist<>0")
            if "trade" in collection_columns:
                connection.execute("UPDATE collection SET trade=0 WHERE trade<>0")
        try:
            self.set_metadata("schema_v108", "deck-placeholders-and-display-settings")
        except Exception:
            pass

    def add_deck_placeholder(self: Any, deck_id: str, collection_key: str, zone: str, card: dict[str, Any] | None = None) -> None:
        requested_zone = str(zone).lower()
        if requested_zone not in {"main", "extra", "side"}:
            raise DatabaseError("Ungültige Deck-Zone.")
        source_key = str(collection_key or "")
        card_id: int | None = None
        card_json: dict[str, Any] | None = card if isinstance(card, dict) else None
        with self._write_lock:
            with self.connect() as connection:
                if source_key:
                    row = connection.execute(
                        "SELECT card_id, card_json FROM collection WHERE collection_key=?",
                        (source_key,),
                    ).fetchone()
                    if row is not None:
                        card_id = int(row["card_id"]) if row["card_id"] is not None else None
                        try:
                            loaded = json.loads(row["card_json"])
                            if isinstance(loaded, dict):
                                card_json = loaded
                        except Exception:
                            pass
                if card_json is None:
                    raise DatabaseError("Für den Platzhalter fehlen die Kartendaten.")
                zone = resolved_deck_zone(card_json, requested_zone)
                if card_id is None:
                    try:
                        card_id = int(card_json.get("id"))
                    except (TypeError, ValueError):
                        card_id = None
                if card_id is None:
                    raise DatabaseError("Für den Platzhalter fehlt der Karten-Passcode.")
                current = int(connection.execute(
                    "SELECT COALESCE(SUM(quantity),0) FROM deck_cards WHERE deck_id=? AND card_id=?",
                    (deck_id, card_id),
                ).fetchone()[0] or 0)
                if current >= 3:
                    raise DatabaseError("Eine Karte darf insgesamt höchstens dreimal im Deck vorkommen.")
                synthetic = placeholder_collection_key(source_key or f"card-{card_id}")
                row = connection.execute(
                    "SELECT quantity FROM deck_cards WHERE deck_id=? AND collection_key=? AND zone=?",
                    (deck_id, synthetic, zone),
                ).fetchone()
                if row is None:
                    connection.execute(
                        "INSERT INTO deck_cards(deck_id, collection_key, card_id, zone, quantity, card_json, is_placeholder, source_collection_key) VALUES(?,?,?,?,?,?,1,?)",
                        (deck_id, synthetic, card_id, zone, 1, self._json(card_json), source_key),
                    )
                else:
                    connection.execute(
                        "UPDATE deck_cards SET quantity=? WHERE deck_id=? AND collection_key=? AND zone=?",
                        (int(row["quantity"]) + 1, deck_id, synthetic, zone),
                    )
                connection.execute("UPDATE decks SET updated_at=? WHERE deck_id=?", (time.time(), deck_id))

    def add_deck_card(self: Any, deck_id: str, collection_key: str, zone: str, allow_placeholder: bool = False) -> None:
        requested_zone = str(zone or "main").lower()
        card_json: dict[str, Any] = {}
        try:
            with self.connect() as connection:
                row = connection.execute(
                    "SELECT card_json FROM collection WHERE collection_key=? LIMIT 1",
                    (str(collection_key or ""),),
                ).fetchone()
            if row is not None:
                loaded = json.loads(row["card_json"]) if isinstance(row["card_json"], str) else row["card_json"]
                if isinstance(loaded, dict):
                    card_json = loaded
        except Exception:
            card_json = {}
        target_zone = resolved_deck_zone(card_json, requested_zone)
        try:
            return original_add_deck_card(self, deck_id, collection_key, target_zone)
        except DatabaseError as exc:
            if allow_placeholder and "nicht genug Bestand" in str(exc):
                return add_deck_placeholder(self, deck_id, collection_key, target_zone, card_json or None)
            raise

    def deck_cards(self: Any, deck_id: str) -> list[dict[str, Any]]:
        items = original_deck_cards(self, deck_id)
        for item in items:
            if isinstance(item, dict):
                item["placeholder"] = is_placeholder_item(item)
        return items

    def validate_deck(self: Any, deck_id: str) -> dict[str, Any]:
        result = original_validate_deck(self, deck_id)
        items = deck_cards(self, deck_id)
        missing = sum(int(item.get("quantity") or 0) for item in items if is_placeholder_item(item))
        if missing:
            errors = result.setdefault("errors", [])
            errors.append(f"{missing} Karten-Platzhalter sind noch nicht durch vorhandene Sammlungsexemplare gedeckt.")
            result["valid"] = False
            result["placeholders"] = missing
        return result

    def create_backup(self: Any, target: Any, settings: dict[str, Any] | None = None) -> Path:
        path = Path(target)
        path.parent.mkdir(parents=True, exist_ok=True)
        collection = self.collection_items("")
        for row in collection:
            if isinstance(row, dict):
                row["wishlist"] = False
                row["trade"] = False
                row["purchase_price"] = None
        decks = self.list_decks()
        deck_rows: list[dict[str, Any]] = []
        for deck in decks:
            deck_id = str(deck.get("deck_id") or "")
            for item in self.deck_cards(deck_id):
                row = dict(item)
                row["deck_id"] = deck_id
                row["is_placeholder"] = bool(is_placeholder_item(row))
                deck_rows.append(row)
        all_settings: dict[str, Any] = {}
        with self.connect() as connection:
            for row in connection.execute("SELECT key, value_json FROM settings").fetchall():
                try:
                    all_settings[str(row["key"])] = self._load(row["value_json"], None)
                except Exception:
                    pass
        if isinstance(settings, dict):
            all_settings.update(settings)
        payload = {
            "format": "justincard-windows-backup-v2",
            "app_version": APP_VERSION,
            "created_at": time.time(),
            "collection": collection,
            "decks": decks,
            "deck_cards": deck_rows,
            "settings": all_settings,
        }
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("backup.json", json.dumps(payload, ensure_ascii=False, indent=2))
        return path

    def import_backup_file(self: Any, source: Any) -> dict[str, int]:
        path = Path(source)
        payload = normalize_backup_payload(_read_backup_payload(path))
        report = {"imported": 0, "skipped": 0, "decks": 0, "deck_cards": 0}
        key_map: dict[str, str] = {}

        for raw in payload.get("collection", []):
            if not isinstance(raw, dict):
                report["skipped"] += 1
                continue
            card = raw.get("card")
            if not isinstance(card, dict) or not (card.get("name") or card.get("id")):
                report["skipped"] += 1
                continue
            print_item = {
                "set_code": raw.get("print_code") or "",
                "set_name": raw.get("set_name") or "",
                "set_rarity": raw.get("rarity") or "",
            }
            if not any(print_item.values()):
                print_item = None
            quantity = max(1, int(raw.get("quantity") or 1))
            try:
                self.add_to_collection(
                    card,
                    print_item,
                    quantity,
                    str(raw.get("condition") or "Unbewertet"),
                    str(raw.get("artwork_url") or ""),
                    str(raw.get("note") or ""),
                )
                new_key = self.collection_key(card, print_item, str(raw.get("artwork_url") or ""))
                old_key = str(raw.get("collection_key") or "")
                if old_key:
                    key_map[old_key] = new_key
                # Wishlist, trade and manually entered purchase prices were
                # removed in 1.1.3.  Legacy backups remain importable, but
                # these obsolete flags are intentionally not restored.
                try:
                    self.update_collection_metadata(new_key, wishlist=False, trade=False)
                except Exception:
                    pass
                report["imported"] += 1
            except Exception:
                report["skipped"] += 1

        deck_id_map: dict[str, str] = {}
        decks = [item for item in payload.get("decks", []) if isinstance(item, dict)]
        for deck in decks:
            try:
                new_id = self.create_deck(str(deck.get("name") or "Importiertes Deck"), str(deck.get("description") or ""))
                old_id = str(deck.get("deck_id") or deck.get("id") or "")
                if old_id:
                    deck_id_map[old_id] = new_id
                if bool(deck.get("favorite")):
                    self.toggle_deck_favorite(new_id)
                report["decks"] += 1
            except Exception:
                continue

        deck_cards_payload = [item for item in payload.get("deck_cards", []) if isinstance(item, dict)]
        for deck in decks:
            embedded = deck.get("cards") or deck.get("deck_cards")
            if isinstance(embedded, list):
                for item in embedded:
                    if isinstance(item, dict):
                        row = dict(item)
                        row.setdefault("deck_id", deck.get("deck_id") or deck.get("id"))
                        deck_cards_payload.append(row)

        for item in deck_cards_payload:
            old_deck_id = str(item.get("deck_id") or "")
            new_deck_id = deck_id_map.get(old_deck_id, old_deck_id if any(str(d.get("deck_id")) == old_deck_id for d in self.list_decks()) else "")
            if not new_deck_id:
                continue
            source_key = str(item.get("source_collection_key") or item.get("collection_key") or "")
            mapped_key = key_map.get(source_key, source_key)
            zone = str(item.get("zone") or "main").lower()
            quantity = max(1, int(item.get("quantity") or 1))
            card = item.get("card") if isinstance(item.get("card"), dict) else None
            if card is None and isinstance(item.get("card_json"), dict):
                card = item.get("card_json")
            if card is None and isinstance(item.get("card_json"), str):
                try:
                    loaded = json.loads(item.get("card_json"))
                    if isinstance(loaded, dict):
                        card = loaded
                except Exception:
                    pass

            if mapped_key.startswith("__placeholder__:"):
                mapped_key = mapped_key.split(":", 1)[1]
            if not mapped_key and card and card.get("id"):
                with self.connect() as connection:
                    row = connection.execute(
                        "SELECT collection_key FROM collection WHERE card_id=? AND quantity>0 ORDER BY quantity DESC, updated_at DESC LIMIT 1",
                        (int(card.get("id")),),
                    ).fetchone()
                    if row is not None:
                        mapped_key = str(row["collection_key"])

            for _ in range(quantity):
                try:
                    if is_placeholder_item(item):
                        add_deck_placeholder(self, new_deck_id, mapped_key, zone, card)
                    elif mapped_key:
                        try:
                            add_deck_card(self, new_deck_id, mapped_key, zone, False)
                        except DatabaseError as exc:
                            if "nicht genug Bestand" in str(exc):
                                add_deck_placeholder(self, new_deck_id, mapped_key, zone, card)
                            else:
                                raise
                    elif card:
                        add_deck_placeholder(self, new_deck_id, "", zone, card)
                    else:
                        continue
                    report["deck_cards"] += 1
                except Exception:
                    continue

        for key, value in (payload.get("settings") or {}).items():
            try:
                self.set_setting(str(key), value)
            except Exception:
                pass
        return report

    CardDatabase.__init__ = db_init
    CardDatabase.add_deck_placeholder = add_deck_placeholder
    CardDatabase.add_deck_card = add_deck_card
    CardDatabase.deck_cards = deck_cards
    CardDatabase.validate_deck = validate_deck
    CardDatabase.create_backup = create_backup
    CardDatabase.import_backup_file = import_backup_file


def _patch_collection_page() -> None:
    from justincard.ui.collection_page import CollectionPage

    original_init = CollectionPage.__init__
    original_refresh = CollectionPage.refresh
    original_show_item = CollectionPage._show_item

    def page_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        _configure_table(self.table, self.database)
        _add_sort_bar(self.table, "Sammlung sortieren")
        if hasattr(self, "selected_name"):
            self.selected_name.setWordWrap(True)

        toolbar = self.search.parentWidget() if hasattr(self, "search") else None
        layout = toolbar.layout() if toolbar is not None else None
        if isinstance(layout, QHBoxLayout):
            all_button = QPushButton("Alle Infos")
            all_button.setProperty("role", "ghost")
            basic_button = QPushButton("Basisansicht")
            basic_button.setProperty("role", "ghost")
            name_only_button = QPushButton("Nur Namen")
            name_only_button.setProperty("role", "ghost")
            layout.addWidget(all_button)
            layout.addWidget(basic_button)
            layout.addWidget(name_only_button)
            self._jic_all_info_button = all_button
            self._jic_basic_info_button = basic_button
            self._jic_name_only_button = name_only_button

            def use_all() -> None:
                override = visibility_preset("all")
                self.table._jic_local_visibility_override = override
                _apply_table_visibility(self.table, _visibility_for_database(self.database), override)

            def use_basic() -> None:
                override = visibility_preset("basic")
                self.table._jic_local_visibility_override = override
                _apply_table_visibility(self.table, _visibility_for_database(self.database), override)

            def use_name_only() -> None:
                override = visibility_preset("none")
                self.table._jic_local_visibility_override = override
                _apply_table_visibility(self.table, _visibility_for_database(self.database), override)

            all_button.clicked.connect(use_all)
            basic_button.clicked.connect(use_basic)
            name_only_button.clicked.connect(use_name_only)

    def refresh(self: Any) -> None:
        original_refresh(self)
        QTimer.singleShot(0, lambda: _ensure_name_width(self.table))
        _apply_table_visibility(
            self.table,
            _visibility_for_database(self.database),
            getattr(self.table, "_jic_local_visibility_override", None),
        )

    def show_item(self: Any, item: Any) -> None:
        original_show_item(self, item)
        if hasattr(self, "selected_name"):
            self.selected_name.setWordWrap(True)
        if not isinstance(item, dict) or not hasattr(self, "selected_print"):
            return
        prefs = _visibility_for_database(self.database)
        parts: list[str] = []
        if prefs.get("set_code", True):
            parts.append(str(item.get("print_code") or "Kein Set-Code"))
        if prefs.get("set_name", True) and item.get("set_name"):
            parts.append(str(item.get("set_name")))
        if prefs.get("rarity", True) and item.get("rarity"):
            parts.append(str(item.get("rarity")))
        if prefs.get("language", True) and item.get("language"):
            parts.append(str(item.get("language")).upper())
        self.selected_print.setText(" • ".join(parts))

    def import_backup(self: Any) -> None:
        path, _selected = QFileDialog.getOpenFileName(
            self,
            "Sammlung oder Sicherung importieren",
            str(getattr(self, "backup_directory", "")),
            "Just InCard Sicherungen (*.zip *.json *.sqlite3 *.sqlite *.db);;ZIP-Dateien (*.zip);;JSON-Dateien (*.json);;SQLite-Datenbanken (*.sqlite3 *.sqlite *.db)",
        )
        if not path:
            return
        try:
            report = self.database.import_backup_file(path)
        except Exception as exc:
            QMessageBox.critical(self, "Import fehlgeschlagen", str(exc))
            return
        self.refresh()
        self.collection_changed.emit()
        QMessageBox.information(
            self,
            "Import abgeschlossen",
            f"{int(report.get('imported', 0))} Sammlungseinträge importiert, "
            f"{int(report.get('skipped', 0))} übersprungen.\n"
            f"{int(report.get('decks', 0))} Decks mit "
            f"{int(report.get('deck_cards', 0))} Karten/Platzhaltern übernommen.",
        )

    CollectionPage.__init__ = page_init
    CollectionPage.refresh = refresh
    CollectionPage._show_item = show_item
    CollectionPage.import_backup = import_backup


def _patch_decks_page() -> None:
    from justincard.database import DatabaseError
    from justincard.ui.decks_page import DecksPage

    original_init = DecksPage.__init__
    original_refresh_collection = DecksPage.refresh_collection
    original_refresh_deck_cards = DecksPage.refresh_deck_cards

    def page_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        _configure_table(self.collection_table, self.database)
        _configure_table(self.deck_table, self.database)
        _add_sort_bar(self.collection_table, "Karten sortieren")
        _add_sort_bar(self.deck_table, "Deck sortieren")

    def refresh_collection(self: Any) -> None:
        original_refresh_collection(self)
        QTimer.singleShot(0, lambda: _ensure_name_width(self.collection_table))
        _apply_table_visibility(self.collection_table, _visibility_for_database(self.database))

    def refresh_deck_cards(self: Any) -> None:
        original_refresh_deck_cards(self)
        QTimer.singleShot(0, lambda: _ensure_name_width(self.deck_table))
        _apply_table_visibility(self.deck_table, _visibility_for_database(self.database))

    def add_card(self: Any, zone: str) -> None:
        rows = self.collection_table.selectionModel().selectedRows()
        if not rows or not self.current_deck_id:
            return
        item = self.collection_model.item_at(rows[0].row())
        if not isinstance(item, dict):
            return
        collection_key = str(item.get("collection_key") or "")
        if not collection_key:
            return
        card = item.get("card") if isinstance(item.get("card"), dict) else {}
        target_zone = resolved_deck_zone(card, zone)
        try:
            self.database.add_deck_card(self.current_deck_id, collection_key, target_zone)
        except DatabaseError as exc:
            message = str(exc)
            if "nicht genug Bestand" not in message:
                QMessageBox.warning(self, "Karte konnte nicht hinzugefügt werden", message)
                return
            box = QMessageBox(self)
            box.setWindowTitle("Nicht genug Bestand")
            box.setIcon(QMessageBox.Warning)
            card = item.get("card") if isinstance(item.get("card"), dict) else {}
            name = str(card.get("name") or "Diese Karte")
            box.setText(f"{name} ist nicht oft genug in der Sammlung vorhanden.")
            box.setInformativeText(
                "Sie können sie trotzdem als grauen Platzhalter in das Deck übernehmen. "
                "So bleibt sichtbar, welches Exemplar für das Deck noch benötigt wird."
            )
            placeholder_button = box.addButton("Als Platzhalter hinzufügen", QMessageBox.AcceptRole)
            box.addButton("Abbrechen", QMessageBox.RejectRole)
            box.exec()
            if box.clickedButton() is not placeholder_button:
                return
            try:
                self.database.add_deck_card(self.current_deck_id, collection_key, target_zone, allow_placeholder=True)
            except DatabaseError as placeholder_error:
                QMessageBox.warning(self, "Platzhalter konnte nicht hinzugefügt werden", str(placeholder_error))
                return
        self.refresh_deck_cards()
        card = item.get("card") if isinstance(item.get("card"), dict) else {}
        zone_label = {"main": "Main", "extra": "Extra", "side": "Side"}.get(target_zone, target_zone.title())
        self.status_message.emit(f"{card.get('name', 'Karte')} zum {zone_label} Deck hinzugefügt")

    DecksPage.__init__ = page_init
    DecksPage.refresh_collection = refresh_collection
    DecksPage.refresh_deck_cards = refresh_deck_cards
    DecksPage.add_card = add_card


def _add_visibility_settings(page: Any) -> None:
    scroll = page.findChild(QScrollArea)
    content = scroll.widget() if scroll is not None else None
    layout = content.layout() if content is not None else None
    if not isinstance(layout, QVBoxLayout):
        return

    group = QGroupBox("Anzeigeoptionen – Karteninformationen")
    outer = QVBoxLayout(group)
    info = QLabel(
        "Wählen Sie wie Kacheln aus, welche Informationen in Suche, Sammlung und Decks angezeigt werden. "
        "Der Kartenname bleibt immer sichtbar und vollständig lesbar."
    )
    info.setWordWrap(True)
    info.setObjectName("Muted")
    outer.addWidget(info)
    grid = QGridLayout()
    prefs = _visibility_for_database(page.database)
    buttons: dict[str, QToolButton] = {}

    for index, (key, label) in enumerate(CARD_INFORMATION_FIELDS):
        button = QToolButton()
        button.setText(label)
        button.setCheckable(True)
        button.setChecked(bool(prefs.get(key, True)))
        button.setMinimumHeight(40)
        button.setToolButtonStyle(Qt.ToolButtonTextOnly)
        button.setStyleSheet(
            "QToolButton { padding: 8px 12px; border: 1px solid #2a4268; border-radius: 9px; }"
            "QToolButton:checked { background: #2d70c9; color: white; border-color: #5a9bf2; }"
        )
        buttons[key] = button
        grid.addWidget(button, index // 4, index % 4)
    outer.addLayout(grid)

    actions = QHBoxLayout()
    all_button = QPushButton("Alle auswählen")
    all_button.setProperty("role", "ghost")
    basis_button = QPushButton("Basisansicht")
    basis_button.setProperty("role", "ghost")
    none_button = QPushButton("Alle abwählen")
    none_button.setProperty("role", "ghost")
    actions.addWidget(all_button)
    actions.addWidget(basis_button)
    actions.addWidget(none_button)
    actions.addStretch(1)
    outer.addLayout(actions)
    page._jic_visibility_buttons = buttons

    def save() -> None:
        current = {key: button.isChecked() for key, button in buttons.items()}
        page.database.set_setting(VISIBILITY_SETTING_KEY, current)
        apply_visibility_to_window(page.window(), current)
        try:
            page.status_message.emit("Anzeigeoptionen gespeichert")
        except Exception:
            pass

    for button in buttons.values():
        button.toggled.connect(lambda _checked, save=save: save())

    def apply_preset(mode: str) -> None:
        target = visibility_preset(mode)
        for key, button in buttons.items():
            old = button.blockSignals(True)
            button.setChecked(bool(target.get(key, True)))
            button.blockSignals(old)
        save()

    all_button.clicked.connect(lambda: apply_preset("all"))
    basis_button.clicked.connect(lambda: apply_preset("basic"))
    none_button.clicked.connect(lambda: apply_preset("none"))

    # Insert before the final stretch when possible.
    layout.insertWidget(max(0, layout.count() - 1), group)


def _patch_settings_page() -> None:
    from justincard.ui.settings_page import SettingsPage

    original_init = SettingsPage.__init__

    def page_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        _add_visibility_settings(self)

    SettingsPage.__init__ = page_init


def _patch_search_page() -> None:
    from justincard.ui.search_page import SearchPage

    original_init = SearchPage.__init__
    original_show_results = SearchPage._show_results

    def page_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        _configure_table(self.table, self.database)
        prefs = _visibility_for_database(self.database)
        _apply_table_visibility(self.table, prefs)
        self.detail._jic_visibility = prefs
        _refresh_detail_panel(self.detail)

    def show_results(self: Any, result: object) -> None:
        original_show_results(self, result)
        QTimer.singleShot(0, lambda: _ensure_name_width(self.table))
        _apply_table_visibility(self.table, _visibility_for_database(self.database))

    SearchPage.__init__ = page_init
    SearchPage._show_results = show_results


def _patch_main_window() -> None:
    from justincard.ui.main_window import MainWindow

    original_init = MainWindow.__init__

    def window_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        apply_visibility_to_window(self)

    MainWindow.__init__ = window_init


def install_v108_patches() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _patch_database()
    _patch_models()
    _patch_collection_page()
    _patch_decks_page()
    _patch_settings_page()
    _patch_search_page()
    _patch_main_window()
    _INSTALLED = True
