package org.yugioh.kartenliste

import android.Manifest
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.CollectionsBookmark
import androidx.compose.material.icons.filled.Inventory2
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationRail
import androidx.compose.material3.NavigationRailItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import androidx.lifecycle.viewmodel.compose.viewModel
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import org.yugioh.kartenliste.sync.GoogleAuthorizationManager
import org.yugioh.kartenliste.ui.AppViewModelFactory
import org.yugioh.kartenliste.ui.CollectionViewModel
import org.yugioh.kartenliste.ui.DeckViewModel
import org.yugioh.kartenliste.ui.ScanViewModel
import org.yugioh.kartenliste.ui.SearchViewModel
import org.yugioh.kartenliste.ui.SettingsViewModel
import org.yugioh.kartenliste.ui.screens.AccountLoginDialog
import org.yugioh.kartenliste.ui.screens.CollectionScreen
import org.yugioh.kartenliste.ui.screens.DeckScreen
import org.yugioh.kartenliste.ui.screens.ScanScreen
import org.yugioh.kartenliste.ui.screens.SearchScreen
import org.yugioh.kartenliste.ui.screens.SettingsScreen
import org.yugioh.kartenliste.ui.theme.JustInCardTheme
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            val application = application as JustInCardApplication
            val factory = remember { AppViewModelFactory(application.container, contentResolver) }
            val searchViewModel: SearchViewModel = viewModel(factory = factory)
            val collectionViewModel: CollectionViewModel = viewModel(factory = factory)
            val scanViewModel: ScanViewModel = viewModel(factory = factory)
            val deckViewModel: DeckViewModel = viewModel(factory = factory)
            val settingsViewModel: SettingsViewModel = viewModel(factory = factory)
            val settings by settingsViewModel.state.collectAsState()

            JustInCardTheme(settings.themeMode) {
                JustInCardApp(
                    activity = this,
                    searchViewModel = searchViewModel,
                    collectionViewModel = collectionViewModel,
                    scanViewModel = scanViewModel,
                    deckViewModel = deckViewModel,
                    settingsViewModel = settingsViewModel,
                )
            }
        }
    }
}

private enum class Destination(val title: String, val icon: ImageVector) {
    SEARCH("Suche", Icons.Default.Search),
    COLLECTION("Sammlung", Icons.Default.Inventory2),
    SCAN("Livebild", Icons.Default.CameraAlt),
    DECKS("Decks", Icons.Default.CollectionsBookmark),
    SETTINGS("Einstellungen", Icons.Default.Settings),
}

