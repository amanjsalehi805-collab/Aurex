package app.aurex.ui

import android.app.Activity
import androidx.compose.material3.ColorScheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.text.font.FontWeight
import androidx.core.view.WindowCompat
import app.aurex.data.ThemeId

/** Semantic colors that Material's ColorScheme has no slot for. */
@Immutable
data class AurexColors(
    val gold: Color,
    val positive: Color,
    val negative: Color,
    val warning: Color,
    val elevated: Color,
    val textSecondary: Color,
    val border: Color,
)

private fun c(hex: Long) = Color(0xFF000000 or hex)

private val PositiveGreen = c(0x28B67A)
private val NegativeRed = c(0xE45C64)
private val WarningAmber = c(0xE0A23B)

// Midnight Professional: charcoal + muted gold
private val Midnight = darkColorScheme(
    background = c(0x0B0D10), surface = c(0x14181E), surfaceVariant = c(0x1B2028),
    primary = c(0xD6AD55), onPrimary = c(0x15110A), secondary = c(0xB8934A),
    onBackground = c(0xF4F4F2), onSurface = c(0xF4F4F2), onSurfaceVariant = c(0x9299A3),
    outline = c(0x2A313B), outlineVariant = c(0x222832),
    error = NegativeRed, onError = c(0x0B0D10))
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

private val MidnightExtras = AurexColors(
    gold = c(0xD6AD55), positive = PositiveGreen, negative = NegativeRed,
    warning = WarningAmber, elevated = c(0x1B2028),
    textSecondary = c(0x9299A3), border = c(0x262C35))

private fun extrasFor(scheme: ColorScheme) = AurexColors(
    gold = scheme.primary, positive = PositiveGreen, negative = NegativeRed,
    warning = WarningAmber, elevated = scheme.surfaceVariant,
    textSecondary = scheme.onSurface.copy(alpha = 0.65f),
    border = scheme.onSurface.copy(alpha = 0.12f))

val LocalAurexColors = staticCompositionLocalOf { MidnightExtras }

// No letter-spacing overrides: they break letter joining in Persian/Kurdish script.
private val AurexTypography = Typography().run {
    copy(
        titleLarge = titleLarge.copy(fontWeight = FontWeight.SemiBold),
        titleMedium = titleMedium.copy(fontWeight = FontWeight.SemiBold),
        titleSmall = titleSmall.copy(fontWeight = FontWeight.SemiBold),
    )
}

@Composable
fun AurexTheme(theme: ThemeId, content: @Composable () -> Unit) {
    val scheme = when (theme) {
        ThemeId.MIDNIGHT -> Midnight
        ThemeId.OBSIDIAN -> Obsidian
        ThemeId.ARCTIC -> Arctic
        ThemeId.CYBER -> Cyber
        ThemeId.FOREST -> Forest
    }
    val extras = if (theme == ThemeId.MIDNIGHT) MidnightExtras else extrasFor(scheme)

    // Keep status/navigation bar icons readable on the chosen theme.
    val view = LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as Activity).window
            val controller = WindowCompat.getInsetsController(window, view)
            val light = theme == ThemeId.ARCTIC
            controller.isAppearanceLightStatusBars = light
            controller.isAppearanceLightNavigationBars = light
        }
    }

    CompositionLocalProvider(LocalAurexColors provides extras) {
        MaterialTheme(colorScheme = scheme, typography = AurexTypography, content = content)
    }
}
