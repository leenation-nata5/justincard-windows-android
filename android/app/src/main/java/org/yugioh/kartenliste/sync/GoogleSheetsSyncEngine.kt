package org.yugioh.kartenliste.sync

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import org.yugioh.kartenliste.data.local.AppPreferences
import org.yugioh.kartenliste.data.model.Card
import org.yugioh.kartenliste.data.model.CardKey
import org.yugioh.kartenliste.data.model.CollectionItem
import org.yugioh.kartenliste.data.model.Deck
import org.yugioh.kartenliste.data.model.DeckCard
import org.yugioh.kartenliste.data.model.GoogleSpreadsheet
import org.yugioh.kartenliste.data.model.SyncDevice
import org.yugioh.kartenliste.data.model.SyncPhase
import org.yugioh.kartenliste.data.model.SyncStatus
import org.yugioh.kartenliste.data.repository.CardRepository
import org.yugioh.kartenliste.data.repository.CollectionRepository
import org.yugioh.kartenliste.data.repository.DeckRepository

class GoogleSheetsSyncEngine(
    context: Context,
    private val preferences: AppPreferences,
    private val cardRepository: CardRepository,
    private val collectionRepository: CollectionRepository,
    private val deckRepository: DeckRepository,
) {
    private val appContext = context.applicationContext
    private val mutex = Mutex()
    private val _status = MutableStateFlow(SyncStatus())
    val status: StateFlow<SyncStatus> = _status.asStateFlow()

    suspend fun listSpreadsheets(token: String): List<GoogleSpreadsheet> = withContext(Dispatchers.IO) {
        execute(
            phase = SyncPhase.LOADING_SHEETS,
            message = "Google-Tabellen werden geladen …",
        ) {
            val client = GoogleApiClient(token)
            val sheets = client.listSpreadsheets().toMutableList()
            val linked = client.linkedSpreadsheetId()
            if (linked.isNotBlank() && sheets.none { it.id == linked }) {
                runCatching { client.spreadsheet(linked) }.getOrNull()?.let(sheets::add)
            }
            _status.value = SyncStatus(SyncPhase.IDLE, "Tabelle auswählen")
            sheets.distinctBy(GoogleSpreadsheet::id)
        }
    }

    suspend fun linkSpreadsheet(token: String, spreadsheetIdOrUrl: String): GoogleSpreadsheet =
        withContext(Dispatchers.IO) {
            execute(SyncPhase.LOADING_SHEETS, "Google-Tabelle wird verbunden …") {
                val client = GoogleApiClient(token)
                val sheet = client.spreadsheet(spreadsheetIdOrUrl)
                client.ensureTemplate(sheet.id)
                remember(sheet)
                _status.value = SyncStatus(SyncPhase.COMPLETE, "Google-Tabelle verbunden", 1f)
                sheet
            }
        }

    suspend fun createSpreadsheet(token: String, name: String): GoogleSpreadsheet =
        withContext(Dispatchers.IO) {
            execute(SyncPhase.UPLOADING, "Just-InCard-Tabelle wird erstellt …") {
                val template = appContext.assets.open(TEMPLATE_ASSET).use { it.readBytes() }
                val sheet = GoogleApiClient(token).createSpreadsheet(name, template)
                remember(sheet)
                _status.value = SyncStatus(SyncPhase.COMPLETE, "Google-Tabelle erstellt", 1f)
                sheet
            }
        }

    suspend fun save(token: String, spreadsheet: GoogleSpreadsheet? = null) = mutex.withLock {
        withContext(Dispatchers.IO) {
            execute(SyncPhase.UPLOADING, "Sammlung und Decks werden in Google gespeichert …", 0.08f) {
                val selected = resolveSpreadsheet(token, spreadsheet)
                val snapshot = localSnapshot()
                val cards = resolveCards(snapshot)
                val client = GoogleApiClient(token)
                _status.value = SyncStatus(SyncPhase.UPLOADING, "Sichtbare Tabellen werden aktualisiert …", 0.45f)
                client.replaceVisibleWorkbook(selected.id, WindowsSheetTemplate.workbook(snapshot, cards))
                _status.value = SyncStatus(SyncPhase.UPLOADING, "Vollständiges Cloud-Backup wird gespeichert …", 0.82f)
                client.saveBackup(WindowsCloudCodec.encode(selected.id, preferences.deviceName, snapshot, cards))
                finish(selected, "Sammlung und Decks in Google gespeichert")
            }
        }
    }

    suspend fun load(token: String, spreadsheet: GoogleSpreadsheet? = null) = mutex.withLock {
        withContext(Dispatchers.IO) {
            execute(SyncPhase.DOWNLOADING, "Sammlung und Decks werden aus Google geladen …", 0.1f) {
                val selected = resolveSpreadsheet(token, spreadsheet)
                val payload = GoogleApiClient(token).loadBackup(selected.id)
                    ?: throw GoogleSyncException(
                        "Für diese Tabelle wurde noch kein vollständiges Just-InCard-Cloud-Backup gespeichert.",
                    )
                val remote = WindowsCloudCodec.decode(payload, CLOUD_DEVICE_ID)
                _status.value = SyncStatus(SyncPhase.MERGING, "Cloud-Daten werden lokal zusammengeführt …", 0.64f)
                cardRepository.importCards(remote.cards.values)
                applyMerged(localSnapshot(), remote)
                finish(selected, "Sammlung und Decks aus Google geladen")
            }
        }
    }

    suspend fun sync(token: String, spreadsheet: GoogleSpreadsheet? = null) = mutex.withLock {
        withContext(Dispatchers.IO) {
            execute(SyncPhase.DOWNLOADING, "Google-Sammlung und Decks werden geladen …", 0.08f) {
                val selected = resolveSpreadsheet(token, spreadsheet)
                val client = GoogleApiClient(token)
                val local = localSnapshot()
                val remote = client.loadBackup(selected.id)?.let {
                    WindowsCloudCodec.decode(it, CLOUD_DEVICE_ID)
                } ?: CloudSnapshot()

                _status.value = SyncStatus(SyncPhase.MERGING, "Änderungen werden zusammengeführt …", 0.38f)
                cardRepository.importCards(remote.cards.values)
                val merged = mergeSnapshots(local, remote)
                collectionRepository.replaceAll(merged.collection)
                deckRepository.replaceAll(merged.decks)
                val cards = resolveCards(merged)

                _status.value = SyncStatus(SyncPhase.UPLOADING, "Gemeinsame Tabellen werden gespeichert …", 0.68f)
                client.replaceVisibleWorkbook(selected.id, WindowsSheetTemplate.workbook(merged, cards))
                _status.value = SyncStatus(SyncPhase.UPLOADING, "Vollständiges Cloud-Backup wird gespeichert …", 0.88f)
                client.saveBackup(WindowsCloudCodec.encode(selected.id, preferences.deviceName, merged, cards))
                finish(selected, "Google-Synchronisierung abgeschlossen")
            }
        }
    }

    fun devices(): List<SyncDevice> = emptyList()

    @Suppress("UNUSED_PARAMETER")
    suspend fun setDeviceEnabled(token: String, deviceId: String, enabled: Boolean) {
        throw GoogleSyncException(
            "Gerätefreigaben werden im gemeinsamen Windows-/Android-Cloudformat nicht benötigt.",
        )
    }

    private suspend fun resolveSpreadsheet(
        token: String,
        spreadsheet: GoogleSpreadsheet?,
    ): GoogleSpreadsheet {
        if (spreadsheet != null) {
            GoogleApiClient(token).ensureTemplate(spreadsheet.id)
            remember(spreadsheet)
            return spreadsheet
        }
        val id = CloudContract.normalizeSpreadsheetId(preferences.spreadsheetId)
        require(id.isNotBlank()) { "Bitte zuerst eine Google-Tabelle auswählen oder verbinden." }
        return GoogleApiClient(token).spreadsheet(id).also(::remember)
    }

    private suspend fun localSnapshot(): CloudSnapshot = CloudSnapshot(
        collection = collectionRepository.allForSync(),
        decks = deckRepository.allForSync(),
    )

    private suspend fun resolveCards(snapshot: CloudSnapshot): Map<CardKey, Card> {
        val keys = buildSet {
            snapshot.collection.forEach { add(it.cardKey) }
            snapshot.decks.flatMap(Deck::cards).forEach { add(it.cardKey) }
        }
        return buildMap {
            putAll(snapshot.cards)
            keys.forEach { key ->
                if (key !in this) cardRepository.card(key)?.let { put(key, it) }
            }
        }
    }

    private suspend fun applyMerged(local: CloudSnapshot, remote: CloudSnapshot) {
        val merged = mergeSnapshots(local, remote)
        collectionRepository.replaceAll(merged.collection)
        deckRepository.replaceAll(merged.decks)
    }

    private fun mergeSnapshots(local: CloudSnapshot, remote: CloudSnapshot): CloudSnapshot =
        CloudSnapshot(
            collection = mergeCollection(local.collection, remote.collection),
            decks = mergeDecks(local.decks, remote.decks),
            cards = local.cards + remote.cards,
        )

    private fun mergeCollection(
        local: List<CollectionItem>,
        remote: List<CollectionItem>,
    ): List<CollectionItem> = (local + remote)
        .groupBy { item ->
            listOf(
                item.cardKey.cardId,
                item.cardKey.artworkId,
                item.selectedPrint.setCode,
                item.selectedPrint.rarity,
                item.language,
            ).joinToString("|") { it.toString().trim().lowercase() }
        }
        .values
        .map { candidates ->
            candidates.maxWithOrNull(compareBy<CollectionItem>({ it.updatedAt }, { it.deviceId }, { it.id }))!!
        }
        .sortedBy(CollectionItem::cardName)

    private fun mergeDecks(local: List<Deck>, remote: List<Deck>): List<Deck> {
        val localIdsByName = local.associate { it.name.trim().lowercase() to it.id }
        return (local + remote)
            .groupBy { it.name.trim().lowercase() }
            .values
            .map { candidates ->
                val winner = candidates.maxWithOrNull(compareBy<Deck>({ it.updatedAt }, { it.deviceId }, { it.id }))!!
                val deckId = localIdsByName[winner.name.trim().lowercase()] ?: winner.id
                val cards = candidates
                    .flatMap(Deck::cards)
                    .groupBy(::deckCardIdentity)
                    .values
                    .map { rows ->
                        rows.maxWithOrNull(compareBy<DeckCard>({ it.updatedAt }, { it.deviceId }, { it.id }))!!
                            .copy(deckId = deckId)
                    }
                winner.copy(id = deckId, cards = cards)
            }
            .sortedBy(Deck::name)
    }

    private fun deckCardIdentity(card: DeckCard): String = listOf(
        card.cardKey.cardId,
        card.cardKey.artworkId,
        card.cardKey.language.lowercase(),
        card.setCode.uppercase(),
        card.section.name,
    ).joinToString("|")

    private fun remember(sheet: GoogleSpreadsheet) {
        preferences.spreadsheetId = sheet.id
        preferences.spreadsheetName = sheet.name
    }

    private fun finish(sheet: GoogleSpreadsheet, message: String) {
        remember(sheet)
        preferences.lastSyncAt = System.currentTimeMillis()
        _status.value = SyncStatus(SyncPhase.COMPLETE, message, 1f)
    }

    private suspend fun <T> execute(
        phase: SyncPhase,
        message: String,
        progress: Float? = null,
        block: suspend () -> T,
    ): T {
        _status.value = SyncStatus(phase, message, progress)
        return try {
            block()
        } catch (error: Throwable) {
            _status.value = SyncStatus(
                SyncPhase.ERROR,
                error.message ?: "Google-Synchronisierung fehlgeschlagen.",
            )
            throw error
        }
    }

    private companion object {
        const val TEMPLATE_ASSET = "google_sheets_template.xlsx"
        const val CLOUD_DEVICE_ID = "google-cloud"
    }
}
