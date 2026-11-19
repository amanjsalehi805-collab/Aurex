package app.aurex.ui

import androidx.compose.runtime.staticCompositionLocalOf
import java.math.BigDecimal
import java.text.DateFormat
import java.text.NumberFormat
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone
import kotlin.math.abs

/** Current app language locale; provided by AurexTheme so numbers follow the chosen language. */
val LocalAppLocale = staticCompositionLocalOf { Locale.getDefault() }

fun formatPrice(value: Double, locale: Locale = Locale.getDefault()): String {
    val nf = NumberFormat.getNumberInstance(locale)
    nf.minimumFractionDigits = 0
    nf.maximumFractionDigits = if (abs(value) >= 100_000) 0 else 2
    return nf.format(value)
}

fun formatPercent(value: Double, locale: Locale = Locale.getDefault()): String {
    val nf = NumberFormat.getNumberInstance(locale)
    nf.minimumFractionDigits = 2
    nf.maximumFractionDigits = 2
    return nf.format(abs(value)) + "%"
}

/** Exact decimal formatting with grouping; trailing zeros trimmed down to [minFrac]. */
fun formatDecimal(value: BigDecimal, maxFrac: Int, locale: Locale = Locale.getDefault()): String {
    val nf = NumberFormat.getNumberInstance(locale)
    nf.minimumFractionDigits = 0
    nf.maximumFractionDigits = maxFrac
    nf.isGroupingUsed = true
    return nf.format(value)
}

fun formatInt(value: Int, locale: Locale = Locale.getDefault()): String =
    NumberFormat.getIntegerInstance(locale).format(value)

/** Parses backend ISO-8601 UTC timestamps such as 2026-11-18T10:07:47.793476Z. */
fun parseIsoUtcMillis(value: String?): Long? {
    if (value.isNullOrBlank() || value.length < 19) return null
    return try {
        val fmt = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.US)
        fmt.timeZone = TimeZone.getTimeZone("UTC")
        fmt.parse(value.take(19))?.time
    } catch (e: Exception) {
        null
    }
}

fun formatLocalTime(millis: Long, locale: Locale = Locale.getDefault()): String =
    DateFormat.getTimeInstance(DateFormat.SHORT, locale).format(Date(millis))

fun formatLocalDateTime(millis: Long, locale: Locale = Locale.getDefault()): String =
    DateFormat.getDateTimeInstance(DateFormat.SHORT, DateFormat.SHORT, locale).format(Date(millis))

/** "fa", "ckb" or "en" (anything else is treated as English for backend language hints). */
fun languageTag(locale: Locale): String = when (locale.language) {
    "fa" -> "fa"
    "ckb" -> "ckb"
    else -> "en"
}
