package org.yugioh.kartenliste.sync

import org.json.JSONArray
import org.json.JSONObject
import org.yugioh.kartenliste.data.model.Card
import org.yugioh.kartenliste.data.model.CardCondition
import org.yugioh.kartenliste.data.model.CardKey
import org.yugioh.kartenliste.data.model.CardPrint
import org.yugioh.kartenliste.data.model.CollectionItem
import org.yugioh.kartenliste.data.model.Deck
import org.yugioh.kartenliste.data.model.DeckCard
import org.yugioh.kartenliste.data.model.DeckSection
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone
import java.util.UUID

data class CloudSnapshot(
    val collection: List<CollectionItem> = emptyList(),
    val decks: List<Deck> = emptyList(),
    val cards: Map<CardKey, Card> = emptyMap(),
)

/** Lossless Android <-> Windows 1.2.7 JSON representation stored in Drive appDataFolder. */
object WindowsCloudCodec {
    fun encode(
        spreadsheetId: String,
        deviceName: String,
        snapshot: CloudSnapshot,
        cards: Map<CardKey, Card>,
    ): JSONObject = JSONObject()
        .put("schema", CloudContract.CLOUD_SCHEMA)
        .put("app_version", "13.0.10")
        .put("updated_at", utcNow())
        .put("device", deviceName)
        .put("spreadsheet_id", CloudContract.normalizeSpreadsheetId(spreadsheetId))
        .put("collection", JSONArray().apply {
            snapshot.collection.sortedBy(CollectionItem::id).forEach { item ->
                put(collectionRecord(item, cards[item.cardKey]))
            }
        })
        .put("decks", JSONArray().apply {
            snapshot.decks.filterNot(Deck::deleted).sortedBy(Deck::id).forEach { deck ->
                put(deckRecord(deck, snapshot.collection, cards))
            }
        })

    fun decode(payload: JSONObject, fallbackDeviceId: String): CloudSnapshot {
        val collection = buildList {
            val rows = payload.optJSONArray("collection") ?: JSONArray()
            for (index in 0 until rows.length()) {
                rows.optJSONObject(index)?.let { row ->
                    runCatching { decodeCollection(row, fallbackDeviceId) }.getOrNull()?.let(::add)
                }
            }
        }
        val decks = buildList {
            val rows = payload.optJSONArray("decks") ?: JSONArray()
            for (index in 0 until rows.length()) {
                rows.optJSONObject(index)?.let { row ->
                    runCatching { decodeDeck(row, fallbackDeviceId) }.getOrNull()?.let(::add)
                }
            }
        }
        val decodedCards = cardPayloads(payload)
            .mapNotNull(::decodeCard)
            .groupBy { it.key.cardId }
        val referencedKeys = buildSet {
            collection.forEach { add(it.cardKey) }
            decks.flatMap(Deck::cards).forEach { add(it.cardKey) }
        }
        val cards = buildMap {
            referencedKeys.forEach { key ->
                decodedCards[key.cardId]?.firstOrNull()?.let { put(key, it.copy(key = key)) }
            }
        }
        return CloudSnapshot(collection, decks, cards)
    }

    private fun collectionRecord(item: CollectionItem, resolved: Card?): JSONObject {
        val card = resolved ?: fallbackCard(item.cardKey, item.cardName, item.imageUrl, item.selectedPrint)
        val artworkUrl = card.imageUrl.ifBlank { item.imageUrl }
        return JSONObject()
            .put("collection_key", CloudContract.canonicalCollectionKey(
                item.cardKey.cardId,
                item.selectedPrint.setCode,
                item.selectedPrint.rarity,
                item.language,
                artworkUrl,
            ))
            .put("print_code", item.selectedPrint.setCode)
            .put("set_name", item.selectedPrint.setName)
            .put("rarity", item.selectedPrint.rarity)
            .put("artwork_url", artworkUrl)
            .put("language", item.language)
            .put("quantity", item.quantity.coerceAtLeast(0))
            .put("condition", item.condition.label)
            .put("note", item.notes)
            .put("updated_at", item.updatedAt / 1_000.0)
            .put("deleted", item.deleted)
            .put("source_device_id", item.deviceId)
            .put("card", cardToJson(card))
    }

