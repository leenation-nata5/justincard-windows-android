package org.yugioh.kartenliste.data.local

import android.content.ContentValues
import android.content.Context
import android.database.Cursor
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import org.yugioh.kartenliste.data.model.Card
import org.yugioh.kartenliste.data.model.CardKey
import org.yugioh.kartenliste.data.model.CardPrint
import org.yugioh.kartenliste.data.model.SearchFilters
import org.yugioh.kartenliste.data.model.SearchPage
import org.yugioh.kartenliste.util.TextNormalizer

class JustInCardDatabase(context: Context) : SQLiteOpenHelper(
    context,
    DATABASE_NAME,
    null,
    DATABASE_VERSION,
) {
    init {
        setWriteAheadLoggingEnabled(true)
    }

    override fun onConfigure(db: SQLiteDatabase) {
        super.onConfigure(db)
        db.setForeignKeyConstraintsEnabled(true)
        db.rawQuery("PRAGMA synchronous=NORMAL", null).close()
    }

    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL(
            """CREATE TABLE cards (
                stable_key TEXT PRIMARY KEY NOT NULL,
                card_id INTEGER NOT NULL,
                artwork_id INTEGER NOT NULL,
                language TEXT NOT NULL,
                name TEXT NOT NULL,
                name_key TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                description_key TEXT NOT NULL DEFAULT '',
                type TEXT NOT NULL DEFAULT '',
                type_key TEXT NOT NULL DEFAULT '',
                frame_type TEXT NOT NULL DEFAULT '',
                frame_type_key TEXT NOT NULL DEFAULT '',
                race TEXT NOT NULL DEFAULT '',
                race_key TEXT NOT NULL DEFAULT '',
                attribute TEXT NOT NULL DEFAULT '',
                attribute_key TEXT NOT NULL DEFAULT '',
                archetype TEXT NOT NULL DEFAULT '',
                archetype_key TEXT NOT NULL DEFAULT '',
                atk INTEGER,
                def INTEGER,
                level INTEGER,
                link_value INTEGER,
                pendulum_scale INTEGER,
                image_url TEXT NOT NULL DEFAULT '',
                thumbnail_url TEXT NOT NULL DEFAULT '',
                cropped_image_url TEXT NOT NULL DEFAULT '',
                cardmarket_price REAL,
                tcgplayer_price REAL,
                updated_at INTEGER NOT NULL
            )""".trimIndent(),
        )
        db.execSQL(
            """CREATE TABLE card_prints (
                stable_key TEXT PRIMARY KEY NOT NULL,
                card_id INTEGER NOT NULL,
                set_name TEXT NOT NULL,
                set_name_key TEXT NOT NULL,
                set_code TEXT NOT NULL,
                set_code_key TEXT NOT NULL,
                rarity TEXT NOT NULL,
                rarity_key TEXT NOT NULL,
                rarity_code TEXT NOT NULL DEFAULT '',
                price_usd REAL,
                language TEXT NOT NULL DEFAULT 'unknown'
            )""".trimIndent(),
        )
        db.execSQL(
            """CREATE TABLE collection_items (
                id TEXT PRIMARY KEY NOT NULL,
                identity_key TEXT NOT NULL UNIQUE,
                card_id INTEGER NOT NULL,
                artwork_id INTEGER NOT NULL,
                card_language TEXT NOT NULL,
                card_name TEXT NOT NULL,
                image_url TEXT NOT NULL,
                set_name TEXT NOT NULL,
                set_code TEXT NOT NULL,
                rarity TEXT NOT NULL,
                rarity_code TEXT NOT NULL DEFAULT '',
                price_usd REAL,
                language TEXT NOT NULL,
                condition_name TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                updated_at INTEGER NOT NULL,
                device_id TEXT NOT NULL,
                deleted INTEGER NOT NULL DEFAULT 0
            )""".trimIndent(),
        )
        db.execSQL(
            """CREATE TABLE decks (
                id TEXT PRIMARY KEY NOT NULL,
                name TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                updated_at INTEGER NOT NULL,
                device_id TEXT NOT NULL,
                deleted INTEGER NOT NULL DEFAULT 0
            )""".trimIndent(),
        )
        db.execSQL(
            """CREATE TABLE deck_cards (
                id TEXT PRIMARY KEY NOT NULL,
                deck_id TEXT NOT NULL,
                card_id INTEGER NOT NULL,
                artwork_id INTEGER NOT NULL,
                card_language TEXT NOT NULL,
                card_name TEXT NOT NULL,
                image_url TEXT NOT NULL,
                set_code TEXT NOT NULL DEFAULT '',
                section_name TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                device_id TEXT NOT NULL,
                deleted INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(deck_id) REFERENCES decks(id) ON DELETE CASCADE
            )""".trimIndent(),
        )
        db.execSQL(
            """CREATE TABLE sync_devices (
                id TEXT PRIMARY KEY NOT NULL,
                name TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                last_seen_at INTEGER NOT NULL
            )""".trimIndent(),
        )
        db.execSQL(
            """CREATE TABLE metadata (
                key TEXT PRIMARY KEY NOT NULL,
                value TEXT NOT NULL
            )""".trimIndent(),
        )

        listOf(
            "CREATE INDEX idx_cards_name ON cards(name_key)",
            "CREATE INDEX idx_cards_description ON cards(description_key)",
            "CREATE INDEX idx_cards_id ON cards(card_id)",
            "CREATE INDEX idx_cards_language ON cards(language)",
            "CREATE INDEX idx_cards_type ON cards(type_key)",
            "CREATE INDEX idx_cards_stats ON cards(atk, def, level, link_value)",
            "CREATE INDEX idx_prints_card ON card_prints(card_id)",
            "CREATE INDEX idx_prints_code ON card_prints(set_code_key)",
            "CREATE INDEX idx_prints_name ON card_prints(set_name_key)",
            "CREATE INDEX idx_prints_rarity ON card_prints(rarity_key)",
            "CREATE INDEX idx_collection_card ON collection_items(card_id, deleted, quantity)",
            "CREATE INDEX idx_collection_updated ON collection_items(updated_at)",
            "CREATE INDEX idx_deck_cards_deck ON deck_cards(deck_id, deleted)",
        ).forEach(db::execSQL)
    }

    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
        if (oldVersion == newVersion) return
        db.execSQL("DROP TABLE IF EXISTS deck_cards")
        db.execSQL("DROP TABLE IF EXISTS decks")
        db.execSQL("DROP TABLE IF EXISTS collection_items")
        db.execSQL("DROP TABLE IF EXISTS card_prints")
        db.execSQL("DROP TABLE IF EXISTS cards")
        db.execSQL("DROP TABLE IF EXISTS sync_devices")
        db.execSQL("DROP TABLE IF EXISTS metadata")
        onCreate(db)
    }

    fun replaceCatalog(cards: Sequence<Card>, language: String, catalogVersion: String): Int {
        val db = writableDatabase
        var count = 0
        db.beginTransaction()
        try {
            db.delete("cards", "language = ?", arrayOf(language))
            cards.forEach { card ->
                upsertCard(db, card)
                card.prints.forEach { upsertPrint(db, it) }
                count += 1
            }
            putMetadata(db, "catalog_version_$language", catalogVersion)
            putMetadata(db, "catalog_updated_$language", System.currentTimeMillis().toString())
            db.setTransactionSuccessful()
        } finally {
            db.endTransaction()
        }
        return count
    }

    fun upsertCards(cards: List<Card>) {
        if (cards.isEmpty()) return
        val db = writableDatabase
        db.beginTransaction()
        try {
            cards.forEach { card ->
                upsertCard(db, card)
                card.prints.forEach { upsertPrint(db, it) }
            }
            db.setTransactionSuccessful()
        } finally {
            db.endTransaction()
        }
    }

    fun search(filters: SearchFilters, page: Int, pageSize: Int): SearchPage {
        val safePage = page.coerceAtLeast(0)
        val safeSize = pageSize.coerceIn(1, 100)
        val query = SearchSqlBuilder.build(filters)
        val db = readableDatabase
        val args = query.arguments.toTypedArray()
        val total = db.rawQuery(
            "SELECT COUNT(*) FROM cards c WHERE ${query.whereClause}",
            args,
        ).use { cursor -> if (cursor.moveToFirst()) cursor.getInt(0) else 0 }

        val cards = db.rawQuery(
            """SELECT c.* FROM cards c
               WHERE ${query.whereClause}
               ORDER BY ${query.orderBy}
               LIMIT $safeSize OFFSET ${safePage * safeSize}""".trimIndent(),
            args,
        ).use { cursor -> buildList { while (cursor.moveToNext()) add(cursor.toCard()) } }
        return SearchPage(
            cards = attachPrints(db, cards),
            total = total,
            page = safePage,
            pageSize = safeSize,
        )
    }

    fun cardsByPrintCode(code: String, limit: Int = 12): List<Card> {
        val signature = TextNormalizer.setCodeSignature(code).lowercase()
        if (signature.isBlank()) return emptyList()
        val db = readableDatabase
        val cards = db.rawQuery(
            """SELECT DISTINCT c.* FROM cards c
               JOIN card_prints p ON p.card_id = c.card_id
               WHERE p.set_code_key = ? OR p.set_code_key LIKE ?
               ORDER BY CASE WHEN p.set_code_key = ? THEN 0 ELSE 1 END, c.name_key
               LIMIT ${limit.coerceIn(1, 50)}""".trimIndent(),
            arrayOf(signature, "%$signature%", signature),
        ).use { cursor -> buildList { while (cursor.moveToNext()) add(cursor.toCard()) } }
        return attachPrints(db, cards)
    }

    fun cardsByPasscodes(passcodes: List<String>): List<Card> {
        val ids = passcodes.mapNotNull(String::toLongOrNull).distinct()
        if (ids.isEmpty()) return emptyList()
        val placeholders = ids.joinToString(",") { "?" }
        val db = readableDatabase
        val cards = db.rawQuery(
            "SELECT c.* FROM cards c WHERE c.card_id IN ($placeholders) ORDER BY c.name_key",
            ids.map(Long::toString).toTypedArray(),
        ).use { cursor -> buildList { while (cursor.moveToNext()) add(cursor.toCard()) } }
        return attachPrints(db, cards)
    }

    fun cardsByPossibleNames(names: List<String>, limit: Int = 20): List<Card> {
        val keys = names.map(TextNormalizer::searchKey).filter { it.length >= 3 }.distinct().take(8)
        if (keys.isEmpty()) return emptyList()
        val clauses = keys.joinToString(" OR ") { "c.name_key LIKE ?" }
        val db = readableDatabase
        val cards = db.rawQuery(
            "SELECT c.* FROM cards c WHERE $clauses ORDER BY c.name_key LIMIT ${limit.coerceIn(1, 50)}",
            keys.map { "%$it%" }.toTypedArray(),
        ).use { cursor -> buildList { while (cursor.moveToNext()) add(cursor.toCard()) } }
        return attachPrints(db, cards)
    }

    fun cardByKey(key: CardKey): Card? {
        val db = readableDatabase
        val card = db.rawQuery(
            "SELECT c.* FROM cards c WHERE c.stable_key = ? LIMIT 1",
            arrayOf(key.stableKey),
        ).use { cursor -> if (cursor.moveToFirst()) cursor.toCard() else null }
        return card?.let { attachPrints(db, listOf(it)).firstOrNull() }
    }

    fun cardByIdentityLanguage(cardId: Long, artworkId: Long, language: String): Card? {
        val db = readableDatabase
        val card = db.rawQuery(
            """SELECT c.* FROM cards c
               WHERE c.card_id = ? AND c.language = ?
               ORDER BY CASE WHEN c.artwork_id = ? THEN 0 ELSE 1 END, c.stable_key
               LIMIT 1""".trimIndent(),
            arrayOf(cardId.toString(), language.lowercase(), artworkId.toString()),
        ).use { cursor -> if (cursor.moveToFirst()) cursor.toCard() else null }
        return card?.let { attachPrints(db, listOf(it)).firstOrNull() }
    }

    fun catalogCount(language: String? = null): Int {
        val (where, args) = if (language.isNullOrBlank() || language == "all") {
            "1 = 1" to emptyArray<String>()
        } else {
            "language = ?" to arrayOf(language)
        }
        return readableDatabase.rawQuery("SELECT COUNT(*) FROM cards WHERE $where", args).use {
            if (it.moveToFirst()) it.getInt(0) else 0
        }
    }

    fun metadata(key: String): String? = readableDatabase.rawQuery(
        "SELECT value FROM metadata WHERE key = ?",
        arrayOf(key),
    ).use { if (it.moveToFirst()) it.getString(0) else null }

    fun setMetadata(key: String, value: String) = putMetadata(writableDatabase, key, value)

    internal fun databaseForRead(): SQLiteDatabase = readableDatabase
    internal fun databaseForWrite(): SQLiteDatabase = writableDatabase

    private fun upsertCard(db: SQLiteDatabase, card: Card) {
        db.insertWithOnConflict("cards", null, ContentValues().apply {
            put("stable_key", card.key.stableKey)
            put("card_id", card.key.cardId)
            put("artwork_id", card.key.artworkId)
            put("language", card.key.language)
            put("name", card.name)
            put("name_key", TextNormalizer.searchKey(card.name))
            put("description", card.description)
            put("description_key", TextNormalizer.searchKey(card.description))
            put("type", card.type)
            put("type_key", TextNormalizer.searchKey(card.type))
            put("frame_type", card.frameType)
            put("frame_type_key", TextNormalizer.searchKey(card.frameType))
            put("race", card.race)
            put("race_key", TextNormalizer.searchKey(card.race))
            put("attribute", card.attribute)
            put("attribute_key", TextNormalizer.searchKey(card.attribute))
            put("archetype", card.archetype)
            put("archetype_key", TextNormalizer.searchKey(card.archetype))
            putNullable("atk", card.atk)
            putNullable("def", card.def)
            putNullable("level", card.level)
            putNullable("link_value", card.linkValue)
            putNullable("pendulum_scale", card.pendulumScale)
            put("image_url", card.imageUrl)
            put("thumbnail_url", card.thumbnailUrl)
            put("cropped_image_url", card.croppedImageUrl)
            putNullable("cardmarket_price", card.cardMarketPrice)
            putNullable("tcgplayer_price", card.tcgPlayerPrice)
            put("updated_at", card.updatedAt)
        }, SQLiteDatabase.CONFLICT_REPLACE)
    }

    private fun upsertPrint(db: SQLiteDatabase, print: CardPrint) {
        db.insertWithOnConflict("card_prints", null, ContentValues().apply {
            put("stable_key", print.stableKey)
            put("card_id", print.cardId)
            put("set_name", print.setName)
            put("set_name_key", TextNormalizer.searchKey(print.setName))
            put("set_code", print.setCode)
            put("set_code_key", TextNormalizer.setCodeSignature(print.setCode).lowercase())
            put("rarity", print.rarity)
            put("rarity_key", TextNormalizer.searchKey(print.rarity))
            put("rarity_code", print.rarityCode)
            putNullable("price_usd", print.priceUsd)
            put("language", print.language)
        }, SQLiteDatabase.CONFLICT_REPLACE)
    }

    private fun attachPrints(db: SQLiteDatabase, cards: List<Card>): List<Card> {
        if (cards.isEmpty()) return cards
        val ids = cards.map { it.key.cardId }.distinct()
        val placeholders = ids.joinToString(",") { "?" }
        val prints = db.rawQuery(
            "SELECT * FROM card_prints WHERE card_id IN ($placeholders) ORDER BY set_name_key, set_code",
            ids.map(Long::toString).toTypedArray(),
        ).use { cursor -> buildList { while (cursor.moveToNext()) add(cursor.toPrint()) } }
            .groupBy(CardPrint::cardId)
        return cards.map { it.copy(prints = prints[it.key.cardId].orEmpty()) }
    }

    private fun putMetadata(db: SQLiteDatabase, key: String, value: String) {
        db.insertWithOnConflict("metadata", null, ContentValues().apply {
            put("key", key)
            put("value", value)
        }, SQLiteDatabase.CONFLICT_REPLACE)
    }

    companion object {
        private const val DATABASE_NAME = "justincard-v13.db"
        private const val DATABASE_VERSION = 2
    }
}

