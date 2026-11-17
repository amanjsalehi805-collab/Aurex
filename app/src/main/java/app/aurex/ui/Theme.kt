package app.aurex.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import app.aurex.data.ThemeId

private fun c(hex: Long) = Color(0xFF000000 or hex)

private val Midnight = darkColorScheme(
    background = c(0x0A1628), surface = c(0x11223B), surfaceVariant = c(0x1A2F4D),
    primary = c(0x2DD4BF), secondary = c(0x3B82F6),
    onBackground = c(0xE6EEF8), onSurface = c(0xE6EEF8), onPrimary = c(0x04201C))
private val Obsidian = darkColorScheme(
    background = c(0x0B0B0B), surface = c(0x161616), surfaceVariant = c(0x222222),
    primary = c(0xD4AF37), secondary = c(0xB8962E),
    onBackground = c(0xF2EBD9), onSurface = c(0xF2EBD9), onPrimary = c(0x1A1405))
private val Arctic = lightColorScheme(
    background = c(0xFFFFFF), surface = c(0xF3F6FB), surfaceVariant = c(0xE3EAF5),
    primary = c(0x1D4ED8), secondary = c(0x0EA5E9),
    onBackground = c(0x0F172A), onSurface = c(0x0F172A), onPrimary = c(0xFFFFFF))
private val Cyber = darkColorScheme(
    background = c(0x0B0716), surface = c(0x150F26), surfaceVariant = c(0x211738),
    primary = c(0x22D3EE), secondary = c(0xA855F7),
    onBackground = c(0xECE8F8), onSurface = c(0xECE8F8), onPrimary = c(0x04202A))
private val Forest = darkColorScheme(
    background = c(0x06201A), surface = c(0x0B2E25), surfaceVariant = c(0x13403A),
    primary = c(0x34D399), secondary = c(0x86EFAC),
    onBackground = c(0xE4F5EC), onSurface = c(0xE4F5EC), onPrimary = c(0x03231A))

@Composable
fun AurexTheme(theme: ThemeId, content: @Composable () -> Unit) {
    val scheme = when (theme) {
        ThemeId.MIDNIGHT -> Midnight
        ThemeId.OBSIDIAN -> Obsidian
        ThemeId.ARCTIC -> Arctic
        ThemeId.CYBER -> Cyber
        ThemeId.FOREST -> Forest
    }
    MaterialTheme(colorScheme = scheme, content = content)
}
