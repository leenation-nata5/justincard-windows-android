package org.yugioh.kartenliste.sync

import org.json.JSONArray
import org.json.JSONObject
import org.yugioh.kartenliste.BuildConfig
import org.yugioh.kartenliste.data.model.GoogleSpreadsheet
import java.io.ByteArrayOutputStream
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URI
import java.net.URLEncoder
import java.nio.charset.StandardCharsets

/** Small REST client used after GoogleAuthorizationManager returned an access token. */
class GoogleApiClient(private val accessToken: String) {
    fun listSpreadsheets(): List<GoogleSpreadsheet> {
        val query = "mimeType='application/vnd.google-apps.spreadsheet' and trashed=false"
        val result = mutableListOf<GoogleSpreadsheet>()
        var pageToken = ""
        do {
            val tokenParameter = if (pageToken.isBlank()) "" else "&pageToken=${encode(pageToken)}"
            val path = "files?q=${encode(query)}&orderBy=modifiedTime%20desc" +
                "&fields=nextPageToken,files(id,name,modifiedTime)&pageSize=100$tokenParameter"
            val response = JSONObject(jsonRequest(Api.DRIVE, "GET", path))
            val files = response.optJSONArray("files") ?: JSONArray()
            for (index in 0 until files.length()) {
                val file = files.optJSONObject(index) ?: continue
                val id = file.optString("id")
                if (id.isNotBlank()) result += GoogleSpreadsheet(
                    id = id,
                    name = file.optString("name", "Google Tabelle"),
                    modifiedTime = file.optString("modifiedTime", ""),
                )
            }
            pageToken = response.optString("nextPageToken", "")
        } while (pageToken.isNotBlank() && result.size < 1_000)
        return result.distinctBy(GoogleSpreadsheet::id)
    }

    fun spreadsheet(spreadsheetIdOrUrl: String): GoogleSpreadsheet {
        val spreadsheetId = CloudContract.normalizeSpreadsheetId(spreadsheetIdOrUrl)
        require(spreadsheetId.isNotBlank()) { "Ungültige Google-Sheets-ID oder URL." }
        val response = JSONObject(jsonRequest(
            Api.SHEETS,
            "GET",
            "spreadsheets/${encodePath(spreadsheetId)}?fields=spreadsheetId,properties.title",
        ))
        return GoogleSpreadsheet(
            id = response.optString("spreadsheetId", spreadsheetId),
            name = response.optJSONObject("properties")?.optString("title").orEmpty().ifBlank { "Google Tabelle" },
        )
    }

    fun createSpreadsheet(name: String, templateBytes: ByteArray): GoogleSpreadsheet {
        require(templateBytes.isNotEmpty()) { "Die Google-Sheets-Vorlage ist leer." }
        val metadata = JSONObject()
            .put("name", name.trim().ifBlank { CloudContract.SHEET_TITLE })
            .put("mimeType", GOOGLE_SHEET_MIME)
            .put("appProperties", JSONObject().put(CloudContract.APP_PROPERTY_KEY, CloudContract.APP_PROPERTY_VALUE))
        val response = JSONObject(multipartUpload(
            method = "POST",
            path = "files?uploadType=multipart&fields=id,name,modifiedTime",
            metadata = metadata,
            mediaType = XLSX_MIME,
            media = templateBytes,
        ))
        val sheet = GoogleSpreadsheet(
            id = response.getString("id"),
            name = response.optString("name", name),
            modifiedTime = response.optString("modifiedTime", ""),
        )
        ensureTemplate(sheet.id)
        return sheet
    }

    fun ensureTemplate(spreadsheetId: String) {
        val current = sheetIds(spreadsheetId)
        val missing = CloudContract.BASE_SHEETS.filterNot(current::containsKey)
        if (missing.isNotEmpty()) {
            val requests = JSONArray().apply {
                missing.forEach { title ->
                    put(JSONObject().put(
                        "addSheet",
                        JSONObject().put("properties", JSONObject().put("title", title)),
                    ))
                }
            }
            jsonRequest(
                Api.SHEETS,
                "POST",
                "spreadsheets/${encodePath(spreadsheetId)}:batchUpdate",
                JSONObject().put("requests", requests),
            )
        }
        val headers = mapOf(
            CloudContract.MONSTER_SHEET to CloudContract.MONSTER_HEADERS,
            CloudContract.SPELL_SHEET to CloudContract.SPELL_HEADERS,
            CloudContract.TRAP_SHEET to CloudContract.TRAP_HEADERS,
        )
        batchWrite(spreadsheetId, headers.map { (title, values) ->
            SheetValues("${quotedTitle(title)}!A1", listOf(values))
        })
    }

