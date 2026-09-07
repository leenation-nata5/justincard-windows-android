package org.yugioh.kartenliste.data.local

import android.content.ContentValues
import android.database.Cursor
import android.database.sqlite.SQLiteDatabase
import org.yugioh.kartenliste.data.model.CardKey
import org.yugioh.kartenliste.data.model.CollectionItem
import org.yugioh.kartenliste.data.model.Deck
import org.yugioh.kartenliste.data.model.DeckCard
import org.yugioh.kartenliste.data.model.DeckSection
import java.util.UUID

class DeckStore(
    private val database: JustInCardDatabase,
    private val collectionStore: CollectionStore,
) {
    fun list(includeDeleted: Boolean = false): List<Deck> {
        val where = if (includeDeleted) "1 = 1" else "deleted = 0"
        val db = database.databaseForRead()
        val decks = db.rawQuery(
            "SELECT * FROM decks WHERE $where ORDER BY name COLLATE NOCASE",
            null,
        ).use { cursor -> buildList { while (cursor.moveToNext()) add(cursor.toDeck(emptyList())) } }
        if (decks.isEmpty()) return decks
        val ids = decks.map(Deck::id)
        val placeholders = ids.joinToString(",") { "?" }
        val cards = db.rawQuery(
            "SELECT * FROM deck_cards WHERE deck_id IN ($placeholders) ORDER BY section_name, card_name",
            ids.toTypedArray(),
        ).use { cursor -> buildList { while (cursor.moveToNext()) add(cursor.toDeckCard()) } }
            .groupBy(DeckCard::deckId)
        return decks.map { it.copy(cards = cards[it.id].orEmpty()) }
    }

    fun create(name: String, deviceId: String): Deck {
        require(list().size < MAX_DECKS) { "Es können höchstens $MAX_DECKS Decks angelegt werden." }
        val cleanName = name.trim().ifBlank { "Neues Deck" }
        val deck = Deck(name = cleanName, deviceId = deviceId)
        upsertDeck(database.databaseForWrite(), deck)
        return deck
    }

    fun rename(deckId: String, name: String, notes: String, deviceId: String): Deck? {
        val current = list(includeDeleted = true).firstOrNull { it.id == deckId } ?: return null
        val updated = current.copy(
            name = name.trim().ifBlank { current.name },
            notes = notes.trim(),
            updatedAt = System.currentTimeMillis(),
            deviceId = deviceId,
        )
        upsertDeck(database.databaseForWrite(), updated)
        return updated
    }

    fun delete(deckId: String, deviceId: String) {
        val current = list(includeDeleted = true).firstOrNull { it.id == deckId } ?: return
        upsertDeck(database.databaseForWrite(), current.copy(
            deleted = true,
            updatedAt = System.currentTimeMillis(),
            deviceId = deviceId,
        ))
    }

    fun addFromCollection(
        deckId: String,
        item: CollectionItem,
        section: DeckSection,
        deviceId: String,
    ): DeckCard {
        require(item.quantity > 0 && !item.deleted) { "Nur vorhandene Sammlungskarten können verwendet werden." }
        val deck = list().firstOrNull { it.id == deckId } ?: error("Deck nicht gefunden.")
        val inDeck = deck.cards.filter { !it.deleted && it.cardKey.cardId == item.cardKey.cardId }.sumOf { it.quantity }
        val owned = collectionStore.ownedQuantity(item.cardKey.cardId)
        require(inDeck < minOf(3, owned)) { "Keine weitere vorhandene Kopie dieser Karte verfügbar." }
        val existing = deck.cards.firstOrNull {
            !it.deleted && it.cardKey == item.cardKey && it.setCode == item.selectedPrint.setCode && it.section == section
        }
        val updated = if (existing == null) DeckCard(
            deckId = deckId,
            cardKey = item.cardKey,
            cardName = item.cardName,
            imageUrl = item.imageUrl,
            setCode = item.selectedPrint.setCode,
            section = section,
            deviceId = deviceId,
        ) else existing.copy(
            quantity = existing.quantity + 1,
            updatedAt = System.currentTimeMillis(),
            deviceId = deviceId,
            deleted = false,
        )
        val db = database.databaseForWrite()
        db.beginTransaction()
        try {
            upsertCard(db, updated)
            touchDeck(db, deckId, deviceId)
            db.setTransactionSuccessful()
        } finally {
            db.endTransaction()
        }
        return updated
    }

    fun setCardQuantity(id: String, quantity: Int, deviceId: String) {
        val db = database.databaseForRead()
        val current = db.rawQuery("SELECT * FROM deck_cards WHERE id = ?", arrayOf(id)).use {
            if (it.moveToFirst()) it.toDeckCard() else null
        } ?: return
        val owned = collectionStore.ownedQuantity(current.cardKey.cardId)
        val deck = list().firstOrNull { it.id == current.deckId } ?: return
        val otherCopies = deck.cards.filter { !it.deleted && it.id != id && it.cardKey.cardId == current.cardKey.cardId }
            .sumOf { it.quantity }
        val safeQuantity = quantity.coerceIn(0, maxOf(0, minOf(3, owned) - otherCopies))
        upsertCard(database.databaseForWrite(), current.copy(
            quantity = safeQuantity,
            deleted = safeQuantity == 0,
            updatedAt = System.currentTimeMillis(),
            deviceId = deviceId,
        ))
        touchDeck(database.databaseForWrite(), current.deckId, deviceId)
    }

    fun merge(decks: List<Deck>) {
        if (decks.isEmpty()) return
        val db = database.databaseForWrite()
        db.beginTransaction()
        try {
            val local = list(includeDeleted = true).associateBy(Deck::id)
            decks.forEach { incoming ->
                val existing = local[incoming.id]
                if (existing == null || wins(incoming.updatedAt, incoming.deviceId, existing.updatedAt, existing.deviceId)) {
                    upsertDeck(db, incoming.copy(cards = emptyList()))
                }
                val localCards = existing?.cards.orEmpty().associateBy(DeckCard::id)
                incoming.cards.forEach { card ->
                    val localCard = localCards[card.id]
                    if (localCard == null || wins(card.updatedAt, card.deviceId, localCard.updatedAt, localCard.deviceId)) {
                        deleteEquivalentCards(db, card)
                        upsertCard(db, card)
                    }
                }
            }
            db.setTransactionSuccessful()
        } finally {
            db.endTransaction()
        }
    }

    fun replaceAll(decks: List<Deck>) {
        val db = database.databaseForWrite()
        db.beginTransaction()
        try {
            db.delete("deck_cards", null, null)
            db.delete("decks", null, null)
            decks.forEach { deck ->
                upsertDeck(db, deck.copy(cards = emptyList()))
                deck.cards.forEach { upsertCard(db, it) }
            }
            db.setTransactionSuccessful()
        } finally {
            db.endTransaction()
        }
    }

    private fun touchDeck(db: SQLiteDatabase, deckId: String, deviceId: String) {
        val updated = db.update(
            "decks",
            ContentValues().apply {
                put("updated_at", System.currentTimeMillis())
                put("device_id", deviceId)
            },
            "id = ?",
            arrayOf(deckId),
        )
        check(updated == 1) { "Deck konnte nicht aktualisiert werden." }
    }

    private fun upsertDeck(db: SQLiteDatabase, deck: Deck) {
        val deckId = deck.id.ifBlank { UUID.randomUUID().toString() }
        val values = ContentValues().apply {
            put("id", deckId)
            put("name", deck.name)
            put("notes", deck.notes)
            put("updated_at", deck.updatedAt)
            put("device_id", deck.deviceId)
            put("deleted", if (deck.deleted) 1 else 0)
        }
        val updated = db.update("decks", values, "id = ?", arrayOf(deckId))
        if (updated == 0) {
            check(db.insertWithOnConflict("decks", null, values, SQLiteDatabase.CONFLICT_ABORT) != -1L) {
                "Deck konnte nicht gespeichert werden."
            }
        }
    }

    private fun upsertCard(db: SQLiteDatabase, card: DeckCard) {
        check(db.insertWithOnConflict("deck_cards", null, ContentValues().apply {
            put("id", card.id.ifBlank { UUID.randomUUID().toString() })
            put("deck_id", card.deckId)
            put("card_id", card.cardKey.cardId)
            put("artwork_id", card.cardKey.artworkId)
            put("card_language", card.cardKey.language)
            put("card_name", card.cardName)
            put("image_url", card.imageUrl)
            put("set_code", card.setCode)
            put("section_name", card.section.name)
            put("quantity", card.quantity)
            put("updated_at", card.updatedAt)
            put("device_id", card.deviceId)
            put("deleted", if (card.deleted) 1 else 0)
        }, SQLiteDatabase.CONFLICT_REPLACE) != -1L) { "Deckkarte konnte nicht gespeichert werden." }
    }

    private fun deleteEquivalentCards(db: SQLiteDatabase, card: DeckCard) {
        db.delete(
            "deck_cards",
            "deck_id = ? AND card_id = ? AND artwork_id = ? AND card_language = ? " +
                "AND set_code = ? AND section_name = ? AND id <> ?",
            arrayOf(
                card.deckId,
                card.cardKey.cardId.toString(),
                card.cardKey.artworkId.toString(),
                card.cardKey.language,
                card.setCode,
                card.section.name,
                card.id,
            ),
        )
    }

    private fun wins(incomingTime: Long, incomingDevice: String, localTime: Long, localDevice: String): Boolean =
        incomingTime > localTime || (incomingTime == localTime && incomingDevice > localDevice)

    companion object {
        const val MAX_DECKS = 50
    }
}

private fun Cursor.toDeck(cards: List<DeckCard>): Deck = Deck(
    id = getString(idx("id")),
    name = getString(idx("name")),
    notes = getString(idx("notes")),
    cards = cards,
    updatedAt = getLong(idx("updated_at")),
    deviceId = getString(idx("device_id")),
    deleted = getInt(idx("deleted")) != 0,
)

private fun Cursor.toDeckCard(): DeckCard = DeckCard(
    id = getString(idx("id")),
    deckId = getString(idx("deck_id")),
    cardKey = CardKey(
        cardId = getLong(idx("card_id")),
        artworkId = getLong(idx("artwork_id")),
        language = getString(idx("card_language")),
    ),
    cardName = getString(idx("card_name")),
    imageUrl = getString(idx("image_url")),
    setCode = getString(idx("set_code")),
    section = runCatching { DeckSection.valueOf(getString(idx("section_name"))) }.getOrDefault(DeckSection.MAIN),
    quantity = getInt(idx("quantity")),
    updatedAt = getLong(idx("updated_at")),
    deviceId = getString(idx("device_id")),
    deleted = getInt(idx("deleted")) != 0,
)

private fun Cursor.idx(name: String): Int = getColumnIndexOrThrow(name)
