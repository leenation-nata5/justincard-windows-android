package org.yugioh.kartenliste.data.repository

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.withContext
import org.yugioh.kartenliste.data.local.AppPreferences
import org.yugioh.kartenliste.data.local.CollectionStore
import org.yugioh.kartenliste.data.model.Card
import org.yugioh.kartenliste.data.model.CardCondition
import org.yugioh.kartenliste.data.model.CardPrint
import org.yugioh.kartenliste.data.model.CollectionItem
import org.yugioh.kartenliste.data.model.CollectionSummary

class CollectionRepository(
    private val store: CollectionStore,
    private val preferences: AppPreferences,
) {
    private val _items = MutableStateFlow<List<CollectionItem>>(emptyList())
    val items: StateFlow<List<CollectionItem>> = _items.asStateFlow()
    private val _summary = MutableStateFlow(CollectionSummary())
    val summary: StateFlow<CollectionSummary> = _summary.asStateFlow()

    suspend fun refresh() = withContext(Dispatchers.IO) {
        _items.value = store.list()
        _summary.value = store.summary()
    }

    suspend fun add(card: Card, print: CardPrint, quantity: Int = 1): CollectionItem =
        withContext(Dispatchers.IO) {
            val item = store.add(card, print, preferences.deviceId, quantity)
            refresh()
            item
        }

    suspend fun changeQuantity(id: String, delta: Int) = withContext(Dispatchers.IO) {
        val current = store.item(id) ?: return@withContext
        store.setQuantity(id, current.quantity + delta, preferences.deviceId)
        refresh()
    }

    suspend fun setDetails(id: String, condition: CardCondition, notes: String) = withContext(Dispatchers.IO) {
        store.updateDetails(id, condition, notes, preferences.deviceId)
        refresh()
    }

    suspend fun allForSync(): List<CollectionItem> = withContext(Dispatchers.IO) { store.list(includeDeleted = true) }

    suspend fun merge(records: List<CollectionItem>) = withContext(Dispatchers.IO) {
        store.merge(records)
        refresh()
    }

    suspend fun replaceAll(records: List<CollectionItem>) = withContext(Dispatchers.IO) {
        store.replaceAll(records)
        refresh()
    }
}
