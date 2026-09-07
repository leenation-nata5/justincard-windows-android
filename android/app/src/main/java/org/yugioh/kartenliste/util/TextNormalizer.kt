package org.yugioh.kartenliste.util

import java.text.Normalizer
import java.util.Locale

object TextNormalizer {
    private val nonAlphaNumeric = Regex("[^a-z0-9]+")
    private val setCodePattern = Regex("([A-Z0-9]{2,12})[- ](?:([A-Z]{1,2})[- ]?)?([0-9]{2,4}[A-Z]?)")

    fun searchKey(value: String?): String {
        if (value.isNullOrBlank()) return ""
        val ascii = Normalizer.normalize(value, Normalizer.Form.NFD)
            .replace(Regex("\\p{M}+"), "")
            .replace("ß", "ss")
            .lowercase(Locale.ROOT)
        return ascii.replace(nonAlphaNumeric, " ").trim().replace(Regex("\\s+"), " ")
    }

    fun compactKey(value: String?): String = searchKey(value).replace(" ", "")

    fun setCodeSignature(value: String?): String {
        val raw = value.orEmpty().uppercase(Locale.ROOT).replace('_', '-').trim()
        val match = setCodePattern.find(raw) ?: return raw.filter(Char::isLetterOrDigit)
        return match.groupValues[1] + match.groupValues[3]
    }

    fun setPrefix(value: String?): String {
        val normalized = value.orEmpty().uppercase(Locale.ROOT).trim()
        return Regex("^[A-Z0-9]{2,12}").find(normalized)?.value.orEmpty()
    }

    fun languageFromSetCode(value: String?): String {
        val code = value.orEmpty().uppercase(Locale.ROOT)
        return Regex("-([A-Z]{2})(?=[0-9]{2,4}[A-Z]?$)")
            .find(code)?.groupValues?.get(1)?.lowercase(Locale.ROOT) ?: "unknown"
    }

    fun setCodeEquivalent(left: String?, right: String?): Boolean {
        val a = setCodeSignature(left)
        val b = setCodeSignature(right)
        return a.isNotBlank() && a == b
    }
}
