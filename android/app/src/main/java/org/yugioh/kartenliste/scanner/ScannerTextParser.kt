package org.yugioh.kartenliste.scanner

object ScannerTextParser {
    // Complete print code first; language markers are intentionally retained.
    private val setCode = Regex("\\b([A-Z0-9]{2,12})[- ](DE|EN|FR|IT|PT|ES|JP|JA|KO|KR|TC|SC)([A-Z0-9]{1,8})\\b", RegexOption.IGNORE_CASE)
    private val passcode = Regex("(?<!\\d)(\\d{8})(?!\\d)")

    data class Candidate(val query: String, val kind: Kind) {
        enum class Kind { SET_CODE, PASSCODE }
    }

    fun best(text: String): Candidate? {
        val normalized = text.uppercase().replace('–', '-').replace('—', '-')
        setCode.find(normalized)?.let { match ->
            val value = "${match.groupValues[1]}-${match.groupValues[2]}${match.groupValues[3]}"
            return Candidate(value, Candidate.Kind.SET_CODE)
        }
        passcode.find(text)?.let { return Candidate(it.groupValues[1], Candidate.Kind.PASSCODE) }
        return null
    }
}
