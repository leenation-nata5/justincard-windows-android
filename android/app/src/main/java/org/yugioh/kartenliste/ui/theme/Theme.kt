package org.yugioh.kartenliste.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

val JicBlue = Color(0xFF4EA1FF)
val JicGold = Color(0xFFFFC857)
val JicNavy = Color(0xFF07131F)
val JicSurface = Color(0xFF101F2D)
val JicSurfaceHigh = Color(0xFF192C3D)

private val DarkColors = darkColorScheme(
    primary = JicBlue,
    onPrimary = Color(0xFF001D35),
    primaryContainer = Color(0xFF153D60),
    onPrimaryContainer = Color(0xFFD2E8FF),
    secondary = JicGold,
    onSecondary = Color(0xFF3E2E00),
    secondaryContainer = Color(0xFF594500),
    onSecondaryContainer = Color(0xFFFFE08D),
    background = JicNavy,
    onBackground = Color(0xFFE3EDF5),
    surface = JicSurface,
    onSurface = Color(0xFFE3EDF5),
    surfaceVariant = JicSurfaceHigh,
    onSurfaceVariant = Color(0xFFC4D3DF),
    outline = Color(0xFF8294A3),
    error = Color(0xFFFFB4AB),
)

private val LightColors = lightColorScheme(
    primary = Color(0xFF00629A),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFCDE5FF),
    onPrimaryContainer = Color(0xFF001D32),
    secondary = Color(0xFF755B00),
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFFFE08A),
    onSecondaryContainer = Color(0xFF241A00),
    background = Color(0xFFF6FAFD),
    onBackground = Color(0xFF17212A),
    surface = Color(0xFFFFFFFF),
    onSurface = Color(0xFF17212A),
    surfaceVariant = Color(0xFFE1EAF1),
    onSurfaceVariant = Color(0xFF414B53),
    outline = Color(0xFF717B84),
)

@Composable
fun JustInCardTheme(
    mode: String = "system",
    content: @Composable () -> Unit,
) {
    val dark = when (mode.lowercase()) {
        "dark" -> true
        "light" -> false
        else -> isSystemInDarkTheme()
    }
    MaterialTheme(
        colorScheme = if (dark) DarkColors else LightColors,
        content = content,
    )
}
