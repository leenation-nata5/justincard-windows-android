package org.yugioh.kartenliste.ui

import android.content.ContentResolver
import android.net.Uri
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.yugioh.kartenliste.data.local.AppPreferences
import org.yugioh.kartenliste.data.model.CardLanguages
import org.yugioh.kartenliste.data.model.GoogleSpreadsheet
import org.yugioh.kartenliste.data.model.SyncDevice
import org.yugioh.kartenliste.data.repository.CardRepository
import org.yugioh.kartenliste.data.repository.CollectionRepository
import org.yugioh.kartenliste.data.repository.DeckRepository
import org.yugioh.kartenliste.sync.AccountSyncEngine
import org.yugioh.kartenliste.sync.BackupManager
import org.yugioh.kartenliste.sync.CsvCollectionCodec
import org.yugioh.kartenliste.sync.GoogleSheetsSyncEngine

data class SettingsUiState(
    val deviceName: String,
    val themeMode: String,
    val reducedMotion: Boolean,
    val cardTextLanguage: String,
    val accountMode: String,
    val accountLoggedIn: Boolean,
    val accountLabel: String,
    val accountAutomaticSync: Boolean,
    val accountLastSyncAt: Long,
    val automaticSync: Boolean,
    val spreadsheetId: String,
    val spreadsheetName: String,
    val spreadsheets: List<GoogleSpreadsheet> = emptyList(),
    val devices: List<SyncDevice> = emptyList(),
    val busy: Boolean = false,
    val message: String? = null,
    val error: String? = null,
)

