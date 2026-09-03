package org.yugioh.kartenliste.ui

import android.app.Application
import android.content.Intent
import android.net.Uri
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.latin.TextRecognizerOptions
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import org.yugioh.kartenliste.JustInCardApplication
import org.yugioh.kartenliste.cloud.GoogleCloudRepository
import org.yugioh.kartenliste.cloud.SheetTemplate
import org.yugioh.kartenliste.core.MarketValue
import org.yugioh.kartenliste.data.CollectionItem
import org.yugioh.kartenliste.data.Deck
import org.yugioh.kartenliste.data.DeckCard
import org.yugioh.kartenliste.data.SearchResult
import org.yugioh.kartenliste.network.YgoApi
import org.yugioh.kartenliste.scanner.ScannerTextParser
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

enum class AppScreen(val label: String) {
    HOME("Start"), SEARCH("Suche"), SCANNER("Live-Scanner"), COLLECTION("Sammlung"), DECKS("Decks"), SETTINGS("Einstellungen")
}

data class AppUiState(
    val screen: AppScreen = AppScreen.HOME,
    val searchQuery: String = "",
    val searchResults: List<SearchResult> = emptyList(),
    val selectedSearch: SearchResult? = null,
    val searchQuantity: Int = 1,
    val scannerQuantity: Int = 1,
    val scannerResult: SearchResult? = null,
    val scannerStatus: String = "Livebild bereit",
    val collection: List<CollectionItem> = emptyList(),
    val selectedCollection: CollectionItem? = null,
    val decks: List<Deck> = emptyList(),
    val selectedDeckId: String = "",
    val cloudStatus: GoogleCloudRepository.Status = GoogleCloudRepository.Status(false),
    val cloudBusy: Boolean = false,
    val cloudMessage: String = "",
    val busy: Boolean = false,
    val message: String = "",
    val displayProfiles: Map<String, Map<String, Boolean>> = emptyMap(),
)

class JustInCardViewModel(application: Application) : AndroidViewModel(application) {
    private val app = application as JustInCardApplication
    private val db = app.database
    private val api = YgoApi()
    val cloud = GoogleCloudRepository(application, db)
    private val displayPrefs = DisplayPrefs(db)
    private val _state = MutableStateFlow(AppUiState())
    val state: StateFlow<AppUiState> = _state.asStateFlow()
    private var lastScannerQuery = ""
    private var lastScannerAt = 0L

    init {
        refreshAll()
        if (db.getSetting(GoogleCloudRepository.SETTING_AUTO_SYNC, "false").toBoolean()) {
            viewModelScope.launch { runCatching { cloud.syncBidirectional() }.onSuccess { refreshAll() } }
        }
    }

    fun navigate(screen: AppScreen) {
        _state.value = _state.value.copy(screen = screen, message = "")
        if (screen == AppScreen.COLLECTION || screen == AppScreen.DECKS) refreshAll()
    }

    fun refreshAll() {
        val collection = db.listCollection()
        val decks = db.listDecks()
        val oldSelectedDeck = _state.value.selectedDeckId
        val selectedDeck = oldSelectedDeck.takeIf { id -> decks.any { it.deckId == id } } ?: decks.firstOrNull()?.deckId.orEmpty()
        _state.value = _state.value.copy(
            collection = collection,
            decks = decks,
            selectedDeckId = selectedDeck,
            cloudStatus = cloud.status(),
            displayProfiles = displayPrefs.load(),
        )
    }

    fun setSearchQuery(value: String) { _state.value = _state.value.copy(searchQuery = value) }
    fun setSearchQuantity(value: Int) { _state.value = _state.value.copy(searchQuantity = value.coerceIn(1, 999)) }
    fun setScannerQuantity(value: Int) { _state.value = _state.value.copy(scannerQuantity = value.coerceIn(1, 999)) }
    fun selectSearch(result: SearchResult) { _state.value = _state.value.copy(selectedSearch = result) }
    fun selectCollection(item: CollectionItem?) { _state.value = _state.value.copy(selectedCollection = item) }
    fun selectDeck(id: String) { _state.value = _state.value.copy(selectedDeckId = id) }

