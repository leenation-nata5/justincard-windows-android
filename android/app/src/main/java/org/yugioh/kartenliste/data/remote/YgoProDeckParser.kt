package org.yugioh.kartenliste.data.remote

import android.util.JsonReader
import android.util.JsonToken
import org.yugioh.kartenliste.data.model.Card
import org.yugioh.kartenliste.data.model.CardKey
import org.yugioh.kartenliste.data.model.CardPrint
import java.io.InputStream
import java.io.InputStreamReader

object YgoProDeckParser {
    fun parse(input: InputStream, language: String): List<Card> {
        val cards = mutableListOf<Card>()
        JsonReader(InputStreamReader(input, Charsets.UTF_8)).use { reader ->
            reader.beginObject()
            while (reader.hasNext()) {
                when (reader.nextName()) {
                    "data" -> {
                        reader.beginArray()
                        while (reader.hasNext()) cards += readCard(reader, language)
                        reader.endArray()
                    }
                    else -> reader.skipValue()
                }
            }
            reader.endObject()
        }
        return cards
    }

    private fun readCard(reader: JsonReader, language: String): List<Card> {
        var id = 0L
        var name = ""
        var description = ""
        var type = ""
        var frameType = ""
        var race = ""
        var attribute = ""
        var archetype = ""
        var atk: Int? = null
        var def: Int? = null
        var level: Int? = null
        var linkValue: Int? = null
        var scale: Int? = null
        var cardMarketPrice: Double? = null
        var tcgPlayerPrice: Double? = null
        val prints = mutableListOf<CardPrint>()
        val images = mutableListOf<RemoteImage>()

        reader.beginObject()
        while (reader.hasNext()) {
            when (reader.nextName()) {
                "id" -> id = reader.longOrNull() ?: 0L
                "name" -> name = reader.stringOrEmpty()
                "desc" -> description = reader.stringOrEmpty()
                "type" -> type = reader.stringOrEmpty()
                "frameType" -> frameType = reader.stringOrEmpty()
                "race" -> race = reader.stringOrEmpty()
                "attribute" -> attribute = reader.stringOrEmpty()
                "archetype" -> archetype = reader.stringOrEmpty()
                "atk" -> atk = reader.intOrNull()
                "def" -> def = reader.intOrNull()
                "level" -> level = reader.intOrNull()
                "linkval" -> linkValue = reader.intOrNull()
                "scale" -> scale = reader.intOrNull()
                "card_sets" -> readPrints(reader, id, prints)
                "card_images" -> readImages(reader, images)
                "card_prices" -> {
                    reader.beginArray()
                    if (reader.hasNext()) {
                        reader.beginObject()
                        while (reader.hasNext()) {
                            when (reader.nextName()) {
                                "cardmarket_price" -> cardMarketPrice = reader.doubleOrNull()
                                "tcgplayer_price" -> tcgPlayerPrice = reader.doubleOrNull()
                                else -> reader.skipValue()
                            }
                        }
                        reader.endObject()
                    }
                    while (reader.hasNext()) reader.skipValue()
                    reader.endArray()
                }
                else -> reader.skipValue()
            }
        }
        reader.endObject()

        if (id <= 0L || name.isBlank()) return emptyList()
        val safeImages = images.ifEmpty {
            mutableListOf(RemoteImage(
                id = id,
                imageUrl = "https://images.ygoprodeck.com/images/cards/$id.jpg",
                thumbnailUrl = "https://images.ygoprodeck.com/images/cards_small/$id.jpg",
                croppedUrl = "https://images.ygoprodeck.com/images/cards_cropped/$id.jpg",
            ))
        }
        val now = System.currentTimeMillis()
        val normalizedPrints = prints.map { if (it.cardId == id) it else it.copy(cardId = id) }
        return safeImages.map { image ->
            Card(
                key = CardKey(id, image.id.takeIf { it > 0 } ?: id, language),
                name = name,
                description = description,
                type = type,
                frameType = frameType,
                race = race,
                attribute = attribute,
                archetype = archetype,
                atk = atk,
                def = def,
                level = level,
                linkValue = linkValue,
                pendulumScale = scale,
                imageUrl = image.imageUrl,
                thumbnailUrl = image.thumbnailUrl.ifBlank { image.imageUrl },
                croppedImageUrl = image.croppedUrl,
                cardMarketPrice = cardMarketPrice,
                tcgPlayerPrice = tcgPlayerPrice,
                prints = normalizedPrints.distinctBy(CardPrint::stableKey),
                updatedAt = now,
            )
        }
    }

    private fun readPrints(reader: JsonReader, cardId: Long, target: MutableList<CardPrint>) {
        if (reader.peek() == JsonToken.NULL) {
            reader.nextNull()
            return
        }
        reader.beginArray()
        while (reader.hasNext()) {
            var setName = ""
            var setCode = ""
            var rarity = ""
            var rarityCode = ""
            var price: Double? = null
            reader.beginObject()
            while (reader.hasNext()) {
                when (reader.nextName()) {
                    "set_name" -> setName = reader.stringOrEmpty()
                    "set_code" -> setCode = reader.stringOrEmpty()
                    "set_rarity" -> rarity = reader.stringOrEmpty()
                    "set_rarity_code" -> rarityCode = reader.stringOrEmpty()
                    "set_price" -> price = reader.doubleOrNull()
                    else -> reader.skipValue()
                }
            }
            reader.endObject()
            if (setCode.isNotBlank() || setName.isNotBlank()) {
                target += CardPrint(
                    cardId = cardId,
                    setName = setName.ifBlank { "Unbekanntes Set" },
                    setCode = setCode.ifBlank { "UNBEKANNT" },
                    rarity = rarity.ifBlank { "Unbekannt" },
                    rarityCode = rarityCode,
                    priceUsd = price,
                )
            }
        }
        reader.endArray()
    }

    private fun readImages(reader: JsonReader, target: MutableList<RemoteImage>) {
        if (reader.peek() == JsonToken.NULL) {
            reader.nextNull()
            return
        }
        reader.beginArray()
        while (reader.hasNext()) {
            var id = 0L
            var image = ""
            var small = ""
            var cropped = ""
            reader.beginObject()
            while (reader.hasNext()) {
                when (reader.nextName()) {
                    "id" -> id = reader.longOrNull() ?: 0L
                    "image_url" -> image = reader.stringOrEmpty()
                    "image_url_small" -> small = reader.stringOrEmpty()
                    "image_url_cropped" -> cropped = reader.stringOrEmpty()
                    else -> reader.skipValue()
                }
            }
            reader.endObject()
            if (image.isNotBlank()) target += RemoteImage(id, image, small, cropped)
        }
        reader.endArray()
    }

    private data class RemoteImage(
        val id: Long,
        val imageUrl: String,
        val thumbnailUrl: String,
        val croppedUrl: String,
    )
}

private fun JsonReader.stringOrEmpty(): String = when (peek()) {
    JsonToken.NULL -> { nextNull(); "" }
    JsonToken.STRING, JsonToken.NUMBER, JsonToken.BOOLEAN -> nextString()
    else -> { skipValue(); "" }
}

private fun JsonReader.longOrNull(): Long? = stringOrEmpty().toLongOrNull()
private fun JsonReader.intOrNull(): Int? = stringOrEmpty().toIntOrNull()
private fun JsonReader.doubleOrNull(): Double? = stringOrEmpty().replace(',', '.').toDoubleOrNull()
