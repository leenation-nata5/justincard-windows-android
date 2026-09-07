package org.yugioh.kartenliste

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.yugioh.kartenliste.data.model.Card
import org.yugioh.kartenliste.data.model.CardCondition
import org.yugioh.kartenliste.data.model.CardKey
import org.yugioh.kartenliste.data.model.CardPrint
import org.yugioh.kartenliste.data.model.CollectionItem
import org.yugioh.kartenliste.data.model.Deck
import org.yugioh.kartenliste.data.model.DeckCard
import org.yugioh.kartenliste.data.model.DeckSection
import org.yugioh.kartenliste.sync.CloudContract
import org.yugioh.kartenliste.sync.CloudSnapshot
import org.yugioh.kartenliste.sync.WindowsCloudCodec
import org.yugioh.kartenliste.sync.WindowsSheetTemplate

class GoogleCloudContractTest {
    private val key = CardKey(123L, 456L, "de")
    private val print = CardPrint(
        cardId = 123L,
        setName = "Test Set",
        setCode = "TEST-DE001",
        rarity = "Common",
        rarityCode = "C",
        priceUsd = 1.25,
        language = "de",
    )
    private val card = Card(
        key = key,
        name = "Cloud Test Card",
        description = "Effekttext",
        type = "Tuner Effect Monster",
        race = "Dragon",
        attribute = "DARK",
        level = 8,
        imageUrl = "https://img.example/full.jpg",
        thumbnailUrl = "https://img.example/small.jpg",
        prints = listOf(print),
    )
    private val item = CollectionItem(
        id = "local-item",
        cardKey = key,
        cardName = card.name,
        imageUrl = card.thumbnailUrl,
        selectedPrint = print,
        condition = CardCondition.NEAR_MINT,
        language = "de",
        quantity = 2,
        notes = "Testnotiz",
        updatedAt = 1_700_000_000_000L,
        deviceId = "android-device",
    )
    private val deck = Deck(
        id = "deck-1",
        name = "Drachen Deck",
        cards = listOf(
            DeckCard(
                id = "deck-card-1",
                deckId = "deck-1",
                cardKey = key,
                cardName = card.name,
                imageUrl = card.thumbnailUrl,
                setCode = print.setCode,
                section = DeckSection.MAIN,
                quantity = 2,
                updatedAt = 1_700_000_000_000L,
                deviceId = "android-device",
            ),
        ),
        updatedAt = 1_700_000_000_000L,
        deviceId = "android-device",
    )

    @Test
    fun windowsBackupRoundTripPreservesCollectionAndDecks() {
        val snapshot = CloudSnapshot(listOf(item), listOf(deck))
        val payload = WindowsCloudCodec.encode(
            "abcDEF_12345678901234567890",
            "Android",
            snapshot,
            mapOf(key to card),
        )

        assertEquals(CloudContract.CLOUD_SCHEMA, payload.getString("schema"))
        assertEquals("TEST-DE001", payload.getJSONArray("collection").getJSONObject(0).getString("print_code"))
        assertEquals("main", payload.getJSONArray("decks").getJSONObject(0)
            .getJSONArray("cards").getJSONObject(0).getString("zone"))

        val restored = WindowsCloudCodec.decode(payload, "google-cloud")
        assertEquals(1, restored.collection.size)
        assertEquals(2, restored.collection.single().quantity)
        assertEquals(CardCondition.NEAR_MINT, restored.collection.single().condition)
        assertEquals("Tuner Effect Monster", restored.cards.getValue(restored.collection.single().cardKey).type)
        assertEquals(1, restored.decks.size)
        assertEquals(2, restored.decks.single().cards.single().quantity)
        assertEquals(DeckSection.MAIN, restored.decks.single().cards.single().section)
    }

    @Test
    fun visibleWorkbookMatchesWindowsTemplateAndRepeatsQuantity() {
        val workbook = WindowsSheetTemplate.workbook(
            CloudSnapshot(listOf(item), listOf(deck)),
            mapOf(key to card),
        )

        assertEquals(
            listOf("Monsterkarten", "Zauberkarten", "Fallenkarten", "Drachen Deck"),
            workbook.keys.toList(),
        )
        assertEquals(3, workbook.getValue("Monsterkarten").size)
        assertEquals("Empfänger", workbook.getValue("Monsterkarten")[1][4])
        assertEquals("Main Deck", workbook.getValue("Drachen Deck")[1][1])
        assertEquals(2, workbook.getValue("Drachen Deck").drop(2).count { it[1] == card.name })
    }

    @Test
    fun spreadsheetUrlOrIdIsNormalized() {
        val id = "abcDEF_12345678901234567890"
        assertEquals(id, CloudContract.normalizeSpreadsheetId(id))
        assertEquals(id, CloudContract.normalizeSpreadsheetId(
            "https://docs.google.com/spreadsheets/d/$id/edit#gid=0",
        ))
        assertTrue(CloudContract.spreadsheetUrl(id).endsWith("/$id/edit"))
    }
}
