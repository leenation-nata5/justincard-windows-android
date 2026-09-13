package org.yugioh.kartenliste.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.ArrowForward
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Clear
import androidx.compose.material.icons.filled.FilterAlt
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.foundation.text.KeyboardOptions
import org.yugioh.kartenliste.data.model.Card
import org.yugioh.kartenliste.data.model.CardLanguages
import org.yugioh.kartenliste.data.model.CardPrint
import org.yugioh.kartenliste.data.model.SearchFilters
import org.yugioh.kartenliste.data.model.SearchSort
import org.yugioh.kartenliste.data.repository.CatalogStatus
import org.yugioh.kartenliste.ui.SearchUiState
import org.yugioh.kartenliste.ui.SearchViewModel
import org.yugioh.kartenliste.ui.components.CardThumbnail
import org.yugioh.kartenliste.ui.components.ChoiceField
import org.yugioh.kartenliste.ui.components.EmptyState
import org.yugioh.kartenliste.ui.components.StatPill

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SearchScreen(
    viewModel: SearchViewModel,
    modifier: Modifier = Modifier,
) {
    val state by viewModel.state.collectAsState()
    val catalogStatus by viewModel.catalogStatus.collectAsState()
    var showFilters by remember { mutableStateOf(false) }

    Column(modifier.fillMaxSize()) {
        SearchHeader(
            state = state,
            onFilters = viewModel::setFilters,
            onSearch = viewModel::searchDebounced,
            onOpenFilters = { showFilters = true },
            onClear = viewModel::clearFilters,
        )
        when (val status = catalogStatus) {
            is CatalogStatus.Syncing -> {
                status.progress?.let {
                    LinearProgressIndicator(progress = { it }, modifier = Modifier.fillMaxWidth())
                } ?: LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                Text(
                    status.message,
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp),
                    style = MaterialTheme.typography.labelMedium,
                )
            }
            is CatalogStatus.Error -> Text(
                status.message,
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp),
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.labelMedium,
            )
            CatalogStatus.Ready -> Unit
        }
        SearchResults(
            state = state,
            onCard = viewModel::select,
            onPrevious = viewModel::previousPage,
            onNext = viewModel::nextPage,
            modifier = Modifier.weight(1f),
        )
    }

    if (showFilters) {
        FilterSheet(
            filters = state.filters,
            onChange = viewModel::setFilters,
            onApply = {
                showFilters = false
                viewModel.search()
            },
            onDismiss = { showFilters = false },
        )
    }
    state.selectedCard?.let { card ->
        CardDetailSheet(
            card = card,
            selectedPrint = state.selectedPrint,
            onSelectPrint = viewModel::selectPrint,
            onAdd = viewModel::addSelected,
            onDismiss = { viewModel.select(null) },
        )
    }
}

@Composable
private fun SearchHeader(
    state: SearchUiState,
    onFilters: (SearchFilters) -> Unit,
    onSearch: () -> Unit,
    onOpenFilters: () -> Unit,
    onClear: () -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        OutlinedTextField(
            value = state.filters.name,
            onValueChange = {
                onFilters(state.filters.copy(name = it))
                onSearch()
            },
            label = { Text("Kartenname") },
            leadingIcon = { Icon(Icons.Default.Search, contentDescription = null) },
            trailingIcon = if (state.filters.name.isNotBlank()) ({
                IconButton(onClick = {
                    onFilters(state.filters.copy(name = ""))
                    onSearch()
                }) { Icon(Icons.Default.Clear, contentDescription = "Name löschen") }
            }) else null,
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
            OutlinedTextField(
                value = state.filters.setQuery,
                onValueChange = {
                    onFilters(state.filters.copy(setQuery = it))
                    onSearch()
                },
                label = { Text("Set / Set-Code") },
                singleLine = true,
                modifier = Modifier.weight(1f),
            )
            OutlinedTextField(
                value = state.filters.passcode,
                onValueChange = {
                    onFilters(state.filters.copy(passcode = it.filter(Char::isDigit).take(8)))
                    onSearch()
                },
                label = { Text("Passcode") },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                singleLine = true,
                modifier = Modifier.weight(1f),
            )
        }
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            OutlinedButton(onClick = onOpenFilters, modifier = Modifier.weight(1f)) {
                Icon(Icons.Default.FilterAlt, contentDescription = null)
                Spacer(Modifier.width(6.dp))
                Text("Alle Filter")
            }
            TextButton(onClick = onClear) { Text("Zurücksetzen") }
        }
    }
}

