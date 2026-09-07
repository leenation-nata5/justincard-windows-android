package org.yugioh.kartenliste.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import org.yugioh.kartenliste.data.model.CollectionItem
import org.yugioh.kartenliste.data.model.Deck
import org.yugioh.kartenliste.data.model.DeckCard
import org.yugioh.kartenliste.data.model.DeckSection
import org.yugioh.kartenliste.data.repository.CollectionRepository
import org.yugioh.kartenliste.data.repository.DeckRepository

class DeckViewModel(
    private val repository: DeckRepository,
    collectionRepository: CollectionRepository,
) : ViewModel() {
    val decks = repository.decks
    val collection = collectionRepository.items
    private val _selectedDeckId = MutableStateFlow<String?>(null)
    val selectedDeckId: StateFlow<String?> = _selectedDeckId.asStateFlow()
    private val _message = MutableStateFlow<String?>(null)
    val message: StateFlow<String?> = _message.asStateFlow()

    init { viewModelScope.launch { repository.refresh() } }

    fun selected(decks: List<Deck>): Deck? = decks.firstOrNull { it.id == _selectedDeckId.value } ?: decks.firstOrNull()
    fun select(deckId: String) { _selectedDeckId.value = deckId }

    fun create(name: String) {
        viewModelScope.launch {
            runCatching { repository.create(name) }
                .onSuccess { _selectedDeckId.value = it.id }
                .onFailure { _message.value = it.message }
        }
    }

    fun rename(deck: Deck, name: String, notes: String) {
        viewModelScope.launch { repository.rename(deck.id, name, notes) }
    }

    fun delete(deck: Deck) {
        viewModelScope.launch {
            repository.delete(deck.id)
            _selectedDeckId.value = null
        }
    }

    fun add(deck: Deck, item: CollectionItem, section: DeckSection) {
        viewModelScope.launch {
            runCatching { repository.add(deck.id, item, section) }
                .onSuccess { _message.value = "${item.cardName} wurde zu ${section.label} hinzugefügt." }
                .onFailure { _message.value = it.message }
        }
    }

    fun changeQuantity(card: DeckCard, value: Int) {
        viewModelScope.launch { repository.changeQuantity(card.id, value) }
    }

    fun dismissMessage() { _message.value = null }
}
