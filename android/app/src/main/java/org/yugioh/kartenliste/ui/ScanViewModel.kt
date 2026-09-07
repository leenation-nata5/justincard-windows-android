package org.yugioh.kartenliste.ui

import android.content.Context
import android.net.Uri
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.yugioh.kartenliste.data.model.CardPrint
import org.yugioh.kartenliste.data.model.ScanBatchState
import org.yugioh.kartenliste.data.model.ScanCandidate
import org.yugioh.kartenliste.data.model.ScanResult
import org.yugioh.kartenliste.data.model.ScanSignals
import org.yugioh.kartenliste.data.repository.CardRepository
import org.yugioh.kartenliste.data.repository.CollectionRepository
import org.yugioh.kartenliste.scanner.OcrEngine
import java.util.concurrent.atomic.AtomicBoolean

class ScanViewModel(
    private val cards: CardRepository,
    private val collection: CollectionRepository,
) : ViewModel() {
    val ocrEngine = OcrEngine()
    private val matchingLive = AtomicBoolean(false)
    private val processedSources = mutableSetOf<String>()
    private val _current = MutableStateFlow<ScanResult?>(null)
    val current: StateFlow<ScanResult?> = _current.asStateFlow()
    private val _batch = MutableStateFlow(ScanBatchState())
    val batch: StateFlow<ScanBatchState> = _batch.asStateFlow()
    private val _message = MutableStateFlow<String?>(null)
    val message: StateFlow<String?> = _message.asStateFlow()

    fun onLiveSignals(signals: ScanSignals) {
        if (_current.value != null || !matchingLive.compareAndSet(false, true)) return
        viewModelScope.launch {
            try {
                val candidates = cards.matchScan(signals)
                if (candidates.isNotEmpty()) _current.value = ScanResult("Livebild", signals, candidates)
            } finally {
                matchingLive.set(false)
            }
        }
    }

    fun scanUris(context: Context, uris: List<Uri>, source: String) {
        if (uris.isEmpty()) return
        viewModelScope.launch {
            processedSources.clear()
            _current.value = null
            _batch.value = ScanBatchState(total = uris.size, running = true)
            val results = mutableListOf<ScanResult>()
            uris.forEachIndexed { index, uri ->
                val result = runCatching {
                    val signals = withContext(Dispatchers.Default) { ocrEngine.scanUri(context, uri, thorough = true) }
                    ScanResult("$source ${index + 1}", signals, cards.matchScan(signals))
                }.getOrElse { error ->
                    ScanResult("$source ${index + 1}", ScanSignals("", emptyList(), emptyList(), emptyList()), emptyList(), error.message)
                }
                results += result
                _batch.value = ScanBatchState(uris.size, index + 1, results.toList(), running = index + 1 < uris.size)
                if (_current.value == null && result.best != null) _current.value = result
            }
        }
    }

    fun showResult(result: ScanResult) {
        processedSources.remove(result.sourceLabel)
        _current.value = result
    }

    fun reject() { advanceBatch() }

    fun add(candidate: ScanCandidate, selectedPrint: CardPrint? = candidate.matchedPrint) {
        val print = selectedPrint
        if (print == null) {
            _message.value = "Bitte das tatsächlich abgebildete Set auswählen; ohne Set wird nichts gespeichert."
            return
        }
        viewModelScope.launch {
            collection.add(candidate.card, print)
            _message.value = "${candidate.card.name} · ${print.setCode} wurde hinzugefügt."
            advanceBatch()
        }
    }

    fun dismissMessage() { _message.value = null }

    private fun advanceBatch() {
        _current.value?.sourceLabel?.let(processedSources::add)
        _current.value = _batch.value.results.firstOrNull {
            it.sourceLabel !in processedSources && it.best != null
        }
    }

    override fun onCleared() {
        ocrEngine.close()
        super.onCleared()
    }
}
