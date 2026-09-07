package org.yugioh.kartenliste.scanner

import org.yugioh.kartenliste.data.model.ScanSignals
import java.util.Locale

object OcrSignalParser {
    private val fullSetCode = Regex(
        "\\b([A-Z0-9]{2,12})[- ]((?:DE|EN|FR|IT|PT|SP|ES|JP|KR|AE|EU|NA|OC|TC|GR|BR|PL|RU|TR)?)[- ]?([0-9]{2,4}[A-Z]?)\\b",
        RegexOption.IGNORE_CASE,
    )
    private val passcode = Regex("(?<![0-9])([0-9]{8})(?![0-9])")
    private val atkDef = Regex(
        "(?:ATK|ANGR(?:IFF)?)[\\s/:.-]*([?0-9]{1,5}).{0,24}?(?:DEF|VERT(?:EIDIGUNG)?)[\\s/:.-]*([?0-9]{1,5})",
        setOf(RegexOption.IGNORE_CASE, RegexOption.DOT_MATCHES_ALL),
    )
    private val level = Regex("(?:LEVEL|LVL|STUFE|RANG|RANK|LINK)[\\s:.-]*([0-9]{1,2})", RegexOption.IGNORE_CASE)

    fun parse(rawTexts: List<String>): ScanSignals {
        val text = rawTexts.filter(String::isNotBlank).distinct().joinToString("\n")
        val upper = text.uppercase(Locale.ROOT)
            .replace('—', '-')
            .replace('–', '-')
            .replace('_', '-')

        val setCodes = buildList {
            fullSetCode.findAll(upper).forEach { match ->
                val prefix = repairPrefix(match.groupValues[1])
                val language = match.groupValues[2]
                val number = repairNumber(match.groupValues[3])
                val code = "$prefix-${language}$number"
                if (prefix.length >= 2 && number.length >= 2 && code !in this) add(code)
            }
        }
        val passcodes = passcode.findAll(upper).map { it.groupValues[1] }.distinct().take(6).toList()
        val stats = atkDef.find(upper)
        val possibleNames = text.lineSequence()
            .map(String::trim)
            .filter { line ->
                line.length in 3..70 &&
                    line.count(Char::isLetter) >= 3 &&
                    !line.contains("ATK", true) &&
                    !line.contains("DEF", true) &&
                    !fullSetCode.containsMatchIn(line) &&
                    !passcode.containsMatchIn(line) &&
                    !line.contains("©")
            }
            .distinctBy { it.lowercase(Locale.ROOT) }
            .take(10)
            .toList()

        return ScanSignals(
            rawText = text,
            setCodes = setCodes,
            passcodes = passcodes,
            possibleNames = possibleNames,
            atk = stats?.groupValues?.getOrNull(1)?.takeUnless { it == "?" }?.toIntOrNull(),
            def = stats?.groupValues?.getOrNull(2)?.takeUnless { it == "?" }?.toIntOrNull(),
            level = level.find(upper)?.groupValues?.getOrNull(1)?.toIntOrNull(),
            detectedScripts = detectScripts(text),
        )
    }

    private fun repairPrefix(value: String): String = value.uppercase(Locale.ROOT)
        .replace('1', 'I')
        .replace('0', 'O')
        .replace('5', 'S')
        .replace('8', 'B')

    private fun repairNumber(value: String): String = value.uppercase(Locale.ROOT)
        .replace('O', '0')
        .replace('I', '1')
        .replace('L', '1')
        .replace('S', '5')
        .replace('B', '8')

    private fun detectScripts(value: String): Set<String> = buildSet {
        value.forEach { char ->
            when (char.code) {
                in 0x3040..0x30FF -> add("japanese")
                in 0x4E00..0x9FFF -> add("cjk")
                in 0xAC00..0xD7AF -> add("korean")
                in 0x0900..0x097F -> add("devanagari")
                in 0x0041..0x024F -> add("latin")
            }
        }
    }
}