@Composable
private fun JustInCardApp(
    activity: MainActivity,
    searchViewModel: SearchViewModel,
    collectionViewModel: CollectionViewModel,
    scanViewModel: ScanViewModel,
    deckViewModel: DeckViewModel,
    settingsViewModel: SettingsViewModel,
) {
    val snackbar = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()
    var destination by rememberSaveable { mutableStateOf(Destination.SEARCH) }
    var googleToken by remember { mutableStateOf("") }
    var startupAccountLogin by rememberSaveable { mutableStateOf(false) }
    val uriHandler = LocalUriHandler.current
    val cameraAvailable = remember {
        activity.packageManager.hasSystemFeature(PackageManager.FEATURE_CAMERA_ANY)
    }
    var cameraPermission by remember {
        mutableStateOf(ContextCompat.checkSelfPermission(activity, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED)
    }
    var pendingCameraUri by remember { mutableStateOf<Uri?>(null) }
    var captureAfterPermission by remember { mutableStateOf(false) }

    val searchState by searchViewModel.state.collectAsState()
    val collectionMessage by collectionViewModel.message.collectAsState()
    val scanMessage by scanViewModel.message.collectAsState()
    val deckMessage by deckViewModel.message.collectAsState()
    val settingsState by settingsViewModel.state.collectAsState()

    LaunchedEffect(
        settingsState.accountMode,
        settingsState.accountLoggedIn,
        settingsState.accountAutomaticSync,
    ) {
        if (settingsState.accountMode == "account" && settingsState.accountLoggedIn && settingsState.accountAutomaticSync) {
            settingsViewModel.syncAccount(silent = true)
            while (true) {
                delay(5 * 60 * 1000L)
                settingsViewModel.syncAccount(silent = true)
            }
        }
    }

    LaunchedEffect(searchState.message, searchState.error) {
        (searchState.error ?: searchState.message)?.let {
            snackbar.showSnackbar(it)
            searchViewModel.dismissMessage()
        }
    }
    LaunchedEffect(collectionMessage) {
        collectionMessage?.let {
            snackbar.showSnackbar(it)
            collectionViewModel.dismissMessage()
        }
    }
    LaunchedEffect(scanMessage) {
        scanMessage?.let {
            snackbar.showSnackbar(it)
            scanViewModel.dismissMessage()
        }
    }
    LaunchedEffect(deckMessage) {
        deckMessage?.let {
            snackbar.showSnackbar(it)
            deckViewModel.dismissMessage()
        }
    }
    LaunchedEffect(settingsState.message, settingsState.error) {
        (settingsState.error ?: settingsState.message)?.let {
            snackbar.showSnackbar(it)
            settingsViewModel.dismissMessage()
        }
    }

    val takePictureLauncher = rememberLauncherForActivityResult(ActivityResultContracts.TakePicture()) { success ->
        val uri = pendingCameraUri
        if (success && uri != null) scanViewModel.scanUris(activity, listOf(uri), "Kamera")
        else scope.launch { snackbar.showSnackbar("Keine Aufnahme übernommen.") }
    }
    val cameraPermissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        cameraPermission = granted
        if (granted && captureAfterPermission) {
            captureAfterPermission = false
            runCatching {
                val uri = createCameraUri(activity)
                pendingCameraUri = uri
                takePictureLauncher.launch(uri)
            }.onFailure { error ->
                scope.launch { snackbar.showSnackbar(error.message ?: "Kamera konnte nicht geöffnet werden.") }
            }
        } else if (!granted) {
            captureAfterPermission = false
            scope.launch { snackbar.showSnackbar("Kamerazugriff abgelehnt. Die Galerie bleibt verfügbar.") }
        }
    }
    val galleryLauncher = rememberLauncherForActivityResult(ActivityResultContracts.PickMultipleVisualMedia(50)) { uris ->
        scanViewModel.scanUris(activity, uris, "Galerie")
    }
    val exportBackup = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/zip")) { uri ->
        uri?.let(settingsViewModel::exportBackup)
    }
    val importBackup = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        uri?.let(settingsViewModel::importBackup)
    }
    val exportCsv = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("text/csv")) { uri ->
        uri?.let(settingsViewModel::exportCsv)
    }
    val importCsv = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        uri?.let(settingsViewModel::importCsv)
    }

    val googleAuthorization = remember(activity) { GoogleAuthorizationManager(activity) }
    val googleResolution = rememberLauncherForActivityResult(ActivityResultContracts.StartIntentSenderForResult()) { result ->
        // AuthorizationClient encodes success and errors in the returned Intent.
        // The Activity result code must not be used as an early cancellation gate.
        googleAuthorization.handleResult(result.data)
    }
    val authorizeGoogleFor: ((String) -> Unit) -> Unit = { afterAuthorization ->
        googleAuthorization.authorize(
            launchResolution = googleResolution::launch,
            onSuccess = { token ->
                googleToken = token
                afterAuthorization(token)
            },
            onError = { message -> scope.launch { snackbar.showSnackbar(message) } },
        )
    }
    val authorizeGoogle = {
        authorizeGoogleFor { token ->
            if (settingsState.automaticSync && settingsState.spreadsheetId.isNotBlank()) {
                settingsViewModel.sync(token)
            } else {
                settingsViewModel.loadSpreadsheets(token)
            }
        }
    }

    if (settingsState.accountMode.isBlank() && !startupAccountLogin) {
        AlertDialog(
            onDismissRequest = settingsViewModel::useLocalMode,
            title = { Text("Wie möchtest du Just InCard verwenden?") },
            text = {
                Text(
                    "Du kannst Just InCard vollständig lokal ohne Konto verwenden. Mit einem Just-InCard-Konto von justincard.de werden nur Sammlung und Decks zusätzlich auf deinem IONOS-Webspace gesichert und zwischen Windows und Android synchronisiert. Kartenbilder bleiben auf den Endgeräten."
                )
            },
            confirmButton = {
                TextButton(onClick = { startupAccountLogin = true }) { Text("Mit Konto anmelden") }
            },
            dismissButton = {
                TextButton(onClick = settingsViewModel::useLocalMode) { Text("Nur lokal verwenden") }
            },
        )
    }
    if (startupAccountLogin) {
        AccountLoginDialog(
            busy = settingsState.busy,
            onLogin = { identity, password ->
                settingsViewModel.loginAccount(identity, password)
                startupAccountLogin = false
            },
            onRegister = { uriHandler.openUri("https://justincard.de/register.php") },
            onDismiss = {
                startupAccountLogin = false
                settingsViewModel.useLocalMode()
            },
        )
    }

    AdaptiveAppShell(
        destination = destination,
        onDestination = { destination = it },
        snackbar = snackbar,
    ) { contentModifier ->
        when (destination) {
            Destination.SEARCH -> SearchScreen(searchViewModel, contentModifier)
            Destination.COLLECTION -> CollectionScreen(collectionViewModel, contentModifier)
            Destination.SCAN -> ScanScreen(
                viewModel = scanViewModel,
                cameraAvailable = cameraAvailable,
                cameraPermission = cameraPermission,
                onRequestCameraPermission = { cameraPermissionLauncher.launch(Manifest.permission.CAMERA) },
                onTakePicture = {
                    runCatching {
                        require(cameraAvailable) { "Auf diesem Gerät ist keine Kamera verfügbar." }
                        if (!cameraPermission) {
                            captureAfterPermission = true
                            cameraPermissionLauncher.launch(Manifest.permission.CAMERA)
                        } else {
                            val uri = createCameraUri(activity)
                            pendingCameraUri = uri
                            takePictureLauncher.launch(uri)
                        }
                    }.onFailure { error ->
                        scope.launch { snackbar.showSnackbar(error.message ?: "Kamera konnte nicht geöffnet werden.") }
                    }
                },
                onPickGallery = {
                    galleryLauncher.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly))
                },
                modifier = contentModifier,
            )
            Destination.DECKS -> DeckScreen(deckViewModel, contentModifier)
            Destination.SETTINGS -> SettingsScreen(
                viewModel = settingsViewModel,
                googleToken = googleToken,
                onAuthorizeGoogle = authorizeGoogle,
                onFreshGoogleToken = authorizeGoogleFor,
                onExportBackup = { exportBackup.launch("JustInCard_Backup_${todayStamp()}.jicbackup") },
                onImportBackup = { importBackup.launch(arrayOf("application/zip", "application/octet-stream", "*/*")) },
                onExportCsv = { exportCsv.launch("JustInCard_Sammlung_${todayStamp()}.csv") },
                onImportCsv = { importCsv.launch(arrayOf("text/csv", "text/comma-separated-values", "text/plain")) },
                modifier = contentModifier,
            )
        }
    }
}

