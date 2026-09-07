package org.yugioh.kartenliste.ui

import android.content.ContentResolver
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import org.yugioh.kartenliste.data.repository.AppContainer

class AppViewModelFactory(
    private val container: AppContainer,
    private val contentResolver: ContentResolver,
) : ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T = when {
        modelClass.isAssignableFrom(SearchViewModel::class.java) ->
            SearchViewModel(container.cards, container.collection) as T
        modelClass.isAssignableFrom(CollectionViewModel::class.java) ->
            CollectionViewModel(container.collection) as T
        modelClass.isAssignableFrom(DeckViewModel::class.java) ->
            DeckViewModel(container.decks, container.collection) as T
        modelClass.isAssignableFrom(ScanViewModel::class.java) ->
            ScanViewModel(container.cards, container.collection) as T
        modelClass.isAssignableFrom(SettingsViewModel::class.java) ->
            SettingsViewModel(
                container.preferences,
                container.cards,
                container.collection,
                container.decks,
                container.backups,
                container.googleSheets,
                contentResolver,
            ) as T
        else -> error("Unbekanntes ViewModel: ${modelClass.name}")
    }
}
