package org.yugioh.kartenliste.data.local

import android.content.ContentValues
import android.database.sqlite.SQLiteDatabase
import org.yugioh.kartenliste.data.model.SyncDevice

class DeviceStore(private val database: JustInCardDatabase) {
    fun list(currentDeviceId: String): List<SyncDevice> = database.databaseForRead().rawQuery(
        "SELECT * FROM sync_devices ORDER BY enabled DESC, name COLLATE NOCASE",
        null,
    ).use { cursor ->
        buildList {
            while (cursor.moveToNext()) {
                val id = cursor.getString(cursor.getColumnIndexOrThrow("id"))
                add(SyncDevice(
                    id = id,
                    name = cursor.getString(cursor.getColumnIndexOrThrow("name")),
                    enabled = cursor.getInt(cursor.getColumnIndexOrThrow("enabled")) != 0,
                    lastSeenAt = cursor.getLong(cursor.getColumnIndexOrThrow("last_seen_at")),
                    isCurrent = id == currentDeviceId,
                ))
            }
        }
    }

    fun upsert(device: SyncDevice) {
        database.databaseForWrite().insertWithOnConflict("sync_devices", null, ContentValues().apply {
            put("id", device.id)
            put("name", device.name)
            put("enabled", if (device.enabled) 1 else 0)
            put("last_seen_at", device.lastSeenAt)
        }, SQLiteDatabase.CONFLICT_REPLACE)
    }

    fun replaceAll(devices: List<SyncDevice>) {
        val db = database.databaseForWrite()
        db.beginTransaction()
        try {
            db.delete("sync_devices", null, null)
            devices.forEach(::upsert)
            db.setTransactionSuccessful()
        } finally {
            db.endTransaction()
        }
    }
}