@Composable
private fun AdaptiveAppShell(
    destination: Destination,
    onDestination: (Destination) -> Unit,
    snackbar: SnackbarHostState,
    content: @Composable (Modifier) -> Unit,
) {
    androidx.compose.foundation.layout.BoxWithConstraints(
        modifier = Modifier
            .fillMaxSize()
            .safeDrawingPadding(),
    ) {
        val expanded = maxWidth >= 700.dp
        if (expanded) {
            Row(Modifier.fillMaxSize()) {
                NavigationRail {
                    Destination.entries.forEach { item ->
                        NavigationRailItem(
                            selected = destination == item,
                            onClick = { onDestination(item) },
                            icon = { Icon(item.icon, contentDescription = item.title) },
                            label = { Text(item.title) },
                        )
                    }
                }
                AppScaffold(destination, snackbar, Modifier.weight(1f), null, content)
            }
        } else {
            AppScaffold(
                destination = destination,
                snackbar = snackbar,
                modifier = Modifier.fillMaxSize(),
                bottomBar = {
                    NavigationBar {
                        Destination.entries.forEach { item ->
                            NavigationBarItem(
                                selected = destination == item,
                                onClick = { onDestination(item) },
                                icon = { Icon(item.icon, contentDescription = item.title) },
                                label = { Text(item.title) },
                            )
                        }
                    }
                },
                content = content,
            )
        }
    }
}

@Composable
private fun AppScaffold(
    destination: Destination,
    snackbar: SnackbarHostState,
    modifier: Modifier,
    bottomBar: (@Composable () -> Unit)?,
    content: @Composable (Modifier) -> Unit,
) {
    Scaffold(
        modifier = modifier,
        topBar = { BrandHeader(destination.title) },
        bottomBar = { bottomBar?.invoke() },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        content(Modifier.fillMaxSize().padding(padding))
    }
}

@Composable
private fun BrandHeader(title: String) {
    Surface(tonalElevation = 3.dp) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .height(58.dp)
                .padding(horizontal = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Image(
                painter = painterResource(R.drawable.app_logo),
                contentDescription = "Just InCard",
                contentScale = ContentScale.Fit,
                modifier = Modifier.size(48.dp),
            )
            Column(Modifier.padding(start = 8.dp)) {
                Text("Just InCard", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                Text(title, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}

private fun createCameraUri(activity: ComponentActivity): Uri {
    val folder = File(activity.cacheDir, "shared").apply { mkdirs() }
    val file = File.createTempFile("scan_", ".jpg", folder)
    return FileProvider.getUriForFile(activity, "${activity.packageName}.files", file)
}

private fun todayStamp(): String = SimpleDateFormat("yyyy-MM-dd", Locale.ROOT).format(Date())
