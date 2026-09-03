package org.yugioh.kartenliste.ui

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.result.contract.ActivityResultContracts.PickVisualMedia
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import coil.compose.AsyncImage
import org.yugioh.kartenliste.cloud.SheetTemplate
import org.yugioh.kartenliste.data.CollectionItem
import org.yugioh.kartenliste.data.Deck
import org.yugioh.kartenliste.data.DeckCard
import org.yugioh.kartenliste.data.SearchResult
import org.yugioh.kartenliste.scanner.LiveScanner
import java.util.Locale

private val Navy = Color(0xFF07111F)
private val Surface = Color(0xFF0D1A2D)
private val Surface2 = Color(0xFF12243C)
private val Blue = Color(0xFF397DDD)
private val TextMuted = Color(0xFFA9BDD9)

@Composable
fun JustInCardApp(vm: JustInCardViewModel) {
    val state by vm.state.collectAsState()
    MaterialTheme(
        colorScheme = darkColorScheme(
            primary = Blue,
            background = Navy,
            surface = Surface,
            surfaceVariant = Surface2,
            onBackground = Color.White,
            onSurface = Color.White,
        )
    ) {
        BoxWithConstraints(Modifier.fillMaxSize().background(Navy)) {
            val wide = maxWidth >= 900.dp
            if (wide) {
                Row(Modifier.fillMaxSize()) {
                    NavigationRail(modifier = Modifier.width(190.dp), containerColor = Color(0xFF091426)) {
                        Spacer(Modifier.height(18.dp))
                        Text("Just InCard", fontWeight = FontWeight.Bold, fontSize = 20.sp, modifier = Modifier.padding(12.dp))
                        Spacer(Modifier.height(10.dp))
                        AppScreen.entries.forEach { screen ->
                            NavigationRailItem(
                                selected = state.screen == screen,
                                onClick = { vm.navigate(screen) },
                                icon = { Icon(iconFor(screen), screen.label) },
                                label = { Text(screen.label) },
                                alwaysShowLabel = true,
                            )
                        }
                    }
                    ScreenContent(vm, state, Modifier.weight(1f))
                }
            } else {
                Scaffold(
                    containerColor = Navy,
                    bottomBar = {
                        NavigationBar(containerColor = Color(0xFF091426)) {
                            listOf(AppScreen.HOME, AppScreen.SEARCH, AppScreen.SCANNER, AppScreen.COLLECTION, AppScreen.DECKS, AppScreen.SETTINGS).forEach { screen ->
                                NavigationBarItem(
                                    selected = state.screen == screen,
                                    onClick = { vm.navigate(screen) },
                                    icon = { Icon(iconFor(screen), screen.label) },
                                    label = { Text(shortLabel(screen), maxLines = 1) },
                                )
                            }
                        }
                    }
                ) { padding -> ScreenContent(vm, state, Modifier.padding(padding)) }
            }
        }
    }
}

private fun iconFor(screen: AppScreen): ImageVector = when (screen) {
    AppScreen.HOME -> Icons.Outlined.Home
    AppScreen.SEARCH -> Icons.Outlined.Search
    AppScreen.SCANNER -> Icons.Outlined.PhotoCamera
    AppScreen.COLLECTION -> Icons.Outlined.Inventory2
    AppScreen.DECKS -> Icons.Outlined.ViewKanban
    AppScreen.SETTINGS -> Icons.Outlined.Settings
}

private fun shortLabel(screen: AppScreen) = when (screen) {
    AppScreen.SCANNER -> "Scan"
    AppScreen.COLLECTION -> "Sammlung"
    else -> screen.label
}

@Composable
private fun ScreenContent(vm: JustInCardViewModel, state: AppUiState, modifier: Modifier = Modifier) {
    Box(modifier.fillMaxSize()) {
        when (state.screen) {
            AppScreen.HOME -> HomeScreen(state)
            AppScreen.SEARCH -> SearchScreen(vm, state)
            AppScreen.SCANNER -> ScannerScreen(vm, state)
            AppScreen.COLLECTION -> CollectionScreen(vm, state)
            AppScreen.DECKS -> DecksScreen(vm, state)
            AppScreen.SETTINGS -> SettingsScreen(vm, state)
        }
        if (state.message.isNotBlank()) {
            Surface(
                modifier = Modifier.align(Alignment.TopCenter).padding(top = 14.dp),
                shape = RoundedCornerShape(14.dp), tonalElevation = 8.dp,
            ) { Text(state.message, Modifier.padding(horizontal = 18.dp, vertical = 10.dp)) }
        }
    }
}

