package org.yugioh.kartenliste.data.model

import org.yugioh.kartenliste.util.TextNormalizer

data class CardKey(
    val cardId: Long,
    val artworkId: Long = cardId,
    val language: String = "en",
) {
    val stableKey: String get() = "$cardId:$artworkId:${language.lowercase()}"
}

data class CardPrint(
    val cardId: Long,
    val setName: String,
    val setCode: String,
    val rarity: String,
    val rarityCode: String = "",
    val priceUsd: Double? = null,
    val language: String = TextNormalizer.languageFromSetCode(setCode),
) {
    val stableKey: String
        get() = "$cardId:${TextNormalizer.setCodeSignature(setCode)}:${TextNormalizer.searchKey(rarity)}"
}

data class Card(
    val key: CardKey,
    val name: String,
    val description: String = "",
    val type: String = "",
    val frameType: String = "",
    val race: String = "",
    val attribute: String = "",
    val archetype: String = "",
    val atk: Int? = null,
    val def: Int? = null,
    val level: Int? = null,
    val linkValue: Int? = null,
    val pendulumScale: Int? = null,
    val imageUrl: String = "",
    val thumbnailUrl: String = "",
    val croppedImageUrl: String = "",
    val cardMarketPrice: Double? = null,
    val tcgPlayerPrice: Double? = null,
    val prints: List<CardPrint> = emptyList(),
    val updatedAt: Long = System.currentTimeMillis(),
) {
    val displayLevel: Int? get() = linkValue ?: level
    val isExtraDeck: Boolean
        get() = type.contains("Fusion", true) || type.contains("Synchro", true) ||
            type.contains("XYZ", true) || type.contains("Link", true)
}

enum class SearchSort(val label: String) {
    NAME("Name"),
    ATTACK_DESC("ATK absteigend"),
    DEFENCE_DESC("DEF absteigend"),
    LEVEL_DESC("Stufe / Rang / Link"),
    NEWEST("Neueste zuerst"),
}

data class SearchFilters(
    val name: String = "",
    val effectText: String = "",
    val setQuery: String = "",
    val passcode: String = "",
    val language: String = "all",
    val cardType: String = "",
    val frameType: String = "",
    val race: String = "",
    val attribute: String = "",
    val archetype: String = "",
    val rarity: String = "",
    val atkMin: Int? = null,
    val atkMax: Int? = null,
    val defMin: Int? = null,
    val defMax: Int? = null,
    val levelMin: Int? = null,
    val levelMax: Int? = null,
    val scaleMin: Int? = null,
    val scaleMax: Int? = null,
    val priceMin: Double? = null,
    val priceMax: Double? = null,
    val ownedOnly: Boolean = false,
    val sort: SearchSort = SearchSort.NAME,
) {
    val hasAnyInput: Boolean
        get() = listOf(
            name, effectText, setQuery, passcode, cardType, frameType, race, attribute, archetype, rarity,
        ).any { it.isNotBlank() } || listOf(
            atkMin, atkMax, defMin, defMax, levelMin, levelMax, scaleMin, scaleMax,
        ).any { it != null } || priceMin != null || priceMax != null || ownedOnly || language != "all"

    fun normalized(): SearchFilters = copy(
        name = name.trim(),
        effectText = effectText.trim(),
        setQuery = setQuery.trim(),
        passcode = passcode.filter(Char::isDigit).take(8),
        language = language.lowercase().trim().ifBlank { "all" },
        cardType = cardType.trim(),
        frameType = frameType.trim(),
        race = race.trim(),
        attribute = attribute.trim(),
        archetype = archetype.trim(),
        rarity = rarity.trim(),
        atkMin = atkMin?.coerceAtLeast(-1),
        atkMax = atkMax?.coerceAtLeast(-1),
        defMin = defMin?.coerceAtLeast(-1),
        defMax = defMax?.coerceAtLeast(-1),
        levelMin = levelMin?.coerceIn(0, 13),
        levelMax = levelMax?.coerceIn(0, 13),
        scaleMin = scaleMin?.coerceIn(0, 13),
        scaleMax = scaleMax?.coerceIn(0, 13),
        priceMin = priceMin?.coerceAtLeast(0.0),
        priceMax = priceMax?.coerceAtLeast(0.0),
    )
}

data class SearchPage(
    val cards: List<Card>,
    val total: Int,
    val page: Int,
    val pageSize: Int,
) {
    val hasNext: Boolean get() = (page + 1) * pageSize < total
}
