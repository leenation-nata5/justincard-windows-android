package org.yugioh.kartenliste.core

object DeckRules {
    const val MAIN = "main"
    const val EXTRA = "extra"
    const val SIDE = "side"

    fun isExtraDeckCard(cardType: String?, frameType: String?): Boolean {
        val text = "${cardType.orEmpty()} ${frameType.orEmpty()}".lowercase()
        return listOf("fusion", "synchro", "xyz", "link").any(text::contains)
    }

    fun automaticZone(cardType: String?, frameType: String?): String =
        if (isExtraDeckCard(cardType, frameType)) EXTRA else MAIN

    fun allowedZone(requested: String?, cardType: String?, frameType: String?): String {
        if (requested.equals(SIDE, ignoreCase = true)) return SIDE
        return automaticZone(cardType, frameType)
    }
}
