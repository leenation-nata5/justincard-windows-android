package org.yugioh.kartenliste.cloud

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import com.google.android.gms.auth.GoogleAuthUtil
import com.google.android.gms.auth.api.signin.GoogleSignIn
import com.google.android.gms.auth.api.signin.GoogleSignInAccount
import com.google.android.gms.auth.api.signin.GoogleSignInClient
import com.google.android.gms.auth.api.signin.GoogleSignInOptions
import com.google.android.gms.common.api.Scope
import com.google.gson.Gson
import com.google.gson.JsonArray
import com.google.gson.JsonObject
import com.google.gson.reflect.TypeToken
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.yugioh.kartenliste.core.CloudContract
import org.yugioh.kartenliste.data.CloudBackup
import org.yugioh.kartenliste.data.CollectionItem
import org.yugioh.kartenliste.data.Deck
import org.yugioh.kartenliste.data.JustInCardDatabase
import java.net.URLEncoder
import java.time.Instant
import java.util.concurrent.TimeUnit

class GoogleCloudRepository(
    private val context: Context,
    private val database: JustInCardDatabase,
    private val client: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(20, TimeUnit.SECONDS)
        .readTimeout(45, TimeUnit.SECONDS)
        .writeTimeout(45, TimeUnit.SECONDS)
        .build(),
) {
    companion object {
        const val SETTING_SHEET_ID = "google_cloud_sheet_id"
        const val SETTING_SORT = "google_cloud_sort_field"
        const val SETTING_DIRECTION = "google_cloud_sort_direction"
        const val SETTING_AUTO_SYNC = "google_cloud_auto_sync"
        const val ANDROID_VERSION = "14.1.1"
    }

    data class Status(
        val signedIn: Boolean,
        val email: String = "",
        val spreadsheetId: String = "",
        val spreadsheetUrl: String = "",
    )

    data class SyncResult(
        val spreadsheetId: String,
        val collectionCount: Int,
        val deckCount: Int,
        val url: String,
        val message: String,
    )

    private val gson = Gson()
    private val mapType = object : TypeToken<Map<String, Any?>>() {}.type
    private val listMapType = object : TypeToken<List<Map<String, Any?>>>() {}.type

    private val options: GoogleSignInOptions by lazy {
        GoogleSignInOptions.Builder(GoogleSignInOptions.DEFAULT_SIGN_IN)
            .requestEmail()
            .requestScopes(
                Scope(CloudContract.DRIVE_FILE_SCOPE),
                Scope(CloudContract.DRIVE_APPDATA_SCOPE),
            )
            .build()
    }

    val signInClient: GoogleSignInClient by lazy { GoogleSignIn.getClient(context, options) }

    fun signInIntent(): Intent = signInClient.signInIntent

    fun handleSignInResult(data: Intent?): GoogleSignInAccount {
        val task = GoogleSignIn.getSignedInAccountFromIntent(data)
        return task.getResult(Exception::class.java)
    }

    suspend fun signOut() = withContext(Dispatchers.IO) { signInClient.signOut().awaitCompat() }

    fun status(): Status {
        val account = GoogleSignIn.getLastSignedInAccount(context)
        val signedIn = account != null && GoogleSignIn.hasPermissions(
            account,
            Scope(CloudContract.DRIVE_FILE_SCOPE),
            Scope(CloudContract.DRIVE_APPDATA_SCOPE),
        )
        val id = database.getSetting(SETTING_SHEET_ID)
        return Status(signedIn, account?.email.orEmpty(), id, CloudContract.sheetUrl(id))
    }

    suspend fun ensureSpreadsheet(): String = withContext(Dispatchers.IO) {
        val preferred = database.getSetting(SETTING_SHEET_ID)
        if (preferred.isNotBlank() && runCatching { verifySpreadsheet(preferred) }.isSuccess) return@withContext preferred
        val linkedFromBackup = findLinkedSpreadsheetFromBackup()
        if (linkedFromBackup.isNotBlank() && runCatching { verifySpreadsheet(linkedFromBackup) }.isSuccess) {
            database.setSetting(SETTING_SHEET_ID, linkedFromBackup)
            return@withContext linkedFromBackup
        }
        val found = findSpreadsheet()
        val id = found.ifBlank { createSpreadsheetFromTemplate() }
        database.setSetting(SETTING_SHEET_ID, id)
        id
    }

    suspend fun uploadLocal(): SyncResult = withContext(Dispatchers.IO) {
        requireAccount()
        val id = ensureSpreadsheet()
        val collection = database.listCollection()
        val decks = database.listDecks()
        updateVisibleWorkbook(id, collection, decks)
        saveBackup(id, collection, decks)
        SyncResult(id, collection.size, decks.size, CloudContract.sheetUrl(id), "Cloud-Sicherung aktualisiert")
    }

    suspend fun loadCloud(): SyncResult = withContext(Dispatchers.IO) {
        requireAccount()
        val id = ensureSpreadsheet()
        val cloud = loadBackup(id)
        cloud.collection.forEach(database::upsertCollection)
        database.replaceDecksFromCloud(cloud.decks)
        SyncResult(id, cloud.collection.size, cloud.decks.size, CloudContract.sheetUrl(id), "Cloud-Daten geladen")
    }

    suspend fun syncBidirectional(): SyncResult = withContext(Dispatchers.IO) {
        requireAccount()
        val id = ensureSpreadsheet()
        val cloud = loadBackup(id)
        val mergedCollection = CloudMapper.mergeCollection(database.listCollection(), cloud.collection)
        val mergedDecks = CloudMapper.mergeDecks(database.listDecks(), cloud.decks)
        mergedCollection.forEach(database::upsertCollection)
        database.replaceDecksFromCloud(mergedDecks)
        updateVisibleWorkbook(id, mergedCollection, mergedDecks)
        saveBackup(id, mergedCollection, mergedDecks)
        SyncResult(id, mergedCollection.size, mergedDecks.size, CloudContract.sheetUrl(id), "Windows/Android-Cloud synchronisiert")
    }

    private fun requireAccount(): GoogleSignInAccount {
        val account = GoogleSignIn.getLastSignedInAccount(context)
            ?: error("Bitte zuerst mit Google anmelden.")
        if (!GoogleSignIn.hasPermissions(account, Scope(CloudContract.DRIVE_FILE_SCOPE), Scope(CloudContract.DRIVE_APPDATA_SCOPE))) {
            error("Google Drive-Berechtigungen fehlen. Bitte erneut anmelden.")
        }
        return account
    }

    private fun token(): String {
        val account = requireAccount().account ?: error("Google-Konto ist nicht verfügbar.")
        return GoogleAuthUtil.getToken(context, account, "oauth2:${CloudContract.SCOPES.joinToString(" ")}")
    }

    private fun authorized(requestBuilder: Request.Builder): String {
        var authToken = token()
        repeat(2) { attempt ->
            val request = requestBuilder.header("Authorization", "Bearer $authToken").build()
            client.newCall(request).execute().use { response ->
                val text = response.body?.string().orEmpty()
                if (response.isSuccessful) return text
                if (response.code == 401 && attempt == 0) {
                    runCatching { GoogleAuthUtil.clearToken(context, authToken) }
                    authToken = token()
                } else {
                    error("Google API ${response.code}: ${text.take(500)}")
                }
            }
        }
        error("Google-Anmeldung ist abgelaufen.")
    }

    private fun driveGet(pathAndQuery: String): JsonObject {
        val body = authorized(Request.Builder().url("https://www.googleapis.com/drive/v3/$pathAndQuery").get())
        return gson.fromJson(body, JsonObject::class.java)
    }

    private fun verifySpreadsheet(id: String) {
        val escaped = encode(id)
        val result = driveGet("files/$escaped?fields=id,mimeType,appProperties")
        require(result.get("mimeType")?.asString == "application/vnd.google-apps.spreadsheet") { "Google-Datei ist kein Sheet." }
    }

    private fun findSpreadsheet(): String {
        val q = "trashed=false and appProperties has { key='${CloudContract.APP_PROPERTY_KEY}' and value='${CloudContract.APP_PROPERTY_VALUE}' }"
        val result = driveGet("files?q=${encode(q)}&spaces=drive&orderBy=modifiedTime%20desc&pageSize=10&fields=files(id,name,modifiedTime)")
        return result.getAsJsonArray("files")?.firstOrNull()?.asJsonObject?.get("id")?.asString.orEmpty()
    }

    private fun createSpreadsheetFromTemplate(): String {
        val media = context.assets.open("google_sheets_template.xlsx").use { it.readBytes() }
        val metadata = JsonObject().apply {
            addProperty("name", CloudContract.SHEET_TITLE)
            addProperty("mimeType", "application/vnd.google-apps.spreadsheet")
            add("appProperties", JsonObject().apply { addProperty(CloudContract.APP_PROPERTY_KEY, CloudContract.APP_PROPERTY_VALUE) })
        }
        val multipart = MultipartBody.Builder("justincard-${System.nanoTime()}")
            .setType("multipart/related".toMediaType())
            .addPart(metadata.toString().toRequestBody("application/json; charset=utf-8".toMediaType()))
            .addPart(media.toRequestBody("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet".toMediaType()))
            .build()
        val body = authorized(
            Request.Builder()
                .url("https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id,webViewLink")
                .post(multipart)
        )
        val id = gson.fromJson(body, JsonObject::class.java).get("id")?.asString.orEmpty()
        require(id.isNotBlank()) { "Google Drive hat keine Tabellen-ID zurückgegeben." }
        return id
    }

    private fun findBackupFile(): String {
        val q = "name='${CloudContract.BACKUP_FILE_NAME}' and trashed=false"
        val result = driveGet("files?q=${encode(q)}&spaces=appDataFolder&orderBy=modifiedTime%20desc&pageSize=10&fields=files(id,name,modifiedTime)")
        return result.getAsJsonArray("files")?.firstOrNull()?.asJsonObject?.get("id")?.asString.orEmpty()
    }

    private fun findLinkedSpreadsheetFromBackup(): String {
        val id = findBackupFile()
        if (id.isBlank()) return ""
        return runCatching {
            val raw = authorized(Request.Builder().url("https://www.googleapis.com/drive/v3/files/${encode(id)}?alt=media").get())
            gson.fromJson(raw, JsonObject::class.java)?.get("spreadsheet_id")?.asString.orEmpty()
        }.getOrDefault("")
    }

    private fun saveBackup(spreadsheetId: String, collection: List<CollectionItem>, decks: List<Deck>) {
        val payload = CloudBackup(
            schema = CloudContract.CLOUD_SCHEMA,
            appVersion = ANDROID_VERSION,
            updatedAt = Instant.now().toString(),
            device = "${Build.MANUFACTURER} ${Build.MODEL}".trim(),
            spreadsheetId = spreadsheetId,
            collection = collection.map(CloudMapper::collectionToMap),
            decks = decks.map(CloudMapper::deckToMap),
        )
        val data = gson.toJson(payload).toByteArray(Charsets.UTF_8)
        val existing = findBackupFile()
        if (existing.isBlank()) {
            val metadata = JsonObject().apply {
                addProperty("name", CloudContract.BACKUP_FILE_NAME)
                addProperty("mimeType", "application/json")
                add("parents", JsonArray().apply { add("appDataFolder") })
            }
            val multipart = MultipartBody.Builder("jic-backup-${System.nanoTime()}")
                .setType("multipart/related".toMediaType())
                .addPart(metadata.toString().toRequestBody("application/json; charset=utf-8".toMediaType()))
                .addPart(data.toRequestBody("application/json".toMediaType()))
                .build()
            authorized(Request.Builder().url("https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id").post(multipart))
        } else {
            authorized(
                Request.Builder()
                    .url("https://www.googleapis.com/upload/drive/v3/files/${encode(existing)}?uploadType=media&fields=id")
                    .patch(data.toRequestBody("application/json".toMediaType()))
            )
        }
    }

    private fun loadBackup(spreadsheetId: String): ParsedBackup {
        val id = findBackupFile()
        if (id.isBlank()) return ParsedBackup(emptyList(), emptyList())
        val raw = authorized(Request.Builder().url("https://www.googleapis.com/drive/v3/files/${encode(id)}?alt=media").get())
        val root = gson.fromJson(raw, JsonObject::class.java) ?: return ParsedBackup(emptyList(), emptyList())
        val linked = root.get("spreadsheet_id")?.asString.orEmpty()
        if (linked.isNotBlank() && linked != spreadsheetId) return ParsedBackup(emptyList(), emptyList())
        val collectionRaw: List<Map<String, Any?>> = runCatching {
            gson.fromJson(root.get("collection"), listMapType)
        }.getOrDefault(emptyList())
        val decksRaw: List<Map<String, Any?>> = runCatching {
            gson.fromJson(root.get("decks"), listMapType)
        }.getOrDefault(emptyList())
        return ParsedBackup(
            collectionRaw.mapNotNull(CloudMapper::mapToCollection),
            decksRaw.mapNotNull(CloudMapper::mapToDeck),
        )
    }

    private data class ParsedBackup(val collection: List<CollectionItem>, val decks: List<Deck>)

    private fun updateVisibleWorkbook(spreadsheetId: String, collection: List<CollectionItem>, decks: List<Deck>) {
        val sort = runCatching { SheetTemplate.SortField.valueOf(database.getSetting(SETTING_SORT, SheetTemplate.SortField.NAME.name)) }
            .getOrDefault(SheetTemplate.SortField.NAME)
        val direction = runCatching { SheetTemplate.Direction.valueOf(database.getSetting(SETTING_DIRECTION, SheetTemplate.Direction.ASC.name)) }
            .getOrDefault(SheetTemplate.Direction.ASC)
        val workbook = SheetTemplate.workbook(collection, decks, sort, direction)
        syncDeckSheets(spreadsheetId, workbook.deckTabs.keys)

        val clearRanges = buildList {
            add("'${CloudContract.MONSTER_SHEET}'!A2:F")
            add("'${CloudContract.SPELL_SHEET}'!A2:C")
            add("'${CloudContract.TRAP_SHEET}'!A2:C")
            workbook.deckTabs.keys.forEach { add("'${escapeTitle(it)}'!A2:F") }
        }
        sheetsPost(spreadsheetId, "values:batchClear", JsonObject().apply {
            add("ranges", gson.toJsonTree(clearRanges))
        })

        val data = JsonArray()
        workbook.collectionTabs.forEach { (title, rows) ->
            if (rows.size > 1) data.add(valueRange("'${escapeTitle(title)}'!A2", rows.drop(1)))
        }
        workbook.deckTabs.forEach { (title, rows) ->
            if (rows.size > 1) data.add(valueRange("'${escapeTitle(title)}'!A2", rows.drop(1)))
        }
        if (data.size() > 0) {
            sheetsPost(spreadsheetId, "values:batchUpdate", JsonObject().apply {
                addProperty("valueInputOption", "RAW")
                add("data", data)
            })
        }
    }

    private fun valueRange(range: String, rows: List<List<Any>>): JsonObject = JsonObject().apply {
        addProperty("range", range)
        add("values", gson.toJsonTree(rows))
    }

    private fun sheetIds(spreadsheetId: String): Map<String, Int> {
        val text = authorized(
            Request.Builder().url("https://sheets.googleapis.com/v4/spreadsheets/${encode(spreadsheetId)}?fields=sheets.properties").get()
        )
        val root = gson.fromJson(text, JsonObject::class.java)
        return root.getAsJsonArray("sheets").orEmpty().associate { node ->
            val p = node.asJsonObject.getAsJsonObject("properties")
            p.get("title").asString to p.get("sheetId").asInt
        }
    }

    private fun syncDeckSheets(spreadsheetId: String, desiredTitles: Set<String>) {
        var ids = sheetIds(spreadsheetId)
        val sourceId = ids[CloudContract.MONSTER_SHEET] ?: error("Vorlage besitzt keinen Monsterkarten-Reiter.")
        val existingDecks = ids.keys - CloudContract.BASE_SHEETS.toSet()
        val requests = JsonArray()
        (existingDecks - desiredTitles).sorted().forEach { title ->
            requests.add(JsonObject().apply {
                add("deleteSheet", JsonObject().apply { addProperty("sheetId", ids.getValue(title)) })
            })
        }
        (desiredTitles - ids.keys).sorted().forEach { title ->
            requests.add(JsonObject().apply {
                add("duplicateSheet", JsonObject().apply {
                    addProperty("sourceSheetId", sourceId)
                    addProperty("newSheetName", title)
                })
            })
        }
        if (requests.size() > 0) {
            sheetsPost(spreadsheetId, ":batchUpdate", JsonObject().apply { add("requests", requests) })
            ids = sheetIds(spreadsheetId)
        }
        require(CloudContract.BASE_SHEETS.all { it in ids }) { "Google-Sheets-Vorlage ist unvollständig." }
    }

    private fun sheetsPost(spreadsheetId: String, suffix: String, payload: JsonObject): JsonObject {
        val url = if (suffix.startsWith(":")) {
            "https://sheets.googleapis.com/v4/spreadsheets/${encode(spreadsheetId)}$suffix"
        } else {
            "https://sheets.googleapis.com/v4/spreadsheets/${encode(spreadsheetId)}/$suffix"
        }
        val text = authorized(Request.Builder().url(url).post(payload.toString().toRequestBody("application/json; charset=utf-8".toMediaType())))
        return if (text.isBlank()) JsonObject() else gson.fromJson(text, JsonObject::class.java)
    }

    fun browserIntent(spreadsheetId: String = database.getSetting(SETTING_SHEET_ID)): Intent =
        Intent(Intent.ACTION_VIEW, Uri.parse(CloudContract.sheetUrl(spreadsheetId)))

    private fun escapeTitle(value: String) = value.replace("'", "''")
    private fun encode(value: String): String = URLEncoder.encode(value, Charsets.UTF_8.name()).replace("+", "%20")
}

private suspend fun com.google.android.gms.tasks.Task<Void>.awaitCompat() = withContext(Dispatchers.IO) {
    while (!isComplete) Thread.sleep(15)
    if (!isSuccessful) throw (exception ?: IllegalStateException("Google Task fehlgeschlagen"))
}

private fun JsonArray?.orEmpty(): JsonArray = this ?: JsonArray()