    fun search(query: String = _state.value.searchQuery) {
        if (query.isBlank()) return
        viewModelScope.launch {
            _state.value = _state.value.copy(busy = true, message = "Suche …")
            runCatching { api.search(query) }
                .onSuccess { results ->
                    _state.value = _state.value.copy(
                        busy = false,
                        searchQuery = query,
                        searchResults = results,
                        selectedSearch = results.firstOrNull(),
                        message = if (results.isEmpty()) "Keine Karten gefunden" else "${results.size} Treffer",
                    )
                }
                .onFailure { error -> _state.value = _state.value.copy(busy = false, message = error.message ?: "Suche fehlgeschlagen") }
        }
    }

    fun addSelectedSearch() {
        val result = _state.value.selectedSearch ?: return
        addResultToCollection(result, _state.value.searchQuantity, scanner = false)
    }

    fun addScannerResult() {
        val result = _state.value.scannerResult ?: return
        addResultToCollection(result, _state.value.scannerQuantity, scanner = true)
    }

    private fun addResultToCollection(result: SearchResult, quantity: Int, scanner: Boolean) {
        val print = result.matchedPrint ?: result.card.cardSets.firstOrNull()
        val requestedCode = result.requestedSetCode.ifBlank { print?.setCode.orEmpty() }
        val language = result.requestedLanguage.ifBlank { result.card.language.ifBlank { "en" } }
        db.addToCollection(
            result.card,
            print,
            language,
            quantity.coerceAtLeast(1),
            requestedPrintCode = requestedCode,
        )
        refreshAll()
        if (scanner) {
            _state.value = _state.value.copy(scannerQuantity = 1, scannerStatus = "${result.card.name} hinzugefügt", message = "Zur Sammlung hinzugefügt")
        } else {
            _state.value = _state.value.copy(searchQuantity = 1, searchQuery = "", searchResults = emptyList(), selectedSearch = null, message = "Zur Sammlung hinzugefügt")
        }
    }

    fun scannerCandidate(candidate: ScannerTextParser.Candidate) {
        val now = System.currentTimeMillis()
        if (candidate.query == lastScannerQuery && now - lastScannerAt < 3000) return
        lastScannerQuery = candidate.query
        lastScannerAt = now
        _state.value = _state.value.copy(scannerStatus = "Erkannt: ${candidate.query} – wird geprüft …")
        viewModelScope.launch {
            runCatching { api.search(candidate.query) }
                .onSuccess { results ->
                    _state.value = _state.value.copy(
                        scannerResult = results.firstOrNull(),
                        scannerStatus = results.firstOrNull()?.let { "Gefunden: ${it.card.name}" } ?: "Keine Karte zu ${candidate.query} gefunden",
                    )
                }
                .onFailure { _state.value = _state.value.copy(scannerStatus = "Scanprüfung fehlgeschlagen") }
        }
    }

