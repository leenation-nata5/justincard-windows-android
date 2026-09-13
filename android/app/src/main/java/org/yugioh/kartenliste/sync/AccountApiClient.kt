package org.yugioh.kartenliste.sync

import org.json.JSONObject
import org.yugioh.kartenliste.BuildConfig
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL

class AccountApiException(
    message: String,
    val status: Int? = null,
    val code: String = "",
) : IOException(message)

data class AccountLoginResult(
    val token: String,
    val label: String,
)

data class AccountSnapshotResult(
    val revision: Long,
    val payload: JSONObject,
)

class AccountApiClient(
    baseUrl: String = BuildConfig.JIC_ACCOUNT_API_BASE,
) {
    private val base = baseUrl.trim().trimEnd('/') + "/"

    fun login(identity: String, password: String, deviceName: String): AccountLoginResult {
        val data = request(
            path = "login.php",
            method = "POST",
            body = JSONObject()
                .put("identity", identity.trim())
                .put("password", password)
                .put("device_name", deviceName.trim()),
        )
        val token = data.optString("token")
        if (token.isBlank()) throw AccountApiException("Der Server hat kein Anmelde-Token zurückgegeben.")
        val user = data.optJSONObject("user") ?: JSONObject()
        val label = listOf(
            user.optString("display_name"),
            user.optString("username"),
            user.optString("email"),
        ).firstOrNull { it.isNotBlank() } ?: identity.trim()
        return AccountLoginResult(token, label)
    }

    fun logout(token: String) {
        if (token.isBlank()) return
        request("logout.php", "POST", token, JSONObject())
    }

    fun getSnapshot(token: String): AccountSnapshotResult {
        val data = request("sync.php", token = token)
        return AccountSnapshotResult(
            revision = data.optLong("revision", 0L),
            payload = data.optJSONObject("payload") ?: emptyPayload(),
        )
    }

    fun putSnapshot(token: String, payload: JSONObject, revision: Long, deviceName: String): Long {
        val data = request(
            path = "sync.php",
            method = "POST",
            token = token,
            body = JSONObject()
                .put("if_revision", revision)
                .put("source_device", deviceName)
                .put("schema", ACCOUNT_SCHEMA)
                .put("payload", payload),
        )
        return data.optLong("revision", revision + 1L)
    }

    private fun request(
        path: String,
        method: String = "GET",
        token: String = "",
        body: JSONObject? = null,
    ): JSONObject {
        val connection = (URL(base + path.trimStart('/')).openConnection() as HttpURLConnection).apply {
            requestMethod = method
            connectTimeout = 15_000
            readTimeout = 25_000
            useCaches = false
            setRequestProperty("Accept", "application/json")
            setRequestProperty("User-Agent", "JustInCard-Android/13.0.9")
            if (token.isNotBlank()) setRequestProperty("Authorization", "Bearer $token")
            if (body != null) {
                doOutput = true
                setRequestProperty("Content-Type", "application/json; charset=utf-8")
            }
        }
        try {
            if (body != null) {
                connection.outputStream.bufferedWriter(Charsets.UTF_8).use { it.write(body.toString()) }
            }
            val status = connection.responseCode
            val stream = if (status in 200..299) connection.inputStream else connection.errorStream
            val text = stream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() }.orEmpty()
            val data = runCatching { if (text.isBlank()) JSONObject() else JSONObject(text) }.getOrElse {
                throw AccountApiException("Der Just-InCard-Server hat keine gültige JSON-Antwort geliefert.", status)
            }
            if (status !in 200..299 || data.optBoolean("ok", true).not()) {
                val code = data.optString("error")
                val message = data.optString("message").ifBlank {
                    when (code) {
                        "invalid_credentials" -> "Benutzername/E-Mail oder Passwort ist nicht korrekt."
                        "invalid_token", "unauthorized" -> "Die Kontoanmeldung ist abgelaufen. Bitte erneut anmelden."
                        "revision_conflict" -> "Der Serverstand wurde zwischenzeitlich geändert."
                        else -> code.ifBlank { "Serverfehler HTTP $status" }
                    }
                }
                throw AccountApiException(message, status, code)
            }
            return data
        } finally {
            connection.disconnect()
        }
    }

    companion object {
        const val ACCOUNT_SCHEMA = "justincard-account-sync-v1"
        fun emptyPayload(): JSONObject = JSONObject()
            .put("schema", ACCOUNT_SCHEMA)
            .put("collection", org.json.JSONArray())
            .put("decks", org.json.JSONArray())
    }
}
