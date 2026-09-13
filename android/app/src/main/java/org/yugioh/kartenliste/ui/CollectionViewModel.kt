package org.yugioh.kartenliste.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.yugioh.kartenliste.data.local.AppPreferences
import org.yugioh.kartenliste.data.model.CardCondition
import org.yugioh.kartenliste.data.model.CollectionItem
import org.yugioh.kartenliste.data.repository.CardRepository
import org.yugioh.kartenliste.data.repository.CollectionRepository
import org.yugioh.kartenliste.util.TextNormalizer

enum class CollectionSort(val label: String) {
    NAME("Name"),
    SET_CODE("Set-Code"),
    RARITY("Seltenheit"),
    QUANTITY("Menge"),
    UPDATED("Zuletzt geändert"),
}

class CollectionViewModel(
    private val repository: CollectionRepository,
    private val cards: CardRepository,
    preferences: AppPreferences,
) : ViewModel() {
    val items: StateFlow<List<CollectionItem>> = combine(
        repository.items,
        preferences.cardTextLanguageFlow,
    ) { rows, language -> rows to language }
        .map { (rows, language) ->
            withContext(Dispatchers.IO) {
                rows.map { item ->
                    cards.localizedCard(item.cardKey, language)?.let { card ->
                        item.copy(
                            cardName = card.name,
                            imageUrl = card.imageUrl.ifBlank { item.imageUrl },
                        )
                    } ?: item
                }
            }
        }
        .stateIn(viewModelScope, SharingStarted.Eagerly, emptyList())

    val summary = repository.summary
    private val _query = MutableStateFlow("")
    val query: StateFlow<String> = _query.asStateFlow()
    private val _selected = MutableStateFlow<CollectionItem?>(null)
    val selected: StateFlow<CollectionItem?> = _selected.asStateFlow()
    private val _sort = MutableStateFlow(CollectionSort.NAME)
    val sort: StateFlow<CollectionSort> = _sort.asStateFlow()
    private val _ascending = MutableStateFlow(true)
    val ascending: StateFlow<Boolean> = _ascending.asStateFlow()
    private val _message = MutableStateFlow<String?>(null)
    val message: StateFlow<String?> = _message.asStateFlow()

    init { viewModelScope.launch { repository.refresh() } }

    fun setQuery(value: String) { _query.value = value }
    fun select(item: CollectionItem?) { _selected.value = item }
    fun setSort(value: CollectionSort) { _sort.value = value }
    fun setAscending(value: Boolean) { _ascending.value = value }

    fun filtered(items: List<CollectionItem>): List<CollectionItem> {
        val key = TextNormalizer.searchKey(_query.value)
        val compact = TextNormalizer.compactKey(_query.value)
        val filtered = if (key.isBlank()) items else items.filter {
            TextNormalizer.searchKey(it.cardName).contains(key) ||
                TextNormalizer.compactKey(it.selectedPrint.setCode).contains(compact) ||
                TextNormalizer.searchKey(it.selectedPrint.setName).contains(key) ||
                TextNormalizer.searchKey(it.selectedPrint.rarity).contains(key)
        }
        val comparator = when (_sort.value) {
            CollectionSort.NAME -> compareBy<CollectionItem, String>(String.CASE_INSENSITIVE_ORDER) { it.cardName }
            CollectionSort.SET_CODE -> compareBy<CollectionItem, String>(String.CASE_INSENSITIVE_ORDER) { it.selectedPrint.setCode }
            CollectionSort.RARITY -> compareBy<CollectionItem, String>(String.CASE_INSENSITIVE_ORDER) { it.selectedPrint.rarity }
            CollectionSort.QUANTITY -> compareBy<CollectionItem> { it.quantity }
            CollectionSort.UPDATED -> compareBy<CollectionItem> { it.updatedAt }
        }
        return if (_ascending.value) filtered.sortedWith(comparator) else filtered.sortedWith(comparator.reversed())
    }

    fun changeQuantity(item: CollectionItem, delta: Int) {
        viewModelScope.launch {
            repository.changeQuantity(item.id, delta)
            _selected.value = null
        }
    }

    fun saveDetails(item: CollectionItem, condition: CardCondition, notes: String) {
        viewModelScope.launch {
            repository.setDetails(item.id, condition, notes)
            _selected.value = null
            _message.value = "Kartendetails gespeichert."
        }
    }

    fun dismissMessage() { _message.value = null }
}