@Composable
private fun HomeScreen(state: AppUiState) {
    Column(Modifier.fillMaxSize().padding(22.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        Text("Just InCard", fontSize = 30.sp, fontWeight = FontWeight.Bold)
        Text("Android 14.1.1 • Windows-kompatible Cloud-Sammlung", color = TextMuted)
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            StatCard("Karten", state.collection.sumOf { it.quantity }.toString(), Modifier.weight(1f))
            StatCard("Druckvarianten", state.collection.size.toString(), Modifier.weight(1f))
        }
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            StatCard("Decks", state.decks.size.toString(), Modifier.weight(1f))
            StatCard("Google Cloud", if (state.cloudStatus.signedIn) "Verbunden" else "Offline", Modifier.weight(1f))
        }
        Surface(shape = RoundedCornerShape(16.dp), color = Surface2) {
            Column(Modifier.padding(18.dp)) {
                Text("Live-Scanner bleibt aktiv", fontWeight = FontWeight.Bold)
                Text("CameraX + ML Kit erkennen Set-Code zuerst und Passcode danach. Galerie-Bilder verwenden denselben Suchpfad.", color = TextMuted)
            }
        }
    }
}

@Composable
private fun StatCard(label: String, value: String, modifier: Modifier = Modifier) {
    Surface(modifier = modifier, shape = RoundedCornerShape(16.dp), color = Surface2) {
        Column(Modifier.padding(16.dp)) { Text(label, color = TextMuted); Text(value, fontSize = 26.sp, fontWeight = FontWeight.Bold) }
    }
}

@Composable
private fun SearchScreen(vm: JustInCardViewModel, state: AppUiState) {
    Column(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Text("Kartensuche", fontSize = 25.sp, fontWeight = FontWeight.Bold)
        Text("Set-Codes werden intern immer über EN gesucht; die eingegebene Sprache bleibt beim Speichern erhalten.", color = TextMuted)
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(
                value = state.searchQuery,
                onValueChange = vm::setSearchQuery,
                label = { Text("Name, Set-Code oder Passcode") },
                singleLine = true,
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                keyboardActions = KeyboardActions(onSearch = { vm.search() }),
                modifier = Modifier.weight(1f),
            )
            Button(onClick = { vm.search() }, enabled = !state.busy) { Text("Suchen") }
        }
        Row(Modifier.weight(1f), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            LazyColumn(Modifier.weight(1f).fillMaxHeight(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                items(state.searchResults, key = { "${it.card.id}-${it.requestedSetCode}-${it.matchedPrint?.setCode}" }) { result ->
                    SearchRow(result, state.selectedSearch == result) { vm.selectSearch(result) }
                }
            }
            if (state.selectedSearch != null && LocalContext.current.resources.configuration.screenWidthDp >= 700) {
                CardDetail(state.selectedSearch, DisplayContext.SEARCH, vm, Modifier.weight(1f), state.searchQuantity, vm::setSearchQuantity, vm::addSelectedSearch)
            }
        }
        if (state.selectedSearch != null && LocalContext.current.resources.configuration.screenWidthDp < 700) {
            CardDetail(state.selectedSearch, DisplayContext.SEARCH, vm, Modifier.fillMaxWidth(), state.searchQuantity, vm::setSearchQuantity, vm::addSelectedSearch)
        }
    }
}

@Composable
private fun SearchRow(result: SearchResult, selected: Boolean, onClick: () -> Unit) {
    Surface(
        modifier = Modifier.fillMaxWidth().clickable(onClick = onClick),
        color = if (selected) Blue.copy(alpha = .35f) else Surface2,
        shape = RoundedCornerShape(12.dp),
    ) {
        Row(Modifier.padding(10.dp), verticalAlignment = Alignment.CenterVertically) {
            AsyncImage(result.card.cardImages.firstOrNull()?.imageUrlSmall, null, Modifier.width(54.dp).height(78.dp))
            Spacer(Modifier.width(10.dp))
            Column(Modifier.weight(1f)) {
                Text(result.card.name, fontWeight = FontWeight.SemiBold)
                val print = result.requestedSetCode.ifBlank { result.matchedPrint?.setCode.orEmpty() }
                if (print.isNotBlank()) Text(print, color = TextMuted, fontSize = 13.sp)
                Text(result.card.type, color = TextMuted, fontSize = 12.sp)
            }
        }
    }
}

