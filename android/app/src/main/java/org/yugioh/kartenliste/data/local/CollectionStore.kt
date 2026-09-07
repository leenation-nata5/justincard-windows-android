package org.yugioh.kartenliste.data.local

import android.content.ContentValues
import android.database.Cursor
import android.database.sqlite.SQLiteDatabase
import org.yugioh.kartenliste.data.model.Card
import org.yugioh.kartenliste.data.model.CardCondition
import org.yugioh.kartenliste.data.model.CardKey
import org.yugioh.kartenliste.data.model.CardPrint
import org.yugioh.kartenliste.data.model.CollectionItem
import org.yugioh.kartenliste.data.model.CollectionSummary
import java.util.UUID

class CollectionStore(private val database: JustInCardDatabase) {
    fun list(includeDeleted: Boolean = false): List<CollectionItem> {
        val where = if (includeDeleted) "1 = 1" else "deleted = 0 AND quantity > 0"
        return database.databaseForRead().rawQuery(
            "SELECT * FROM collection_items WHERE $where ORDER BY card_name COLLATE NOCASE, set_code, rarity",
            null,
        ).use { cursor -> buildList { while (cursor.moveToNext()) add(cursor.toCollectionItem()) } }
    }

    fun summary(): CollectionSummary = database.databaseForRead().rawQuery(
        """SELECT COALESCE(SUM(quantity), 0), COUNT(*),
                  COALESCE(SUM(quantity * COALESCE(price_usd, 0)), 0)
           FROM collection_items WHERE deleted = 0 AND quantity > 0""".trimIndent(),
        null,
    ).use { cursor ->
        if (!cursor.moveToFirst()) CollectionSummary()
        else CollectionSummary(cursor.getInt(0), cursor.getInt(1), cursor.getDouble(2))
    }

    fun add(
        card: Card,
        print: CardPrint,
        deviceId: String,
        quantity: Int = 1,
        condition: CardCondition = CardCondition.NEAR_MINT,
        language: String = print.language,
        notes: String = "",
    ): CollectionItem {
        val draft = CollectionItem(
            cardKey = card.key,
            cardName = card.name,
            imageUrl = card.thumbnailUrl.ifBlank { card.imageUrl },
            selectedPrint = print,
            condition = condition,
            language = language,
            quantity = quantity.coerceAtLeast(1),
            notes = notes,
            deviceId = deviceId,
        )
        val db = database.databaseForWrite()
        val existing = db.rawQuery(
            "SELECT * FROM collection_items WHERE identity_key = ? LIMIT 1",
            arrayOf(draft.identityKey),
        ).use { if (it.moveToFirst()) it.toCollectionItem() else null }
        val result = if (existing == null) draft else existing.copy(
            quantity = existing.quantity.coerceAtLeast(0) + draft.quantity,
            cardName = draft.cardName,
            imageUrl = draft.imageUrl,
            updatedAt = System.currentTimeMillis(),
            deviceId = deviceId,
            deleted = false,
        )
        upsert(db, result)
        return result
    }

    fun setQuantity(id: String, quantity: Int, deviceId: String): CollectionItem? {
        val current = item(id) ?: return null
        val updated = current.copy(
            quantity = quantity.coerceAtLeast(0),
            updatedAt = System.currentTimeMillis(),
            deviceId = deviceId,
            deleted = quantity <= 0,
        )
        upsert(database.databaseForWrite(), updated)
        return updated
    }

    fun updateDetails(
        id: String,
        condition: CardCondition,
        notes: String,
        deviceId: String,
    ): CollectionItem? {
        val current = item(id) ?: return null
        val updated = current.copy(
            condition = condition,
            notes = notes.trim(),
            updatedAt = System.currentTimeMillis(),
            deviceId = deviceId,
        )
        val db = database.databaseForWrite()
        db.beginTransaction()
        try {
            db.delete("collection_items", "id = ?", arrayOf(id))
            val collision = db.rawQuery(
                "SELECT * FROM collection_items WHERE identity_key = ? LIMIT 1",
                arrayOf(updated.identityKey),
            ).use { if (it.moveToFirst()) it.toCollectionItem() else null }
            val merged = if (collision == null) updated else collision.copy(
                quantity = collision.quantity + updated.quantity,
                notes = updated.notes.ifBlank { collision.notes },
                updatedAt = updated.updatedAt,
                deviceId = deviceId,
                deleted = false,
            )
            upsert(db, merged)
            db.setTransactionSuccessful()
            return merged
        } finally {
            db.endTransaction()
        }
    }

