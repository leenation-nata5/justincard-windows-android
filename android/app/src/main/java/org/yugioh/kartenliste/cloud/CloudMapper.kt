package org.yugioh.kartenliste.cloud

import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import org.yugioh.kartenliste.core.CloudContract
import org.yugioh.kartenliste.core.DeckRules
import org.yugioh.kartenliste.data.Card
import org.yugioh.kartenliste.data.CollectionItem
import org.yugioh.kartenliste.data.Deck
import org.yugioh.kartenliste.data.DeckCard

object CloudMapper {
    private val gson = Gson()
    private val mapType = object : TypeToken<Map<String, Any?>>() {}.type

    fun collectionToMap(item: CollectionItem): Map<String, Any?> = linkedMapOf(
        "collection_key" to canonicalKey(item),
        "print_code" to item.printCode,
        "set_name" to item.setName,
        "rarity" to item.rarity,
        "artwork_url" to item.artworkUrl,
        "language" to item.language,
        "quantity" to item.quantity,
        "condition" to item.condition,
        "note" to item.note,
        "updated_at" to item.updatedAt,
        "card" to gson.fromJson<Map<String, Any?>>(gson.toJson(item.card), mapType),
    )

    fun mapToCollection(raw: Map<String, Any?>): CollectionItem? {
        val cardRaw = raw["card"] ?: raw["card_json"] ?: return null
        val card = when (cardRaw) {
            is String -> runCatching { gson.fromJson(cardRaw, Card::class.java) }.getOrNull()
            else -> runCatching { gson.fromJson(gson.toJson(cardRaw), Card::class.java) }.getOrNull()
        } ?: return null
        val printCode = raw.string("print_code")
        val rarity = raw.string("rarity")
        val language = raw.string("language").ifBlank { card.language.ifBlank { "en" } }
        val artwork = raw.string("artwork_url")
        val key = CloudContract.canonicalCollectionKey(card.id, printCode, rarity, language, artwork)
        return CollectionItem(
            collectionKey = key,
            printCode = printCode,
            setName = raw.string("set_name"),
            rarity = rarity,
            artworkUrl = artwork,
            language = language,
            quantity = raw.int("quantity").coerceAtLeast(0),
            condition = raw.string("condition").ifBlank { "Near Mint" },
            note = raw.string("note"),
            updatedAt = raw.double("updated_at"),
            card = card.copy(language = language),
        )
    }

    fun mergeCollection(local: List<CollectionItem>, cloud: List<CollectionItem>): List<CollectionItem> {
        val merged = linkedMapOf<String, CollectionItem>()
        (local + cloud).forEach { item ->
            val key = canonicalKey(item)
            val normalized = item.copy(collectionKey = key)
            val current = merged[key]
            if (current == null || normalized.updatedAt >= current.updatedAt) merged[key] = normalized
        }
        return merged.values.sortedWith(compareBy({ it.card.name.lowercase() }, { it.printCode.lowercase() }, { it.rarity.lowercase() }))
    }

    fun deckToMap(deck: Deck): Map<String, Any?> = linkedMapOf(
        "deck_id" to deck.deckId,
        "name" to deck.name,
        "description" to deck.description,
        "favorite" to deck.favorite,
        "updated_at" to deck.updatedAt,
        "cards" to deck.cards.map(::deckCardToMap),
    )

    private fun deckCardToMap(item: DeckCard): Map<String, Any?> = linkedMapOf(
        "collection_key" to item.collectionKey,
        "source_collection_key" to item.sourceCollectionKey,
        "print_code" to item.printCode,
        "set_name" to item.setName,
        "rarity" to item.rarity,
        "artwork_url" to item.artworkUrl,
        "language" to item.language,
        "quantity" to item.quantity,
        "condition" to item.condition,
        "note" to item.note,
        "updated_at" to item.updatedAt,
        "zone" to DeckRules.allowedZone(item.zone, item.card.type, item.card.frameType),
        "is_placeholder" to item.isPlaceholder,
        "card" to gson.fromJson<Map<String, Any?>>(gson.toJson(item.card), mapType),
    )

    fun mapToDeck(raw: Map<String, Any?>): Deck? {
        val id = raw.string("deck_id").ifBlank { raw.string("id") }
        val name = raw.string("name")
        if (id.isBlank() && name.isBlank()) return null
        val deckId = id.ifBlank { "cloud:${name.lowercase().replace(' ', '-')}" }
        val cards = (raw["cards"] as? List<*>)?.mapNotNull { value ->
            @Suppress("UNCHECKED_CAST")
            val item = value as? Map<String, Any?> ?: return@mapNotNull null
            mapToDeckCard(deckId, item)
        }.orEmpty()
        return Deck(
            deckId = deckId,
            name = name.ifBlank { "Unbenanntes Deck" },
            description = raw.string("description"),
            favorite = raw.bool("favorite"),
            updatedAt = raw.double("updated_at"),
            cards = cards,
        )
    }

    private fun mapToDeckCard(deckId: String, raw: Map<String, Any?>): DeckCard? {
        val cardRaw = raw["card"] ?: return null
        val card = runCatching { gson.fromJson(gson.toJson(cardRaw), Card::class.java) }.getOrNull() ?: return null
        val source = raw.string("source_collection_key").ifBlank { raw.string("collection_key").removePrefix("__placeholder__:") }
        return DeckCard(
            deckId = deckId,
            collectionKey = raw.string("collection_key").ifBlank { source },
            sourceCollectionKey = source,
            zone = DeckRules.allowedZone(raw.string("zone"), card.type, card.frameType),
            quantity = raw.int("quantity").coerceAtLeast(1),
            isPlaceholder = raw.bool("is_placeholder") || raw.string("collection_key").startsWith("__placeholder__:"),
            printCode = raw.string("print_code"),
            setName = raw.string("set_name"),
            rarity = raw.string("rarity"),
            artworkUrl = raw.string("artwork_url"),
            language = raw.string("language"),
            condition = raw.string("condition"),
            note = raw.string("note"),
            updatedAt = raw.double("updated_at"),
            card = card,
        )
    }

    fun mergeDecks(local: List<Deck>, cloud: List<Deck>): List<Deck> {
        val merged = linkedMapOf<String, Deck>()
        (local + cloud).forEach { deck ->
            val key = deck.deckId.ifBlank { deck.name.lowercase() }
            val current = merged[key]
            if (current == null || deck.updatedAt >= current.updatedAt) merged[key] = deck.copy(
                cards = deck.cards.map { it.copy(zone = DeckRules.allowedZone(it.zone, it.card.type, it.card.frameType)) }
            )
        }
        return merged.values.toList()
    }

    fun canonicalKey(item: CollectionItem): String = CloudContract.canonicalCollectionKey(
        item.card.id, item.printCode, item.rarity, item.language, item.artworkUrl
    )

    private fun Map<String, Any?>.string(key: String) = this[key]?.toString().orEmpty()
    private fun Map<String, Any?>.double(key: String): Double = when (val v = this[key]) {
        is Number -> v.toDouble(); else -> v?.toString()?.toDoubleOrNull() ?: 0.0
    }
    private fun Map<String, Any?>.int(key: String): Int = when (val v = this[key]) {
        is Number -> v.toInt(); else -> v?.toString()?.toDoubleOrNull()?.toInt() ?: 0
    }
    private fun Map<String, Any?>.bool(key: String): Boolean = when (val v = this[key]) {
        is Boolean -> v; is Number -> v.toInt() != 0; else -> v?.toString()?.equals("true", true) == true
    }
}