    private fun deckRecord(
        deck: Deck,
        collection: List<CollectionItem>,
        cards: Map<CardKey, Card>,
    ): JSONObject = JSONObject()
        .put("deck_id", deck.id)
        .put("name", deck.name)
        .put("description", deck.notes)
        .put("favorite", false)
        .put("updated_at", deck.updatedAt / 1_000.0)
        .put("deleted", deck.deleted)
        .put("source_device_id", deck.deviceId)
        .put("cards", JSONArray().apply {
            deck.cards.filter { !it.deleted && it.quantity > 0 }.forEach { deckCard ->
                val source = collection.firstOrNull {
                    it.cardKey == deckCard.cardKey &&
                        it.selectedPrint.setCode.equals(deckCard.setCode, ignoreCase = true)
                }
                val resolved = cards[deckCard.cardKey]
                    ?: fallbackCard(
                        deckCard.cardKey,
                        deckCard.cardName,
                        deckCard.imageUrl,
                        source?.selectedPrint ?: CardPrint(
                            cardId = deckCard.cardKey.cardId,
                            setName = "",
                            setCode = deckCard.setCode,
                            rarity = "",
                            language = deckCard.cardKey.language,
                        ),
                    )
                val artworkUrl = resolved.imageUrl.ifBlank {
                    source?.imageUrl.orEmpty().ifBlank { deckCard.imageUrl }
                }
                val rarity = source?.selectedPrint?.rarity.orEmpty()
                val language = source?.language.orEmpty().ifBlank { deckCard.cardKey.language }
                put(JSONObject()
                    .put("collection_key", CloudContract.canonicalCollectionKey(
                        deckCard.cardKey.cardId,
                        deckCard.setCode,
                        rarity,
                        language,
                        artworkUrl,
                    ))
                    .put("source_collection_key", CloudContract.canonicalCollectionKey(
                        deckCard.cardKey.cardId,
                        deckCard.setCode,
                        rarity,
                        language,
                        artworkUrl,
                    ))
                    .put("print_code", deckCard.setCode)
                    .put("set_name", source?.selectedPrint?.setName.orEmpty())
                    .put("rarity", rarity)
                    .put("artwork_url", artworkUrl)
                    .put("language", language)
                    .put("quantity", deckCard.quantity.coerceAtLeast(0))
                    .put("condition", source?.condition?.label.orEmpty())
                    .put("note", source?.notes.orEmpty())
                    .put("updated_at", deckCard.updatedAt / 1_000.0)
                    .put("zone", deckCard.section.zone)
                    .put("deleted", deckCard.deleted)
                    .put("source_device_id", deckCard.deviceId)
                    .put("card", cardToJson(resolved)))
            }
        })

    private fun cardToJson(card: Card): JSONObject = JSONObject()
        .put("id", card.key.cardId)
        .put("name", card.name)
        .put("desc", card.description)
        .put("type", card.type)
        .put("frameType", card.frameType)
        .put("race", card.race)
        .put("attribute", card.attribute)
        .put("archetype", card.archetype)
        .put("atk", card.atk ?: JSONObject.NULL)
        .put("def", card.def ?: JSONObject.NULL)
        .put("level", card.level ?: JSONObject.NULL)
        .put("linkval", card.linkValue ?: JSONObject.NULL)
        .put("scale", card.pendulumScale ?: JSONObject.NULL)
        .put("_language", card.key.language)
        .put("card_sets", JSONArray().apply {
            card.prints.forEach { print ->
                put(JSONObject()
                    .put("set_name", print.setName)
                    .put("set_code", print.setCode)
                    .put("set_rarity", print.rarity)
                    .put("set_rarity_code", print.rarityCode)
                    .put("set_price", print.priceUsd ?: JSONObject.NULL))
            }
        })
        .put("card_images", JSONArray().put(JSONObject()
            .put("id", card.key.artworkId)
            .put("image_url", card.imageUrl)
            .put("image_url_small", card.thumbnailUrl)
            .put("image_url_cropped", card.croppedImageUrl)))
        .put("card_prices", JSONArray().put(JSONObject()
            .put("cardmarket_price", card.cardMarketPrice ?: JSONObject.NULL)
            .put("tcgplayer_price", card.tcgPlayerPrice ?: JSONObject.NULL)))

