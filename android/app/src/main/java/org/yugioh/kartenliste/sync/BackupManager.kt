package org.yugioh.kartenliste.sync

import android.content.ContentResolver
import android.net.Uri
import org.json.JSONObject
import org.yugioh.kartenliste.data.model.CollectionItem
import org.yugioh.kartenliste.data.model.Deck
import java.io.BufferedInputStream
import java.io.BufferedOutputStream
import java.io.IOException
import java.util.zip.ZipEntry
import java.util.zip.ZipInputStream
import java.util.zip.ZipOutputStream

data class BackupPayload(
    val collection: List<CollectionItem>,
    val decks: List<Deck>,
    val createdAt: Long,
)

class BackupManager(private val resolver: ContentResolver) {
    fun export(uri: Uri, collection: List<CollectionItem>, decks: List<Deck>) {
        val output = resolver.openOutputStream(uri, "w") ?: throw IOException("Zieldatei kann nicht geöffnet werden.")
        ZipOutputStream(BufferedOutputStream(output)).use { zip ->
            zip.writeJson("manifest.json", JSONObject().apply {
                put("format", FORMAT)
                put("version", FORMAT_VERSION)
                put("createdAt", System.currentTimeMillis())
                put("collectionRows", collection.size)
                put("deckRows", decks.size)
            })
            zip.writeJson("collection.json", JSONObject().put("items", DataJsonCodec.collectionToJson(collection)))
            zip.writeJson("decks.json", JSONObject().put("decks", DataJsonCodec.decksToJson(decks)))
        }
    }

    fun import(uri: Uri): BackupPayload {
        val input = resolver.openInputStream(uri) ?: throw IOException("Backupdatei kann nicht geöffnet werden.")
        val entries = mutableMapOf<String, String>()
        ZipInputStream(BufferedInputStream(input)).use { zip ->
            var entry = zip.nextEntry
            while (entry != null) {
                if (!entry.isDirectory && entry.name in ALLOWED_ENTRIES) {
                    val bytes = zip.readBytesLimited(MAX_ENTRY_BYTES)
                    entries[entry.name] = bytes.decodeToString()
                }
                zip.closeEntry()
                entry = zip.nextEntry
            }
        }
        val manifest = entries["manifest.json"]?.let(::JSONObject)
            ?: throw IOException("Ungültiges Backup: manifest.json fehlt.")
        if (manifest.optString("format") != FORMAT || manifest.optInt("version") !in 1..FORMAT_VERSION) {
            throw IOException("Dieses Backupformat wird nicht unterstützt.")
        }
        val collectionJson = entries["collection.json"]?.let(::JSONObject)
            ?: throw IOException("Ungültiges Backup: collection.json fehlt.")
        val decksJson = entries["decks.json"]?.let(::JSONObject) ?: JSONObject().put("decks", org.json.JSONArray())
        return BackupPayload(
            collection = DataJsonCodec.collectionFromJson(collectionJson.getJSONArray("items")),
            decks = DataJsonCodec.decksFromJson(decksJson.getJSONArray("decks")),
            createdAt = manifest.optLong("createdAt", 0L),
        )
    }

    companion object {
        const val FILE_EXTENSION = "jicbackup"
        private const val FORMAT = "JustInCardBackup"
        private const val FORMAT_VERSION = 1
        private const val MAX_ENTRY_BYTES = 64 * 1024 * 1024
        private val ALLOWED_ENTRIES = setOf("manifest.json", "collection.json", "decks.json")
    }
}

private fun ZipOutputStream.writeJson(name: String, value: JSONObject) {
    putNextEntry(ZipEntry(name))
    write(value.toString(2).toByteArray(Charsets.UTF_8))
    closeEntry()
}

private fun ZipInputStream.readBytesLimited(limit: Int): ByteArray {
    val buffer = ByteArray(16 * 1024)
    val output = java.io.ByteArrayOutputStream()
    while (true) {
        val read = read(buffer)
        if (read < 0) break
        if (output.size() + read > limit) throw IOException("Backupeintrag ist unerwartet groß.")
        output.write(buffer, 0, read)
    }
    return output.toByteArray()
}