@Composable
private fun SearchResults(
    state: SearchUiState,
    onCard: (Card) -> Unit,
    onPrevious: () -> Unit,
    onNext: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(modifier) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                "${state.page.total} Treffer",
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.weight(1f),
            )
            if (state.page.total > state.page.pageSize) {
                IconButton(onClick = onPrevious, enabled = state.page.page > 0) {
                    Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Vorherige Seite")
                }
                Text("${state.page.page + 1}", style = MaterialTheme.typography.labelLarge)
                IconButton(onClick = onNext, enabled = state.page.hasNext) {
                    Icon(Icons.AutoMirrored.Filled.ArrowForward, contentDescription = "Nächste Seite")
                }
            }
        }
        Box(modifier = Modifier.fillMaxSize()) {
            if (state.page.cards.isEmpty() && !state.loading) {
                EmptyState(
                    title = "Keine Karten gefunden",
                    text = "Filter anpassen oder den lokalen Kartenindex in den Einstellungen aktualisieren.",
                    modifier = Modifier.align(Alignment.Center),
                )
            } else {
                androidx.compose.foundation.layout.BoxWithConstraints(Modifier.fillMaxSize()) {
                    if (maxWidth >= 680.dp) {
                        LazyVerticalGrid(
                            columns = GridCells.Adaptive(310.dp),
                            contentPadding = PaddingValues(12.dp),
                            horizontalArrangement = Arrangement.spacedBy(10.dp),
                            verticalArrangement = Arrangement.spacedBy(10.dp),
                        ) {
                            items(state.page.cards, key = { it.key.stableKey }) { card ->
                                SearchCard(card, state.filters.setQuery) { onCard(card) }
                            }
                        }
                    } else {
                        LazyColumn(
                            contentPadding = PaddingValues(12.dp),
                            verticalArrangement = Arrangement.spacedBy(10.dp),
                        ) {
                            items(state.page.cards, key = { it.key.stableKey }) { card ->
                                SearchCard(card, state.filters.setQuery) { onCard(card) }
                            }
                        }
                    }
                }
            }
            if (state.loading) CircularProgressIndicator(Modifier.align(Alignment.Center))
        }
    }
}