@Composable
private fun CardDetail(
    result: SearchResult, context: DisplayContext, vm: JustInCardViewModel, modifier: Modifier,
    quantity: Int, onQuantity: (Int) -> Unit, onAdd: () -> Unit,
) {
    val card = result.card
    Surface(modifier, shape = RoundedCornerShape(16.dp), color = Surface2) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row {
                AsyncImage(card.cardImages.firstOrNull()?.imageUrl, null, Modifier.width(90.dp).height(132.dp))
                Spacer(Modifier.width(12.dp))
                Column(Modifier.weight(1f)) {
                    Text(card.name, fontSize = 20.sp, fontWeight = FontWeight.Bold)
                    if (vm.displayEnabled(context, DisplayField.TYPE)) Text(card.type, color = TextMuted)
                    if (vm.displayEnabled(context, DisplayField.RACE)) Text(card.race, color = TextMuted)
                    if (vm.displayEnabled(context, DisplayField.ATTRIBUTE)) Text(card.attribute, color = TextMuted)
                    if (vm.displayEnabled(context, DisplayField.STATS)) Text("ATK ${card.atk ?: "–"} / DEF ${card.def ?: "–"} / Lv ${card.level ?: "–"}", color = TextMuted)
                    val printCode = result.requestedSetCode.ifBlank { result.matchedPrint?.setCode.orEmpty() }
                    if (vm.displayEnabled(context, DisplayField.SET_CODE)) Text(printCode, color = TextMuted)
                    if (vm.displayEnabled(context, DisplayField.RARITY)) Text(result.matchedPrint?.setRarity.orEmpty(), color = TextMuted)
                    if (vm.displayEnabled(context, DisplayField.LANGUAGE)) Text("Sprache: ${result.requestedLanguage.uppercase()}", color = TextMuted)
                }
            }
            QuantityControl(quantity, onQuantity)
            Button(onClick = onAdd, Modifier.fillMaxWidth()) { Text("$quantity × zur Sammlung hinzufügen") }
        }
    }
}

@Composable
private fun QuantityControl(value: Int, onValue: (Int) -> Unit) {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Text("Menge", color = TextMuted)
        OutlinedButton(onClick = { onValue(value - 1) }) { Text("−") }
        OutlinedTextField(value.toString(), { onValue(it.toIntOrNull() ?: 1) }, modifier = Modifier.width(82.dp), singleLine = true)
        OutlinedButton(onClick = { onValue(value + 1) }) { Text("+") }
    }
}

@Composable
private fun ScannerScreen(vm: JustInCardViewModel, state: AppUiState) {
    val context = LocalContext.current
    var cameraGranted by remember { mutableStateOf(ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) }
    val permissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { cameraGranted = it }
    val galleryLauncher = rememberLauncherForActivityResult(PickVisualMedia()) { uri -> if (uri != null) vm.scanGallery(uri) }
    LaunchedEffect(Unit) { if (!cameraGranted) permissionLauncher.launch(Manifest.permission.CAMERA) }

    Box(Modifier.fillMaxSize().background(Color.Black)) {
        if (cameraGranted) {
            LiveScanner(Modifier.fillMaxSize(), enabled = state.screen == AppScreen.SCANNER, onCandidate = vm::scannerCandidate)
        } else {
            Text("Kameraberechtigung wird für das Livebild benötigt.", Modifier.align(Alignment.Center).padding(20.dp))
        }
        Column(
            Modifier.align(Alignment.TopCenter).fillMaxWidth().padding(14.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Surface(color = Color.Black.copy(alpha = .65f), shape = RoundedCornerShape(14.dp)) {
                Text(state.scannerStatus, Modifier.padding(horizontal = 14.dp, vertical = 9.dp))
            }
        }
        Row(Modifier.align(Alignment.TopEnd).padding(14.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            FilledTonalButton(onClick = { galleryLauncher.launch(PickVisualMediaRequest(PickVisualMedia.ImageOnly)) }) {
                Icon(Icons.Outlined.PhotoLibrary, null); Spacer(Modifier.width(5.dp)); Text("Galerie")
            }
        }
        state.scannerResult?.let { result ->
            Surface(
                Modifier.align(Alignment.BottomCenter).fillMaxWidth().padding(14.dp),
                color = Surface.copy(alpha = .96f), shape = RoundedCornerShape(18.dp), tonalElevation = 10.dp
            ) {
                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        AsyncImage(result.card.cardImages.firstOrNull()?.imageUrlSmall, null, Modifier.width(54.dp).height(78.dp))
                        Spacer(Modifier.width(10.dp))
                        Column(Modifier.weight(1f)) {
                            Text(result.card.name, fontWeight = FontWeight.Bold, fontSize = 18.sp)
                            Text(result.requestedSetCode.ifBlank { result.matchedPrint?.setCode.orEmpty() }, color = TextMuted)
                            Text("Sprache ${result.requestedLanguage.uppercase()} • ${result.matchedPrint?.setRarity.orEmpty()}", color = TextMuted)
                        }
                    }
                    QuantityControl(state.scannerQuantity, vm::setScannerQuantity)
                    Button(onClick = vm::addScannerResult, Modifier.fillMaxWidth()) { Text("Zur Sammlung hinzufügen") }
                }
            }
        }
    }
}