    private fun decodeCollection(row: JSONObject, fallbackDeviceId: String): CollectionItem {
        val card = row.optJSONObject("card") ?: JSONObject()
        val cardId = longValue(card, "id").takeIf { it > 0 }
            ?: cardIdFromCollectionKey(row.optCleanString("collection_key"))
            ?: error("Cloud-Eintrag ohne Karten-ID")
        val artworkUrl = row.optCleanString("artwork_url")
            .ifBlank { firstImage(card).optCleanString("image_url") }
        val language = row.optCleanString("language")
            .ifBlank { card.optCleanString("_language") }
            .ifBlank { "unknown" }
        val setCode = row.optCleanString("print_code")
        val rarity = row.optCleanString("rarity")
        val condition = parseCondition(row.optCleanString("condition"))
        val canonical = CloudContract.canonicalCollectionKey(cardId, setCode, rarity, language, artworkUrl)
        val quantity = row.optInt("quantity", 0).coerceAtLeast(0)
        val updatedAt = millis(row.optDouble("updated_at", 0.0))
        val image = firstImage(card)
        return CollectionItem(
            id = stableUuid("collection|$canonical"),
            cardKey = CardKey(
                cardId = cardId,
                artworkId = longValue(image, "id").takeIf { it > 0 } ?: cardId,
                language = card.optCleanString("_language").ifBlank { language },
            ),
            cardName = card.optCleanString("name").ifBlank { "Karte $cardId" },
            imageUrl = image.optCleanString("image_url_small")
                .ifBlank { artworkUrl.ifBlank { image.optCleanString("image_url") } },
            selectedPrint = CardPrint(
                cardId = cardId,
                setName = row.optCleanString("set_name").ifBlank { "Unbekanntes Set" },
                setCode = setCode.ifBlank { "UNBEKANNT" },
                rarity = rarity.ifBlank { "Unbekannt" },
                rarityCode = matchingPrint(card, setCode).optCleanString("set_rarity_code"),
                priceUsd = matchingPrint(card, setCode).nullableDouble("set_price"),
                language = language,
            ),
            condition = condition,
            language = language,
            quantity = quantity,
            notes = row.optCleanString("note"),
            updatedAt = updatedAt,
            deviceId = row.optCleanString("source_device_id").ifBlank { fallbackDeviceId },
            deleted = row.optBoolean("deleted", false) || quantity == 0,
        )
    }