private fun Cursor.toCard(): Card = Card(
    key = CardKey(
        cardId = getLong(column("card_id")),
        artworkId = getLong(column("artwork_id")),
        language = getString(column("language")),
    ),
    name = getString(column("name")),
    description = getString(column("description")),
    type = getString(column("type")),
    frameType = getString(column("frame_type")),
    race = getString(column("race")),
    attribute = getString(column("attribute")),
    archetype = getString(column("archetype")),
    atk = nullableInt("atk"),
    def = nullableInt("def"),
    level = nullableInt("level"),
    linkValue = nullableInt("link_value"),
    pendulumScale = nullableInt("pendulum_scale"),
    imageUrl = getString(column("image_url")),
    thumbnailUrl = getString(column("thumbnail_url")),
    croppedImageUrl = getString(column("cropped_image_url")),
    cardMarketPrice = nullableDouble("cardmarket_price"),
    tcgPlayerPrice = nullableDouble("tcgplayer_price"),
    updatedAt = getLong(column("updated_at")),
)

private fun Cursor.toPrint(): CardPrint = CardPrint(
    cardId = getLong(column("card_id")),
    setName = getString(column("set_name")),
    setCode = getString(column("set_code")),
    rarity = getString(column("rarity")),
    rarityCode = getString(column("rarity_code")),
    priceUsd = nullableDouble("price_usd"),
    language = getString(column("language")),
)

private fun Cursor.column(name: String): Int = getColumnIndexOrThrow(name)
private fun Cursor.nullableInt(name: String): Int? = column(name).let { if (isNull(it)) null else getInt(it) }
private fun Cursor.nullableDouble(name: String): Double? = column(name).let { if (isNull(it)) null else getDouble(it) }

private fun ContentValues.putNullable(key: String, value: Int?) {
    if (value == null) putNull(key) else put(key, value)
}

private fun ContentValues.putNullable(key: String, value: Double?) {
    if (value == null) putNull(key) else put(key, value)
}