@Composable
private fun CollectionScreen(vm: JustInCardViewModel, state: AppUiState) {
    var filter by remember { mutableStateOf("") }
    val shown = remember(state.collection, filter) {
        state.collection.filter { item ->
            filter.isBlank() || listOf(item.card.name, item.printCode, item.setName, item.rarity).any { it.contains(filter, true) }
        }.sortedBy { it.card.name.lowercase() }
    }
    Column(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Text("Meine Sammlung", fontSize = 25.sp, fontWeight = FontWeight.Bold)
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            StatCard("Karten gesamt", state.collection.sumOf { it.quantity }.toString(), Modifier.weight(1f))
            StatCard("Geschätzter Sammlungswert", String.format(Locale.GERMANY, "%.2f €", vm.totalCollectionValue()), Modifier.weight(1f))
        }
        OutlinedTextField(filter, { filter = it }, label = { Text("Sammlung filtern") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
        LazyColumn(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(7.dp)) {
            items(shown, key = { it.collectionKey }) { item ->
                CollectionRow(item, vm, state.selectedCollection?.collectionKey == item.collectionKey) { vm.selectCollection(item) }
            }
        }
        state.selectedCollection?.let { SelectedCollectionEditor(it, vm) }
    }
}

@Composable
private fun CollectionRow(item: CollectionItem, vm: JustInCardViewModel, selected: Boolean, onClick: () -> Unit) {
    Surface(Modifier.fillMaxWidth().clickable(onClick = onClick), color = if (selected) Blue.copy(alpha = .30f) else Surface2, shape = RoundedCornerShape(12.dp)) {
        Row(Modifier.padding(10.dp), verticalAlignment = Alignment.CenterVertically) {
            AsyncImage(item.artworkUrl.ifBlank { item.card.cardImages.firstOrNull()?.imageUrlSmall }, null, Modifier.width(46.dp).height(66.dp))
            Spacer(Modifier.width(10.dp))
            Column(Modifier.weight(1f)) {
                Text(item.card.name, fontWeight = FontWeight.SemiBold)
                val details = buildList {
                    if (vm.displayEnabled(DisplayContext.COLLECTION, DisplayField.SET_CODE)) add(item.printCode)
                    if (vm.displayEnabled(DisplayContext.COLLECTION, DisplayField.RARITY)) add(item.rarity)
                    if (vm.displayEnabled(DisplayContext.COLLECTION, DisplayField.LANGUAGE)) add(item.language.uppercase())
                }.filter { it.isNotBlank() }
                Text(details.joinToString(" • "), color = TextMuted, fontSize = 12.sp)
            }
            Column(horizontalAlignment = Alignment.End) {
                Text("×${item.quantity}", fontWeight = FontWeight.Bold)
                if (vm.displayEnabled(DisplayContext.COLLECTION, DisplayField.MARKET)) Text(String.format(Locale.GERMANY, "%.2f €", vm.estimatedValue(item)), color = TextMuted)
            }
        }
    }
}

@Composable
private fun SelectedCollectionEditor(item: CollectionItem, vm: JustInCardViewModel) {
    var quantity by remember(item.collectionKey, item.quantity) { mutableIntStateOf(item.quantity) }
    var note by remember(item.collectionKey, item.note) { mutableStateOf(item.note) }
    var condition by remember(item.collectionKey, item.condition) { mutableStateOf(item.condition) }
    Surface(shape = RoundedCornerShape(16.dp), color = Surface2) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Ausgabe bearbeiten: ${item.card.name}", fontWeight = FontWeight.Bold)
            QuantityControl(quantity) { quantity = it }
            SimpleSelect("Zustand", listOf("Mint", "Near Mint", "Excellent", "Good", "Light Played", "Played", "Poor"), condition) { condition = it }
            OutlinedTextField(note, { note = it }, label = { Text("Notiz") }, modifier = Modifier.fillMaxWidth())
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { vm.updateCollection(item.copy(quantity = quantity, condition = condition, note = note)) }, modifier = Modifier.weight(1f)) { Text("Speichern") }
                OutlinedButton(onClick = { vm.deleteCollection(item) }) { Text("Entfernen") }
            }
        }
    }
}

