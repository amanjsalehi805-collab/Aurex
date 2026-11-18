package app.aurex.ui

import java.text.DateFormat
import java.text.NumberFormat
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone
import kotlin.math.abs

fun formatPrice(value: Double): String {
    val nf = NumberFormat.getNumberInstance()
    nf.minimumFractionDigits = 0
    nf.maximumFractionDigits = if (abs(value) >= 100_000) 0 else 2
    return nf.format(value)
}

fun formatPercent(value: Double): String {
    val nf = NumberFormat.getNumberInstance()
    nf.minimumFractionDigits = 2
    nf.maximumFractionDigits = 2
    return nf.format(abs(value)) + "%"
}

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

fun formatLocalTime(millis: Long): String =
    DateFormat.getTimeInstance(DateFormat.SHORT).format(Date(millis))
