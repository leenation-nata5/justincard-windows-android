package org.yugioh.kartenliste.core

data class NormalizedSetCode(
    val original: String,
    val englishReference: String,
    val language: String,
    val marker: String,
)

object SetCodeNormalizer {
    private val codeRegex = Regex("^([A-Z0-9]{2,12})-([A-Z]{2,3})([A-Z0-9-]*)$")
    private val languageMap = mapOf(
        "DE" to "de", "EN" to "en", "FR" to "fr", "IT" to "it",
        "PT" to "pt", "ES" to "es", "JP" to "ja", "JA" to "ja",
        "KO" to "ko", "KR" to "ko", "TC" to "zh-tw", "SC" to "zh-cn"
    )

    fun normalize(value: String): NormalizedSetCode? {
        val input = value.trim().uppercase().replace('–', '-').replace('—', '-')
        val match = codeRegex.matchEntire(input) ?: return null
        val prefix = match.groupValues[1]
        val marker = match.groupValues[2]
        val suffix = match.groupValues[3]
        val language = languageMap[marker] ?: return null
        return NormalizedSetCode(
            original = "$prefix-$marker$suffix",
            englishReference = "$prefix-EN$suffix",
            language = language,
            marker = marker,
        )
    }

    fun languageFromSetCode(value: String, fallback: String = "en"): String =
        normalize(value)?.language ?: fallback.lowercase()
}
