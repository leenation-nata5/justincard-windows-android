package org.yugioh.kartenliste.data.remote

import org.json.JSONArray
import org.json.JSONObject
import org.json.JSONTokener
import org.yugioh.kartenliste.BuildConfig
import org.yugioh.kartenliste.data.model.Card
import org.yugioh.kartenliste.data.model.CardPrint
import org.yugioh.kartenliste.data.model.SearchFilters
import org.yugioh.kartenliste.data.model.SearchSort
import org.yugioh.kartenliste.util.TextNormalizer
import java.io.BufferedInputStream
import java.io.ByteArrayInputStream
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URI
import java.net.URLEncoder
import java.util.zip.GZIPInputStream

class YgoProDeckClient {
    fun databaseVersion(): String {
        val json = requestBytes("checkDBVer.php").decodeToString()
        return when (val root = JSONTokener(json).nextValue()) {
            is JSONArray -> root.optJSONObject(0)?.optString("database_version")
                .orEmpty().ifBlank { root.optJSONObject(0)?.optString("version").orEmpty() }
            is JSONObject -> {
                val versions = root.optJSONArray("database_version")
                if (versions != null && versions.length() > 0) {
                    versions.optJSONObject(0)?.optString("version").orEmpty()
                } else {
                    root.optString("version", root.optString("database_version", "unknown"))
                }
            }
            else -> "unknown"
        }.ifBlank { "unknown" }
    }

    fun allCards(language: String): List<Card> {
        val params = mutableMapOf<String, String>()
        apiLanguage(language)?.let { params["language"] = it }
        return requestCards("cardinfo.php", params, language)
    }

    fun search(filters: SearchFilters): List<Card> {
        val value = filters.normalized()
        if (looksLikeFullPrintCode(value.setQuery)) return searchExactPrint(value.setQuery, value.language)

        val params = linkedMapOf<String, String>()
        if (value.passcode.isNotBlank()) params["id"] = value.passcode
        if (value.name.isNotBlank()) params["fname"] = value.name
        if (value.setQuery.isNotBlank()) params["cardset"] = value.setQuery
        if (value.cardType.isNotBlank()) params["type"] = value.cardType
        if (value.race.isNotBlank()) params["race"] = translateRace(value.race)
        if (value.attribute.isNotBlank()) params["attribute"] = translateAttribute(value.attribute)
        if (value.archetype.isNotBlank()) params["archetype"] = value.archetype
        addNumericFilter(params, "atk", value.atkMin, value.atkMax)
        addNumericFilter(params, "def", value.defMin, value.defMax)
        addNumericFilter(params, "level", value.levelMin, value.levelMax)
        if (value.scaleMin != null && value.scaleMin == value.scaleMax) params["scale"] = value.scaleMin.toString()
        params["sort"] = when (value.sort) {
            SearchSort.NAME -> "name"
            SearchSort.ATTACK_DESC -> "atk"
            SearchSort.DEFENCE_DESC -> "def"
            SearchSort.LEVEL_DESC -> "level"
            SearchSort.NEWEST -> "new"
        }
        apiLanguage(value.language)?.let { params["language"] = it }

        if (params.keys.none { it !in setOf("sort", "language") }) return emptyList()
        return requestCards("cardinfo.php", params, normalizedLanguage(value.language))
            .asSequence()
            .filter { remoteMatches(it, value) }
            .distinctBy { it.key.stableKey }
            .toList()
    }

    fun cardById(id: String, language: String = "en"): List<Card> {
        val params = linkedMapOf("id" to id)
        apiLanguage(language)?.let { params["language"] = it }
        return requestCards("cardinfo.php", params, normalizedLanguage(language))
    }

    private fun searchExactPrint(code: String, language: String): List<Card> {
        val bytes = requestBytes("cardsetsinfo.php", mapOf("setcode" to code.uppercase()))
        val objectValue = JSONObject(bytes.decodeToString())
        val id = objectValue.optLong("id", 0L)
        if (id <= 0L) return emptyList()
        val exactPrint = CardPrint(
            cardId = id,
            setName = objectValue.optString("set_name", "Unbekanntes Set"),
            setCode = objectValue.optString("set_code", code.uppercase()),
            rarity = objectValue.optString("set_rarity", "Unbekannt"),
            rarityCode = objectValue.optString("set_rarity_code", ""),
            priceUsd = objectValue.optString("set_price", "").toDoubleOrNull(),
        )
        return cardById(id.toString(), language).map { card ->
            val matching = card.prints.filter { TextNormalizer.setCodeEquivalent(it.setCode, exactPrint.setCode) }
            card.copy(prints = (matching + exactPrint).distinctBy(CardPrint::stableKey))
        }
    }

    private fun requestCards(path: String, params: Map<String, String>, language: String): List<Card> {
        val bytes = requestBytes(path, params)
        return YgoProDeckParser.parse(ByteArrayInputStream(bytes), normalizedLanguage(language))
    }

