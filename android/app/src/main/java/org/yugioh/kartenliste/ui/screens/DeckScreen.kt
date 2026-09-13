package org.yugioh.kartenliste.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import org.yugioh.kartenliste.data.model.CollectionItem
import org.yugioh.kartenliste.data.model.Deck
import org.yugioh.kartenliste.data.model.DeckCard
import org.yugioh.kartenliste.data.model.DeckSection
import org.yugioh.kartenliste.ui.DeckSort
import org.yugioh.kartenliste.ui.DeckViewModel
import org.yugioh.kartenliste.ui.components.CardThumbnail
import org.yugioh.kartenliste.ui.components.ChoiceField
import org.yugioh.kartenliste.ui.components.EmptyState
import org.yugioh.kartenliste.ui.components.QuantityStepper
import org.yugioh.kartenliste.ui.components.StatPill
import org.yugioh.kartenliste.util.TextNormalizer

@Composable
fun DeckScreen(
    viewModel: DeckViewModel,
    modifier: Modifier = Modifier,
) {
    val decks by viewModel.decks.collectAsState()
    val collection by viewModel.collection.collectAsState()
    val selectedId by viewModel.selectedDeckId.collectAsState()
    val sort by viewModel.sort.collectAsState()
    val ascending by viewModel.ascending.collectAsState()
    val selected = remember(decks, selectedId) { viewModel.selected(decks) }
    var createDialog by remember { mutableStateOf(false) }
    var editDialog by remember { mutableStateOf(false) }
    var addDialog by remember { mutableStateOf(false) }

    Column(modifier.fillMaxSize()) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 12.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            LazyRow(
                modifier = Modifier.weight(1f),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                items(decks, key = Deck::id) { deck ->
                    AssistChip(
                        onClick = { viewModel.select(deck.id) },
                        label = {
                            Text(
                                if (selected?.id == deck.id) "● ${deck.name}" else deck.name,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                            )
                        },
                    )
                }
            }
            IconButton(onClick = { createDialog = true }) {
                Icon(Icons.Default.Add, contentDescription = "Deck erstellen")
            }
        }
        if (selected == null) {
            EmptyState(
                title = "Noch kein Deck",
                text = "Lege ein Deck an und füge Drucke aus deiner Sammlung zu Main, Extra oder Side Deck hinzu.",
                modifier = Modifier.weight(1f),
            )
            Button(
                onClick = { createDialog = true },
                modifier = Modifier
                    .align(Alignment.CenterHorizontally)
                    .padding(20.dp),
            ) {
                Icon(Icons.Default.Add, contentDescription = null)
                Spacer(Modifier.width(8.dp))
                Text("Erstes Deck erstellen")
            }
        } else {
            DeckContent(
                deck = selected,
                onEdit = { editDialog = true },
                onAdd = { addDialog = true },
                onQuantity = viewModel::changeQuantity,
                sort = sort,
                ascending = ascending,
                onSort = viewModel::setSort,
                onAscending = viewModel::setAscending,
                sortCards = viewModel::sorted,
                modifier = Modifier.weight(1f),
            )
        }
    }

    if (createDialog) {
        DeckNameDialog(
            title = "Deck erstellen",
            initialName = "",
            initialNotes = "",
            onSave = { name, _ ->
                viewModel.create(name)
                createDialog = false
            },
            onDismiss = { createDialog = false },
        )
    }
    if (editDialog && selected != null) {
        DeckNameDialog(
            title = "Deck bearbeiten",
            initialName = selected.name,
            initialNotes = selected.notes,
            onSave = { name, notes ->
                viewModel.rename(selected, name, notes)
                editDialog = false
            },
            onDelete = {
                viewModel.delete(selected)
                editDialog = false
            },
            onDismiss = { editDialog = false },
        )
    }
    if (addDialog && selected != null) {
        AddCollectionCardDialog(
            collection = collection,
            onAdd = { item, section ->
                viewModel.add(selected, item, section)
                addDialog = false
            },
            onDismiss = { addDialog = false },
        )
    }
}

