package org.yugioh.kartenliste.data.local

import android.content.Context
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import org.yugioh.kartenliste.data.model.CardLanguages
import org.yugioh.kartenliste.data.model.SyncProfile
import java.util.UUID

class AppPreferences(context: Context) {
    private val preferences = context.getSharedPreferences("justincard_preferences_v13", Context.MODE_PRIVATE)
    private val _cardTextLanguage = MutableStateFlow(
        CardLanguages.normalize(preferences.getString(KEY_CARD_TEXT_LANGUAGE, "de")),
    )
    val cardTextLanguageFlow: StateFlow<String> = _cardTextLanguage.asStateFlow()

    val deviceId: String
        get() = preferences.getString(KEY_DEVICE_ID, null) ?: UUID.randomUUID().toString().also {
            preferences.edit().putString(KEY_DEVICE_ID, it).apply()
        }

    var deviceName: String
        get() = preferences.getString(KEY_DEVICE_NAME, null).orEmpty().ifBlank { "Mein Android-Gerät" }
        set(value) { preferences.edit().putString(KEY_DEVICE_NAME, value.trim().ifBlank { "Mein Android-Gerät" }).apply() }

    var themeMode: String
        get() = preferences.getString(KEY_THEME, "system") ?: "system"
        set(value) { preferences.edit().putString(KEY_THEME, value).apply() }

    var reducedMotion: Boolean
        get() = preferences.getBoolean(KEY_REDUCED_MOTION, false)
        set(value) { preferences.edit().putBoolean(KEY_REDUCED_MOTION, value).apply() }


    var cardTextLanguage: String
        get() = CardLanguages.normalize(preferences.getString(KEY_CARD_TEXT_LANGUAGE, "de"))
        set(value) {
            val normalized = CardLanguages.normalize(value)
            preferences.edit().putString(KEY_CARD_TEXT_LANGUAGE, normalized).apply()
            _cardTextLanguage.value = normalized
        }

    var spreadsheetId: String
        get() = preferences.getString(KEY_SHEET_ID, "") ?: ""
        set(value) { preferences.edit().putString(KEY_SHEET_ID, value.trim()).apply() }

    var spreadsheetName: String
        get() = preferences.getString(KEY_SHEET_NAME, "") ?: ""
        set(value) { preferences.edit().putString(KEY_SHEET_NAME, value.trim()).apply() }

    var automaticSync: Boolean
        get() = preferences.getBoolean(KEY_AUTO_SYNC, false)
        set(value) { preferences.edit().putBoolean(KEY_AUTO_SYNC, value).apply() }

    var lastSyncAt: Long
        get() = preferences.getLong(KEY_LAST_SYNC, 0L)
        set(value) { preferences.edit().putLong(KEY_LAST_SYNC, value).apply() }

    var welcomeShown: Boolean
        get() = preferences.getBoolean(KEY_WELCOME_SHOWN, false)
        set(value) { preferences.edit().putBoolean(KEY_WELCOME_SHOWN, value).apply() }

    var accountMode: String
        get() = preferences.getString(KEY_ACCOUNT_MODE, "") ?: ""
        set(value) { preferences.edit().putString(KEY_ACCOUNT_MODE, value).apply() }

    var accountToken: String
        get() = preferences.getString(KEY_ACCOUNT_TOKEN, "") ?: ""
        set(value) { preferences.edit().putString(KEY_ACCOUNT_TOKEN, value).apply() }

    var accountLabel: String
        get() = preferences.getString(KEY_ACCOUNT_LABEL, "") ?: ""
        set(value) { preferences.edit().putString(KEY_ACCOUNT_LABEL, value).apply() }

    var accountAutomaticSync: Boolean
        get() = preferences.getBoolean(KEY_ACCOUNT_AUTO_SYNC, true)
        set(value) { preferences.edit().putBoolean(KEY_ACCOUNT_AUTO_SYNC, value).apply() }

    var accountLastSyncAt: Long
        get() = preferences.getLong(KEY_ACCOUNT_LAST_SYNC, 0L)
        set(value) { preferences.edit().putLong(KEY_ACCOUNT_LAST_SYNC, value).apply() }

    var accountRestoreReady: Boolean
        get() = preferences.getBoolean(KEY_ACCOUNT_RESTORE_READY, false)
        set(value) { preferences.edit().putBoolean(KEY_ACCOUNT_RESTORE_READY, value).apply() }

    fun syncProfile(): SyncProfile = SyncProfile(
        spreadsheetId = spreadsheetId,
        spreadsheetName = spreadsheetName,
        deviceId = deviceId,
        deviceName = deviceName,
        automaticSync = automaticSync,
        lastSyncAt = lastSyncAt,
    )

    companion object {
        private const val KEY_DEVICE_ID = "device_id"
        private const val KEY_DEVICE_NAME = "device_name"
        private const val KEY_THEME = "theme"
        private const val KEY_REDUCED_MOTION = "reduced_motion"
        private const val KEY_CARD_TEXT_LANGUAGE = "card_text_language"
        private const val KEY_SHEET_ID = "spreadsheet_id"
        private const val KEY_SHEET_NAME = "spreadsheet_name"
        private const val KEY_AUTO_SYNC = "automatic_sync"
        private const val KEY_LAST_SYNC = "last_sync_at"
        private const val KEY_WELCOME_SHOWN = "welcome_shown"
        private const val KEY_ACCOUNT_MODE = "account_mode_v1308"
        private const val KEY_ACCOUNT_TOKEN = "account_token_v1308"
        private const val KEY_ACCOUNT_LABEL = "account_label_v1308"
        private const val KEY_ACCOUNT_AUTO_SYNC = "account_auto_sync_v1308"
        private const val KEY_ACCOUNT_LAST_SYNC = "account_last_sync_v1308"
        private const val KEY_ACCOUNT_RESTORE_READY = "account_restore_ready_v1310"
    }
}
