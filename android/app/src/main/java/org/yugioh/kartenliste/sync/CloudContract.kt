package org.yugioh.kartenliste.sync

object CloudContract {
    const val SHEET_TITLE = "Just InCard – Sammlung"
    const val MONSTER_SHEET = "Monsterkarten"
    const val SPELL_SHEET = "Zauberkarten"
    const val TRAP_SHEET = "Fallenkarten"
    val BASE_SHEETS = listOf(MONSTER_SHEET, SPELL_SHEET, TRAP_SHEET)

    const val APP_PROPERTY_KEY = "justincard_cloud_type"
    const val APP_PROPERTY_VALUE = "collection-template-v1"
    const val CLOUD_SCHEMA = "justincard-google-drive-backup-v4"
    const val BACKUP_FILE_NAME = "justincard-cloud-backup-v125.json"

    const val DRIVE_FILE_SCOPE = "https://www.googleapis.com/auth/drive.file"
    const val DRIVE_APPDATA_SCOPE = "https://www.googleapis.com/auth/drive.appdata"
    const val SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"

    // Android 13.0.11 requests the explicit Sheets scope in addition to the
    // per-file Drive scopes. This makes reading and editing an existing shared
    // Just-InCard spreadsheet independent from Drive's per-file authorization
    // while the private appData backup remains protected by drive.appdata.
    val SCOPES = listOf(DRIVE_FILE_SCOPE, DRIVE_APPDATA_SCOPE, SHEETS_SCOPE)

    val MONSTER_HEADERS = listOf("Sterne", "Name", "Typ", "Element", "Kategorie", "Set-Code")
    val SPELL_HEADERS = listOf("Kategorie", "Name", "Set-Code")
    val TRAP_HEADERS = listOf("Kategorie", "Name", "Set-Code")

    fun normalizeSpreadsheetId(value: String?): String {
        val text = value.orEmpty().trim()
        if (text.isBlank()) return ""
        val fromUrl = Regex("/spreadsheets/d/([A-Za-z0-9_-]+)").find(text)?.groupValues?.getOrNull(1)
        if (!fromUrl.isNullOrBlank()) return fromUrl
        return text.takeIf { it.matches(Regex("[A-Za-z0-9_-]{20,}")) }.orEmpty()
    }

    fun canonicalCollectionKey(
        cardId: Long,
        printCode: String?,
        rarity: String?,
        language: String?,
        artworkUrl: String?,
    ): String = listOf(
        cardId.toString(),
        printCode.orEmpty().trim().uppercase(),
        rarity.orEmpty().trim().lowercase(),
        language.orEmpty().trim().lowercase(),
        artworkUrl.orEmpty().trim(),
    ).joinToString("|")

    fun spreadsheetUrl(id: String): String = normalizeSpreadsheetId(id).let {
        if (it.isBlank()) "" else "https://docs.google.com/spreadsheets/d/$it/edit"
    }
}
