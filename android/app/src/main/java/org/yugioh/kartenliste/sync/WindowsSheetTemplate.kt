package org.yugioh.kartenliste.sync

import org.yugioh.kartenliste.data.model.Card
import org.yugioh.kartenliste.data.model.CardKey
import org.yugioh.kartenliste.data.model.CollectionItem
import org.yugioh.kartenliste.data.model.Deck
import org.yugioh.kartenliste.data.model.DeckCard
import org.yugioh.kartenliste.data.model.DeckSection
import java.util.Locale

/** Builds the exact browser-visible workbook used by Just InCard Windows 1.2.7. */
object WindowsSheetTemplate {
    fun workbook(snapshot: CloudSnapshot, cards: Map<CardKey, Card>): Map<String, List<List<Any?>>> {
        val result = linkedMapOf<String, List<List<Any?>>>()
        val activeCollection = snapshot.collection
            .filter { !it.deleted && it.quantity > 0 }
            .sortedWith(compareBy(String.CASE_INSENSITIVE_ORDER) { it.cardName })

        val monsterRows = mutableListOf(header(CloudContract.MONSTER_HEADERS))
        val spellRows = mutableListOf(header(CloudContract.SPELL_HEADERS))
        val trapRows = mutableListOf(header(CloudContract.TRAP_HEADERS))
        activeCollection.forEach { item ->
            val card = cards[item.cardKey] ?: fallbackCard(item)
            val target = when (family(card)) {
                Family.SPELL -> spellRows
                Family.TRAP -> trapRows
                Family.MONSTER -> monsterRows
            }
            repeat(item.quantity.coerceAtLeast(0)) {
                target += collectionRow(item, card)
            }
        }
        result[CloudContract.MONSTER_SHEET] = monsterRows
        result[CloudContract.SPELL_SHEET] = spellRows
        result[CloudContract.TRAP_SHEET] = trapRows

        val used = CloudContract.BASE_SHEETS.toMutableSet()
        snapshot.decks.filterNot(Deck::deleted).forEach { deck ->
            val base = sanitizeTitle(deck.name)
            var title = base
            var counter = 2
            while (title in used) {
                val suffix = " ($counter)"
                title = base.take(100 - suffix.length) + suffix
                counter += 1
            }
            used += title
            result[title] = deckRows(deck, snapshot.collection, cards)
        }
        return result
    }

    private fun collectionRow(item: CollectionItem, card: Card): List<Any?> = when (family(card)) {
        Family.MONSTER -> listOf(
            card.level ?: card.linkValue ?: "",
            card.name,
            card.race,
            card.attribute,
            monsterCategory(card),
            item.selectedPrint.setCode,
        )
        Family.SPELL, Family.TRAP -> listOf(
            spellTrapCategory(card),
            card.name,
            item.selectedPrint.setCode,
        )
    }

    private fun deckRows(
        deck: Deck,
        collection: List<CollectionItem>,
        cards: Map<CardKey, Card>,
    ): List<List<Any?>> {
        val rows = mutableListOf(header(CloudContract.MONSTER_HEADERS))
        var firstSection = true
        listOf(
            DeckSection.MAIN to "Main Deck",
            DeckSection.EXTRA to "Extra Deck",
            DeckSection.SIDE to "Side Deck",
        ).forEach { (section, label) ->
            val sectionCards = deck.cards.filter { !it.deleted && it.quantity > 0 && it.section == section }
            if (sectionCards.isEmpty()) return@forEach
            if (!firstSection) rows += listOf("", "", "", "", "", "")
            rows += listOf("", label, "", "", "", "")
            sectionCards.forEach { item ->
                val source = collection.firstOrNull {
                    it.cardKey == item.cardKey &&
                        it.selectedPrint.setCode.equals(item.setCode, ignoreCase = true)
                }
                val card = cards[item.cardKey] ?: fallbackCard(item)
                repeat(item.quantity.coerceAtLeast(1)) {
                    rows += deckRow(item, source, card)
                }
            }
            firstSection = false
        }
        return rows
    }

    private fun deckRow(item: DeckCard, source: CollectionItem?, card: Card): List<Any?> =
        if (family(card) == Family.MONSTER) {
            listOf(
                card.level ?: card.linkValue ?: "",
                card.name,
                card.race,
                card.attribute,
                monsterCategory(card),
                item.setCode.ifBlank { source?.selectedPrint?.setCode.orEmpty() },
            )
        } else {
            listOf(
                "",
                card.name,
                "",
                "",
                spellTrapCategory(card),
                item.setCode.ifBlank { source?.selectedPrint?.setCode.orEmpty() },
            )
        }

    private fun family(card: Card): Family {
        val text = listOf(card.type, card.frameType, card.race).joinToString(" ").lowercase(Locale.ROOT)
        return when {
            "spell" in text -> Family.SPELL
            "trap" in text -> Family.TRAP
            else -> Family.MONSTER
        }
    }

    private fun monsterCategory(card: Card): String {
        val text = listOf(card.type, card.frameType, card.race).joinToString(" ").lowercase(Locale.ROOT)
        if ("tuner" in text) return "Empfänger"
        return listOf(
            "fusion" to "Fusion",
            "synchro" to "Synchro",
            "xyz" to "Xyz",
            "link" to "Link",
            "ritual" to "Ritual",
            "pendulum" to "Pendel",
            "normal" to "Normal",
            "effect" to "Effekt",
            "token" to "Token",
        ).firstOrNull { (token, _) -> token in text }?.second ?: "Monster"
    }

    private fun spellTrapCategory(card: Card): String = when (card.race.trim().lowercase(Locale.ROOT)) {
        "normal" -> "Normal"
        "continuous" -> "Permanent"
        "quick-play", "quick play" -> "Schnellzauber"
        "field" -> "Spielfeld"
        "equip" -> "Ausrüstung"
        "ritual" -> "Ritual"
        "counter" -> "Konter"
        else -> card.race.ifBlank { "Normal" }
    }

    private fun sanitizeTitle(value: String): String {
        val forbidden = setOf(':', '\\', '/', '?', '*', '[', ']')
        val clean = value.trim()
            .map { if (it in forbidden) '-' else it }
            .joinToString("")
            .split(Regex("\\s+"))
            .filter(String::isNotBlank)
            .joinToString(" ")
            .ifBlank { "Ohne Namen" }
        val base = clean.take(100)
        if (base !in CloudContract.BASE_SHEETS) return base
        val suffix = " (Deck)"
        return base.take(100 - suffix.length) + suffix
    }

    private fun fallbackCard(item: CollectionItem): Card = Card(
        key = item.cardKey,
        name = item.cardName,
        imageUrl = item.imageUrl,
        thumbnailUrl = item.imageUrl,
        prints = listOf(item.selectedPrint),
    )

    private fun fallbackCard(item: DeckCard): Card = Card(
        key = item.cardKey,
        name = item.cardName,
        imageUrl = item.imageUrl,
        thumbnailUrl = item.imageUrl,
    )

    private fun header(values: List<String>): List<Any?> = values.map { it }

    private enum class Family { MONSTER, SPELL, TRAP }
}

