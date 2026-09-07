package org.yugioh.kartenliste.data.repository

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import org.yugioh.kartenliste.data.local.JustInCardDatabase
import org.yugioh.kartenliste.data.model.Card
import org.yugioh.kartenliste.data.model.CardPrint
import org.yugioh.kartenliste.data.model.ScanCandidate
import org.yugioh.kartenliste.data.model.ScanSignals
import org.yugioh.kartenliste.data.model.SearchFilters
import org.yugioh.kartenliste.data.model.SearchPage
import org.yugioh.kartenliste.data.remote.YgoProDeckClient
import org.yugioh.kartenliste.util.TextNormalizer

sealed interface CatalogStatus {
    data object Ready : CatalogStatus
    data class Syncing(val message: String, val progress: Float? = null) : CatalogStatus
    data class Error(val message: String) : CatalogStatus
}

class CardRepository(
    private val database: JustInCardDatabase,
    private val remote: YgoProDeckClient,
) {
    private val syncMutex = Mutex()
    private val _catalogStatus = MutableStateFlow<CatalogStatus>(CatalogStatus.Ready)
    val catalogStatus: StateFlow<CatalogStatus> = _catalogStatus.asStateFlow()

    suspend fun search(filters: SearchFilters, page: Int = 0, pageSize: Int = 50): SearchPage =
        withContext(Dispatchers.IO) {
            val local = database.search(filters, page, pageSize)
            if (local.total > 0 || page > 0 || !filters.hasAnyInput) return@withContext local

            val value = filters.normalized()
            if (value.ownedOnly) return@withContext local
            val language = value.language.takeUnless { it == "all" } ?: "de"
            val remoteSelective = listOf(
                value.name,
                value.setQuery,
                value.passcode,
                value.cardType,
                value.race,
                value.attribute,
                value.archetype,
            ).any(String::isNotBlank) || listOf(
                value.atkMin, value.atkMax, value.defMin, value.defMax,
                value.levelMin, value.levelMax, value.scaleMin, value.scaleMax,
            ).any { it != null }
            if (!remoteSelective && database.catalogCount(language) >= 1_000) return@withContext local

            val remoteCards = runCatching {
                if (remoteSelective) remote.search(value) else remote.allCards(language)
            }.getOrElse { error ->
                if (database.catalogCount() == 0) throw error
                emptyList()
            }
            if (remoteCards.isNotEmpty()) database.upsertCards(remoteCards)
            database.search(filters, page, pageSize)
        }

    suspend fun syncCatalog(language: String = "de", force: Boolean = false): Int =
        syncMutex.withLock {
            withContext(Dispatchers.IO) {
                try {
                    _catalogStatus.value = CatalogStatus.Syncing("Datenbankversion wird geprüft …", 0.05f)
                    val remoteVersion = runCatching(remote::databaseVersion).getOrDefault("unknown")
                    val localVersion = database.metadata("catalog_version_$language")
                    if (!force && localVersion != null && localVersion == remoteVersion && database.catalogCount(language) > 0) {
                        _catalogStatus.value = CatalogStatus.Ready
                        return@withContext database.catalogCount(language)
                    }
                    _catalogStatus.value = CatalogStatus.Syncing("Kartendaten werden geladen …", null)
                    val cards = remote.allCards(language)
                    _catalogStatus.value = CatalogStatus.Syncing("Lokaler Suchindex wird aktualisiert …", 0.85f)
                    val count = database.replaceCatalog(cards.asSequence(), language, remoteVersion)
                    _catalogStatus.value = CatalogStatus.Ready
                    count
                } catch (error: Throwable) {
                    val message = error.message ?: "Die Kartendaten konnten nicht aktualisiert werden."
                    _catalogStatus.value = CatalogStatus.Error(message)
                    if (database.catalogCount() == 0) throw error
                    database.catalogCount(language)
                }
            }
        }

    suspend fun ensureCatalog() {
        if (withContext(Dispatchers.IO) { database.catalogCount() } >= 1_000) return
        runCatching { syncCatalog("de") }
    }

    suspend fun card(key: org.yugioh.kartenliste.data.model.CardKey): Card? =
        withContext(Dispatchers.IO) { database.cardByKey(key) }

    suspend fun importCards(cards: Collection<Card>) = withContext(Dispatchers.IO) {
        database.upsertCards(cards.distinctBy { it.key.stableKey })
    }

    suspend fun matchScan(signals: ScanSignals): List<ScanCandidate> = withContext(Dispatchers.IO) {
        val candidates = linkedMapOf<String, ScanCandidate>()

        signals.setCodes.forEachIndexed { index, code ->
            val cards = database.cardsByPrintCode(code).ifEmpty {
                runCatching { remote.search(SearchFilters(setQuery = code)) }.getOrDefault(emptyList()).also(database::upsertCards)
            }
            cards.forEach { card ->
                val exactPrint = exactPrint(card.prints, code)
                val score = 1_000 - index * 10 + validationScore(card, signals)
                putBest(candidates, ScanCandidate(card, exactPrint, score, "Set-Code $code"))
            }
        }

        if (candidates.isEmpty()) {
            val cards = database.cardsByPasscodes(signals.passcodes).ifEmpty {
                signals.passcodes.flatMap { runCatching { remote.cardById(it) }.getOrDefault(emptyList()) }
                    .also(database::upsertCards)
            }
            cards.forEachIndexed { index, card ->
                putBest(candidates, ScanCandidate(
                    card = card,
                    matchedPrint = choosePrintFromSignals(card, signals),
                    score = 720 - index * 5 + validationScore(card, signals),
                    reason = "Passcode ${card.key.cardId}",
                ))
            }
        }

        if (candidates.isEmpty()) {
            val cards = database.cardsByPossibleNames(signals.possibleNames)
            cards.forEachIndexed { index, card ->
                val nameScore = signals.possibleNames.maxOfOrNull { nameSimilarity(card.name, it) } ?: 0
                putBest(candidates, ScanCandidate(
                    card = card,
                    matchedPrint = choosePrintFromSignals(card, signals),
                    score = 380 + nameScore - index + validationScore(card, signals),
                    reason = "Kartenname als Fallback",
                ))
            }
        }
        candidates.values.sortedByDescending(ScanCandidate::score).take(8)
    }

    fun choosePrint(card: Card, setQuery: String): CardPrint? {
        if (card.prints.isEmpty()) return null
        if (setQuery.isBlank()) return card.prints.firstOrNull()
        return exactPrint(card.prints, setQuery)
            ?: card.prints.firstOrNull {
                TextNormalizer.searchKey(it.setName).contains(TextNormalizer.searchKey(setQuery))
            }
            ?: card.prints.firstOrNull()
    }

    private fun choosePrintFromSignals(card: Card, signals: ScanSignals): CardPrint? =
        signals.setCodes.firstNotNullOfOrNull { code ->
            exactPrint(card.prints, code)
        }

    private fun exactPrint(prints: List<CardPrint>, code: String): CardPrint? {
        val compact = code.filter(Char::isLetterOrDigit)
        return prints.firstOrNull { it.setCode.filter(Char::isLetterOrDigit).equals(compact, true) }
            ?: prints.firstOrNull { TextNormalizer.setCodeEquivalent(it.setCode, code) }
    }

    private fun validationScore(card: Card, signals: ScanSignals): Int {
        var score = 0
        if (signals.atk != null) score += if (signals.atk == card.atk) 45 else -15
        if (signals.def != null) score += if (signals.def == card.def) 45 else -15
        if (signals.level != null) score += if (signals.level == card.displayLevel) 25 else -8
        return score
    }

    private fun nameSimilarity(left: String, right: String): Int {
        val a = TextNormalizer.searchKey(left)
        val b = TextNormalizer.searchKey(right)
        if (a == b) return 200
        if (a.contains(b) || b.contains(a)) return 120
        val leftWords = a.split(' ').filter(String::isNotBlank).toSet()
        val rightWords = b.split(' ').filter(String::isNotBlank).toSet()
        if (leftWords.isEmpty() || rightWords.isEmpty()) return 0
        return ((leftWords.intersect(rightWords).size.toFloat() / leftWords.union(rightWords).size) * 100).toInt()
    }

    private fun putBest(target: MutableMap<String, ScanCandidate>, candidate: ScanCandidate) {
        val key = candidate.card.key.stableKey
        val old = target[key]
        if (old == null || candidate.score > old.score) target[key] = candidate
    }
}
