package org.yugioh.kartenliste.sync

import org.yugioh.kartenliste.data.model.Deck
import org.yugioh.kartenliste.data.model.DeckSection

data class YdkEntry(val passcode: Long, val section: DeckSection)

object YdkCodec {
    fun encode(deck: Deck): String = buildString {
        appendLine("#created by Just InCard")
        appendLine("#main")
        deck.cards.filter { !it.deleted && it.section == DeckSection.MAIN }.forEach { card ->
            repeat(card.quantity) { appendLine(card.cardKey.cardId) }
        }
        appendLine("#extra")
        deck.cards.filter { !it.deleted && it.section == DeckSection.EXTRA }.forEach { card ->
            repeat(card.quantity) { appendLine(card.cardKey.cardId) }
        }
        appendLine("!side")
        deck.cards.filter { !it.deleted && it.section == DeckSection.SIDE }.forEach { card ->
            repeat(card.quantity) { appendLine(card.cardKey.cardId) }
        }
    }

    fun decode(text: String): List<YdkEntry> {
        var section = DeckSection.MAIN
        return buildList {
            text.lineSequence().map(String::trim).forEach { line ->
                when {
                    line.equals("#main", true) -> section = DeckSection.MAIN
                    line.equals("#extra", true) -> section = DeckSection.EXTRA
                    line.equals("!side", true) -> section = DeckSection.SIDE
                    line.startsWith("#") || line.startsWith("!") || line.isBlank() -> Unit
                    else -> line.toLongOrNull()?.takeIf { it > 0 }?.let { add(YdkEntry(it, section)) }
                }
            }
        }
    }
}