    fun replaceVisibleWorkbook(spreadsheetId: String, workbook: Map<String, List<List<Any?>>>) {
        ensureTemplate(spreadsheetId)
        val desiredDecks = workbook.keys - CloudContract.BASE_SHEETS.toSet()
        var ids = sheetIds(spreadsheetId)
        val existingDecks = ids.keys - CloudContract.BASE_SHEETS.toSet()
        val requests = JSONArray()
        (existingDecks - desiredDecks).sorted().forEach { title ->
            ids[title]?.let { requests.put(JSONObject().put("deleteSheet", JSONObject().put("sheetId", it))) }
        }
        (desiredDecks - ids.keys).sorted().forEach { title ->
            val sourceId = ids[CloudContract.MONSTER_SHEET]
                ?: error("Vorlage besitzt keinen Monsterkarten-Reiter.")
            requests.put(JSONObject().put(
                "duplicateSheet",
                JSONObject().put("sourceSheetId", sourceId).put("newSheetName", title),
            ))
        }
        if (requests.length() > 0) {
            jsonRequest(
                Api.SHEETS,
                "POST",
                "spreadsheets/${encodePath(spreadsheetId)}:batchUpdate",
                JSONObject().put("requests", requests),
            )
            ids = sheetIds(spreadsheetId)
        }
        check(CloudContract.BASE_SHEETS.all(ids::containsKey)) {
            "Google-Tabelle entspricht nicht der Just-InCard-Vorlage."
        }

        val ranges = JSONArray().apply {
            put("${quotedTitle(CloudContract.MONSTER_SHEET)}!A2:F")
            put("${quotedTitle(CloudContract.SPELL_SHEET)}!A2:C")
            put("${quotedTitle(CloudContract.TRAP_SHEET)}!A2:C")
            desiredDecks.sorted().forEach { put("${quotedTitle(it)}!A2:F") }
        }
        jsonRequest(
            Api.SHEETS,
            "POST",
            "spreadsheets/${encodePath(spreadsheetId)}/values:batchClear",
            JSONObject().put("ranges", ranges),
        )

        batchWrite(spreadsheetId, workbook.mapNotNull { (title, rows) ->
            rows.drop(1).takeIf { it.isNotEmpty() }?.let {
                SheetValues("${quotedTitle(title)}!A2", it)
            }
        })
    }

    fun loadBackup(spreadsheetId: String): JSONObject? {
        val fileId = findBackupFile() ?: return null
        val payload = runCatching {
            JSONObject(String(
                rawRequest(Api.DRIVE, "GET", "files/${encodePath(fileId)}?alt=media"),
                StandardCharsets.UTF_8,
            ))
        }.getOrElse { throw GoogleSyncException("Google-Cloud-Backup konnte nicht gelesen werden.", it) }
        if (payload.optString("schema") != CloudContract.CLOUD_SCHEMA) {
            throw GoogleSyncException("Das Google-Cloud-Backup besitzt ein unbekanntes Format.")
        }
        val linked = CloudContract.normalizeSpreadsheetId(payload.optString("spreadsheet_id"))
        val requested = CloudContract.normalizeSpreadsheetId(spreadsheetId)
        return if (linked.isNotBlank() && requested.isNotBlank() && linked != requested) null else payload
    }

    fun linkedSpreadsheetId(): String = findBackupFile()?.let { fileId ->
        runCatching {
            JSONObject(String(
                rawRequest(Api.DRIVE, "GET", "files/${encodePath(fileId)}?alt=media"),
                StandardCharsets.UTF_8,
            )).optString("spreadsheet_id")
        }.getOrDefault("")
    }.orEmpty().let(CloudContract::normalizeSpreadsheetId)

    fun saveBackup(payload: JSONObject) {
        val data = payload.toString().toByteArray(StandardCharsets.UTF_8)
        val existing = findBackupFile()
        if (existing == null) {
            multipartUpload(
                method = "POST",
                path = "files?uploadType=multipart&fields=id",
                metadata = JSONObject()
                    .put("name", CloudContract.BACKUP_FILE_NAME)
                    .put("parents", JSONArray().put("appDataFolder"))
                    .put("mimeType", "application/json"),
                mediaType = "application/json; charset=utf-8",
                media = data,
            )
        } else {
            rawRequest(
                Api.DRIVE_UPLOAD,
                "PATCH",
                "files/${encodePath(existing)}?uploadType=media&fields=id",
                data,
                "application/json; charset=utf-8",
            )
        }
    }

    private fun sheetIds(spreadsheetId: String): Map<String, Int> {
        val result = JSONObject(jsonRequest(
            Api.SHEETS,
            "GET",
            "spreadsheets/${encodePath(spreadsheetId)}?fields=sheets.properties(sheetId,title)",
        ))
        val sheets = result.optJSONArray("sheets") ?: JSONArray()
        return buildMap {
            for (index in 0 until sheets.length()) {
                val properties = sheets.optJSONObject(index)?.optJSONObject("properties") ?: continue
                val title = properties.optString("title")
                if (title.isNotBlank()) put(title, properties.optInt("sheetId"))
            }
        }
    }

