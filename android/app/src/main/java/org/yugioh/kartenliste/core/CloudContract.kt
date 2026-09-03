package org.yugioh.kartenliste.core

object CloudContract {
    const val DRIVE_FILE_SCOPE = "https://www.googleapis.com/auth/drive.file"
    const val DRIVE_APPDATA_SCOPE = "https://www.googleapis.com/auth/drive.appdata"
    val SCOPES = listOf(DRIVE_FILE_SCOPE, DRIVE_APPDATA_SCOPE)

    const val SHEET_TITLE = "Just InCard – Sammlung"
    const val MONSTER_SHEET = "Monsterkarten"
    const val SPELL_SHEET = "Zauberkarten"
    const val TRAP_SHEET = "Fallenkarten"
    val BASE_SHEETS = listOf(MONSTER_SHEET, SPELL_SHEET, TRAP_SHEET)

    const val APP_PROPERTY_KEY = "justincard_cloud_type"
    const val APP_PROPERTY_VALUE = "collection-template-v1"
    const val CLOUD_SCHEMA = "justincard-google-drive-backup-v4"
    const val BACKUP_FILE_NAME = "justincard-cloud-backup-v125.json"

    val MONSTER_HEADERS = listOf("Sterne", "Name", "Typ", "Element", "Kategorie", "Set-Code")
    val SPELL_HEADERS = listOf("Kategorie", "Name", "Set-Code")
    val TRAP_HEADERS = listOf("Kategorie", "Name", "Set-Code")

    fun canonicalCollectionKey(
        cardId: Long?, printCode: String?, rarity: String?, language: String?, artworkUrl: String?
    ): String = listOf(
        cardId?.toString().orEmpty().trim(),
        printCode.orEmpty().trim().uppercase(),
        rarity.orEmpty().trim().lowercase(),
        language.orEmpty().trim().lowercase(),
        artworkUrl.orEmpty().trim(),
    ).joinToString("|")

    fun sheetUrl(id: String): String =
        if (id.isBlank()) "" else "https://docs.google.com/spreadsheets/d/$id/edit"
}
