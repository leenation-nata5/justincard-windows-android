package org.yugioh.kartenliste

import java.io.StringReader
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.yugioh.kartenliste.data.model.CardCondition
import org.yugioh.kartenliste.data.model.CardKey
import org.yugioh.kartenliste.data.model.CardPrint
import org.yugioh.kartenliste.data.model.CollectionItem
import org.yugioh.kartenliste.data.model.Deck
import org.yugioh.kartenliste.data.model.DeckCard
import org.yugioh.kartenliste.data.model.DeckSection
import org.yugioh.kartenliste.sync.CsvCollectionCodec
import org.yugioh.kartenliste.sync.DataJsonCodec
import org.yugioh.kartenliste.sync.SheetsTabCodec
import org.yugioh.kartenliste.sync.YdkCodec

class TransferCodecTest {
    private val print = CardPrint(89631139, "Legend of Blue Eyes", "LOB-DE001", "Ultra Rare", priceUsd = 7.5)
    private val item = CollectionItem(
        id = "item-1",
        cardKey = CardKey(89631139, language = "de"),
        cardName = "Blauäugiger w. Drache",
        imageUrl = "https://example.test/card.jpg",
        selectedPrint = print,
        condition = CardCondition.NEAR_MINT,
        quantity = 2,
        notes = "Ordner, Seite 1\nmit Hülle",
        updatedAt = 1234,
        deviceId = "device-a",
    )

    @Test
    fun csvRoundTripKeepsExactPrintAndQuotedNotes() {
        val decoded = CsvCollectionCodec.decode(StringReader(CsvCollectionCodec.encode(listOf(item))), "fallback").single()
        assertEquals(item.cardName, decoded.cardName)
        assertEquals("LOB-DE001", decoded.selectedPrint.setCode)
        assertEquals(item.notes, decoded.notes)
        assertEquals(2, decoded.quantity)
    }

    @Test
    fun jsonRoundTripKeepsTombstoneFields() {
        val restored = DataJsonCodec.collectionFromJson(DataJsonCodec.collectionToJson(listOf(item.copy(deleted = true)))).single()
        assertTrue(restored.deleted)
        assertEquals(item.selectedPrint.stableKey, restored.selectedPrint.stableKey)
    }

    @Test
    fun sheetsRoundTripKeepsCollectionAndDeck() {
        val collectionRows = SheetsTabCodec.collectionRows(listOf(item)).map { row -> row.map { it?.toString().orEmpty() } }
        assertEquals(item.identityKey, SheetsTabCodec.parseCollection(collectionRows).single().identityKey)

        val deck = Deck(
            id = "deck-1",
            name = "Test",
            updatedAt = 22,
            deviceId = "device-a",
            cards = listOf(DeckCard(
                id = "deck-card-1",
                deckId = "deck-1",
                cardKey = item.cardKey,
                cardName = item.cardName,
                imageUrl = item.imageUrl,
                setCode = item.selectedPrint.setCode,
                section = DeckSection.MAIN,
                quantity = 2,
                updatedAt = 23,
                deviceId = "device-a",
            )),
        )
        val deckRows = SheetsTabCodec.deckRows(listOf(deck)).map { row -> row.map { it?.toString().orEmpty() } }
        val restoredDeck = SheetsTabCodec.parseDecks(deckRows).single()
        assertEquals(2, restoredDeck.mainCount)
        assertFalse(restoredDeck.deleted)
    }

    @Test
    fun ydkUsesPasscodesAndSections() {
        val deck = Deck(
            name = "YDK",
            deviceId = "device-a",
            cards = listOf(DeckCard(
                deckId = "deck",
                cardKey = item.cardKey,
                cardName = item.cardName,
                imageUrl = item.imageUrl,
                section = DeckSection.SIDE,
                quantity = 2,
                deviceId = "device-a",
            )),
        )
        val decoded = YdkCodec.decode(YdkCodec.encode(deck))
        assertEquals(2, decoded.size)
        assertTrue(decoded.all { it.section == DeckSection.SIDE })
    }
}