    private fun batchWrite(spreadsheetId: String, values: List<SheetValues>) {
        if (values.isEmpty()) return
        val data = JSONArray().apply {
            values.forEach { value ->
                put(JSONObject()
                    .put("range", value.range)
                    .put("majorDimension", "ROWS")
                    .put("values", value.rows.toJsonRows()))
            }
        }
        jsonRequest(
            Api.SHEETS,
            "POST",
            "spreadsheets/${encodePath(spreadsheetId)}/values:batchUpdate",
            JSONObject().put("valueInputOption", "RAW").put("data", data),
        )
    }

    private fun findBackupFile(): String? {
        val query = "name='${CloudContract.BACKUP_FILE_NAME}' and trashed=false"
        val response = JSONObject(jsonRequest(
            Api.DRIVE,
            "GET",
            "files?spaces=appDataFolder&q=${encode(query)}&pageSize=10" +
                "&orderBy=modifiedTime%20desc&fields=files(id,name,modifiedTime)",
        ))
        val files = response.optJSONArray("files") ?: return null
        return files.optJSONObject(0)?.optString("id")?.takeIf(String::isNotBlank)
    }

    private fun multipartUpload(
        method: String,
        path: String,
        metadata: JSONObject,
        mediaType: String,
        media: ByteArray,
    ): String {
        val boundary = "justincard-${System.nanoTime()}"
        val line = "\r\n"
        val output = ByteArrayOutputStream()
        output.write("--$boundary$line".toByteArray())
        output.write("Content-Type: application/json; charset=utf-8$line$line".toByteArray())
        output.write(metadata.toString().toByteArray(StandardCharsets.UTF_8))
        output.write(line.toByteArray())
        output.write("--$boundary$line".toByteArray())
        output.write("Content-Type: $mediaType$line$line".toByteArray())
        output.write(media)
        output.write(line.toByteArray())
        output.write("--$boundary--$line".toByteArray())
        return String(
            rawRequest(
                Api.DRIVE_UPLOAD,
                method,
                path,
                output.toByteArray(),
                "multipart/related; boundary=$boundary",
            ),
            StandardCharsets.UTF_8,
        )
    }

    private fun jsonRequest(api: Api, method: String, path: String, body: JSONObject? = null): String =
        String(
            rawRequest(
                api,
                method,
                path,
                body?.toString()?.toByteArray(StandardCharsets.UTF_8),
                body?.let { "application/json; charset=utf-8" },
            ),
            StandardCharsets.UTF_8,
        ).ifBlank { "{}" }

    private fun rawRequest(
        api: Api,
        method: String,
        path: String,
        body: ByteArray? = null,
        contentType: String? = null,
    ): ByteArray {
        val url = URI.create(api.base + path).toURL()
        val connection = (url.openConnection() as HttpURLConnection).apply {
            requestMethod = if (method == "PATCH") "POST" else method
            if (method == "PATCH") setRequestProperty("X-HTTP-Method-Override", "PATCH")
            connectTimeout = 15_000
            readTimeout = 60_000
            setRequestProperty("Authorization", "Bearer $accessToken")
            setRequestProperty("Accept", "application/json")
            if (body != null) {
                doOutput = true
                setFixedLengthStreamingMode(body.size)
                setRequestProperty("Content-Type", contentType ?: "application/octet-stream")
            }
        }
        try {
            body?.let { bytes -> connection.outputStream.use { it.write(bytes) } }
            val status = connection.responseCode
            val stream = if (status in 200..299) connection.inputStream else connection.errorStream
            val response = stream?.use { it.readBytes() } ?: byteArrayOf()
            if (status !in 200..299) {
                val message = runCatching {
                    JSONObject(String(response, StandardCharsets.UTF_8))
                        .optJSONObject("error")?.optString("message")
                }.getOrNull()
                throw GoogleSyncException(
                    message?.takeIf(String::isNotBlank) ?: "Google API meldet HTTP $status",
                )
            }
            return response
        } finally {
            connection.disconnect()
        }
    }

    private fun List<List<Any?>>.toJsonRows(): JSONArray = JSONArray().apply {
        this@toJsonRows.forEach { row ->
            put(JSONArray().apply { row.forEach { put(it ?: "") } })
        }
    }

    private fun quotedTitle(value: String): String = "'${value.replace("'", "''")}'"
    private fun encode(value: String): String = URLEncoder.encode(value, StandardCharsets.UTF_8.name())
    private fun encodePath(value: String): String = encode(value).replace("+", "%20")

    private data class SheetValues(val range: String, val rows: List<List<Any?>>)

    private enum class Api(val base: String) {
        DRIVE(BuildConfig.GOOGLE_DRIVE_API_BASE),
        DRIVE_UPLOAD(BuildConfig.GOOGLE_DRIVE_UPLOAD_BASE),
        SHEETS(BuildConfig.GOOGLE_SHEETS_API_BASE),
    }

    private companion object {
        const val GOOGLE_SHEET_MIME = "application/vnd.google-apps.spreadsheet"
        const val XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    }
}

class GoogleSyncException(message: String, cause: Throwable? = null) : IOException(message, cause)
