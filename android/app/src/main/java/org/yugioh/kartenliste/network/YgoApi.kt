package org.yugioh.kartenliste.network

import com.google.gson.Gson
import com.google.gson.JsonObject
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.yugioh.kartenliste.core.SetCodeNormalizer
import org.yugioh.kartenliste.data.Card
import org.yugioh.kartenliste.data.CardPrint
import org.yugioh.kartenliste.data.SearchResult
import java.net.URLEncoder
import java.nio.charset.StandardCharsets
import java.util.concurrent.TimeUnit

class YgoApi(
    private val client: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .build(),
) {
    private val gson = Gson()
    private val base = "https://db.ygoprodeck.com/api/v7"

    suspend fun search(query: String): List<SearchResult> = withContext(Dispatchers.IO) {
        val text = query.trim()
        if (text.isBlank()) return@withContext emptyList()
        val normalized = SetCodeNormalizer.normalize(text)
        if (normalized != null) {
            return@withContext searchBySetCode(
                normalized.englishReference,
                normalized.original,
                normalized.language,
            )
        }
        if (text.all(Char::isDigit) && text.length == 8) {
            return@withContext fetchCards("$base/cardinfo.php?id=${encode(text)}")
                .map { SearchResult(it) }
        }
        fetchCards("$base/cardinfo.php?fname=${encode(text)}&misc=yes")
            .map { SearchResult(it) }
    }

    private fun searchBySetCode(englishCode: String, originalCode: String, language: String): List<SearchResult> {
        val suffix = englishCode.substringAfter("-EN", "")
        if (suffix.isNotBlank()) {
            val setInfoUrl = "$base/cardsetsinfo.php?setcode=${encode(englishCode)}"
            val obj = getJsonObject(setInfoUrl)
            val cardId = sequenceOf("id", "card_id", "passcode")
                .mapNotNull { key -> obj?.get(key)?.asLong }
                .firstOrNull()
            val name = obj?.get("name")?.asString.orEmpty()
            val rarity = obj?.get("set_rarity")?.asString.orEmpty()
            val setName = obj?.get("set_name")?.asString.orEmpty()
            val price = obj?.get("set_price")?.asString.orEmpty()
            val print = CardPrint(englishCode, setName, rarity, setPrice = price)
            val cards = when {
                cardId != null -> fetchCards("$base/cardinfo.php?id=$cardId&misc=yes")
                name.isNotBlank() -> fetchCards("$base/cardinfo.php?name=${encode(name)}&misc=yes")
                else -> emptyList()
            }
            return cards.map { card ->
                val actual = card.cardSets.firstOrNull { it.setCode.equals(englishCode, true) } ?: print
                SearchResult(card, actual, originalCode, language)
            }
        }

        val prefix = englishCode.substringBefore('-').uppercase()
        val setName = resolveSetName(prefix) ?: return emptyList()
        return fetchCards("$base/cardinfo.php?cardset=${encode(setName)}&misc=yes").map { card ->
            val matched = card.cardSets.firstOrNull { it.setCode.uppercase().startsWith("$prefix-EN") }
            SearchResult(card, matched, originalCode, language)
        }
    }

    private fun resolveSetName(prefix: String): String? {
        val body = get("$base/cardsets.php") ?: return null
        val array = gson.fromJson(body, Array<JsonObject>::class.java) ?: return null
        return array.firstOrNull { it.get("set_code")?.asString?.equals(prefix, true) == true }
            ?.get("set_name")?.asString
    }

    private fun fetchCards(url: String): List<Card> {
        val body = get(url) ?: return emptyList()
        val root = gson.fromJson(body, JsonObject::class.java) ?: return emptyList()
        val data = root.getAsJsonArray("data") ?: return emptyList()
        return data.mapNotNull { runCatching { gson.fromJson(it, Card::class.java) }.getOrNull() }
    }

    private fun getJsonObject(url: String): JsonObject? =
        get(url)?.let { runCatching { gson.fromJson(it, JsonObject::class.java) }.getOrNull() }

    private fun get(url: String): String? {
        val request = Request.Builder()
            .url(url)
            .header("User-Agent", "JustInCard-Android/14.1.1")
            .build()
        return client.newCall(request).execute().use { response ->
            if (!response.isSuccessful) return null
            response.body?.string()
        }
    }

    private fun encode(value: String): String =
        URLEncoder.encode(value, StandardCharsets.UTF_8.toString())
}
