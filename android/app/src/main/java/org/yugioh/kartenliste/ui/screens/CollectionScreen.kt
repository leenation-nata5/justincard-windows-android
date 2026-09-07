package org.yugioh.kartenliste.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
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
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Inventory2
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
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
import org.yugioh.kartenliste.data.model.CardCondition
import org.yugioh.kartenliste.data.model.CollectionItem
import org.yugioh.kartenliste.data.model.CollectionSummary
import org.yugioh.kartenliste.ui.CollectionViewModel
import org.yugioh.kartenliste.ui.components.CardThumbnail
import org.yugioh.kartenliste.ui.components.ChoiceField
import org.yugioh.kartenliste.ui.components.EmptyState
import org.yugioh.kartenliste.ui.components.QuantityStepper
import java.util.Locale

@Composable
fun CollectionScreen(
    viewModel: CollectionViewModel,
    modifier: Modifier = Modifier,
) {
    val items by viewModel.items.collectAsState()
    val summary by viewModel.summary.collectAsState()
    val query by viewModel.query.collectAsState()
    val selected by viewModel.selected.collectAsState()
    val filtered = remember(items, query) { viewModel.filtered(items) }

    Column(modifier.fillMaxSize()) {
        CollectionSummaryRow(summary)
        OutlinedTextField(
            value = query,
            onValueChange = viewModel::setQuery,
            label = { Text("Sammlung durchsuchen") },
            leadingIcon = { Icon(Icons.Default.Search, contentDescription = null) },
            singleLine = true,
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 12.dp, vertical = 8.dp),
        )
        Box(modifier = Modifier.fillMaxSize()) {
            if (filtered.isEmpty()) {
                EmptyState(
                    title = if (items.isEmpty()) "Deine Sammlung ist leer" else "Kein passender Druck",
                    text = if (items.isEmpty()) {
                        "Füge Karten über die Suche oder den Live-Scanner hinzu. Jeder Druck wird mit Set und Seltenheit gespeichert."
                    } else {
                        "Suche nach Kartenname, Set-Code, Set-Name oder Seltenheit."
                    },
                    modifier = Modifier.align(Alignment.Center),
                )
            } else {
                androidx.compose.foundation.layout.BoxWithConstraints(Modifier.fillMaxSize()) {
                    if (maxWidth >= 720.dp) {
                        LazyVerticalGrid(
                            columns = GridCells.Adaptive(330.dp),
                            contentPadding = PaddingValues(12.dp),
                            horizontalArrangement = Arrangement.spacedBy(10.dp),
                            verticalArrangement = Arrangement.spacedBy(10.dp),
                        ) {
                            items(filtered, key = CollectionItem::id) { item ->
                                CollectionCard(item) { viewModel.select(item) }
                            }
                        }
                    } else {
                        LazyColumn(
                            contentPadding = PaddingValues(12.dp),
                            verticalArrangement = Arrangement.spacedBy(10.dp),
                        ) {
                            items(filtered, key = CollectionItem::id) { item ->
                                CollectionCard(item) { viewModel.select(item) }
                            }
                        }
                    }
                }
            }
        }
    }

    selected?.let { item ->
        CollectionDetailDialog(
            item = item,
            onQuantity = { viewModel.changeQuantity(item, it) },
            onSave = { condition, notes -> viewModel.saveDetails(item, condition, notes) },
            onDismiss = { viewModel.select(null) },
        )
    }
}

@Composable
private fun CollectionSummaryRow(summary: CollectionSummary) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 8.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        SummaryCard("Karten", summary.totalCards.toString(), Modifier.weight(1f))
        SummaryCard("Drucke", summary.uniquePrints.toString(), Modifier.weight(1f))
        SummaryCard("Schätzwert", "$${String.format(Locale.US, "%.2f", summary.estimatedValueUsd)}", Modifier.weight(1f))
    }
}

@Composable
private fun SummaryCard(label: String, value: String, modifier: Modifier = Modifier) {
    Card(
        modifier = modifier,
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer),
    ) {
        Column(Modifier.padding(horizontal = 10.dp, vertical = 9.dp)) {
            Text(label, style = MaterialTheme.typography.labelSmall)
            Text(value, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold, maxLines = 1)
        }
    }
}

@Composable
private fun CollectionCard(item: CollectionItem, onClick: () -> Unit) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.55f)),
    ) {
        Row(Modifier.padding(10.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            CardThumbnail(
                url = item.imageUrl,
                contentDescription = item.cardName,
                modifier = Modifier
                    .width(88.dp)
                    .height(128.dp),
            )
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(
                    item.cardName,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    item.selectedPrint.setCode,
                    style = MaterialTheme.typography.titleSmall,
                    color = MaterialTheme.colorScheme.primary,
                    fontWeight = FontWeight.Bold,
                )
                Text(
                    item.selectedPrint.setName,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                    style = MaterialTheme.typography.bodySmall,
                )
                Text("${item.selectedPrint.rarity} · ${item.language.uppercase()}", style = MaterialTheme.typography.labelMedium)
                Spacer(Modifier.weight(1f))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(item.condition.label, style = MaterialTheme.typography.bodySmall, modifier = Modifier.weight(1f))
                    Text("× ${item.quantity}", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                }
            }
        }
    }
}

@Composable
private fun CollectionDetailDialog(
    item: CollectionItem,
    onQuantity: (Int) -> Unit,
    onSave: (CardCondition, String) -> Unit,
    onDismiss: () -> Unit,
) {
    var condition by remember(item.id, item.condition) { mutableStateOf(item.condition) }
    var notes by remember(item.id, item.notes) { mutableStateOf(item.notes) }
    AlertDialog(
        onDismissRequest = onDismiss,
        icon = { Icon(Icons.Default.Inventory2, contentDescription = null) },
        title = { Text(item.cardName, maxLines = 2, overflow = TextOverflow.Ellipsis) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    CardThumbnail(
                        item.imageUrl,
                        item.cardName,
                        modifier = Modifier
                            .width(88.dp)
                            .height(128.dp),
                    )
                    Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                        Text(item.selectedPrint.setCode, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.primary)
                        Text(item.selectedPrint.setName, style = MaterialTheme.typography.bodySmall)
                        Text(item.selectedPrint.rarity, style = MaterialTheme.typography.bodySmall)
                    }
                }
                QuantityStepper(
                    quantity = item.quantity,
                    onDecrease = { onQuantity(-1) },
                    onIncrease = { onQuantity(1) },
                    modifier = Modifier.align(Alignment.CenterHorizontally),
                )
                ChoiceField(
                    label = "Zustand",
                    value = condition.name,
                    choices = CardCondition.entries.map { it.name to it.label },
                    onSelected = { condition = CardCondition.valueOf(it) },
                )
                OutlinedTextField(
                    value = notes,
                    onValueChange = { notes = it },
                    label = { Text("Notizen") },
                    minLines = 2,
                    maxLines = 4,
                    modifier = Modifier.fillMaxWidth(),
                )
                Text(
                    "Menge 0 entfernt diesen Druck aus der sichtbaren Sammlung. Backups und Sync behalten eine Löschmarkierung.",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        },
        confirmButton = { TextButton(onClick = { onSave(condition, notes) }) { Text("Speichern") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Schließen") } },
    )
}