@Composable
private fun DecksScreen(vm: JustInCardViewModel, state: AppUiState) {
    var newDeck by remember { mutableStateOf("") }
    val selected = state.decks.firstOrNull { it.deckId == state.selectedDeckId }
    Column(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Text("Deckbuilder", fontSize = 25.sp, fontWeight = FontWeight.Bold)
        Text("Fusion, Synchro, Xyz und Link werden automatisch ins Extra Deck gelegt. Nur Side Deck wird manuell gewählt.", color = TextMuted)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
            OutlinedTextField(newDeck, { newDeck = it }, label = { Text("Neues Deck") }, modifier = Modifier.weight(1f), singleLine = true)
            Button(onClick = { vm.createDeck(newDeck); newDeck = "" }) { Text("Anlegen") }
        }
        if (state.decks.isNotEmpty()) {
            SimpleSelect("Deck", state.decks.map { it.name }, selected?.name.orEmpty()) { name ->
                state.decks.firstOrNull { it.name == name }?.let { vm.selectDeck(it.deckId) }
            }
        }
        if (selected == null) {
            Text("Noch kein Deck angelegt.", color = TextMuted)
            return@Column
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = vm::deleteSelectedDeck) { Text("Deck löschen") }
            Text("Main ${selected.cards.filter { it.zone == "main" }.sumOf { it.quantity }} • Extra ${selected.cards.filter { it.zone == "extra" }.sumOf { it.quantity }} • Side ${selected.cards.filter { it.zone == "side" }.sumOf { it.quantity }}", modifier = Modifier.align(Alignment.CenterVertically), color = TextMuted)
        }
        Text("Deckkarten", fontWeight = FontWeight.Bold)
        LazyColumn(Modifier.weight(.45f), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            items(selected.cards, key = { "${it.id}-${it.collectionKey}-${it.zone}" }) { card -> DeckCardRow(card, vm) }
        }
        Text("Aus Sammlung hinzufügen", fontWeight = FontWeight.Bold)
        LazyColumn(Modifier.weight(.55f), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            items(state.collection, key = { it.collectionKey }) { item ->
                Surface(color = Surface2, shape = RoundedCornerShape(10.dp)) {
                    Row(Modifier.padding(9.dp), verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) { Text(item.card.name); Text("${item.printCode} • ×${item.quantity}", color = TextMuted, fontSize = 12.sp) }
                        FilledTonalButton(onClick = { vm.addDeckCard(item, false) }) { Text("Auto") }
                        Spacer(Modifier.width(6.dp))
                        OutlinedButton(onClick = { vm.addDeckCard(item, true) }) { Text("Side") }
                    }
                }
            }
        }
    }
}

@Composable
private fun DeckCardRow(card: DeckCard, vm: JustInCardViewModel) {
    Surface(color = if (card.isPlaceholder) Color(0xFF3A3F4A) else Surface2, shape = RoundedCornerShape(10.dp)) {
        Row(Modifier.padding(9.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(card.card.name, fontWeight = FontWeight.SemiBold)
                Text("${card.zone.uppercase()} • ${if (card.isPlaceholder) "Platzhalter" else card.printCode}", color = TextMuted, fontSize = 12.sp)
            }
            Text("×${card.quantity}")
            IconButton(onClick = { vm.removeDeckCard(card) }) { Icon(Icons.Outlined.Delete, "Entfernen") }
        }
    }
}

