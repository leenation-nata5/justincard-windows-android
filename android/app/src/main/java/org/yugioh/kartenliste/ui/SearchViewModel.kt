package org.yugioh.kartenliste.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import org.yugioh.kartenliste.data.model.Card
import org.yugioh.kartenliste.data.model.CardPrint
import org.yugioh.kartenliste.data.model.SearchFilters
import org.yugioh.kartenliste.data.model.SearchPage
import org.yugioh.kartenliste.data.repository.CardRepository
import org.yugioh.kartenliste.data.repository.CollectionRepository

data class SearchUiState(
    val filters: SearchFilters = SearchFilters(),
    val page: SearchPage = SearchPage(emptyList(), 0, 0, 50),
    val loading: Boolean = false,
    val error: String? = null,
    val selectedCard: Card? = null,
    val selectedPrint: CardPrint? = null,
    val message: String? = null,
)

class SearchViewModel(
    private val cards: CardRepository,
    private val collection: CollectionRepository,
) : ViewModel() {
    private val _state = MutableStateFlow(SearchUiState())
    val state: StateFlow<SearchUiState> = _state.asStateFlow()
    val catalogStatus = cards.catalogStatus
    private var searchJob: Job? = null

    init {
        viewModelScope.launch {
            cards.ensureCatalog()
            performSearch(0)
        }
    }

    fun setFilters(filters: SearchFilters) {
        _state.value = _state.value.copy(filters = filters, error = null)
    }

    fun clearFilters() {
        _state.value = _state.value.copy(filters = SearchFilters(), selectedCard = null, selectedPrint = null)
        search()
    }

    fun search(page: Int = 0) {
        searchJob?.cancel()
        searchJob = viewModelScope.launch { performSearch(page) }
    }

    fun searchDebounced() {
        searchJob?.cancel()
        searchJob = viewModelScope.launch {
            delay(350)
            performSearch(0)
        }
    }

    fun nextPage() {
        val current = _state.value.page
        if (current.hasNext) search(current.page + 1)
    }

    fun previousPage() {
        val current = _state.value.page
        if (current.page > 0) search(current.page - 1)
    }

    fun select(card: Card?) {
        _state.value = _state.value.copy(
            selectedCard = card,
            selectedPrint = card?.let { cards.choosePrint(it, _state.value.filters.setQuery) },
        )
    }

    fun selectPrint(print: CardPrint) {
        _state.value = _state.value.copy(selectedPrint = print)
    }

    fun addSelected() {
        val card = _state.value.selectedCard ?: return
        val print = _state.value.selectedPrint
        if (print == null) {
            _state.value = _state.value.copy(error = "Bitte zuerst ein konkretes Set auswählen.")
            return
        }
        viewModelScope.launch {
            runCatching { collection.add(card, print) }
                .onSuccess {
                    _state.value = _state.value.copy(
                        message = "${card.name} · ${print.setCode} wurde hinzugefügt.",
                        error = null,
                    )
                }
                .onFailure { _state.value = _state.value.copy(error = it.message) }
        }
    }

    fun dismissMessage() {
        _state.value = _state.value.copy(message = null, error = null)
    }

    fun forceCatalogSync(language: String = "de") {
        viewModelScope.launch {
            runCatching { cards.syncCatalog(language, force = true) }
                .onSuccess { performSearch(0) }
                .onFailure { _state.value = _state.value.copy(error = it.message) }
        }
    }

    private suspend fun performSearch(page: Int) {
        _state.value = _state.value.copy(loading = true, error = null)
        runCatching { cards.search(_state.value.filters, page, 50) }
            .onSuccess { result ->
                val selected = _state.value.selectedCard?.takeIf { old -> result.cards.any { it.key == old.key } }
                _state.value = _state.value.copy(
                    page = result,
                    loading = false,
                    selectedCard = selected,
                    selectedPrint = selected?.let { cards.choosePrint(it, _state.value.filters.setQuery) },
                )
            }
            .onFailure { error ->
                _state.value = _state.value.copy(
                    page = SearchPage(emptyList(), 0, page, 50),
                    loading = false,
                    error = error.message ?: "Suche fehlgeschlagen.",
                )
            }
    }
}