    fun item(id: String): CollectionItem? = database.databaseForRead().rawQuery(
        "SELECT * FROM collection_items WHERE id = ? LIMIT 1",
        arrayOf(id),
    ).use { if (it.moveToFirst()) it.toCollectionItem() else null }

    fun ownedQuantity(cardId: Long): Int = database.databaseForRead().rawQuery(
        "SELECT COALESCE(SUM(quantity), 0) FROM collection_items WHERE card_id = ? AND deleted = 0",
        arrayOf(cardId.toString()),
    ).use { if (it.moveToFirst()) it.getInt(0) else 0 }

    fun merge(records: List<CollectionItem>) {
        if (records.isEmpty()) return
        val db = database.databaseForWrite()
        db.beginTransaction()
        try {
            records.forEach { incoming ->
                val local = item(incoming.id)
                if (local == null || incoming.updatedAt > local.updatedAt ||
                    (incoming.updatedAt == local.updatedAt && incoming.deviceId > local.deviceId)
                ) {
                    upsert(db, incoming)
                }
            }
            db.setTransactionSuccessful()
        } finally {
            db.endTransaction()
        }
    }

    fun replaceAll(records: List<CollectionItem>) {
        val db = database.databaseForWrite()
        db.beginTransaction()
        try {
            db.delete("collection_items", null, null)
            records.forEach { upsert(db, it) }
            db.setTransactionSuccessful()
        } finally {
            db.endTransaction()
        }
    }

    private fun upsert(db: SQLiteDatabase, item: CollectionItem) {
        db.insertWithOnConflict("collection_items", null, ContentValues().apply {
            put("id", item.id.ifBlank { UUID.randomUUID().toString() })
            put("identity_key", item.identityKey)
            put("card_id", item.cardKey.cardId)
            put("artwork_id", item.cardKey.artworkId)
            put("card_language", item.cardKey.language)
            put("card_name", item.cardName)
            put("image_url", item.imageUrl)
            put("set_name", item.selectedPrint.setName)
            put("set_code", item.selectedPrint.setCode)
            put("rarity", item.selectedPrint.rarity)
            put("rarity_code", item.selectedPrint.rarityCode)
            item.selectedPrint.priceUsd?.let { put("price_usd", it) } ?: putNull("price_usd")
            put("language", item.language)
            put("condition_name", item.condition.name)
            put("quantity", item.quantity)
            put("notes", item.notes)
            put("updated_at", item.updatedAt)
            put("device_id", item.deviceId)
            put("deleted", if (item.deleted) 1 else 0)
        }, SQLiteDatabase.CONFLICT_REPLACE)
    }
}

private fun Cursor.toCollectionItem(): CollectionItem = CollectionItem(
    id = getString(index("id")),
    cardKey = CardKey(
        cardId = getLong(index("card_id")),
        artworkId = getLong(index("artwork_id")),
        language = getString(index("card_language")),
    ),
    cardName = getString(index("card_name")),
    imageUrl = getString(index("image_url")),
    selectedPrint = CardPrint(
        cardId = getLong(index("card_id")),
        setName = getString(index("set_name")),
        setCode = getString(index("set_code")),
        rarity = getString(index("rarity")),
        rarityCode = getString(index("rarity_code")),
        priceUsd = nullableDouble("price_usd"),
        language = getString(index("language")),
    ),
    condition = runCatching { CardCondition.valueOf(getString(index("condition_name"))) }
        .getOrDefault(CardCondition.NEAR_MINT),
    language = getString(index("language")),
    quantity = getInt(index("quantity")),
    notes = getString(index("notes")),
    updatedAt = getLong(index("updated_at")),
    deviceId = getString(index("device_id")),
    deleted = getInt(index("deleted")) != 0,
)

private fun Cursor.index(name: String): Int = getColumnIndexOrThrow(name)
private fun Cursor.nullableDouble(name: String): Double? = index(name).let { if (isNull(it)) null else getDouble(it) }
