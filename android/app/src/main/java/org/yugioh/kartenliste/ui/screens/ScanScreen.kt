package org.yugioh.kartenliste.ui.screens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Collections
import androidx.compose.material.icons.filled.PhotoCamera
import androidx.compose.material.icons.filled.ZoomIn
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import org.yugioh.kartenliste.data.model.CardPrint
import org.yugioh.kartenliste.data.model.ScanCandidate
import org.yugioh.kartenliste.data.model.ScanResult
import org.yugioh.kartenliste.ui.ScanViewModel
import org.yugioh.kartenliste.ui.components.CardThumbnail
import org.yugioh.kartenliste.ui.components.LiveCameraPreview
import org.yugioh.kartenliste.ui.theme.JicGold

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ScanScreen(
    viewModel: ScanViewModel,
    cameraAvailable: Boolean,
    cameraPermission: Boolean,
    onRequestCameraPermission: () -> Unit,
    onTakePicture: () -> Unit,
    onPickGallery: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val current by viewModel.current.collectAsState()
    val batch by viewModel.batch.collectAsState()
    var menuExpanded by remember { mutableStateOf(false) }
    var detailCandidate by remember { mutableStateOf<ScanCandidate?>(null) }

    Box(modifier.fillMaxSize().background(Color.Black)) {
        if (cameraAvailable && cameraPermission) {
            LiveCameraPreview(
                ocrEngine = viewModel.ocrEngine,
                onSignals = viewModel::onLiveSignals,
                modifier = Modifier.fillMaxSize(),
            )
        } else {
            Column(
                modifier = Modifier.align(Alignment.Center).padding(28.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(14.dp),
            ) {
                Icon(Icons.Default.CameraAlt, contentDescription = null, tint = Color.White, modifier = Modifier.size(56.dp))
                Text(
                    if (cameraAvailable) "Kamerazugriff für das Livebild" else "Auf diesem Gerät ist keine Kamera verfügbar",
                    color = Color.White,
                    style = MaterialTheme.typography.titleMedium,
                )
                Text(
                    "Alternativ kannst du jederzeit Fotos aus der Galerie scannen.",
                    color = Color.White.copy(alpha = 0.75f),
                    style = MaterialTheme.typography.bodyMedium,
                )
                if (cameraAvailable) Button(onClick = onRequestCameraPermission) { Text("Kamera erlauben") }
            }
        }

        androidx.compose.foundation.layout.BoxWithConstraints(Modifier.fillMaxSize()) {
            val frameWidth = minOf(maxWidth * 0.76f, 360.dp)
            val frameHeight = minOf(frameWidth * 1.45f, maxHeight * 0.66f)
            Box(
                modifier = Modifier
                    .align(Alignment.Center)
                    .width(frameWidth)
                    .height(frameHeight)
                    .clip(RoundedCornerShape(18.dp))
                    .background(Color.Transparent)
                    .then(Modifier),
            ) {
                Box(
                    Modifier
                        .fillMaxSize()
                        .clip(RoundedCornerShape(18.dp))
                        .background(Color.Transparent),
                )
                androidx.compose.foundation.Canvas(Modifier.fillMaxSize()) {
                    drawRoundRect(
                        color = JicGold,
                        cornerRadius = androidx.compose.ui.geometry.CornerRadius(18.dp.toPx()),
                        style = androidx.compose.ui.graphics.drawscope.Stroke(width = 3.dp.toPx()),
                    )
                }
            }
        }

        Text(
            "Set-Code und Kartenunterkante in den goldenen Rahmen legen",
            modifier = Modifier
                .align(Alignment.TopCenter)
                .padding(14.dp)
                .clip(RoundedCornerShape(999.dp))
                .background(Color.Black.copy(alpha = 0.68f))
                .padding(horizontal = 14.dp, vertical = 8.dp),
            color = Color.White,
            style = MaterialTheme.typography.labelLarge,
        )

        if (batch.running) {
            Row(
                modifier = Modifier
                    .align(Alignment.TopStart)
                    .padding(top = 62.dp, start = 14.dp)
                    .clip(RoundedCornerShape(999.dp))
                    .background(Color.Black.copy(alpha = 0.7f))
                    .padding(horizontal = 12.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp, color = JicGold)
                Text("${batch.completed}/${batch.total} Fotos", color = Color.White, style = MaterialTheme.typography.labelLarge)
            }
        }

        if (batch.results.size > 1) {
            LazyRow(
                modifier = Modifier
                    .align(Alignment.BottomCenter)
                    .padding(start = 10.dp, end = 84.dp, bottom = 12.dp),
                horizontalArrangement = Arrangement.spacedBy(7.dp),
            ) {
                items(batch.results) { result ->
                    Card(
                        modifier = Modifier.clickable { viewModel.showResult(result) },
                        colors = CardDefaults.cardColors(containerColor = Color.Black.copy(alpha = 0.78f)),
                    ) {
                        Text(
                            result.best?.card?.name ?: "Nicht erkannt",
                            color = Color.White,
                            style = MaterialTheme.typography.labelMedium,
                            maxLines = 1,
                            modifier = Modifier.padding(horizontal = 10.dp, vertical = 8.dp),
                        )
                    }
                }
            }
        }

        current?.best?.let { candidate ->
            ScanResultOverlay(
                result = current!!,
                candidate = candidate,
                onOpen = { detailCandidate = candidate },
                onReject = viewModel::reject,
                onAdd = {
                    if (candidate.matchedPrint != null) viewModel.add(candidate)
                    else detailCandidate = candidate
                },
                modifier = Modifier
                    .align(Alignment.BottomStart)
                    .padding(start = 12.dp, end = 92.dp, bottom = if (batch.results.size > 1) 56.dp else 12.dp),
            )
        }

        Box(
            modifier = Modifier
                .align(Alignment.BottomEnd)
                .padding(16.dp),
        ) {
            FloatingActionButton(
                onClick = { menuExpanded = true },
                containerColor = JicGold,
                contentColor = Color(0xFF2D2100),
            ) {
                Icon(Icons.Default.PhotoCamera, contentDescription = "Aufnahme-Menü")
            }
            DropdownMenu(expanded = menuExpanded, onDismissRequest = { menuExpanded = false }) {
                DropdownMenuItem(
                    text = { Text("Android-Kamera") },
                    leadingIcon = { Icon(Icons.Default.CameraAlt, contentDescription = null) },
                    onClick = {
                        menuExpanded = false
                        onTakePicture()
                    },
                )
                DropdownMenuItem(
                    text = { Text("Bilder aus Galerie") },
                    leadingIcon = { Icon(Icons.Default.Collections, contentDescription = null) },
                    onClick = {
                        menuExpanded = false
                        onPickGallery()
                    },
                )
            }
        }
    }

    detailCandidate?.let { candidate ->
        ScanCandidateSheet(
            candidate = candidate,
            onAdd = { print ->
                viewModel.add(candidate, print)
                detailCandidate = null
            },
            onDismiss = { detailCandidate = null },
        )
    }
}

@Composable
private fun ScanResultOverlay(
    result: ScanResult,
    candidate: ScanCandidate,
    onOpen: () -> Unit,
    onReject: () -> Unit,
    onAdd: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Card(
        modifier = modifier
            .fillMaxWidth()
            .clickable(onClick = onOpen),
        colors = CardDefaults.cardColors(containerColor = Color(0xEE0B1721)),
        border = BorderStroke(1.dp, JicGold.copy(alpha = 0.8f)),
    ) {
        Row(
            modifier = Modifier.padding(9.dp),
            horizontalArrangement = Arrangement.spacedBy(10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            CardThumbnail(
                candidate.card.thumbnailUrl.ifBlank { candidate.card.imageUrl },
                candidate.card.name,
                Modifier
                    .width(58.dp)
                    .height(84.dp),
            )
            Column(Modifier.weight(1f)) {
                Text(
                    candidate.card.name,
                    color = Color.White,
                    fontWeight = FontWeight.Bold,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    candidate.matchedPrint?.let { "${it.setCode} · ${it.rarity}" } ?: "Set bitte auswählen",
                    color = JicGold,
                    style = MaterialTheme.typography.labelMedium,
                )
                Text("${result.sourceLabel} · ${candidate.reason}", color = Color.White.copy(alpha = 0.68f), style = MaterialTheme.typography.labelSmall)
            }
            Column {
                FilledIconButton(onClick = onAdd) { Icon(Icons.Default.Add, contentDescription = "Hinzufügen") }
                FilledIconButton(onClick = onReject) { Icon(Icons.Default.Close, contentDescription = "Verwerfen") }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ScanCandidateSheet(
    candidate: ScanCandidate,
    onAdd: (CardPrint) -> Unit,
    onDismiss: () -> Unit,
) {
    var selected by remember(candidate.card.key.stableKey) {
        mutableStateOf(candidate.matchedPrint ?: candidate.card.prints.firstOrNull())
    }
    ModalBottomSheet(onDismissRequest = onDismiss) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .verticalScroll(rememberScrollState())
                .padding(18.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Row(horizontalArrangement = Arrangement.spacedBy(14.dp)) {
                CardThumbnail(
                    candidate.card.imageUrl,
                    candidate.card.name,
                    Modifier
                        .width(112.dp)
                        .height(164.dp),
                    fullArtwork = true,
                )
                Column(Modifier.weight(1f)) {
                    Text(candidate.card.name, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                    Text(candidate.reason, style = MaterialTheme.typography.bodySmall)
                    Text("Erkennungsscore ${candidate.score}", style = MaterialTheme.typography.labelSmall)
                }
            }
            HorizontalDivider()
            Text("Abgebildeten Druck bestätigen", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            candidate.card.prints.forEach { print ->
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable { selected = print }
                        .padding(vertical = 6.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    RadioButton(selected = selected?.stableKey == print.stableKey, onClick = { selected = print })
                    Column(Modifier.weight(1f)) {
                        Text("${print.setCode} · ${print.rarity}", fontWeight = FontWeight.SemiBold)
                        Text(print.setName, style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
            if (candidate.card.prints.isEmpty()) {
                Text("Kein Set verfügbar – die Karte wird nicht ohne Druckidentität gespeichert.", color = MaterialTheme.colorScheme.error)
            }
            Button(
                onClick = { selected?.let(onAdd) },
                enabled = selected != null,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Icon(Icons.Default.Add, contentDescription = null)
                Spacer(Modifier.width(8.dp))
                Text("Druck hinzufügen")
            }
            OutlinedButton(onClick = onDismiss, modifier = Modifier.fillMaxWidth()) { Text("Schließen") }
            Spacer(Modifier.height(18.dp))
        }
    }
}