    fun scanGallery(uri: Uri) {
        viewModelScope.launch {
            _state.value = _state.value.copy(scannerStatus = "Galeriebild wird ausgelesen …")
            runCatching {
                val image = InputImage.fromFilePath(getApplication(), uri)
                val recognizer = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)
                try {
                    val text = recognizer.process(image).awaitText()
                    ScannerTextParser.best(text)
                } finally { recognizer.close() }
            }.onSuccess { candidate ->
                if (candidate == null) _state.value = _state.value.copy(scannerStatus = "Kein Set-Code/Passcode erkannt")
                else scannerCandidate(candidate)
            }.onFailure { _state.value = _state.value.copy(scannerStatus = it.message ?: "Galerie-Scan fehlgeschlagen") }
        }
    }

    fun updateCollection(item: CollectionItem) {
        db.updateCollection(item.copy(quantity = item.quantity.coerceAtLeast(1)))
        refreshAll()
        _state.value = _state.value.copy(selectedCollection = db.listCollection().firstOrNull { it.collectionKey == item.collectionKey })
    }

    fun deleteCollection(item: CollectionItem) {
        db.deleteCollection(item.collectionKey)
        refreshAll()
        _state.value = _state.value.copy(selectedCollection = null)
    }

    fun estimatedValue(item: CollectionItem): Double = MarketValue.estimateEur(item) ?: 0.0
    fun totalCollectionValue(): Double = _state.value.collection.sumOf { estimatedValue(it) * it.quantity.coerceAtLeast(0) }

    fun createDeck(name: String) {
        runCatching { db.createDeck(name) }
            .onSuccess { refreshAll(); selectDeck(it.deckId) }
            .onFailure { _state.value = _state.value.copy(message = it.message.orEmpty()) }
    }

    fun renameDeck(name: String) {
        val id = _state.value.selectedDeckId.ifBlank { return }
        db.renameDeck(id, name); refreshAll()
    }

    fun deleteSelectedDeck() {
        val id = _state.value.selectedDeckId.ifBlank { return }
        db.deleteDeck(id); refreshAll()
    }

    fun addDeckCard(item: CollectionItem, side: Boolean) {
        val id = _state.value.selectedDeckId.ifBlank { return }
        runCatching { db.addDeckCard(id, item, if (side) "side" else null, allowPlaceholder = true) }
            .onSuccess { refreshAll() }
            .onFailure { _state.value = _state.value.copy(message = it.message.orEmpty()) }
    }

    fun removeDeckCard(card: DeckCard) { db.removeDeckCard(card.id); refreshAll() }
    fun setDeckCardQuantity(card: DeckCard, quantity: Int) { db.setDeckCardQuantity(card.id, quantity); refreshAll() }

    fun handleGoogleSignInResult(intent: Intent?) {
        runCatching { cloud.handleSignInResult(intent) }
            .onSuccess { refreshAll(); _state.value = _state.value.copy(cloudMessage = "Angemeldet als ${it.email.orEmpty()}") }
            .onFailure { _state.value = _state.value.copy(cloudMessage = it.message ?: "Google-Anmeldung fehlgeschlagen") }
    }

    fun cloudUpload() = cloudAction { cloud.uploadLocal() }
    fun cloudLoad() = cloudAction { cloud.loadCloud() }
    fun cloudSync() = cloudAction { cloud.syncBidirectional() }
    fun cloudEnsure() = cloudAction { cloud.ensureSpreadsheet(); cloud.syncBidirectional() }

    private fun cloudAction(block: suspend () -> GoogleCloudRepository.SyncResult) {
        viewModelScope.launch {
            _state.value = _state.value.copy(cloudBusy = true, cloudMessage = "Google Cloud arbeitet …")
            runCatching { block() }
                .onSuccess { result ->
                    refreshAll()
                    _state.value = _state.value.copy(cloudBusy = false, cloudMessage = "${result.message}: ${result.collectionCount} Karten / ${result.deckCount} Decks")
                }
                .onFailure { _state.value = _state.value.copy(cloudBusy = false, cloudMessage = it.message ?: "Google Cloud fehlgeschlagen") }
        }
    }

    fun signOutGoogle() {
        viewModelScope.launch {
            runCatching { cloud.signOut() }
            refreshAll(); _state.value = _state.value.copy(cloudMessage = "Google-Konto abgemeldet")
        }
    }

    fun setCloudSort(field: SheetTemplate.SortField, direction: SheetTemplate.Direction) {
        db.setSetting(GoogleCloudRepository.SETTING_SORT, field.name)
        db.setSetting(GoogleCloudRepository.SETTING_DIRECTION, direction.name)
    }

    fun cloudSortField(): SheetTemplate.SortField = runCatching {
        SheetTemplate.SortField.valueOf(db.getSetting(GoogleCloudRepository.SETTING_SORT, SheetTemplate.SortField.NAME.name))
    }.getOrDefault(SheetTemplate.SortField.NAME)

    fun cloudDirection(): SheetTemplate.Direction = runCatching {
        SheetTemplate.Direction.valueOf(db.getSetting(GoogleCloudRepository.SETTING_DIRECTION, SheetTemplate.Direction.ASC.name))
    }.getOrDefault(SheetTemplate.Direction.ASC)

    fun autoSyncEnabled() = db.getSetting(GoogleCloudRepository.SETTING_AUTO_SYNC, "false").toBoolean()
    fun setAutoSync(value: Boolean) { db.setSetting(GoogleCloudRepository.SETTING_AUTO_SYNC, value.toString()) }

    fun displayEnabled(context: DisplayContext, field: DisplayField): Boolean = displayPrefs.enabled(context, field)
    fun setDisplay(context: DisplayContext, field: DisplayField, enabled: Boolean) { displayPrefs.set(context, field, enabled); refreshAll() }
}

private suspend fun com.google.android.gms.tasks.Task<com.google.mlkit.vision.text.Text>.awaitText(): String =
    suspendCancellableCoroutine { continuation ->
        addOnSuccessListener { if (continuation.isActive) continuation.resume(it.text) }
        addOnFailureListener { if (continuation.isActive) continuation.resumeWithException(it) }
    }
