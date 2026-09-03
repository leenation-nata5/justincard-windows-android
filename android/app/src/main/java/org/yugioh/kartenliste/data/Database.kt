package org.yugioh.kartenliste.data

import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import com.google.gson.Gson
import org.yugioh.kartenliste.core.CloudContract
import org.yugioh.kartenliste.core.DeckRules
import java.util.UUID

class JustInCardDatabase(context: Context) : SQLiteOpenHelper(context, "justincard_android.db", null, 4) {
    private val gson = Gson()

    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL("""
            CREATE TABLE collection(
                collection_key TEXT PRIMARY KEY,
                card_id INTEGER NOT NULL,
                print_code TEXT NOT NULL,
                set_name TEXT NOT NULL,
                rarity TEXT NOT NULL,
                artwork_url TEXT NOT NULL,
                language TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                condition TEXT NOT NULL,
                note TEXT NOT NULL,
                updated_at REAL NOT NULL,
                card_json TEXT NOT NULL
            )
        """.trimIndent())
        db.execSQL("""
            CREATE TABLE decks(
                deck_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                favorite INTEGER NOT NULL DEFAULT 0,
                updated_at REAL NOT NULL
            )
        """.trimIndent())
        db.execSQL("""
            CREATE TABLE deck_cards(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                deck_id TEXT NOT NULL,
                collection_key TEXT NOT NULL,
                source_collection_key TEXT NOT NULL,
                zone TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                is_placeholder INTEGER NOT NULL DEFAULT 0,
                updated_at REAL NOT NULL,
                card_json TEXT NOT NULL
            )
        """.trimIndent())
        db.execSQL("CREATE TABLE settings(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        db.execSQL("CREATE INDEX idx_collection_card ON collection(card_id)")
        db.execSQL("CREATE INDEX idx_deck_cards_deck ON deck_cards(deck_id)")
    }

    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
        if (oldVersion < 4) {
            // The native rewrite treats older local databases as legacy data.
            // Collection/deck cloud restore remains lossless via Google appData.
            db.execSQL("DROP TABLE IF EXISTS deck_cards")
            db.execSQL("DROP TABLE IF EXISTS decks")
            db.execSQL("DROP TABLE IF EXISTS collection")
            db.execSQL("DROP TABLE IF EXISTS settings")
            onCreate(db)
        }
    }

    fun getSetting(key: String, default: String = ""): String {
        readableDatabase.rawQuery("SELECT value FROM settings WHERE key=?", arrayOf(key)).use { c ->
            return if (c.moveToFirst()) c.getString(0) else default
        }
    }

    fun setSetting(key: String, value: String) {
        writableDatabase.insertWithOnConflict("settings", null, ContentValues().apply {
            put("key", key); put("value", value)
        }, SQLiteDatabase.CONFLICT_REPLACE)
    }

    fun listCollection(): List<CollectionItem> {
        val out = mutableListOf<CollectionItem>()
        readableDatabase.rawQuery("SELECT * FROM collection ORDER BY updated_at DESC", null).use { c ->
            while (c.moveToNext()) {
                val card = gson.fromJson(c.getString(c.getColumnIndexOrThrow("card_json")), Card::class.java)
                out += CollectionItem(
                    collectionKey = c.getString(c.getColumnIndexOrThrow("collection_key")),
                    printCode = c.getString(c.getColumnIndexOrThrow("print_code")),
                    setName = c.getString(c.getColumnIndexOrThrow("set_name")),
                    rarity = c.getString(c.getColumnIndexOrThrow("rarity")),
                    artworkUrl = c.getString(c.getColumnIndexOrThrow("artwork_url")),
                    language = c.getString(c.getColumnIndexOrThrow("language")),
                    quantity = c.getInt(c.getColumnIndexOrThrow("quantity")),
                    condition = c.getString(c.getColumnIndexOrThrow("condition")),
                    note = c.getString(c.getColumnIndexOrThrow("note")),
                    updatedAt = c.getDouble(c.getColumnIndexOrThrow("updated_at")),
                    card = card,
                )
            }
        }
        return out
    }

    fun addToCollection(
        card: Card,
        print: CardPrint?,
        language: String,
        quantity: Int,
        requestedPrintCode: String = "",
        artworkUrl: String = card.cardImages.firstOrNull()?.imageUrl.orEmpty(),
    ): CollectionItem {
        val printCode = requestedPrintCode.ifBlank { print?.setCode.orEmpty() }
        val rarity = print?.setRarity.orEmpty()
        val key = CloudContract.canonicalCollectionKey(card.id, printCode, rarity, language, artworkUrl)
        val existing = listCollection().firstOrNull { it.collectionKey == key }
        val now = System.currentTimeMillis() / 1000.0
        val item = CollectionItem(
            collectionKey = key,
            printCode = printCode,
            setName = print?.setName.orEmpty(),
            rarity = rarity,
            artworkUrl = artworkUrl,
            language = language.lowercase(),
            quantity = (existing?.quantity ?: 0) + quantity.coerceAtLeast(1),
            condition = existing?.condition ?: "Near Mint",
            note = existing?.note.orEmpty(),
            updatedAt = now,
            card = card.copy(language = language.lowercase()),
        )
        upsertCollection(item)
        return item
    }

    fun upsertCollection(item: CollectionItem) {
        writableDatabase.insertWithOnConflict("collection", null, ContentValues().apply {
            put("collection_key", item.collectionKey)
            put("card_id", item.card.id)
            put("print_code", item.printCode)
            put("set_name", item.setName)
            put("rarity", item.rarity)
            put("artwork_url", item.artworkUrl)
            put("language", item.language)
            put("quantity", item.quantity.coerceAtLeast(0))
            put("condition", item.condition)
            put("note", item.note)
            put("updated_at", item.updatedAt)
            put("card_json", gson.toJson(item.card))
        }, SQLiteDatabase.CONFLICT_REPLACE)
    }

    fun updateCollection(item: CollectionItem) = upsertCollection(item.copy(updatedAt = System.currentTimeMillis() / 1000.0))

    fun deleteCollection(key: String) {
        writableDatabase.delete("collection", "collection_key=?", arrayOf(key))
    }

    fun listDecks(): List<Deck> {
        val decks = mutableListOf<Deck>()
        readableDatabase.rawQuery("SELECT * FROM decks ORDER BY favorite DESC, updated_at DESC", null).use { c ->
            while (c.moveToNext()) {
                val id = c.getString(c.getColumnIndexOrThrow("deck_id"))
                decks += Deck(
                    deckId = id,
                    name = c.getString(c.getColumnIndexOrThrow("name")),
                    description = c.getString(c.getColumnIndexOrThrow("description")),
                    favorite = c.getInt(c.getColumnIndexOrThrow("favorite")) != 0,
                    updatedAt = c.getDouble(c.getColumnIndexOrThrow("updated_at")),
                    cards = listDeckCards(id),
                )
            }
        }
        return decks
    }

    fun createDeck(name: String): Deck {
        require(listDecks().size < 50) { "Es können höchstens 50 Decks angelegt werden." }
        val deck = Deck(UUID.randomUUID().toString(), name.trim().ifBlank { "Neues Deck" }, updatedAt = now())
        upsertDeck(deck)
        return deck
    }

    fun renameDeck(deckId: String, name: String) {
        writableDatabase.update("decks", ContentValues().apply {
            put("name", name.trim().ifBlank { "Unbenanntes Deck" })
            put("updated_at", now())
        }, "deck_id=?", arrayOf(deckId))
    }

    fun deleteDeck(deckId: String) {
        writableDatabase.delete("deck_cards", "deck_id=?", arrayOf(deckId))
        writableDatabase.delete("decks", "deck_id=?", arrayOf(deckId))
    }

    fun upsertDeck(deck: Deck) {
        writableDatabase.insertWithOnConflict("decks", null, ContentValues().apply {
            put("deck_id", deck.deckId); put("name", deck.name); put("description", deck.description)
            put("favorite", if (deck.favorite) 1 else 0); put("updated_at", deck.updatedAt)
        }, SQLiteDatabase.CONFLICT_REPLACE)
        if (deck.cards.isNotEmpty()) {
            writableDatabase.delete("deck_cards", "deck_id=?", arrayOf(deck.deckId))
            deck.cards.forEach(::upsertDeckCard)
        }
    }

    fun listDeckCards(deckId: String): List<DeckCard> {
        val out = mutableListOf<DeckCard>()
        readableDatabase.rawQuery("SELECT * FROM deck_cards WHERE deck_id=? ORDER BY id", arrayOf(deckId)).use { c ->
            while (c.moveToNext()) {
                val card = gson.fromJson(c.getString(c.getColumnIndexOrThrow("card_json")), Card::class.java)
                val key = c.getString(c.getColumnIndexOrThrow("collection_key"))
                val source = c.getString(c.getColumnIndexOrThrow("source_collection_key"))
                val collection = listCollection().firstOrNull { it.collectionKey == source || it.collectionKey == key }
                out += DeckCard(
                    id = c.getLong(c.getColumnIndexOrThrow("id")), deckId = deckId,
                    collectionKey = key, sourceCollectionKey = source,
                    zone = c.getString(c.getColumnIndexOrThrow("zone")),
                    quantity = c.getInt(c.getColumnIndexOrThrow("quantity")),
                    isPlaceholder = c.getInt(c.getColumnIndexOrThrow("is_placeholder")) != 0,
                    printCode = collection?.printCode.orEmpty(), setName = collection?.setName.orEmpty(),
                    rarity = collection?.rarity.orEmpty(), artworkUrl = collection?.artworkUrl.orEmpty(),
                    language = collection?.language.orEmpty(), condition = collection?.condition.orEmpty(),
                    note = collection?.note.orEmpty(), updatedAt = c.getDouble(c.getColumnIndexOrThrow("updated_at")),
                    card = card,
                )
            }
        }
        return out
    }

    fun addDeckCard(deckId: String, collection: CollectionItem, requestedZone: String? = null, allowPlaceholder: Boolean = true) {
        val zone = DeckRules.allowedZone(requestedZone, collection.card.type, collection.card.frameType)
        val current = listDeckCards(deckId)
        val used = current.filter { it.card.id == collection.card.id }.sumOf { it.quantity }
        require(used < 3) { "Maximal drei Exemplare einer Karte pro Deck." }
        val ownedUsed = current.filter { it.sourceCollectionKey == collection.collectionKey && !it.isPlaceholder }.sumOf { it.quantity }
        val placeholder = ownedUsed >= collection.quantity
        require(!placeholder || allowPlaceholder) { "Nicht genügend Exemplare in der Sammlung." }
        val same = current.firstOrNull {
            it.sourceCollectionKey == collection.collectionKey && it.zone == zone && it.isPlaceholder == placeholder
        }
        val entry = DeckCard(
            id = same?.id ?: 0L, deckId = deckId,
            collectionKey = if (placeholder) "__placeholder__:${collection.collectionKey}" else collection.collectionKey,
            sourceCollectionKey = collection.collectionKey,
            zone = zone, quantity = (same?.quantity ?: 0) + 1,
            isPlaceholder = placeholder,
            printCode = collection.printCode, setName = collection.setName, rarity = collection.rarity,
            artworkUrl = collection.artworkUrl, language = collection.language, condition = collection.condition,
            note = collection.note, updatedAt = now(), card = collection.card,
        )
        upsertDeckCard(entry)
        touchDeck(deckId)
    }

    private fun upsertDeckCard(card: DeckCard) {
        val db = writableDatabase
        if (card.id > 0) {
            db.update("deck_cards", ContentValues().apply {
                put("zone", DeckRules.allowedZone(card.zone, card.card.type, card.card.frameType))
                put("quantity", card.quantity); put("is_placeholder", if (card.isPlaceholder) 1 else 0)
                put("updated_at", card.updatedAt); put("card_json", gson.toJson(card.card))
            }, "id=?", arrayOf(card.id.toString()))
        } else {
            db.insert("deck_cards", null, ContentValues().apply {
                put("deck_id", card.deckId); put("collection_key", card.collectionKey)
                put("source_collection_key", card.sourceCollectionKey)
                put("zone", DeckRules.allowedZone(card.zone, card.card.type, card.card.frameType))
                put("quantity", card.quantity); put("is_placeholder", if (card.isPlaceholder) 1 else 0)
                put("updated_at", card.updatedAt); put("card_json", gson.toJson(card.card))
            })
        }
    }

    fun removeDeckCard(id: Long) {
        val deckId = readableDatabase.rawQuery("SELECT deck_id FROM deck_cards WHERE id=?", arrayOf(id.toString())).use { c ->
            if (c.moveToFirst()) c.getString(0) else ""
        }
        writableDatabase.delete("deck_cards", "id=?", arrayOf(id.toString()))
        if (deckId.isNotBlank()) touchDeck(deckId)
    }

    fun setDeckCardQuantity(id: Long, quantity: Int) {
        if (quantity <= 0) { removeDeckCard(id); return }
        val row = readableDatabase.rawQuery("SELECT deck_id, card_json, zone FROM deck_cards WHERE id=?", arrayOf(id.toString())).use { c ->
            if (!c.moveToFirst()) return
            Triple(c.getString(0), gson.fromJson(c.getString(1), Card::class.java), c.getString(2))
        }
        val safeZone = DeckRules.allowedZone(row.third, row.second.type, row.second.frameType)
        writableDatabase.update("deck_cards", ContentValues().apply {
            put("quantity", quantity.coerceIn(1, 3))
            put("zone", safeZone)
            put("updated_at", now())
        }, "id=?", arrayOf(id.toString()))
        touchDeck(row.first)
    }

    fun replaceDecksFromCloud(decks: List<Deck>) {
        val db = writableDatabase
        db.beginTransaction()
        try {
            decks.forEach { deck ->
                db.insertWithOnConflict("decks", null, ContentValues().apply {
                    put("deck_id", deck.deckId); put("name", deck.name); put("description", deck.description)
                    put("favorite", if (deck.favorite) 1 else 0); put("updated_at", deck.updatedAt)
                }, SQLiteDatabase.CONFLICT_REPLACE)
                db.delete("deck_cards", "deck_id=?", arrayOf(deck.deckId))
                deck.cards.forEach { upsertDeckCard(it.copy(id = 0, deckId = deck.deckId)) }
            }
            db.setTransactionSuccessful()
        } finally { db.endTransaction() }
    }

    private fun touchDeck(deckId: String) {
        writableDatabase.update("decks", ContentValues().apply { put("updated_at", now()) }, "deck_id=?", arrayOf(deckId))
    }

    private fun now() = System.currentTimeMillis() / 1000.0
}
