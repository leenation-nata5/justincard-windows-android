package org.yugioh.kartenliste.sync

import org.yugioh.kartenliste.data.model.CardCondition
import org.yugioh.kartenliste.data.model.CardKey
import org.yugioh.kartenliste.data.model.CardPrint
import org.yugioh.kartenliste.data.model.CollectionItem
import org.yugioh.kartenliste.data.model.Deck
import org.yugioh.kartenliste.data.model.DeckCard
import org.yugioh.kartenliste.data.model.DeckSection
import org.yugioh.kartenliste.data.model.SyncDevice

object SheetsTabCodec {
    const val COLLECTION_TAB = "JIC_COLLECTION"
    const val DECKS_TAB = "JIC_DECKS"
    const val DEVICES_TAB = "JIC_DEVICES"
    val allTabs = listOf(COLLECTION_TAB, DECKS_TAB, DEVICES_TAB)

    private val collectionHeader = listOf(
        "schema", "id", "card_id", "artwork_id", "card_language", "card_name", "image_url",
        "set_name", "set_code", "rarity", "rarity_code", "price_usd", "language", "condition",
        "quantity", "notes", "updated_at", "device_id", "deleted",
    )
    private val deckHeader = listOf(
        "schema", "kind", "id", "deck_id", "name", "notes", "card_id", "artwork_id",
        "card_language", "image_url", "set_code", "section", "quantity", "updated_at", "device_id", "deleted",
    )
    private val deviceHeader = listOf("schema", "id", "name", "enabled", "last_seen_at")

    fun collectionRows(items: List<CollectionItem>): List<List<Any?>> = buildList {
        add(collectionHeader)
        items.sortedBy(CollectionItem::id).forEach { item ->
            add(listOf(
                SCHEMA, item.id, item.cardKey.cardId, item.cardKey.artworkId, item.cardKey.language,
                item.cardName, item.imageUrl, item.selectedPrint.setName, item.selectedPrint.setCode,
                item.selectedPrint.rarity, item.selectedPrint.rarityCode, item.selectedPrint.priceUsd,
                item.language, item.condition.name, item.quantity, item.notes, item.updatedAt, item.deviceId,
                item.deleted,
            ))
        }
    }

    fun parseCollection(rows: List<List<String>>): List<CollectionItem> = parseWithHeader(rows) { row ->
        val cardId = row.long("card_id") ?: return@parseWithHeader null
        CollectionItem(
            id = row.text("id").ifBlank { return@parseWithHeader null },
            cardKey = CardKey(cardId, row.long("artwork_id") ?: cardId, row.text("card_language").ifBlank { "en" }),
            cardName = row.text("card_name").ifBlank { "Karte $cardId" },
            imageUrl = row.text("image_url"),
            selectedPrint = CardPrint(
                cardId = cardId,
                setName = row.text("set_name").ifBlank { "Unbekanntes Set" },
                setCode = row.text("set_code").ifBlank { "UNBEKANNT" },
                rarity = row.text("rarity").ifBlank { "Unbekannt" },
                rarityCode = row.text("rarity_code"),
                priceUsd = row.double("price_usd"),
                language = row.text("language").ifBlank { "unknown" },
            ),
            condition = runCatching { CardCondition.valueOf(row.text("condition")) }.getOrDefault(CardCondition.NEAR_MINT),
            language = row.text("language").ifBlank { "unknown" },
            quantity = row.int("quantity") ?: 0,
            notes = row.text("notes"),
            updatedAt = row.long("updated_at") ?: 0L,
            deviceId = row.text("device_id").ifBlank { "unknown" },
            deleted = row.boolean("deleted"),
        )
    }

    fun deckRows(decks: List<Deck>): List<List<Any?>> = buildList {
        add(deckHeader)
        decks.sortedBy(Deck::id).forEach { deck ->
            add(listOf(
                SCHEMA, "deck", deck.id, "", deck.name, deck.notes, "", "", "", "", "", "", "",
                deck.updatedAt, deck.deviceId, deck.deleted,
            ))
            deck.cards.sortedBy(DeckCard::id).forEach { card ->
                add(listOf(
                    SCHEMA, "card", card.id, deck.id, card.cardName, "", card.cardKey.cardId,
                    card.cardKey.artworkId, card.cardKey.language, card.imageUrl, card.setCode, card.section.name,
                    card.quantity, card.updatedAt, card.deviceId, card.deleted,
                ))
            }
        }
    }

