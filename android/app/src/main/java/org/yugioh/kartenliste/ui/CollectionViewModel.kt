package org.yugioh.kartenliste.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import org.yugioh.kartenliste.data.model.CardCondition
import org.yugioh.kartenliste.data.model.CollectionItem
import org.yugioh.kartenliste.data.repository.CollectionRepository
import org.yugioh.kartenliste.util.TextNormalizer

class CollectionViewModel(private val repository: CollectionRepository) : ViewModel() {
    val items = repository.items
    val summary = repository.summary
    private val _query = MutableStateFlow("")
    val query: StateFlow<String> = _query.asStateFlow()
    private val _selected = MutableStateFlow<CollectionItem?>(null)
    val selected: StateFlow<CollectionItem?> = _selected.asStateFlow()
    private val _message = MutableStateFlow<String?>(null)
    val message: StateFlow<String?> = _message.asStateFlow()

    init { viewModelScope.launch { repository.refresh() } }

    fun setQuery(value: String) { _query.value = value }
    fun select(item: CollectionItem?) { _selected.value = item }

    fun filtered(items: List<CollectionItem>): List<CollectionItem> {
        val key = TextNormalizer.searchKey(_query.value)
        val compact = TextNormalizer.compactKey(_query.value)
        if (key.isBlank()) return items
        return items.filter {
            TextNormalizer.searchKey(it.cardName).contains(key) ||
                TextNormalizer.compactKey(it.selectedPrint.setCode).contains(compact) ||
                TextNormalizer.searchKey(it.selectedPrint.setName).contains(key) ||
                TextNormalizer.searchKey(it.selectedPrint.rarity).contains(key)
        }
    }

    fun changeQuantity(item: CollectionItem, delta: Int) {
        viewModelScope.launch {
            repository.changeQuantity(item.id, delta)
            _selected.value = repository.items.value.firstOrNull { it.id == item.id }
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
