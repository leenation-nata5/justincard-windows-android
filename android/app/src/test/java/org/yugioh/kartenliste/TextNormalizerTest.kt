package org.yugioh.kartenliste

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.yugioh.kartenliste.util.TextNormalizer

class TextNormalizerTest {
    @Test
    fun normalizesGermanTextAndSetLanguages() {
        assertEquals("weisser drache", TextNormalizer.searchKey("Weißer Drache"))
        assertEquals("LOB001", TextNormalizer.setCodeSignature("LOB-DE001"))
        assertEquals("de", TextNormalizer.languageFromSetCode("LOB-DE001"))
        assertTrue(TextNormalizer.setCodeEquivalent("LOB-DE001", "LOB-EN001"))
    }
}
