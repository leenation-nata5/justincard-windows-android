package org.yugioh.kartenliste

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.yugioh.kartenliste.scanner.OcrSignalParser

class OcrSignalParserTest {
    @Test
    fun givesSetCodePriorityAndReadsStats() {
        val result = OcrSignalParser.parse(listOf(
            "Blauäugiger w. Drache\nLOB-DE001\n89631139\nATK/3000 DEF/2500\nSTUFE 8",
        ))
        assertEquals("LOB-DE001", result.setCodes.first())
        assertTrue("89631139" in result.passcodes)
        assertEquals(3000, result.atk)
        assertEquals(2500, result.def)
        assertEquals(8, result.level)
    }

    @Test
    fun detectsJapaneseScript() {
        val result = OcrSignalParser.parse(listOf("ブラック・マジシャン"))
        assertTrue("japanese" in result.detectedScripts)
    }
}
