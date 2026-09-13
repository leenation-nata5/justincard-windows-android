package org.yugioh.kartenliste.data.model

/**
 * Card-text languages understood across Just InCard.
 *
 * YGOPRODeck currently provides full public catalog downloads for EN/DE/FR/IT/PT.
 * The additional language codes remain selectable so local/synchronised catalogs
 * can be displayed consistently when those translations are present. Missing
 * catalogs deliberately fall back to English instead of hiding a collection card.
 */
object CardLanguages {
    val choices: List<Pair<String, String>> = listOf(
        "de" to "Deutsch",
        "en" to "Englisch",
        "fr" to "Französisch",
        "it" to "Italienisch",
        "pt" to "Portugiesisch",
        "es" to "Spanisch",
        "ja" to "Japanisch",
        "ko" to "Koreanisch",
        "zh" to "Chinesisch (vereinfacht)",
        "zh-tw" to "Chinesisch (traditionell)",
        "nl" to "Niederländisch",
        "pl" to "Polnisch",
        "ru" to "Russisch",
        "tr" to "Türkisch",
    )

    val remoteCatalogLanguages: Set<String> = setOf("en", "de", "fr", "it", "pt")

    fun normalize(value: String?): String {
        val code = value.orEmpty().trim().lowercase().ifBlank { "de" }
        return if (choices.any { it.first == code }) code else "de"
    }

    fun label(code: String): String = choices.firstOrNull { it.first == normalize(code) }?.second ?: code.uppercase()

    fun hasRemoteCatalog(code: String): Boolean = normalize(code) in remoteCatalogLanguages
}