    fun parseDecks(rows: List<List<String>>): List<Deck> {
        val parsed = parseWithHeader(rows) { row ->
            when (row.text("kind")) {
                "deck" -> ParsedDeckRow.DeckValue(Deck(
                    id = row.text("id").ifBlank { return@parseWithHeader null },
                    name = row.text("name").ifBlank { "Deck" },
                    notes = row.text("notes"),
                    updatedAt = row.long("updated_at") ?: 0L,
                    deviceId = row.text("device_id").ifBlank { "unknown" },
                    deleted = row.boolean("deleted"),
                ))
                "card" -> {
                    val cardId = row.long("card_id") ?: return@parseWithHeader null
                    ParsedDeckRow.CardValue(DeckCard(
                        id = row.text("id").ifBlank { return@parseWithHeader null },
                        deckId = row.text("deck_id").ifBlank { return@parseWithHeader null },
                        cardKey = CardKey(cardId, row.long("artwork_id") ?: cardId, row.text("card_language").ifBlank { "en" }),
                        cardName = row.text("name").ifBlank { "Karte $cardId" },
                        imageUrl = row.text("image_url"),
                        setCode = row.text("set_code"),
                        section = runCatching { DeckSection.valueOf(row.text("section")) }.getOrDefault(DeckSection.MAIN),
                        quantity = row.int("quantity") ?: 0,
                        updatedAt = row.long("updated_at") ?: 0L,
                        deviceId = row.text("device_id").ifBlank { "unknown" },
                        deleted = row.boolean("deleted"),
                    ))
                }
                else -> null
            }
        }
        val cards = parsed.filterIsInstance<ParsedDeckRow.CardValue>().map(ParsedDeckRow.CardValue::value).groupBy(DeckCard::deckId)
        return parsed.filterIsInstance<ParsedDeckRow.DeckValue>().map { it.value.copy(cards = cards[it.value.id].orEmpty()) }
    }

    fun deviceRows(devices: List<SyncDevice>): List<List<Any?>> = buildList {
        add(deviceHeader)
        devices.sortedBy(SyncDevice::id).forEach { add(listOf(SCHEMA, it.id, it.name, it.enabled, it.lastSeenAt)) }
    }

    fun parseDevices(rows: List<List<String>>, currentId: String): List<SyncDevice> = parseWithHeader(rows) { row ->
        val id = row.text("id").ifBlank { return@parseWithHeader null }
        SyncDevice(
            id = id,
            name = row.text("name").ifBlank { "Android-Gerät" },
            enabled = row.boolean("enabled", true),
            lastSeenAt = row.long("last_seen_at") ?: 0L,
            isCurrent = id == currentId,
        )
    }

    private fun <T> parseWithHeader(rows: List<List<String>>, block: (SheetRow) -> T?): List<T> {
        if (rows.size < 2) return emptyList()
        val header = rows.first().map { it.trim().lowercase() }.withIndex().associate { it.value to it.index }
        return rows.drop(1).mapNotNull { block(SheetRow(it, header)) }
    }

    private sealed interface ParsedDeckRow {
        data class DeckValue(val value: Deck) : ParsedDeckRow
        data class CardValue(val value: DeckCard) : ParsedDeckRow
    }

    private const val SCHEMA = "jic-v1"
}

private class SheetRow(private val values: List<String>, private val header: Map<String, Int>) {
    fun text(name: String): String = header[name]?.let(values::getOrNull).orEmpty().trim()
    fun long(name: String): Long? = text(name).toLongOrNull()
    fun int(name: String): Int? = text(name).toIntOrNull()
    fun double(name: String): Double? = text(name).replace(',', '.').toDoubleOrNull()
    fun boolean(name: String, default: Boolean = false): Boolean = when (text(name).lowercase()) {
        "true", "1", "yes", "ja" -> true
        "false", "0", "no", "nein" -> false
        else -> default
    }
}
