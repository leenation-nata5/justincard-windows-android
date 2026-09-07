package org.yugioh.kartenliste.data.model

import java.util.UUID

enum class CardCondition(val label: String) {
    MINT("Mint"),
    NEAR_MINT("Near Mint"),
    EXCELLENT("Excellent"),
    GOOD("Good"),
    PLAYED("Played"),
    POOR("Poor"),
}

data class CollectionItem(
    val id: String = UUID.randomUUID().toString(),
    val cardKey: CardKey,
    val cardName: String,
    val imageUrl: String,
    val selectedPrint: CardPrint,
    val condition: CardCondition = CardCondition.NEAR_MINT,
    val language: String = selectedPrint.language,
    val quantity: Int = 1,
    val notes: String = "",
    val updatedAt: Long = System.currentTimeMillis(),
    val deviceId: String,
    val deleted: Boolean = false,
) {
    val identityKey: String
        get() = listOf(
            cardKey.cardId,
            cardKey.artworkId,
            selectedPrint.setCode.uppercase(),
            selectedPrint.rarity.lowercase(),
            condition.name,
            language.lowercase(),
        ).joinToString("|")
}

enum class DeckSection(val label: String) {
    MAIN("Main Deck"),
    EXTRA("Extra Deck"),
    SIDE("Side Deck"),
}

data class DeckCard(
    val id: String = UUID.randomUUID().toString(),
    val deckId: String,
    val cardKey: CardKey,
    val cardName: String,
    val imageUrl: String,
    val setCode: String = "",
    val section: DeckSection,
    val quantity: Int = 1,
    val updatedAt: Long = System.currentTimeMillis(),
    val deviceId: String,
    val deleted: Boolean = false,
)

data class Deck(
    val id: String = UUID.randomUUID().toString(),
    val name: String,
    val notes: String = "",
    val cards: List<DeckCard> = emptyList(),
    val updatedAt: Long = System.currentTimeMillis(),
    val deviceId: String,
    val deleted: Boolean = false,
) {
    val mainCount: Int get() = cards.filter { !it.deleted && it.section == DeckSection.MAIN }.sumOf { it.quantity }
    val extraCount: Int get() = cards.filter { !it.deleted && it.section == DeckSection.EXTRA }.sumOf { it.quantity }
    val sideCount: Int get() = cards.filter { !it.deleted && it.section == DeckSection.SIDE }.sumOf { it.quantity }

    val validation: DeckValidation
        get() {
            val problems = buildList {
                if (mainCount !in 40..60) add("Das Main Deck muss 40 bis 60 Karten enthalten.")
                if (extraCount > 15) add("Das Extra Deck darf höchstens 15 Karten enthalten.")
                if (sideCount > 15) add("Das Side Deck darf höchstens 15 Karten enthalten.")
                cards.filterNot { it.deleted }
                    .groupBy { it.cardKey.cardId }
                    .filterValues { rows -> rows.sumOf { it.quantity } > 3 }
                    .forEach { (_, rows) -> add("${rows.first().cardName} ist öfter als dreimal enthalten.") }
            }
            return DeckValidation(problems.isEmpty(), problems)
        }
}

data class DeckValidation(
    val isValid: Boolean,
    val problems: List<String>,
)

data class CollectionSummary(
    val totalCards: Int = 0,
    val uniquePrints: Int = 0,
    val estimatedValueUsd: Double = 0.0,
)
