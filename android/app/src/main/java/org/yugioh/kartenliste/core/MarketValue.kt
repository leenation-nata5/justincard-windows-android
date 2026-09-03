package org.yugioh.kartenliste.core

import org.yugioh.kartenliste.data.Card
import org.yugioh.kartenliste.data.CollectionItem

object MarketValue {
    private val conditionFactors = mapOf(
        "Mint" to 1.08, "Near Mint" to 1.0, "Excellent" to 0.88,
        "Good" to 0.75, "Light Played" to 0.68, "Played" to 0.55, "Poor" to 0.35
    )

    fun estimateEur(item: CollectionItem): Double? {
        val card = item.card
        val cardmarket = card.cardPrices.firstOrNull()?.cardmarketPrice?.toDoubleOrNull()
        val print = card.cardSets.firstOrNull { it.setCode.equals(item.printCode, true) }
            ?: card.cardSets.firstOrNull { p ->
                p.setCode.substringBefore('-').equals(item.printCode.substringBefore('-'), true)
            }
        val printUsd = print?.setPrice?.toDoubleOrNull()
        val allPrints = card.cardSets.mapNotNull { it.setPrice.toDoubleOrNull() }.filter { it > 0.0 }
        val median = if (allPrints.isEmpty()) null else allPrints.sorted()[allPrints.size / 2]
        val base = when {
            cardmarket != null && printUsd != null && median != null && median > 0.0 -> cardmarket * (printUsd / median).coerceIn(0.25, 4.0)
            cardmarket != null -> cardmarket
            printUsd != null -> printUsd * 0.88
            else -> null
        } ?: return null
        return (base * (conditionFactors[item.condition] ?: 1.0)).coerceAtLeast(0.0)
    }

    fun collectionTotal(items: List<CollectionItem>): Double =
        items.sumOf { (estimateEur(it) ?: 0.0) * it.quantity.coerceAtLeast(0) }
}