    private fun decodeDeck(row: JSONObject, fallbackDeviceId: String): Deck {
        val name = row.optCleanString("name").ifBlank { "Importiertes Cloud-Deck" }
        val deckId = row.optCleanString("deck_id").ifBlank { row.optCleanString("id") }
            .ifBlank { stableUuid("deck|${name.lowercase()}") }
        val cards = buildList {
            val values = row.optJSONArray("cards") ?: row.optJSONArray("deck_cards") ?: JSONArray()
            for (index in 0 until values.length()) {
                val value = values.optJSONObject(index) ?: continue
                runCatching {
                    val card = value.optJSONObject("card") ?: JSONObject()
                    val cardId = longValue(card, "id").takeIf { it > 0 }
                        ?: cardIdFromCollectionKey(value.optCleanString("collection_key"))
                        ?: return@runCatching
                    val image = firstImage(card)
                    val language = value.optCleanString("language")
                        .ifBlank { card.optCleanString("_language") }
                        .ifBlank { "unknown" }
                    val section = when (value.optCleanString("zone").lowercase()) {
                        "extra" -> DeckSection.EXTRA
                        "side" -> DeckSection.SIDE
                        else -> DeckSection.MAIN
                    }
                    val setCode = value.optCleanString("print_code")
                    add(DeckCard(
                        id = stableUuid("deck-card|$deckId|$index|$cardId|$setCode|${section.name}"),
                        deckId = deckId,
                        cardKey = CardKey(
                            cardId,
                            longValue(image, "id").takeIf { it > 0 } ?: cardId,
                            card.optCleanString("_language").ifBlank { language },
                        ),
                        cardName = card.optCleanString("name").ifBlank { "Karte $cardId" },
                        imageUrl = value.optCleanString("artwork_url").ifBlank {
                            image.optCleanString("image_url_small").ifBlank { image.optCleanString("image_url") }
                        },
                        setCode = setCode,
                        section = section,
                        quantity = value.optInt("quantity", 1).coerceAtLeast(0),
                        updatedAt = millis(value.optDouble("updated_at", row.optDouble("updated_at", 0.0))),
                        deviceId = value.optCleanString("source_device_id").ifBlank { fallbackDeviceId },
                        deleted = value.optBoolean("deleted", false) || value.optInt("quantity", 1) == 0,
                    ))
                }
            }
        }
        return Deck(
            id = deckId,
            name = name,
            notes = row.optCleanString("description"),
            cards = cards,
            updatedAt = millis(row.optDouble("updated_at", 0.0)),
            deviceId = row.optCleanString("source_device_id").ifBlank { fallbackDeviceId },
            deleted = row.optBoolean("deleted", false),
        )
    }

    private fun fallbackCard(key: CardKey, name: String, image: String, print: CardPrint): Card = Card(
        key = key,
        name = name,
        imageUrl = image,
        thumbnailUrl = image,
        prints = listOf(print),
    )

    private fun cardPayloads(payload: JSONObject): List<JSONObject> = buildList {
        val collection = payload.optJSONArray("collection") ?: JSONArray()
        for (index in 0 until collection.length()) {
            collection.optJSONObject(index)?.optJSONObject("card")?.let(::add)
        }
        val decks = payload.optJSONArray("decks") ?: JSONArray()
        for (deckIndex in 0 until decks.length()) {
            val cards = decks.optJSONObject(deckIndex)?.optJSONArray("cards") ?: continue
            for (cardIndex in 0 until cards.length()) {
                cards.optJSONObject(cardIndex)?.optJSONObject("card")?.let(::add)
            }
        }
    }

    private fun decodeCard(value: JSONObject): Card? {
        val cardId = longValue(value, "id").takeIf { it > 0 } ?: return null
        val image = firstImage(value)
        val prices = value.optJSONArray("card_prices")?.optJSONObject(0) ?: JSONObject()
        val prints = buildList {
            val rows = value.optJSONArray("card_sets") ?: JSONArray()
            for (index in 0 until rows.length()) {
                val row = rows.optJSONObject(index) ?: continue
                add(CardPrint(
                    cardId = cardId,
                    setName = row.optCleanString("set_name"),
                    setCode = row.optCleanString("set_code"),
                    rarity = row.optCleanString("set_rarity"),
                    rarityCode = row.optCleanString("set_rarity_code"),
                    priceUsd = row.nullableDouble("set_price"),
                    language = value.optCleanString("_language").ifBlank { "unknown" },
                ))
            }
        }
        val language = value.optCleanString("_language").ifBlank { prints.firstOrNull()?.language ?: "unknown" }
        return Card(
            key = CardKey(
                cardId,
                longValue(image, "id").takeIf { it > 0 } ?: cardId,
                language,
            ),
            name = value.optCleanString("name").ifBlank { "Karte $cardId" },
            description = value.optCleanString("desc"),
            type = value.optCleanString("type"),
            frameType = value.optCleanString("frameType").ifBlank { value.optCleanString("frame_type") },
            race = value.optCleanString("race"),
            attribute = value.optCleanString("attribute"),
            archetype = value.optCleanString("archetype"),
            atk = value.nullableInt("atk"),
            def = value.nullableInt("def"),
            level = value.nullableInt("level") ?: value.nullableInt("rank"),
            linkValue = value.nullableInt("linkval"),
            pendulumScale = value.nullableInt("scale"),
            imageUrl = image.optCleanString("image_url"),
            thumbnailUrl = image.optCleanString("image_url_small"),
            croppedImageUrl = image.optCleanString("image_url_cropped"),
            cardMarketPrice = prices.nullableDouble("cardmarket_price"),
            tcgPlayerPrice = prices.nullableDouble("tcgplayer_price"),
            prints = prints,
        )
    }