@Composable
private fun SearchCard(card: Card, setQuery: String, onClick: () -> Unit) {
    val matchingPrint = remember(card.prints, setQuery) {
        val compactQuery = setQuery.filter(Char::isLetterOrDigit)
        card.prints.firstOrNull { print ->
            compactQuery.isNotBlank() && print.setCode.filter(Char::isLetterOrDigit).equals(compactQuery, true)
        } ?: card.prints.firstOrNull { print ->
            setQuery.isNotBlank() && (print.setCode.contains(setQuery, true) || print.setName.contains(setQuery, true))
        } ?: card.prints.firstOrNull()
    }
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.55f)),
    ) {
        Row(Modifier.padding(10.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            CardThumbnail(
                url = card.thumbnailUrl.ifBlank { card.imageUrl },
                contentDescription = card.name,
                modifier = Modifier
                    .width(92.dp)
                    .height(134.dp),
            )
            Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                Text(
                    card.name,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(card.type, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    card.atk?.let { StatPill("ATK", it.toString()) }
                    card.def?.let { StatPill("DEF", it.toString()) }
                    card.displayLevel?.let { StatPill("LV", it.toString()) }
                }
                matchingPrint?.let {
                    Spacer(Modifier.weight(1f))
                    Text(it.setCode, style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
                    Text(
                        "${it.setName} · ${it.rarity}",
                        style = MaterialTheme.typography.bodySmall,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun FilterSheet(
    filters: SearchFilters,
    onChange: (SearchFilters) -> Unit,
    onApply: () -> Unit,
    onDismiss: () -> Unit,
) {
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState,
        sheetGesturesEnabled = false,
        dragHandle = null,
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .fillMaxHeight(0.92f)
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 18.dp, vertical = 8.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text("Kombinierbare Filter", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
            Text(
                "Kartentext-Sprache: ${CardLanguages.label(filters.language)} · appweit in Einstellungen",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            ChoiceField("Sortierung", filters.sort.name, SearchSort.entries.map { it.name to it.label }, {
                onChange(filters.copy(sort = SearchSort.valueOf(it)))
            })
            FreeFilter("Effekt- / Beschreibungstext", filters.effectText) { onChange(filters.copy(effectText = it)) }
            FreeFilter("Kartentyp", filters.cardType) { onChange(filters.copy(cardType = it)) }
            FreeFilter("Frame-Typ", filters.frameType) { onChange(filters.copy(frameType = it)) }
            FreeFilter("Monster-Typ / Zauber-Typ", filters.race) { onChange(filters.copy(race = it)) }
            FreeFilter("Attribut", filters.attribute) { onChange(filters.copy(attribute = it)) }
            FreeFilter("Archetyp", filters.archetype) { onChange(filters.copy(archetype = it)) }
            FreeFilter("Seltenheit", filters.rarity) { onChange(filters.copy(rarity = it)) }
            NumberRange("ATK", filters.atkMin, filters.atkMax) { min, max -> onChange(filters.copy(atkMin = min, atkMax = max)) }
            NumberRange("DEF", filters.defMin, filters.defMax) { min, max -> onChange(filters.copy(defMin = min, defMax = max)) }
            NumberRange("Stufe / Rang / Link", filters.levelMin, filters.levelMax) { min, max ->
                onChange(filters.copy(levelMin = min, levelMax = max))
            }
            NumberRange("Pendel-Skala", filters.scaleMin, filters.scaleMax) { min, max ->
                onChange(filters.copy(scaleMin = min, scaleMax = max))
            }
            DecimalRange("Marktpreis (USD)", filters.priceMin, filters.priceMax) { min, max ->
                onChange(filters.copy(priceMin = min, priceMax = max))
            }
            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
                Column(Modifier.weight(1f)) {
                    Text("Nur Karten aus meiner Sammlung", fontWeight = FontWeight.SemiBold)
                    Text("Lässt sich mit allen Filtern kombinieren.", style = MaterialTheme.typography.bodySmall)
                }
                Switch(checked = filters.ownedOnly, onCheckedChange = { onChange(filters.copy(ownedOnly = it)) })
            }
            Button(onClick = onApply, modifier = Modifier.fillMaxWidth()) {
                Icon(Icons.Default.Search, contentDescription = null)
                Spacer(Modifier.width(8.dp))
                Text("Filter anwenden")
            }
            Spacer(Modifier.height(20.dp))
        }
    }
}

@Composable
private fun FreeFilter(label: String, value: String, onValue: (String) -> Unit) {
    OutlinedTextField(
        value = value,
        onValueChange = onValue,
        label = { Text(label) },
        singleLine = true,
        modifier = Modifier.fillMaxWidth(),
    )
}

@Composable
private fun NumberRange(label: String, min: Int?, max: Int?, onChange: (Int?, Int?) -> Unit) {
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
        OutlinedTextField(
            value = min?.toString().orEmpty(),
            onValueChange = { onChange(it.toIntOrNull(), max) },
            label = { Text("$label min.") },
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
            singleLine = true,
            modifier = Modifier.weight(1f),
        )
        OutlinedTextField(
            value = max?.toString().orEmpty(),
            onValueChange = { onChange(min, it.toIntOrNull()) },
            label = { Text("$label max.") },
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
            singleLine = true,
            modifier = Modifier.weight(1f),
        )
    }
}

@Composable
private fun DecimalRange(label: String, min: Double?, max: Double?, onChange: (Double?, Double?) -> Unit) {
    var minText by remember { mutableStateOf(min?.toString().orEmpty()) }
    var maxText by remember { mutableStateOf(max?.toString().orEmpty()) }
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
        OutlinedTextField(
            value = minText,
            onValueChange = {
                minText = it
                onChange(it.replace(',', '.').toDoubleOrNull(), maxText.replace(',', '.').toDoubleOrNull())
            },
            label = { Text("$label min.") },
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
            singleLine = true,
            modifier = Modifier.weight(1f),
        )
        OutlinedTextField(
            value = maxText,
            onValueChange = {
                maxText = it
                onChange(minText.replace(',', '.').toDoubleOrNull(), it.replace(',', '.').toDoubleOrNull())
            },
            label = { Text("$label max.") },
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
            singleLine = true,
            modifier = Modifier.weight(1f),
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun CardDetailSheet(
    card: Card,
    selectedPrint: CardPrint?,
    onSelectPrint: (CardPrint) -> Unit,
    onAdd: () -> Unit,
    onDismiss: () -> Unit,
) {
    ModalBottomSheet(onDismissRequest = onDismiss) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .verticalScroll(rememberScrollState())
                .padding(18.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                CardThumbnail(
                    url = card.imageUrl.ifBlank { card.thumbnailUrl },
                    contentDescription = card.name,
                    fullArtwork = true,
                    modifier = Modifier
                        .width(130.dp)
                        .height(190.dp),
                )
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text(card.name, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                    Text(card.type, style = MaterialTheme.typography.bodyMedium)
                    Text("Passcode ${card.key.cardId}", style = MaterialTheme.typography.labelMedium)
                    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        card.atk?.let { StatPill("ATK", it.toString()) }
                        card.def?.let { StatPill("DEF", it.toString()) }
                    }
                }
            }
            Text(card.description, style = MaterialTheme.typography.bodyMedium)
            HorizontalDivider()
            Text("Tatsächlichen Druck auswählen", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            if (card.prints.isEmpty()) {
                Text(
                    "Für diese Karte ist noch kein Set hinterlegt. Sie wird erst nach einer Set-Auswahl gespeichert.",
                    color = MaterialTheme.colorScheme.error,
                )
            } else {
                Column(
                    modifier = Modifier
                        .heightIn(max = 280.dp)
                        .verticalScroll(rememberScrollState()),
                ) {
                    card.prints.forEach { print ->
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clickable { onSelectPrint(print) }
                                .padding(vertical = 7.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            RadioButton(selected = selectedPrint?.stableKey == print.stableKey, onClick = { onSelectPrint(print) })
                            Column(Modifier.weight(1f)) {
                                Text("${print.setCode} · ${print.rarity}", fontWeight = FontWeight.SemiBold)
                                Text(print.setName, style = MaterialTheme.typography.bodySmall)
                            }
                        }
                    }
                }
            }
            Button(
                onClick = onAdd,
                enabled = selectedPrint != null,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Icon(Icons.Default.Add, contentDescription = null)
                Spacer(Modifier.width(8.dp))
                Text("Diesen Druck zur Sammlung")
            }
            Spacer(Modifier.height(20.dp))
        }
    }
}