class SettingsViewModel(
    private val preferences: AppPreferences,
    private val cards: CardRepository,
    private val collection: CollectionRepository,
    private val decks: DeckRepository,
    private val accountSync: AccountSyncEngine,
    private val backups: BackupManager,
    private val googleSheets: GoogleSheetsSyncEngine,
    private val resolver: ContentResolver,
) : ViewModel() {
    private val _state = MutableStateFlow(snapshot())
    val state: StateFlow<SettingsUiState> = _state.asStateFlow()
    val syncStatus = googleSheets.status

    fun updateDeviceName(value: String) {
        _state.value = _state.value.copy(deviceName = value)
        if (value.isNotBlank()) preferences.deviceName = value
    }

    fun updateTheme(value: String) {
        preferences.themeMode = value
        _state.value = _state.value.copy(themeMode = preferences.themeMode)
    }

    fun updateReducedMotion(value: Boolean) {
        preferences.reducedMotion = value
        _state.value = _state.value.copy(reducedMotion = preferences.reducedMotion)
    }

    fun updateCardTextLanguage(value: String) {
        val language = CardLanguages.normalize(value)
        preferences.cardTextLanguage = language
        _state.value = _state.value.copy(cardTextLanguage = language, busy = true, error = null)
        viewModelScope.launch {
            runCatching { cards.syncCatalog(language, force = false) }
                .onSuccess { count ->
                    val sourceNote = if (CardLanguages.hasRemoteCatalog(language)) {
                        "$count Kartendatensätze sind für ${CardLanguages.label(language)} verfügbar."
                    } else {
                        "${CardLanguages.label(language)} wird verwendet, sobald lokalisierte Daten vorhanden sind; fehlende Texte fallen auf Englisch zurück."
                    }
                    _state.value = settled(message = sourceNote)
                }
                .onFailure { _state.value = settled(error = it.message) }
        }
    }

    fun useLocalMode() {
        accountSync.useLocalMode()
        _state.value = snapshot().copy(message = "Lokaler Modus aktiv. Sammlung und Decks bleiben vollständig auf diesem Gerät.")
    }

    fun useAccountMode() {
        if (preferences.accountToken.isBlank()) {
            _state.value = _state.value.copy(error = "Bitte zuerst mit deinem Just-InCard-Konto anmelden.")
            return
        }
        preferences.accountMode = "account"
        _state.value = snapshot().copy(message = "Kontomodus aktiviert.")
        syncAccount()
    }

    fun updateAccountAutomaticSync(value: Boolean) {
        preferences.accountAutomaticSync = value
        _state.value = _state.value.copy(accountAutomaticSync = value)
    }

    fun loginAccount(identity: String, password: String) {
        if (identity.isBlank() || password.isBlank()) {
            _state.value = _state.value.copy(error = "Bitte Benutzername/E-Mail und Passwort eingeben.")
            return
        }
        val previousMode = preferences.accountMode
        preferences.accountMode = "account"
        _state.value = snapshot().copy(busy = true, error = null, message = null)
        viewModelScope.launch {
            runCatching {
                accountSync.login(identity, password)
                accountSync.sync()
            }.onSuccess { report ->
                _state.value = snapshot().copy(
                    message = "Konto verbunden. ${report.collectionCount} Sammlungseinträge und ${report.deckCount} Decks wurden synchronisiert.",
                )
            }.onFailure { error ->
                preferences.accountMode = previousMode
                _state.value = snapshot().copy(error = error.message ?: "Kontoanmeldung fehlgeschlagen.")
            }
        }
    }

    fun logoutAccount() {
        viewModelScope.launch {
            _state.value = _state.value.copy(busy = true, error = null)
            runCatching { accountSync.logout() }
                .onSuccess { _state.value = snapshot().copy(message = "Just-InCard-Konto wurde abgemeldet. Lokale Daten bleiben erhalten.") }
                .onFailure { _state.value = snapshot().copy(error = it.message) }
        }
    }

    fun syncAccount(silent: Boolean = false) {
        if (preferences.accountMode != "account" || preferences.accountToken.isBlank()) return
        viewModelScope.launch {
            if (!silent) _state.value = _state.value.copy(busy = true, error = null, message = null)
            runCatching { accountSync.sync() }
                .onSuccess { report ->
                    _state.value = snapshot().copy(
                        message = if (silent) null else "Konto synchronisiert: ${report.collectionCount} Sammlungseinträge, ${report.deckCount} Decks.",
                    )
                }
                .onFailure { error ->
                    _state.value = snapshot().copy(error = if (silent) null else error.message)
                }
        }
    }

    fun updateAutomaticSync(value: Boolean) {
        preferences.automaticSync = value
        _state.value = _state.value.copy(automaticSync = preferences.automaticSync)
    }

    fun refreshCatalog() {
        viewModelScope.launch {
            _state.value = _state.value.copy(busy = true)
            runCatching { cards.syncCatalog(preferences.cardTextLanguage, force = true) }
                .onSuccess { _state.value = settled(message = "$it Kartenabbildungen wurden indexiert.") }
                .onFailure { _state.value = settled(error = it.message) }
        }
    }

    fun loadSpreadsheets(token: String) {
        viewModelScope.launch {
            _state.value = _state.value.copy(busy = true, error = null)
            runCatching { googleSheets.listSpreadsheets(token) }
                .onSuccess { _state.value = snapshot().copy(spreadsheets = it) }
                .onFailure { _state.value = settled(error = it.message) }
        }
    }

    fun createSpreadsheet(token: String, name: String) {
        viewModelScope.launch {
            _state.value = _state.value.copy(busy = true)
            runCatching {
                val sheet = googleSheets.createSpreadsheet(token, name)
                googleSheets.save(token, sheet)
                sheet
            }
                .onSuccess { _state.value = settled(message = "Google-Tabelle erstellt; Sammlung und Decks wurden gespeichert.") }
                .onFailure { _state.value = settled(error = it.message) }
        }
    }

    fun linkSpreadsheet(token: String, idOrUrl: String) {
        viewModelScope.launch {
            _state.value = _state.value.copy(busy = true, error = null)
            runCatching { googleSheets.linkSpreadsheet(token, idOrUrl) }
                .onSuccess { _state.value = settled(message = "Google-Tabelle verbunden.") }
                .onFailure { _state.value = settled(error = it.message) }
        }
    }

    fun saveToGoogle(token: String) {
        viewModelScope.launch {
            _state.value = _state.value.copy(busy = true, error = null)
            runCatching { googleSheets.save(token) }
                .onSuccess { _state.value = settled(message = "Sammlung und Decks wurden in Google gespeichert.") }
                .onFailure { _state.value = settled(error = it.message) }
        }
    }

    fun loadFromGoogle(token: String) {
        viewModelScope.launch {
            _state.value = _state.value.copy(busy = true, error = null)
            runCatching { googleSheets.load(token) }
                .onSuccess { _state.value = settled(message = "Sammlung und Decks wurden aus Google geladen.") }
                .onFailure { _state.value = settled(error = it.message) }
        }
    }

    fun sync(token: String, spreadsheet: GoogleSpreadsheet? = null) {
        viewModelScope.launch {
            _state.value = _state.value.copy(busy = true, error = null)
            runCatching { googleSheets.sync(token, spreadsheet) }
                .onSuccess { _state.value = settled(message = "Google-Synchronisierung abgeschlossen.") }
                .onFailure { _state.value = settled(error = it.message) }
        }
    }

    fun setDeviceEnabled(token: String, device: SyncDevice, enabled: Boolean) {
        viewModelScope.launch {
            _state.value = _state.value.copy(busy = true, error = null)
            runCatching { googleSheets.setDeviceEnabled(token, device.id, enabled) }
                .onSuccess { _state.value = settled() }
                .onFailure { _state.value = settled(error = it.message) }
        }
    }

    fun exportBackup(uri: Uri) {
        viewModelScope.launch {
            _state.value = _state.value.copy(busy = true)
            runCatching {
                withContext(Dispatchers.IO) { backups.export(uri, collection.allForSync(), decks.allForSync()) }
            }.onSuccess { _state.value = settled(message = "Backup wurde gespeichert.") }
                .onFailure { _state.value = settled(error = it.message) }
        }
    }

    fun importBackup(uri: Uri) {
        viewModelScope.launch {
            _state.value = _state.value.copy(busy = true)
            runCatching {
                val payload = withContext(Dispatchers.IO) { backups.import(uri) }
                collection.replaceAll(payload.collection)
                decks.replaceAll(payload.decks)
            }.onSuccess { _state.value = settled(message = "Backup wurde vollständig importiert.") }
                .onFailure { _state.value = settled(error = it.message) }
        }
    }

    fun exportCsv(uri: Uri) {
        viewModelScope.launch {
            _state.value = _state.value.copy(busy = true, error = null)
            runCatching {
                val text = CsvCollectionCodec.encode(collection.allForSync())
                withContext(Dispatchers.IO) {
                    resolver.openOutputStream(uri, "w")?.bufferedWriter()?.use { it.write(text) }
                        ?: error("Zieldatei kann nicht geöffnet werden.")
                }
            }.onSuccess { _state.value = settled(message = "CSV wurde für Google Sheets/Excel gespeichert.") }
                .onFailure { _state.value = settled(error = it.message) }
        }
    }

    fun importCsv(uri: Uri) {
        viewModelScope.launch {
            _state.value = _state.value.copy(busy = true, error = null)
            runCatching {
                val imported = withContext(Dispatchers.IO) {
                    resolver.openInputStream(uri)?.bufferedReader()?.use {
                        CsvCollectionCodec.decode(it, preferences.deviceId)
                    } ?: error("CSV-Datei kann nicht geöffnet werden.")
                }
                collection.merge(imported)
            }.onSuccess { _state.value = settled(message = "CSV wurde importiert.") }
                .onFailure { _state.value = settled(error = it.message) }
        }
    }

    fun dismissMessage() { _state.value = _state.value.copy(message = null, error = null) }

    private fun settled(message: String? = null, error: String? = null): SettingsUiState =
        snapshot().copy(
            spreadsheets = _state.value.spreadsheets,
            devices = googleSheets.devices(),
            message = message,
            error = error,
        )

    private fun snapshot(): SettingsUiState = SettingsUiState(
        deviceName = preferences.deviceName,
        themeMode = preferences.themeMode,
        reducedMotion = preferences.reducedMotion,
        cardTextLanguage = preferences.cardTextLanguage,
        accountMode = preferences.accountMode,
        accountLoggedIn = preferences.accountToken.isNotBlank(),
        accountLabel = preferences.accountLabel,
        accountAutomaticSync = preferences.accountAutomaticSync,
        accountLastSyncAt = preferences.accountLastSyncAt,
        automaticSync = preferences.automaticSync,
        spreadsheetId = preferences.spreadsheetId,
        spreadsheetName = preferences.spreadsheetName,
        devices = googleSheets.devices(),
    )
}
