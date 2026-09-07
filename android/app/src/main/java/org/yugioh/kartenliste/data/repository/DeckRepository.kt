package org.yugioh.kartenliste.data.repository

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.withContext
import org.yugioh.kartenliste.data.local.AppPreferences
import org.yugioh.kartenliste.data.local.DeckStore
import org.yugioh.kartenliste.data.model.CollectionItem
import org.yugioh.kartenliste.data.model.Deck
import org.yugioh.kartenliste.data.model.DeckSection

class DeckRepository(
    private val store: DeckStore,
    private val preferences: AppPreferences,
) {
    private val _decks = MutableStateFlow<List<Deck>>(emptyList())
    val decks: StateFlow<List<Deck>> = _decks.asStateFlow()

    suspend fun refresh() = withContext(Dispatchers.IO) { _decks.value = store.list() }

    suspend fun create(name: String): Deck = withContext(Dispatchers.IO) {
        val deck = store.create(name, preferences.deviceId)
        refresh()
        deck
    }

    suspend fun rename(id: String, name: String, notes: String) = withContext(Dispatchers.IO) {
        store.rename(id, name, notes, preferences.deviceId)
        refresh()
    }

    suspend fun delete(id: String) = withContext(Dispatchers.IO) {
        store.delete(id, preferences.deviceId)
        refresh()
    }

    suspend fun add(deckId: String, item: CollectionItem, section: DeckSection) = withContext(Dispatchers.IO) {
        store.addFromCollection(deckId, item, section, preferences.deviceId)
        refresh()
    }

    suspend fun changeQuantity(cardId: String, quantity: Int) = withContext(Dispatchers.IO) {
        store.setCardQuantity(cardId, quantity, preferences.deviceId)
        refresh()
    }

    suspend fun allForSync(): List<Deck> = withContext(Dispatchers.IO) { store.list(includeDeleted = true) }

    suspend fun merge(records: List<Deck>) = withContext(Dispatchers.IO) {
        store.merge(records)
        refresh()
    }

    suspend fun replaceAll(records: List<Deck>) = withContext(Dispatchers.IO) {
        store.replaceAll(records)
        refresh()
    }
}
