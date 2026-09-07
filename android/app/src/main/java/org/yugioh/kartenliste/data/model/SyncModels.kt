package org.yugioh.kartenliste.data.model

data class SyncDevice(
    val id: String,
    val name: String,
    val enabled: Boolean,
    val lastSeenAt: Long,
    val isCurrent: Boolean = false,
)

data class GoogleSpreadsheet(
    val id: String,
    val name: String,
    val modifiedTime: String = "",
)

data class SyncProfile(
    val spreadsheetId: String = "",
    val spreadsheetName: String = "",
    val deviceId: String,
    val deviceName: String,
    val automaticSync: Boolean = false,
    val lastSyncAt: Long = 0L,
)

enum class SyncPhase {
    IDLE,
    AUTHORIZING,
    LOADING_SHEETS,
    DOWNLOADING,
    MERGING,
    UPLOADING,
    COMPLETE,
    ERROR,
}

data class SyncStatus(
    val phase: SyncPhase = SyncPhase.IDLE,
    val message: String = "Nicht verbunden",
    val progress: Float? = null,
)