    private fun requestBytes(path: String, params: Map<String, String> = emptyMap()): ByteArray {
        val query = params.entries.joinToString("&") { (key, value) ->
            "${encode(key)}=${encode(value)}"
        }
        val url = URI.create(BuildConfig.CATALOG_API_BASE + path + if (query.isBlank()) "" else "?$query").toURL()
        val connection = (url.openConnection() as HttpURLConnection).apply {
            requestMethod = "GET"
            connectTimeout = 15_000
            readTimeout = 75_000
            useCaches = true
            setRequestProperty("Accept", "application/json")
            setRequestProperty("Accept-Encoding", "gzip")
            setRequestProperty("User-Agent", "JustInCard-Android/${BuildConfig.VERSION_NAME}")
        }
        try {
            val status = connection.responseCode
            val raw = if (status in 200..299) connection.inputStream else connection.errorStream
            val stream = BufferedInputStream(raw ?: throw IOException("Leere Serverantwort ($status)"))
            val decoded = if (connection.contentEncoding.equals("gzip", true)) GZIPInputStream(stream) else stream
            val bytes = decoded.use { it.readBytes() }
            if (status !in 200..299) {
                val message = runCatching { JSONObject(bytes.decodeToString()).optString("error") }.getOrNull()
                throw CatalogException(message?.takeIf(String::isNotBlank) ?: "Kartendatenbank meldet HTTP $status")
            }
            return bytes
        } finally {
            connection.disconnect()
        }
    }

    private fun remoteMatches(card: Card, filters: SearchFilters): Boolean {
        fun inRange(value: Int?, min: Int?, max: Int?): Boolean {
            if (min == null && max == null) return true
            if (value == null) return false
            return (min == null || value >= min) && (max == null || value <= max)
        }
        if (!inRange(card.atk, filters.atkMin, filters.atkMax)) return false
        if (!inRange(card.def, filters.defMin, filters.defMax)) return false
        if (!inRange(card.displayLevel, filters.levelMin, filters.levelMax)) return false
        if (!inRange(card.pendulumScale, filters.scaleMin, filters.scaleMax)) return false
        if (filters.effectText.isNotBlank() &&
            !TextNormalizer.searchKey(card.description).contains(TextNormalizer.searchKey(filters.effectText))
        ) return false
        val price = card.cardMarketPrice ?: card.tcgPlayerPrice
        if (filters.priceMin != null && (price == null || price < filters.priceMin)) return false
        if (filters.priceMax != null && (price == null || price > filters.priceMax)) return false
        if (filters.frameType.isNotBlank() && !TextNormalizer.searchKey(card.frameType).contains(TextNormalizer.searchKey(filters.frameType))) return false
        if (filters.rarity.isNotBlank() && card.prints.none {
                TextNormalizer.searchKey(it.rarity).contains(TextNormalizer.searchKey(filters.rarity))
            }
        ) return false
        return true
    }

    private fun addNumericFilter(params: MutableMap<String, String>, key: String, min: Int?, max: Int?) {
        when {
            min != null && max != null && min == max -> params[key] = min.toString()
            min != null -> params[key] = "gte$min"
            max != null -> params[key] = "lte$max"
        }
    }

    private fun apiLanguage(value: String): String? = when (value.lowercase()) {
        "de", "fr", "it", "pt" -> value.lowercase()
        else -> null
    }

    private fun normalizedLanguage(value: String): String = apiLanguage(value) ?: "en"
    private fun looksLikeFullPrintCode(value: String): Boolean =
        Regex("^[A-Za-z0-9]{2,12}[- ](?:[A-Za-z]{1,2})?[0-9]{2,4}[A-Za-z]?$", RegexOption.IGNORE_CASE)
            .matches(value.trim())

    private fun translateAttribute(value: String): String = when (TextNormalizer.searchKey(value)) {
        "dunkel" -> "dark"
        "licht" -> "light"
        "erde" -> "earth"
        "wasser" -> "water"
        "feuer" -> "fire"
        "wind" -> "wind"
        "gottlich" -> "divine"
        else -> value
    }

    private fun translateRace(value: String): String = when (TextNormalizer.searchKey(value)) {
        "drache" -> "dragon"
        "hexer", "magier" -> "spellcaster"
        "krieger" -> "warrior"
        "maschine" -> "machine"
        "fee" -> "fairy"
        "unterweltler" -> "fiend"
        "fels" -> "rock"
        "pflanze" -> "plant"
        "insekt" -> "insect"
        "dinosaurier" -> "dinosaur"
        "reptil" -> "reptile"
        "fisch" -> "fish"
        "seeschlange" -> "sea serpent"
        "donner" -> "thunder"
        "geflugeltes ungeheuer" -> "winged beast"
        "ungeheuer" -> "beast"
        "ungeheuer krieger" -> "beast-warrior"
        else -> value
    }

    private fun encode(value: String): String = URLEncoder.encode(value, Charsets.UTF_8.name())
}

class CatalogException(message: String, cause: Throwable? = null) : IOException(message, cause)