@Composable
private fun DeckContent(
    deck: Deck,
    onEdit: () -> Unit,
    onAdd: () -> Unit,
    onQuantity: (DeckCard, Int) -> Unit,
    sort: DeckSort,
    ascending: Boolean,
    onSort: (DeckSort) -> Unit,
    onAscending: (Boolean) -> Unit,
    sortCards: (List<DeckCard>) -> List<DeckCard>,
    modifier: Modifier = Modifier,
) {
    Column(modifier) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 14.dp, vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1f)) {
                Text(deck.name, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                if (deck.notes.isNotBlank()) Text(deck.notes, style = MaterialTheme.typography.bodySmall)
            }
            IconButton(onClick = onEdit) { Icon(Icons.Default.Edit, contentDescription = "Deck bearbeiten") }
            FilledTonalButton(onClick = onAdd) {
                Icon(Icons.Default.Add, contentDescription = null)
                Spacer(Modifier.width(6.dp))
                Text("Karte")
            }
        }
        Row(
            modifier = Modifier.padding(horizontal = 14.dp, vertical = 6.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            StatPill("Main", deck.mainCount.toString())
            StatPill("Extra", deck.extraCount.toString())
            StatPill("Side", deck.sideCount.toString())
        }
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 14.dp, vertical = 4.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            ChoiceField(
                label = "Deck sortieren",
                value = sort.name,
                choices = DeckSort.entries.map { it.name to it.label },
                onSelected = { onSort(DeckSort.valueOf(it)) },
                modifier = Modifier.weight(1f),
            )
            ChoiceField(
                label = "Richtung",
                value = if (ascending) "asc" else "desc",
                choices = listOf("asc" to "Aufsteigend", "desc" to "Absteigend"),
                onSelected = { onAscending(it == "asc") },
                modifier = Modifier.weight(1f),
            )
        }
        Card(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 14.dp, vertical = 6.dp),
            colors = CardDefaults.cardColors(
                containerColor = if (deck.validation.isValid) {
                    MaterialTheme.colorScheme.primaryContainer
                } else {
                    MaterialTheme.colorScheme.errorContainer
                },
            ),
        ) {
            Text(
                if (deck.validation.isValid) "Deckgröße ist gültig."
                else deck.validation.problems.joinToString("\n"),
                modifier = Modifier.padding(10.dp),
                style = MaterialTheme.typography.bodySmall,
            )
        }
        LazyColumn(
            contentPadding = PaddingValues(12.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
            modifier = Modifier.fillMaxSize(),
        ) {
            DeckSection.entries.forEach { section ->
                val cards = sortCards(deck.cards.filter { !it.deleted && it.section == section })
                item(key = "header-${section.name}") {
                    Text(
                        "${section.label} · ${cards.sumOf { it.quantity }}",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        modifier = Modifier.padding(top = 6.dp, bottom = 2.dp),
                    )
                }
                if (cards.isEmpty()) {
                    item(key = "empty-${section.name}") {
                        Text("Noch keine Karten", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                } else {
                    items(cards, key = DeckCard::id) { card ->
                        DeckCardRow(card) { value -> onQuantity(card, value) }
                    }
                }
            }
        }
    }
}

@Composable
private fun DeckCardRow(card: DeckCard, onQuantity: (Int) -> Unit) {
    Card(
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.55f)),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Row(
            modifier = Modifier.padding(8.dp),
            horizontalArrangement = Arrangement.spacedBy(10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            CardThumbnail(
                card.imageUrl,
                card.cardName,
                modifier = Modifier
                    .width(58.dp)
                    .height(84.dp),
            )
            Column(Modifier.weight(1f)) {
                Text(card.cardName, fontWeight = FontWeight.SemiBold, maxLines = 2, overflow = TextOverflow.Ellipsis)
                if (card.setCode.isNotBlank()) Text(card.setCode, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary)
            }
            QuantityStepper(
                quantity = card.quantity,
                onDecrease = { onQuantity(card.quantity - 1) },
                onIncrease = { onQuantity(card.quantity + 1) },
            )
        }
    }
}

@Composable
private fun DeckNameDialog(
    title: String,
    initialName: String,
    initialNotes: String,
    onSave: (String, String) -> Unit,
    onDismiss: () -> Unit,
    onDelete: (() -> Unit)? = null,
) {
    var name by remember(initialName) { mutableStateOf(initialName) }
    var notes by remember(initialNotes) { mutableStateOf(initialNotes) }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                OutlinedTextField(name, { name = it }, label = { Text("Deckname") }, singleLine = true)
                OutlinedTextField(notes, { notes = it }, label = { Text("Notizen") }, minLines = 2, maxLines = 4)
                onDelete?.let {
                    TextButton(onClick = it) {
                        Icon(Icons.Default.Delete, contentDescription = null)
                        Spacer(Modifier.width(5.dp))
                        Text("Deck löschen", color = MaterialTheme.colorScheme.error)
                    }
                }
            }
        },
        confirmButton = {
            TextButton(onClick = { onSave(name.trim(), notes.trim()) }, enabled = name.isNotBlank()) { Text("Speichern") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Abbrechen") } },
    )
}

