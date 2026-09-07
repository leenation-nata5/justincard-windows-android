package org.yugioh.kartenliste.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Backup
import androidx.compose.material.icons.filled.CloudSync
import androidx.compose.material.icons.filled.Download
import androidx.compose.material.icons.filled.FileOpen
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Save
import androidx.compose.material.icons.filled.TableChart
import androidx.compose.material.icons.filled.Upload
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
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
import org.yugioh.kartenliste.data.model.GoogleSpreadsheet
import org.yugioh.kartenliste.data.model.SyncDevice
import org.yugioh.kartenliste.data.model.SyncPhase
import org.yugioh.kartenliste.data.model.SyncStatus
import org.yugioh.kartenliste.ui.SettingsUiState
import org.yugioh.kartenliste.ui.SettingsViewModel
import org.yugioh.kartenliste.ui.components.ChoiceField

@Composable
fun SettingsScreen(
    viewModel: SettingsViewModel,
    googleToken: String,
    onAuthorizeGoogle: () -> Unit,
    onExportBackup: () -> Unit,
    onImportBackup: () -> Unit,
    onExportCsv: () -> Unit,
    onImportCsv: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val state by viewModel.state.collectAsState()
    val syncStatus by viewModel.syncStatus.collectAsState()
    var createSheet by remember { mutableStateOf(false) }
    var confirmBackupImport by remember { mutableStateOf(false) }
    var sheetAddress by remember(state.spreadsheetId) { mutableStateOf(state.spreadsheetId) }

    LazyColumn(
        modifier = modifier,
        contentPadding = PaddingValues(12.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            SettingsSection("Darstellung & Gerät") {
                OutlinedTextField(
                    value = state.deviceName,
                    onValueChange = viewModel::updateDeviceName,
                    label = { Text("Name dieses Geräts") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                ChoiceField(
                    label = "Erscheinungsbild",
                    value = state.themeMode,
                    choices = listOf("system" to "System", "dark" to "Dunkel", "light" to "Hell"),
                    onSelected = viewModel::updateTheme,
                )
                SettingSwitch(
                    title = "Reduzierte Bewegung",
                    subtitle = "Deaktiviert dekorative Übergänge; Listen und Scanner bleiben direkt.",
                    checked = state.reducedMotion,
                    onChecked = viewModel::updateReducedMotion,
                )
            }
        }

        item {
            SettingsSection("Kartenindex") {
                Text(
                    "Die Suche nutzt einen lokalen SQLite-Index. Bilder werden im Speicher- und Festplatten-Cache gehalten, damit lange Ergebnislisten ruhig scrollen.",
                    style = MaterialTheme.typography.bodyMedium,
                )
                FilledTonalButton(
                    onClick = viewModel::refreshCatalog,
                    enabled = !state.busy,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Icon(Icons.Default.Refresh, contentDescription = null)
                    Spacer(Modifier.width(8.dp))
                    Text("Kartenindex jetzt aktualisieren")
                }
            }
        }

        item {
            SettingsSection("Backup & Dateien") {
                Text(
                    "Das komprimierte JSON-Backup enthält Sammlung, exakte Drucke und Decks. CSV ist für Google Sheets und Excel gedacht.",
                    style = MaterialTheme.typography.bodyMedium,
                )
                ActionPair(
                    leftText = "Backup speichern",
                    leftIcon = Icons.Default.Save,
                    onLeft = onExportBackup,
                    rightText = "Backup laden",
                    rightIcon = Icons.Default.FileOpen,
                    onRight = { confirmBackupImport = true },
                )
                ActionPair(
                    leftText = "CSV exportieren",
                    leftIcon = Icons.Default.Download,
                    onLeft = onExportCsv,
                    rightText = "CSV importieren",
                    rightIcon = Icons.Default.Upload,
                    onRight = onImportCsv,
                )
            }
        }

        item {
            SettingsSection("Gemeinsame Google-Tabelle") {
                GoogleSyncHeader(state, syncStatus)
                SettingSwitch(
                    title = "Beim nächsten Verbinden abgleichen",
                    subtitle = "Nach der Google-Freigabe wird die gewählte Tabelle direkt synchronisiert.",
                    checked = state.automaticSync,
                    onChecked = viewModel::updateAutomaticSync,
                )
                Button(onClick = onAuthorizeGoogle, enabled = !state.busy, modifier = Modifier.fillMaxWidth()) {
                    Icon(Icons.Default.CloudSync, contentDescription = null)
                    Spacer(Modifier.width(8.dp))
                    Text(if (googleToken.isBlank()) "Google-Konto verbinden" else "Tabellen neu laden")
                }
                if (googleToken.isNotBlank()) {
                    OutlinedTextField(
                        value = sheetAddress,
                        onValueChange = { sheetAddress = it },
                        label = { Text("Google-Sheets-URL oder Tabellen-ID") },
                        supportingText = { Text("Damit kann dieselbe Tabelle wie unter Windows verbunden werden.") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                    )
                    FilledTonalButton(
                        onClick = { viewModel.linkSpreadsheet(googleToken, sheetAddress) },
                        enabled = !state.busy && sheetAddress.isNotBlank(),
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Icon(Icons.Default.TableChart, contentDescription = null)
                        Spacer(Modifier.width(8.dp))
                        Text("Vorhandene Tabelle verbinden")
                    }
                    FilledTonalButton(
                        onClick = { createSheet = true },
                        enabled = !state.busy,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Icon(Icons.Default.TableChart, contentDescription = null)
                        Spacer(Modifier.width(8.dp))
                        Text("Neue Just InCard-Tabelle")
                    }
                }
                if (state.spreadsheets.isNotEmpty()) {
                    Text("Tabelle auswählen", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
                    state.spreadsheets.forEach { sheet ->
                        SpreadsheetRow(
                            sheet = sheet,
                            selected = sheet.id == state.spreadsheetId,
                            enabled = googleToken.isNotBlank() && !state.busy,
                            onClick = { viewModel.linkSpreadsheet(googleToken, sheet.id) },
                        )
                    }
                }
                if (state.spreadsheetId.isNotBlank()) {
                    Row(
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        OutlinedButton(
                            onClick = { viewModel.saveToGoogle(googleToken) },
                            enabled = googleToken.isNotBlank() && !state.busy,
                            modifier = Modifier.weight(1f),
                        ) {
                            Icon(Icons.Default.Save, contentDescription = null)
                            Spacer(Modifier.width(5.dp))
                            Text("Cloud speichern", maxLines = 2)
                        }
                        OutlinedButton(
                            onClick = { viewModel.loadFromGoogle(googleToken) },
                            enabled = googleToken.isNotBlank() && !state.busy,
                            modifier = Modifier.weight(1f),
                        ) {
                            Icon(Icons.Default.Download, contentDescription = null)
                            Spacer(Modifier.width(5.dp))
                            Text("Cloud laden", maxLines = 2)
                        }
                    }
                    Button(
                        onClick = { viewModel.sync(googleToken) },
                        enabled = googleToken.isNotBlank() && !state.busy,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Icon(Icons.Default.CloudSync, contentDescription = null)
                        Spacer(Modifier.width(8.dp))
                        Text("Jetzt synchronisieren")
                    }
                }
                Text(
                    "Speichern überträgt den lokalen Stand, Laden führt den Cloud-Stand lokal zusammen und Synchronisieren gleicht beide Richtungen ab. Windows 1.2.7 und Android verwenden dieselbe Tabelle und dasselbe private Drive-Backup.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }

        if (state.devices.isNotEmpty()) {
            item {
                SettingsSection("Zugelassene Geräte") {
                    state.devices.forEach { device ->
                        DeviceRow(
                            device = device,
                            enabled = googleToken.isNotBlank() && !state.busy,
                            onToggle = { viewModel.setDeviceEnabled(googleToken, device, it) },
                        )
                    }
                }
            }
        }

        item {
            Text(
                "Just InCard Android 13.0.2 · native Kotlin/Compose-Neuaufbau",
                modifier = Modifier.fillMaxWidth().padding(vertical = 18.dp),
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }

    if (createSheet) {
        CreateSheetDialog(
            onCreate = { name ->
                viewModel.createSpreadsheet(googleToken, name)
                createSheet = false
            },
            onDismiss = { createSheet = false },
        )
    }
    if (confirmBackupImport) {
        AlertDialog(
            onDismissRequest = { confirmBackupImport = false },
            icon = { Icon(Icons.Default.FileOpen, contentDescription = null) },
            title = { Text("Vollständiges Backup wiederherstellen?") },
            text = {
                Text("Die derzeitige lokale Sammlung und alle lokalen Decks werden durch den Inhalt des gewählten Backups ersetzt. CSV-Import und Google-Sync arbeiten dagegen zusammenführend.")
            },
            confirmButton = {
                TextButton(onClick = {
                    confirmBackupImport = false
                    onImportBackup()
                }) { Text("Datei auswählen") }
            },
            dismissButton = { TextButton(onClick = { confirmBackupImport = false }) { Text("Abbrechen") } },
        )
    }
}

@Composable
private fun SettingsSection(title: String, content: @Composable ColumnScope.() -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.48f)),
    ) {
        Column(
            modifier = Modifier.padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(11.dp),
        ) {
            Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            HorizontalDivider()
            content()
        }
    }
}

@Composable
private fun SettingSwitch(
    title: String,
    subtitle: String,
    checked: Boolean,
    onChecked: (Boolean) -> Unit,
) {
    Row(modifier = Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text(title, fontWeight = FontWeight.SemiBold)
            Text(subtitle, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Switch(checked = checked, onCheckedChange = onChecked)
    }
}

@Composable
private fun ActionPair(
    leftText: String,
    leftIcon: androidx.compose.ui.graphics.vector.ImageVector,
    onLeft: () -> Unit,
    rightText: String,
    rightIcon: androidx.compose.ui.graphics.vector.ImageVector,
    onRight: () -> Unit,
) {
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
        OutlinedButton(onClick = onLeft, modifier = Modifier.weight(1f)) {
            Icon(leftIcon, contentDescription = null)
            Spacer(Modifier.width(5.dp))
            Text(leftText, maxLines = 2)
        }
        OutlinedButton(onClick = onRight, modifier = Modifier.weight(1f)) {
            Icon(rightIcon, contentDescription = null)
            Spacer(Modifier.width(5.dp))
            Text(rightText, maxLines = 2)
        }
    }
}

@Composable
private fun GoogleSyncHeader(state: SettingsUiState, status: SyncStatus) {
    if (state.spreadsheetId.isNotBlank()) {
        Text(
            "Aktiv: ${state.spreadsheetName.ifBlank { state.spreadsheetId }}",
            fontWeight = FontWeight.SemiBold,
            color = MaterialTheme.colorScheme.primary,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
        )
    } else {
        Text("Noch keine Tabelle gewählt", style = MaterialTheme.typography.bodyMedium)
    }
    if (status.phase !in listOf(SyncPhase.IDLE, SyncPhase.COMPLETE)) {
        status.progress?.let { LinearProgressIndicator(progress = { it }, modifier = Modifier.fillMaxWidth()) }
        if (status.progress == null && status.phase != SyncPhase.ERROR) CircularProgressIndicator()
        Text(
            status.message,
            style = MaterialTheme.typography.bodySmall,
            color = if (status.phase == SyncPhase.ERROR) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun SpreadsheetRow(
    sheet: GoogleSpreadsheet,
    selected: Boolean,
    enabled: Boolean,
    onClick: () -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth().clickable(enabled = enabled, onClick = onClick),
        colors = CardDefaults.cardColors(
            containerColor = if (selected) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surface,
        ),
    ) {
        Row(Modifier.padding(10.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(Icons.Default.TableChart, contentDescription = null)
            Spacer(Modifier.width(10.dp))
            Column(Modifier.weight(1f)) {
                Text(sheet.name, fontWeight = FontWeight.SemiBold, maxLines = 1, overflow = TextOverflow.Ellipsis)
                if (sheet.modifiedTime.isNotBlank()) Text(sheet.modifiedTime, style = MaterialTheme.typography.labelSmall)
            }
            Text(if (selected) "Aktiv" else "Wählen", style = MaterialTheme.typography.labelLarge)
        }
    }
}

@Composable
private fun DeviceRow(device: SyncDevice, enabled: Boolean, onToggle: (Boolean) -> Unit) {
    Row(modifier = Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text(device.name, fontWeight = FontWeight.SemiBold)
            Text(
                if (device.isCurrent) "Dieses Gerät" else "ID …${device.id.takeLast(8)}",
                style = MaterialTheme.typography.bodySmall,
            )
        }
        Switch(
            checked = device.enabled,
            onCheckedChange = onToggle,
            enabled = enabled && !device.isCurrent,
        )
    }
}

@Composable
private fun CreateSheetDialog(onCreate: (String) -> Unit, onDismiss: () -> Unit) {
    var name by remember { mutableStateOf("Just InCard Sammlung") }
    AlertDialog(
        onDismissRequest = onDismiss,
        icon = { Icon(Icons.Default.Backup, contentDescription = null) },
        title = { Text("Google-Tabelle erstellen") },
        text = {
            OutlinedTextField(
                value = name,
                onValueChange = { name = it },
                label = { Text("Tabellenname") },
                singleLine = true,
            )
        },
        confirmButton = { TextButton(onClick = { onCreate(name) }, enabled = name.isNotBlank()) { Text("Erstellen") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Abbrechen") } },
    )
}
