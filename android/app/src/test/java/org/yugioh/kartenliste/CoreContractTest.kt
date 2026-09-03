package org.yugioh.kartenliste

import org.junit.Assert.*
import org.junit.Test
import org.yugioh.kartenliste.cloud.SheetTemplate
import org.yugioh.kartenliste.core.CloudContract
import org.yugioh.kartenliste.core.DeckRules
import org.yugioh.kartenliste.core.SetCodeNormalizer
import org.yugioh.kartenliste.data.*

class CoreContractTest {
    private val tuner = Card(
        id = 12345678,
        name = "Test Empfänger",
        type = "Effect Tuner Monster",
        frameType = "effect",
        race = "Warrior",
        attribute = "LIGHT",
        level = 4,
    )

    @Test fun setCodesAlwaysUseEnglishReferenceButKeepOriginalLanguage() {
        val de = SetCodeNormalizer.normalize("blmr-de001")!!
        assertEquals("BLMR-EN001", de.englishReference)
        assertEquals("BLMR-DE001", de.original)
        assertEquals("de", de.language)
        val fr = SetCodeNormalizer.normalize("BLMR-FR001")!!
        assertEquals("BLMR-EN001", fr.englishReference)
        assertEquals("fr", fr.language)
    }

    @Test fun cloudContractMatchesWindows() {
        assertEquals("justincard-google-drive-backup-v4", CloudContract.CLOUD_SCHEMA)
        assertEquals("justincard-cloud-backup-v125.json", CloudContract.BACKUP_FILE_NAME)
        assertEquals(listOf("Monsterkarten", "Zauberkarten", "Fallenkarten"), CloudContract.BASE_SHEETS)
        assertEquals(listOf("Sterne", "Name", "Typ", "Element", "Kategorie", "Set-Code"), CloudContract.MONSTER_HEADERS)
        assertTrue(CloudContract.SCOPES.contains(CloudContract.DRIVE_FILE_SCOPE))
        assertTrue(CloudContract.SCOPES.contains(CloudContract.DRIVE_APPDATA_SCOPE))
    }

    @Test fun tunerIsEmpfaengerInExactTemplate() {
        val item = CollectionItem("k", "TEST-DE001", "Set", "Common", "", "de", 2, updatedAt = 1.0, card = tuner)
        val rows = SheetTemplate.collectionTabs(listOf(item)).getValue("Monsterkarten")
        assertEquals(3, rows.size)
        assertEquals("Empfänger", rows[1][4])
        assertEquals("TEST-DE001", rows[1][5])
    }

    @Test fun deckAutomaticallyRoutesExtraCards() {
        assertEquals("extra", DeckRules.allowedZone(null, "Fusion Monster", "fusion"))
        assertEquals("extra", DeckRules.allowedZone("main", "Synchro Monster", "synchro"))
        assertEquals("extra", DeckRules.allowedZone("main", "XYZ Monster", "xyz"))
        assertEquals("extra", DeckRules.allowedZone("main", "Link Monster", "link"))
        assertEquals("main", DeckRules.allowedZone(null, "Effect Monster", "effect"))
        assertEquals("side", DeckRules.allowedZone("side", "Link Monster", "link"))
    }

    @Test fun deckSheetKeepsProgramOrderAndTemplateColumnsOnly() {
        val cards = listOf(
            DeckCard(1, "d", "a", zone = "main", quantity = 1, card = tuner.copy(name = "B")),
            DeckCard(2, "d", "b", zone = "main", quantity = 1, card = tuner.copy(name = "A")),
            DeckCard(3, "d", "c", zone = "extra", quantity = 1, card = tuner.copy(name = "Fusion", type = "Fusion Monster", frameType = "fusion")),
        )
        val rows = SheetTemplate.deckRows(Deck("d", "Deck Eins", updatedAt = 1.0, cards = cards))
        assertEquals(6, rows.first().size)
        assertEquals("Main Deck", rows[1][1])
        assertEquals("B", rows[2][1])
        assertEquals("A", rows[3][1])
        assertTrue(rows.flatten().contains("Extra Deck"))
    }

    @Test fun canonicalCollectionKeyIsCrossPlatformStable() {
        assertEquals(
            "12345678|BLMR-DE001|secret rare|de|https://img/card.jpg",
            CloudContract.canonicalCollectionKey(12345678, "blmr-de001", "Secret Rare", "DE", "https://img/card.jpg")
        )
    }
}