@Composable
private fun AddCollectionCardDialog(
    collection: List<CollectionItem>,
    onAdd: (CollectionItem, DeckSection) -> Unit,
    onDismiss: () -> Unit,
) {
    var query by remember { mutableStateOf("") }
    var section by remember { mutableStateOf(DeckSection.MAIN) }
    var preview by remember { mutableStateOf<CollectionItem?>(null) }
    var sort by remember { mutableStateOf("name") }
    var ascending by remember { mutableStateOf(true) }
    val key = TextNormalizer.searchKey(query)
    val compact = TextNormalizer.compactKey(query)
    val filtered = remember(collection, key, sort, ascending) {
        val base = if (key.isBlank()) collection else collection.filter {
            TextNormalizer.searchKey(it.cardName).contains(key) ||
                TextNormalizer.compactKey(it.selectedPrint.setCode).contains(compact)
        }
        val comparator = when (sort) {
            "set" -> compareBy<CollectionItem, String>(String.CASE_INSENSITIVE_ORDER) { it.selectedPrint.setCode }
            "quantity" -> compareBy<CollectionItem> { it.quantity }
            else -> compareBy<CollectionItem, String>(String.CASE_INSENSITIVE_ORDER) { it.cardName }
        }
        if (ascending) base.sortedWith(comparator) else base.sortedWith(comparator.reversed())
    }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Aus Sammlung hinzufügen") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                    ChoiceField(
                        label = "Bereich",
                        value = section.name,
                        choices = DeckSection.entries.map { it.name to it.label },
                        onSelected = { section = DeckSection.valueOf(it) },
                        modifier = Modifier.weight(1f),
                    )
                    ChoiceField(
                        label = "Sortierung",
                        value = sort,
                        choices = listOf("name" to "Name", "set" to "Set-Code", "quantity" to "Menge"),
                        onSelected = { sort = it },
                        modifier = Modifier.weight(1f),
                    )
                }
                ChoiceField(
                    label = "Richtung",
                    value = if (ascending) "asc" else "desc",
                    choices = listOf("asc" to "Aufsteigend", "desc" to "Absteigend"),
                    onSelected = { ascending = it == "asc" },
                )
                OutlinedTextField(
                    value = query,
                    onValueChange = { query = it },
                    label = { Text("Karte oder Set-Code") },
                    leadingIcon = { Icon(Icons.Default.Search, contentDescription = null) },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                preview?.let { item ->
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.45f)),
                    ) {
                        Row(
                            modifier = Modifier.padding(8.dp),
                            horizontalArrangement = Arrangement.spacedBy(10.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            CardThumbnail(
                                item.imageUrl,
                                item.cardName,
                                Modifier.width(86.dp).height(124.dp),
                            )
                            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                Text(item.cardName, fontWeight = FontWeight.Bold, maxLines = 2, overflow = TextOverflow.Ellipsis)
                                Text(item.selectedPrint.setCode, color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.SemiBold)
                                Text(item.selectedPrint.setName, style = MaterialTheme.typography.bodySmall, maxLines = 2, overflow = TextOverflow.Ellipsis)
                                Text("${item.selectedPrint.rarity} · verfügbar ×${item.quantity}", style = MaterialTheme.typography.bodySmall)
                                Button(onClick = { onAdd(item, section) }) {
                                    Icon(Icons.Default.Add, contentDescription = null)
                                    Spacer(Modifier.width(5.dp))
                                    Text("Hinzufügen")
                                }
                            }
                        }
                    }
                }
                LazyColumn(
                    modifier = Modifier.height(if (preview == null) 360.dp else 220.dp),
                    verticalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    items(filtered, key = CollectionItem::id) { item ->
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clickable { preview = item }
                                .padding(vertical = 5.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            CardThumbnail(
                                item.imageUrl,
                                item.cardName,
                                Modifier.width(42.dp).height(61.dp),
                            )
                            Spacer(Modifier.width(10.dp))
                            Column(Modifier.weight(1f)) {
                                Text(item.cardName, maxLines = 1, overflow = TextOverflow.Ellipsis)
                                Text("${item.selectedPrint.setCode} · verfügbar ×${item.quantity}", style = MaterialTheme.typography.bodySmall)
                            }
                            IconButton(onClick = { onAdd(item, section) }) {
                                Icon(Icons.Default.Add, contentDescription = "Hinzufügen", tint = MaterialTheme.colorScheme.primary)
                            }
                        }
                    }
                }
            }
        },
        confirmButton = {
            TextButton(onClick = { preview?.let { onAdd(it, section) } }, enabled = preview != null) { Text("Hinzufügen") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Fertig") } },
    )
}