    private fun matchingPrint(card: JSONObject, setCode: String): JSONObject {
        val values = card.optJSONArray("card_sets") ?: return JSONObject()
        for (index in 0 until values.length()) {
            val value = values.optJSONObject(index) ?: continue
            if (value.optCleanString("set_code").equals(setCode, true)) return value
        }
        return values.optJSONObject(0) ?: JSONObject()
    }

    private fun firstImage(card: JSONObject): JSONObject =
        card.optJSONArray("card_images")?.optJSONObject(0) ?: JSONObject()

    private fun cardIdFromCollectionKey(value: String): Long? =
        value.substringBefore('|').trim().toLongOrNull()?.takeIf { it > 0 }

    private fun longValue(value: JSONObject, name: String): Long =
        value.opt(name)?.toString()?.toDoubleOrNull()?.toLong() ?: 0L

    private fun millis(value: Double): Long = when {
        !value.isFinite() || value <= 0.0 -> 0L
        value >= 100_000_000_000.0 -> value.toLong()
        else -> (value * 1_000.0).toLong()
    }

    private fun parseCondition(value: String): CardCondition {
        val key = value.trim().lowercase().replace("-", " ").replace("_", " ")
        return when (key) {
            "mint" -> CardCondition.MINT
            "near mint", "neuwertig" -> CardCondition.NEAR_MINT
            "excellent", "exzellent" -> CardCondition.EXCELLENT
            "good", "gut" -> CardCondition.GOOD
            "played", "gespielt" -> CardCondition.PLAYED
            "poor", "schlecht" -> CardCondition.POOR
            else -> CardCondition.NEAR_MINT
        }
    }

    private fun stableUuid(seed: String): String =
        UUID.nameUUIDFromBytes(seed.toByteArray(Charsets.UTF_8)).toString()

    private fun utcNow(): String = SimpleDateFormat(
        "yyyy-MM-dd'T'HH:mm:ss'Z'",
        Locale.ROOT,
    ).apply {
        timeZone = TimeZone.getTimeZone("UTC")
    }.format(Date())

    private val DeckSection.zone: String
        get() = when (this) {
            DeckSection.MAIN -> "main"
            DeckSection.EXTRA -> "extra"
            DeckSection.SIDE -> "side"
        }
}

private fun JSONObject.optCleanString(name: String): String =
    if (!has(name) || isNull(name)) "" else optString(name, "").takeUnless { it == "null" }.orEmpty().trim()

private fun JSONObject.nullableDouble(name: String): Double? =
    if (!has(name) || isNull(name)) null else opt(name)?.toString()?.replace(',', '.')?.toDoubleOrNull()

private fun JSONObject.nullableInt(name: String): Int? =
    if (!has(name) || isNull(name)) null else opt(name)?.toString()?.toDoubleOrNull()?.toInt()
