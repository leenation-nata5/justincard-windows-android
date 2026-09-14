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
import org.yugioh.kartenliste.data.model.CollectionItem
import org.yugioh.kartenliste.data.model.Deck
import org.yugioh.kartenliste.data.model.DeckCard
import org.yugioh.kartenliste.data.model.DeckSection
import org.yugioh.kartenliste.data.repository.CardRepository
import org.yugioh.kartenliste.data.repository.CollectionRepository
import org.yugioh.kartenliste.data.repository.DeckRepository

enum class DeckSort(val label: String) {
    NAME("Name"),
    SET_CODE("Set-Code"),
    QUANTITY("Menge"),
}

data class DeckPreviewUi(
    val name: String,
    val imageUrl: String,
    val setCode: String,
    val description: String,
    val source: String,
)

class DeckViewModel(
    private val repository: DeckRepository,
    collectionRepository: CollectionRepository,
    private val cards: CardRepository,
    preferences: AppPreferences,
) : ViewModel() {
    val decks: StateFlow<List<Deck>> = combine(repository.decks, preferences.cardTextLanguageFlow) { values, language -> values to language }
        .map { (values, language) ->
            withContext(Dispatchers.IO) {
                values.map { deck ->
                    deck.copy(cards = deck.cards.map { row ->
                        cards.localizedCard(row.cardKey, language)?.let { card ->
                            row.copy(cardName = card.name, imageUrl = card.imageUrl.ifBlank { row.imageUrl })
                        } ?: row
                    })
                }
            }
        }
        .stateIn(viewModelScope, SharingStarted.Eagerly, emptyList())

    val collection: StateFlow<List<CollectionItem>> = combine(collectionRepository.items, preferences.cardTextLanguageFlow) { values, language -> values to language }
        .map { (values, language) ->
            withContext(Dispatchers.IO) {
                values.map { item ->
                    cards.localizedCard(item.cardKey, language)?.let { card ->
                        item.copy(cardName = card.name, imageUrl = card.imageUrl.ifBlank { item.imageUrl })
                    } ?: item
                }
            }
        }
        .stateIn(viewModelScope, SharingStarted.Eagerly, emptyList())

    private val _selectedDeckId = MutableStateFlow<String?>(null)
    val selectedDeckId: StateFlow<String?> = _selectedDeckId.asStateFlow()
    private val _sort = MutableStateFlow(DeckSort.NAME)
    val sort: StateFlow<DeckSort> = _sort.asStateFlow()
    private val _ascending = MutableStateFlow(true)
    val ascending: StateFlow<Boolean> = _ascending.asStateFlow()
    private val _message = MutableStateFlow<String?>(null)
    val message: StateFlow<String?> = _message.asStateFlow()
    private val _preview = MutableStateFlow<DeckPreviewUi?>(null)
    val preview: StateFlow<DeckPreviewUi?> = _preview.asStateFlow()

    init {
        viewModelScope.launch {
            repository.refresh()
            collectionRepository.refresh()
        }
    }

    fun selected(decks: List<Deck>): Deck? = decks.firstOrNull { it.id == _selectedDeckId.value } ?: decks.firstOrNull()
    fun select(deckId: String) { _selectedDeckId.value = deckId }
    fun setSort(value: DeckSort) { _sort.value = value }
    fun setAscending(value: Boolean) { _ascending.value = value }

    fun sorted(cards: List<DeckCard>): List<DeckCard> {
        val comparator = when (_sort.value) {
            DeckSort.NAME -> compareBy<DeckCard, String>(String.CASE_INSENSITIVE_ORDER) { it.cardName }
            DeckSort.SET_CODE -> compareBy<DeckCard, String>(String.CASE_INSENSITIVE_ORDER) { it.setCode }
            DeckSort.QUANTITY -> compareBy<DeckCard> { it.quantity }
        }
        return if (_ascending.value) cards.sortedWith(comparator) else cards.sortedWith(comparator.reversed())
    }

    fun preview(item: CollectionItem) {
        viewModelScope.launch {
            val localized = runCatching { cards.localizedCard(item.cardKey) }.getOrNull()
            _preview.value = DeckPreviewUi(
                name = localized?.name ?: item.cardName,
                imageUrl = localized?.imageUrl?.ifBlank { item.imageUrl } ?: item.imageUrl,
                setCode = item.selectedPrint.setCode,
                description = localized?.description.orEmpty(),
                source = "Aus Sammlung",
            )
        }
    }

    fun preview(card: DeckCard) {
        viewModelScope.launch {
            val localized = runCatching { cards.localizedCard(card.cardKey) }.getOrNull()
            _preview.value = DeckPreviewUi(
                name = localized?.name ?: card.cardName,
                imageUrl = localized?.imageUrl?.ifBlank { card.imageUrl } ?: card.imageUrl,
                setCode = card.setCode,
                description = localized?.description.orEmpty(),
                source = "Im aktuellen Deck",
            )
        }
    }

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
