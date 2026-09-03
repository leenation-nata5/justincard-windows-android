package org.yugioh.kartenliste.cloud

import org.yugioh.kartenliste.core.CloudContract
import org.yugioh.kartenliste.data.Card
import org.yugioh.kartenliste.data.CollectionItem
import org.yugioh.kartenliste.data.Deck
import org.yugioh.kartenliste.data.DeckCard
import java.util.Locale

/**
 * Mirrors the exact visible Google-Sheets template used by Windows 1.2.7.
 * No effect text, price, rarity, language, note or backup-only metadata is
 * written to the browser-visible workbook.
 */
object SheetTemplate {
    enum class SortField(val token: String, val label: String) {
        NAME("name", "Name / alphabetisch"),
        CARD_TYPE("card_type", "Kartentyp"),
        PASSCODE("passcode", "Passcode"),
        SET_CODE("set_code", "Set-Code"),
        RACE("race", "Typ"),
        ATTRIBUTE("attribute", "Element"),
        CATEGORY("category", "Kategorie"),
        LEVEL("level", "Sterne"),
    }

    enum class Direction(val token: String, val label: String) {
        ASC("asc", "Aufsteigend"),
        DESC("desc", "Absteigend"),
    }

    data class WorkbookRows(
        val collectionTabs: Map<String, List<List<Any>>>,
        val deckTabs: Map<String, List<List<Any>>>,
    )

    fun family(card: Card): String {
        val text = listOf(card.type, card.frameType, card.race).joinToString(" ").lowercase(Locale.ROOT)
        return when {
            "spell" in text -> CloudContract.SPELL_SHEET
            "trap" in text -> CloudContract.TRAP_SHEET
            else -> CloudContract.MONSTER_SHEET
        }
    }

    fun monsterCategory(card: Card): String {
        val text = listOf(card.type, card.frameType, card.race).joinToString(" ").lowercase(Locale.ROOT)
        if ("tuner" in text) return "Empfänger"
        val mapping = listOf(
            "fusion" to "Fusion",
            "synchro" to "Synchro",
            "xyz" to "Xyz",
            "link" to "Link",
            "ritual" to "Ritual",
            "pendulum" to "Pendel",
            "normal" to "Normal",
            "effect" to "Effekt",
            "token" to "Token",
        )
        return mapping.firstOrNull { (needle, _) -> needle in text }?.second ?: "Monster"
    }

    fun spellTrapCategory(card: Card): String {
        val normalized = card.race.trim().lowercase(Locale.ROOT)
        return when (normalized) {
            "normal" -> "Normal"
            "continuous" -> "Permanent"
            "quick-play", "quick play" -> "Schnellzauber"
            "field" -> "Spielfeld"
            "equip" -> "Ausrüstung"
            "ritual" -> "Ritual"
            "counter" -> "Konter"
            else -> card.race.ifBlank { "Normal" }
        }
    }

    fun category(item: CollectionItem): String =
        if (family(item.card) == CloudContract.MONSTER_SHEET) monsterCategory(item.card) else spellTrapCategory(item.card)

    private fun sortValue(item: CollectionItem, field: SortField): Comparable<*>? = when (field) {
        SortField.NAME -> item.card.name.lowercase(Locale.ROOT)
        SortField.CARD_TYPE -> item.card.type.lowercase(Locale.ROOT)
        SortField.PASSCODE -> item.card.id
        SortField.SET_CODE -> item.printCode.uppercase(Locale.ROOT)
        SortField.RACE -> item.card.race.lowercase(Locale.ROOT)
        SortField.ATTRIBUTE -> item.card.attribute.lowercase(Locale.ROOT)
        SortField.CATEGORY -> category(item).lowercase(Locale.ROOT)
        SortField.LEVEL -> item.card.level ?: -1
    }

    @Suppress("UNCHECKED_CAST")
    fun sorted(items: List<CollectionItem>, field: SortField, direction: Direction): List<CollectionItem> {
        val comparator = Comparator<CollectionItem> { a, b ->
            val av = sortValue(a, field)
            val bv = sortValue(b, field)
            val result = when {
                av == null && bv == null -> 0
                av == null -> 1
                bv == null -> -1
                av is Number && bv is Number -> av.toDouble().compareTo(bv.toDouble())
                else -> (av.toString()).compareTo(bv.toString(), ignoreCase = true)
            }
            if (direction == Direction.DESC) -result else result
        }
        return items.sortedWith(comparator)
    }

