package org.yugioh.kartenliste.sync

import org.yugioh.kartenliste.data.model.CardCondition
import org.yugioh.kartenliste.data.model.CardKey
import org.yugioh.kartenliste.data.model.CardPrint
import org.yugioh.kartenliste.data.model.CollectionItem
import java.io.Reader
import java.util.UUID

object CsvCollectionCodec {
    private val headers = listOf(
        "id", "card_id", "artwork_id", "card_name", "image_url", "set_name", "set_code",
        "rarity", "rarity_code", "language", "condition", "quantity", "price_usd", "notes",
        "updated_at", "device_id", "deleted",
    )

    fun encode(items: List<CollectionItem>): String = buildString {
        appendLine(headers.joinToString(","))
        items.forEach { item ->
            appendLine(listOf(
                item.id,
                item.cardKey.cardId.toString(),
                item.cardKey.artworkId.toString(),
                item.cardName,
                item.imageUrl,
                item.selectedPrint.setName,
                item.selectedPrint.setCode,
                item.selectedPrint.rarity,
                item.selectedPrint.rarityCode,
                item.language,
                item.condition.name,
                item.quantity.toString(),
                item.selectedPrint.priceUsd?.toString().orEmpty(),
                item.notes,
                item.updatedAt.toString(),
                item.deviceId,
                item.deleted.toString(),
            ).joinToString(",", transform = ::escape))
        }
    }

    fun decode(reader: Reader, fallbackDeviceId: String): List<CollectionItem> {
        val rows = parseRows(reader.readText())
        if (rows.isEmpty()) return emptyList()
        val header = rows.first().map { it.trim().lowercase() }
        val index = header.withIndex().associate { it.value to it.index }
        require("card_id" in index && "set_code" in index && "quantity" in index) {
            "CSV-Spalten card_id, set_code und quantity fehlen."
        }
        fun List<String>.value(name: String): String = index[name]?.let { getOrNull(it) }.orEmpty().trim()
        return rows.drop(1).mapNotNull { row ->
            val cardId = row.value("card_id").toLongOrNull() ?: return@mapNotNull null
            val quantity = row.value("quantity").toIntOrNull() ?: 0
            val language = row.value("language").ifBlank { "unknown" }
            CollectionItem(
                id = row.value("id").ifBlank { UUID.randomUUID().toString() },
                cardKey = CardKey(
                    cardId = cardId,
                    artworkId = row.value("artwork_id").toLongOrNull() ?: cardId,
                    language = language.takeIf { it in setOf("de", "en", "fr", "it", "pt") } ?: "en",
                ),
                cardName = row.value("card_name").ifBlank { "Karte $cardId" },
                imageUrl = row.value("image_url"),
                selectedPrint = CardPrint(
                    cardId = cardId,
                    setName = row.value("set_name").ifBlank { "Unbekanntes Set" },
                    setCode = row.value("set_code").ifBlank { "UNBEKANNT" },
                    rarity = row.value("rarity").ifBlank { "Unbekannt" },
                    rarityCode = row.value("rarity_code"),
                    priceUsd = row.value("price_usd").replace(',', '.').toDoubleOrNull(),
                    language = language,
                ),
                condition = runCatching { CardCondition.valueOf(row.value("condition")) }
                    .getOrDefault(CardCondition.NEAR_MINT),
                language = language,
                quantity = quantity.coerceAtLeast(0),
                notes = row.value("notes"),
                updatedAt = row.value("updated_at").toLongOrNull() ?: System.currentTimeMillis(),
                deviceId = row.value("device_id").ifBlank { fallbackDeviceId },
                deleted = row.value("deleted").equals("true", true) || quantity <= 0,
            )
        }
    }

    private fun escape(value: String): String {
        val clean = value.replace("\r\n", "\n").replace('\r', '\n')
        return if (clean.any { it == ',' || it == '"' || it == '\n' }) "\"${clean.replace("\"", "\"\"")}\"" else clean
    }

    private fun parseRows(text: String): List<List<String>> {
        val rows = mutableListOf<List<String>>()
        val row = mutableListOf<String>()
        val field = StringBuilder()
        var quoted = false
        var index = 0
        while (index < text.length) {
            val char = text[index]
            when {
                quoted && char == '"' && index + 1 < text.length && text[index + 1] == '"' -> {
                    field.append('"'); index += 1
                }
                char == '"' -> quoted = !quoted
                !quoted && char == ',' -> { row += field.toString(); field.clear() }
                !quoted && (char == '\n' || char == '\r') -> {
                    if (char == '\r' && index + 1 < text.length && text[index + 1] == '\n') index += 1
                    row += field.toString(); field.clear()
                    if (row.any(String::isNotBlank)) rows += row.toList()
                    row.clear()
                }
                else -> field.append(char)
            }
            index += 1
        }
        if (field.isNotEmpty() || row.isNotEmpty()) {
            row += field.toString()
            if (row.any(String::isNotBlank)) rows += row.toList()
        }
        return rows
    }
}