@Composable
private fun SettingsScreen(vm: JustInCardViewModel, state: AppUiState) {
    val context = LocalContext.current
    val signInLauncher = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { vm.handleGoogleSignInResult(it.data) }
    var sortField by remember { mutableStateOf(vm.cloudSortField()) }
    var direction by remember { mutableStateOf(vm.cloudDirection()) }
    var autoSync by remember { mutableStateOf(vm.autoSyncEnabled()) }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Einstellungen", fontSize = 25.sp, fontWeight = FontWeight.Bold)
        Surface(shape = RoundedCornerShape(16.dp), color = Surface2) {
            Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(9.dp)) {
                Text("Google Cloud-Sammlung", fontWeight = FontWeight.Bold, fontSize = 18.sp)
                Text(if (state.cloudStatus.signedIn) "Angemeldet: ${state.cloudStatus.email}" else "Nicht angemeldet", color = TextMuted)
                Text("Windows und Android verwenden dasselbe private AppData-Backup und dieselbe browserlesbare Google-Sheets-Datei.", color = TextMuted)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    if (!state.cloudStatus.signedIn) Button(onClick = { signInLauncher.launch(vm.cloud.signInIntent()) }) { Text("Mit Google anmelden") }
                    else OutlinedButton(onClick = vm::signOutGoogle) { Text("Abmelden") }
                    if (state.cloudStatus.spreadsheetId.isNotBlank()) OutlinedButton(onClick = { context.startActivity(vm.cloud.browserIntent()) }) { Text("Sheet öffnen") }
                }
                SimpleSelect("Cloud-Sortierung", SheetTemplate.SortField.entries.map { it.label }, sortField.label) { label ->
                    sortField = SheetTemplate.SortField.entries.first { it.label == label }; vm.setCloudSort(sortField, direction)
                }
                SimpleSelect("Richtung", SheetTemplate.Direction.entries.map { it.label }, direction.label) { label ->
                    direction = SheetTemplate.Direction.entries.first { it.label == label }; vm.setCloudSort(sortField, direction)
                }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Switch(autoSync, { autoSync = it; vm.setAutoSync(it) }); Spacer(Modifier.width(8.dp)); Text("Beim App-Start synchronisieren")
                }
                Row(horizontalArrangement = Arrangement.spacedBy(7.dp)) {
                    Button(onClick = vm::cloudSync, enabled = state.cloudStatus.signedIn && !state.cloudBusy) { Text("Synchronisieren") }
                    OutlinedButton(onClick = vm::cloudUpload, enabled = state.cloudStatus.signedIn && !state.cloudBusy) { Text("Hochladen") }
                    OutlinedButton(onClick = vm::cloudLoad, enabled = state.cloudStatus.signedIn && !state.cloudBusy) { Text("Cloud laden") }
                }
                if (state.cloudMessage.isNotBlank()) Text(state.cloudMessage, color = TextMuted)
            }
        }
        Text("Anzeige je Bereich", fontWeight = FontWeight.Bold, fontSize = 18.sp)
        DisplayContext.entries.forEach { displayContext ->
            Surface(shape = RoundedCornerShape(14.dp), color = Surface2) {
                Column(Modifier.padding(12.dp)) {
                    Text(displayContext.label, fontWeight = FontWeight.SemiBold)
                    FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        DisplayField.entries.forEach { field ->
                            FilterChip(
                                selected = vm.displayEnabled(displayContext, field),
                                onClick = { vm.setDisplay(displayContext, field, !vm.displayEnabled(displayContext, field)) },
                                label = { Text(field.label) },
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun SimpleSelect(label: String, options: List<String>, selected: String, onSelected: (String) -> Unit) {
    var expanded by remember { mutableStateOf(false) }
    Column {
        Text(label, color = TextMuted, fontSize = 12.sp)
        Box {
            OutlinedButton(onClick = { expanded = true }) { Text(selected.ifBlank { options.firstOrNull().orEmpty() }); Icon(Icons.Outlined.ArrowDropDown, null) }
            DropdownMenu(expanded, onDismissRequest = { expanded = false }) {
                options.forEach { option -> DropdownMenuItem(text = { Text(option) }, onClick = { onSelected(option); expanded = false }) }
            }
        }
    }
}
