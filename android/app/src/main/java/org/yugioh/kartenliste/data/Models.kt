package org.yugioh.kartenliste.data

import com.google.gson.annotations.SerializedName

data class CardPrint(
    @SerializedName("set_code") val setCode: String = "",
    @SerializedName("set_name") val setName: String = "",
    @SerializedName("set_rarity") val setRarity: String = "",
    @SerializedName("set_rarity_code") val setRarityCode: String = "",
    @SerializedName("set_price") val setPrice: String = "",
)

data class CardImage(
    val id: Long = 0,
    @SerializedName("image_url") val imageUrl: String = "",
    @SerializedName("image_url_small") val imageUrlSmall: String = "",
    @SerializedName("image_url_cropped") val imageUrlCropped: String = "",
)

data class CardPrice(
    @SerializedName("cardmarket_price") val cardmarketPrice: String = "",
    @SerializedName("tcgplayer_price") val tcgplayerPrice: String = "",
    @SerializedName("ebay_price") val ebayPrice: String = "",
    @SerializedName("amazon_price") val amazonPrice: String = "",
    @SerializedName("coolstuffinc_price") val coolstuffincPrice: String = "",
)

data class Card(
    val id: Long = 0,
    val name: String = "",
    val desc: String = "",
    val type: String = "",
    @SerializedName("frameType") val frameType: String = "",
    val race: String = "",
    val attribute: String = "",
    val atk: Int? = null,
    val def: Int? = null,
    val level: Int? = null,
    val scale: Int? = null,
    val linkval: Int? = null,
    val archetype: String = "",
    @SerializedName("card_sets") val cardSets: List<CardPrint> = emptyList(),
    @SerializedName("card_images") val cardImages: List<CardImage> = emptyList(),
    @SerializedName("card_prices") val cardPrices: List<CardPrice> = emptyList(),
    @SerializedName("_language") val language: String = "en",
)

data class CollectionItem(
    val collectionKey: String,
    val printCode: String,
    val setName: String,
    val rarity: String,
    val artworkUrl: String,
    val language: String,
    val quantity: Int,
    val condition: String = "Near Mint",
    val note: String = "",
    val updatedAt: Double,
    val card: Card,
)

data class DeckCard(
    val id: Long = 0,
    val deckId: String,
    val collectionKey: String,
    val sourceCollectionKey: String = collectionKey,
    val zone: String,
    val quantity: Int,
    val isPlaceholder: Boolean = false,
    val printCode: String = "",
    val setName: String = "",
    val rarity: String = "",
    val artworkUrl: String = "",
    val language: String = "",
    val condition: String = "",
    val note: String = "",
    val updatedAt: Double = 0.0,
    val card: Card,
)

data class Deck(
    val deckId: String,
    val name: String,
    val description: String = "",
    val favorite: Boolean = false,
    val updatedAt: Double,
    val cards: List<DeckCard> = emptyList(),
)

data class CloudBackup(
    val schema: String,
    @SerializedName("app_version") val appVersion: String,
    @SerializedName("updated_at") val updatedAt: String,
    val device: String,
    @SerializedName("spreadsheet_id") val spreadsheetId: String,
    val collection: List<Map<String, Any?>>,
    val decks: List<Map<String, Any?>>,
)

data class SearchResult(
    val card: Card,
    val matchedPrint: CardPrint? = null,
    val requestedSetCode: String = "",
    val requestedLanguage: String = "en",
)