    fun monsterRow(item: CollectionItem): List<Any> = listOf(
        item.card.level ?: "",
        item.card.name,
        item.card.race,
        item.card.attribute,
        monsterCategory(item.card),
        item.printCode,
    )

    fun spellRow(item: CollectionItem): List<Any> = listOf(
        spellTrapCategory(item.card),
        item.card.name,
        item.printCode,
    )

    fun collectionTabs(
        items: List<CollectionItem>,
        field: SortField = SortField.NAME,
        direction: Direction = Direction.ASC,
    ): Map<String, List<List<Any>>> {
        val result = linkedMapOf(
            CloudContract.MONSTER_SHEET to mutableListOf<List<Any>>(CloudContract.MONSTER_HEADERS),
            CloudContract.SPELL_SHEET to mutableListOf<List<Any>>(CloudContract.SPELL_HEADERS),
            CloudContract.TRAP_SHEET to mutableListOf<List<Any>>(CloudContract.TRAP_HEADERS),
        )
        sorted(items, field, direction).forEach { item ->
            val rows = result.getValue(family(item.card))
            val row = if (family(item.card) == CloudContract.MONSTER_SHEET) monsterRow(item) else spellRow(item)
            repeat(item.quantity.coerceAtLeast(0)) { rows += row }
        }
        return result
    }

    fun sanitizeSheetTitle(value: String): String {
        var text = value.trim().replace(Regex("[:\\\\/?*\\[\\]]"), "-")
            .replace(Regex("\\s+"), " ").ifBlank { "Ohne Namen" }
        if (text.length > 100) text = text.take(100)
        if (text in CloudContract.BASE_SHEETS) text = (text.take(93) + " (Deck)").take(100)
        return text
    }

    private fun deckRow(card: DeckCard): List<Any> {
        val item = CollectionItem(
            collectionKey = card.sourceCollectionKey,
            printCode = card.printCode,
            setName = card.setName,
            rarity = card.rarity,
            artworkUrl = card.artworkUrl,
            language = card.language,
            quantity = card.quantity,
            condition = card.condition,
            note = card.note,
            updatedAt = card.updatedAt,
            card = card.card,
        )
        return if (family(card.card) == CloudContract.MONSTER_SHEET) monsterRow(item) else listOf(
            "", card.card.name, "", "", spellTrapCategory(card.card), card.printCode
        )
    }

    /** Deck order stays exactly as stored in the app; no cloud sort is applied. */
    fun deckRows(deck: Deck): List<List<Any>> {
        val rows = mutableListOf<List<Any>>(CloudContract.MONSTER_HEADERS)
        var first = true
        listOf("main" to "Main Deck", "extra" to "Extra Deck", "side" to "Side Deck").forEach { (zone, label) ->
            val cards = deck.cards.filter { it.zone.equals(zone, true) }
            if (cards.isEmpty()) return@forEach
            if (!first) rows += listOf("", "", "", "", "", "")
            rows += listOf("", label, "", "", "", "")
            cards.forEach { card -> repeat(card.quantity.coerceAtLeast(1)) { rows += deckRow(card) } }
            first = false
        }
        return rows
    }

    fun deckTabs(decks: List<Deck>): Map<String, List<List<Any>>> {
        val result = linkedMapOf<String, List<List<Any>>>()
        val used = CloudContract.BASE_SHEETS.toMutableSet()
        decks.forEach { deck ->
            val base = sanitizeSheetTitle(deck.name)
            var title = base
            var index = 2
            while (title in used) {
                val suffix = " ($index)"
                title = base.take((100 - suffix.length).coerceAtLeast(1)) + suffix
                index++
            }
            used += title
            result[title] = deckRows(deck)
        }
        return result
    }

    fun workbook(
        collection: List<CollectionItem>, decks: List<Deck>,
        field: SortField = SortField.NAME, direction: Direction = Direction.ASC,
    ) = WorkbookRows(collectionTabs(collection, field, direction), deckTabs(decks))
}
