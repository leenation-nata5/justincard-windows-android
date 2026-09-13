package org.yugioh.kartenliste.data.repository

import android.content.Context
import org.yugioh.kartenliste.data.local.AppPreferences
import org.yugioh.kartenliste.data.local.CollectionStore
import org.yugioh.kartenliste.data.local.DeckStore
import org.yugioh.kartenliste.data.local.DeviceStore
import org.yugioh.kartenliste.data.local.JustInCardDatabase
import org.yugioh.kartenliste.data.remote.YgoProDeckClient
import org.yugioh.kartenliste.sync.BackupManager
import org.yugioh.kartenliste.sync.GoogleSheetsSyncEngine

class AppContainer(context: Context) {
    val preferences = AppPreferences(context)
    val database = JustInCardDatabase(context)
    private val collectionStore = CollectionStore(database)
    private val deckStore = DeckStore(database, collectionStore)
    val deviceStore = DeviceStore(database)
    val cards = CardRepository(database, YgoProDeckClient(), preferences)
    val collection = CollectionRepository(collectionStore, preferences)
    val decks = DeckRepository(deckStore, preferences)
    val backups = BackupManager(context.contentResolver)
    val googleSheets = GoogleSheetsSyncEngine(context, preferences, cards, collection, decks)
}
