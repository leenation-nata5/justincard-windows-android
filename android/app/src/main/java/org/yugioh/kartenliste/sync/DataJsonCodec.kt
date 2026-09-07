package org.yugioh.kartenliste.sync

import org.json.JSONArray
import org.json.JSONObject
import org.yugioh.kartenliste.data.model.CardCondition
import org.yugioh.kartenliste.data.model.CardKey
import org.yugioh.kartenliste.data.model.CardPrint
import org.yugioh.kartenliste.data.model.CollectionItem
import org.yugioh.kartenliste.data.model.Deck
import org.yugioh.kartenliste.data.model.DeckCard
import org.yugioh.kartenliste.data.model.DeckSection

object DataJsonCodec {
    fun collectionToJson(items: List<CollectionItem>): JSONArray = JSONArray().apply {
        items.forEach { put(collectionItemToJson(it)) }
    }

    fun collectionFromJson(array: JSONArray): List<CollectionItem> = buildList {
        for (index in 0 until array.length()) {
            array.optJSONObject(index)?.let { runCatching { add(collectionItemFromJson(it)) } }
        }
    }

    fun decksToJson(decks: List<Deck>): JSONArray = JSONArray().apply {
        decks.forEach { deck ->
            put(JSONObject().apply {
                put("id", deck.id)
                put("name", deck.name)
                put("notes", deck.notes)
                put("updatedAt", deck.updatedAt)
                put("deviceId", deck.deviceId)
                put("deleted", deck.deleted)
                put("cards", JSONArray().apply { deck.cards.forEach { put(deckCardToJson(it)) } })
            })
        }
    }

    fun decksFromJson(array: JSONArray): List<Deck> = buildList {
        for (index in 0 until array.length()) {
            val value = array.optJSONObject(index) ?: continue
            runCatching {
                val cards = value.optJSONArray("cards")?.let { cardArray ->
                    buildList {
                        for (cardIndex in 0 until cardArray.length()) {
                            cardArray.optJSONObject(cardIndex)?.let { add(deckCardFromJson(it)) }
                        }
                    }
                }.orEmpty()
                add(Deck(
                    id = value.requireString("id"),
                    name = value.optString("name", "Deck"),
                    notes = value.optString("notes", ""),
                    cards = cards,
                    updatedAt = value.optLong("updatedAt", 0L),
                    deviceId = value.optString("deviceId", "import"),
                    deleted = value.optBoolean("deleted", false),
                ))
            }
        }
    }

    fun collectionItemToJson(item: CollectionItem): JSONObject = JSONObject().apply {
        put("id", item.id)
        put("cardId", item.cardKey.cardId)
        put("artworkId", item.cardKey.artworkId)
        put("cardLanguage", item.cardKey.language)
        put("cardName", item.cardName)
        put("imageUrl", item.imageUrl)
        put("setName", item.selectedPrint.setName)
        put("setCode", item.selectedPrint.setCode)
        put("rarity", item.selectedPrint.rarity)
        put("rarityCode", item.selectedPrint.rarityCode)
        put("priceUsd", item.selectedPrint.priceUsd ?: JSONObject.NULL)
        put("condition", item.condition.name)
        put("language", item.language)
        put("quantity", item.quantity)
        put("notes", item.notes)
        put("updatedAt", item.updatedAt)
        put("deviceId", item.deviceId)
        put("deleted", item.deleted)
    }

    fun collectionItemFromJson(value: JSONObject): CollectionItem {
        val cardId = value.getLong("cardId")
        return CollectionItem(
            id = value.requireString("id"),
            cardKey = CardKey(
                cardId = cardId,
                artworkId = value.optLong("artworkId", cardId),
                language = value.optString("cardLanguage", "en"),
            ),
            cardName = value.optString("cardName", "Unbekannte Karte"),
            imageUrl = value.optString("imageUrl", ""),
            selectedPrint = CardPrint(
                cardId = cardId,
                setName = value.optString("setName", "Unbekanntes Set"),
                setCode = value.optString("setCode", "UNBEKANNT"),
                rarity = value.optString("rarity", "Unbekannt"),
                rarityCode = value.optString("rarityCode", ""),
                priceUsd = value.optNullableDouble("priceUsd"),
                language = value.optString("language", "unknown"),
            ),
            condition = runCatching { CardCondition.valueOf(value.optString("condition")) }
                .getOrDefault(CardCondition.NEAR_MINT),
            language = value.optString("language", "unknown"),
            quantity = value.optInt("quantity", 0),
            notes = value.optString("notes", ""),
            updatedAt = value.optLong("updatedAt", 0L),
            deviceId = value.optString("deviceId", "import"),
            deleted = value.optBoolean("deleted", false),
        )
    }

    fun deckCardToJson(card: DeckCard): JSONObject = JSONObject().apply {
        put("id", card.id)
        put("deckId", card.deckId)
        put("cardId", card.cardKey.cardId)
        put("artworkId", card.cardKey.artworkId)
        put("cardLanguage", card.cardKey.language)
        put("cardName", card.cardName)
        put("imageUrl", card.imageUrl)
        put("setCode", card.setCode)
        put("section", card.section.name)
        put("quantity", card.quantity)
        put("updatedAt", card.updatedAt)
        put("deviceId", card.deviceId)
        put("deleted", card.deleted)
    }

    fun deckCardFromJson(value: JSONObject): DeckCard = DeckCard(
        id = value.requireString("id"),
        deckId = value.requireString("deckId"),
        cardKey = CardKey(
            cardId = value.getLong("cardId"),
            artworkId = value.optLong("artworkId", value.getLong("cardId")),
            language = value.optString("cardLanguage", "en"),
        ),
        cardName = value.optString("cardName", "Unbekannte Karte"),
        imageUrl = value.optString("imageUrl", ""),
        setCode = value.optString("setCode", ""),
        section = runCatching { DeckSection.valueOf(value.optString("section")) }.getOrDefault(DeckSection.MAIN),
        quantity = value.optInt("quantity", 0),
        updatedAt = value.optLong("updatedAt", 0L),
        deviceId = value.optString("deviceId", "import"),
        deleted = value.optBoolean("deleted", false),
    )
}

private fun JSONObject.requireString(name: String): String = getString(name).also {
    require(it.isNotBlank()) { "$name darf nicht leer sein." }
}

private fun JSONObject.optNullableDouble(name: String): Double? =
    if (!has(name) || isNull(name)) null else optDouble(name).takeUnless(Double::isNaN)
