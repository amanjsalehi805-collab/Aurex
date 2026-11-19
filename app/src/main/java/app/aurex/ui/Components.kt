package app.aurex.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.aurex.R
import app.aurex.data.HistoryPoint
import app.aurex.data.MarketQuote

@Composable
fun AurexCard(
    modifier: Modifier = Modifier,
    borderColor: Color = LocalAurexColors.current.border,
    content: @Composable ColumnScope.() -> Unit,
) {
    Surface(
        modifier = modifier,
        shape = RoundedCornerShape(10.dp),
        color = MaterialTheme.colorScheme.surface,
        border = BorderStroke(1.dp, borderColor),
    ) {
        Column(content = content)
    }
}

@Composable
fun SectionHeader(textRes: Int) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Box(
            Modifier
                .width(3.dp)
                .height(14.dp)
                .clip(RoundedCornerShape(2.dp))
                .background(LocalAurexColors.current.gold)
        )
        Spacer(Modifier.width(8.dp))
        Text(stringResource(textRes), style = MaterialTheme.typography.titleSmall)
    }
}

@Composable
fun AurexHeader(onConverter: () -> Unit, onSettings: () -> Unit) {
    val colors = LocalAurexColors.current
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        AurexLogo(size = 44.dp)
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            Text(
                stringResource(R.string.app_name),
                style = MaterialTheme.typography.titleLarge,
            )
            Text(
                stringResource(R.string.tagline),
                style = MaterialTheme.typography.labelSmall,
                color = colors.textSecondary,
            )
        }
        ConverterButton(onConverter)
        IconButton(onClick = onSettings) {
            Icon(
                Icons.Filled.Settings,
                contentDescription = stringResource(R.string.cd_settings),
                tint = colors.textSecondary,
            )
        }
    }
}

/** "$" is available in every font, so no icon dependency is needed. */
@Composable
fun ConverterButton(onClick: () -> Unit) {
    IconButton(onClick = onClick) {
        Text(
            "$",
            color = LocalAurexColors.current.gold,
            fontWeight = FontWeight.Bold,
            fontSize = 22.sp,
        )
    }
}

/** Simple vertical arrow drawn on a canvas (direction-neutral, no icon dependency). */
@Composable
fun ArrowGlyph(up: Boolean, tint: Color, modifier: Modifier = Modifier) {
    Canvas(modifier.size(18.dp)) {
        val w = size.width
        val h = size.height
        val stroke = 2.2f * density
        val tip = if (up) 2f * density else h - 2f * density
        val tail = if (up) h - 2f * density else 2f * density
        val dir = if (up) 1f else -1f
        drawLine(tint, Offset(w / 2, tail), Offset(w / 2, tip), strokeWidth = stroke, cap = StrokeCap.Round)
        val head = Path().apply {
            moveTo(w * 0.2f, tip + dir * h * 0.3f)
            lineTo(w / 2, tip)
            lineTo(w * 0.8f, tip + dir * h * 0.3f)
        }
        drawPath(head, tint, style = Stroke(stroke, cap = StrokeCap.Round, join = StrokeJoin.Round))
    }
}

/** Real price line from recorded history. Draws nothing when there are fewer than 2 points. */
@Composable
fun PriceChart(
    points: List<HistoryPoint>,
    modifier: Modifier = Modifier,
    lineColor: Color = LocalAurexColors.current.gold,
) {
    Canvas(modifier) {
        if (points.size < 2) return@Canvas
        val minP = points.minOf { it.price }
        val maxP = points.maxOf { it.price }
        val t0 = points.first().ts
        val dt = (points.last().ts - t0).coerceAtLeast(1L).toFloat()
        val pad = 6f * density
        val w = size.width - 2 * pad
        val h = size.height - 2 * pad
        fun px(ts: Long) = pad + (ts - t0).toFloat() / dt * w
        fun py(price: Double) =
            if (maxP == minP) pad + h / 2 else pad + (1f - ((price - minP) / (maxP - minP)).toFloat()) * h
        val line = Path()
        points.forEachIndexed { i, p ->
            if (i == 0) line.moveTo(px(p.ts), py(p.price)) else line.lineTo(px(p.ts), py(p.price))
        }
        val fill = Path().apply {
            points.forEachIndexed { i, p ->
                if (i == 0) moveTo(px(p.ts), py(p.price)) else lineTo(px(p.ts), py(p.price))
            }
            lineTo(px(points.last().ts), size.height - pad)
            lineTo(px(points.first().ts), size.height - pad)
            close()
        }
        drawPath(fill, Brush.verticalGradient(listOf(lineColor.copy(alpha = 0.22f), Color.Transparent)))
        drawPath(line, lineColor, style = Stroke(2f * density, cap = StrokeCap.Round, join = StrokeJoin.Round))
        val last = points.last()
        drawCircle(lineColor, radius = 3.5f * density, center = Offset(px(last.ts), py(last.price)))
    }
}

@Composable
fun StatusPill(label: String, color: Color) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = Modifier
            .clip(RoundedCornerShape(50))
            .background(color.copy(alpha = 0.12f))
            .padding(horizontal = 10.dp, vertical = 5.dp),
    ) {
        Box(
            Modifier
                .size(7.dp)
                .clip(CircleShape)
                .background(color)
        )
        Spacer(Modifier.width(6.dp))
        Text(label, style = MaterialTheme.typography.labelMedium, color = color)
    }
}

@Composable
fun FreshnessChip(freshness: String) {
    val c = LocalAurexColors.current
    val (label, color) = when (freshness) {
        "live", "fresh" -> stringResource(R.string.fresh_live) to c.positive
        "delayed" -> stringResource(R.string.fresh_delayed) to c.warning
        "stale" -> stringResource(R.string.fresh_stale) to c.negative
        "cached" -> stringResource(R.string.fresh_cached) to c.warning
        "historical" -> stringResource(R.string.fresh_historical) to c.textSecondary
        else -> stringResource(R.string.fresh_unknown) to c.textSecondary
    }
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = Modifier
            .clip(RoundedCornerShape(50))
            .background(color.copy(alpha = 0.12f))
            .padding(horizontal = 8.dp, vertical = 3.dp),
    ) {
        Box(
            Modifier
                .size(6.dp)
                .clip(CircleShape)
                .background(color)
        )
        Spacer(Modifier.width(5.dp))
        Text(label, style = MaterialTheme.typography.labelSmall, color = color)
    }
}

@Composable
fun ChangeText(
    changePct: Double?,
    style: TextStyle = MaterialTheme.typography.bodySmall,
) {
    val colors = LocalAurexColors.current
    if (changePct == null) {
        Text(
            stringResource(R.string.change_unavailable),
            style = style,
            color = colors.textSecondary,
        )
        return
    }
    val (color, arrow) = when {
        changePct > 0 -> colors.positive to "▲"
        changePct < 0 -> colors.negative to "▼"
        else -> colors.textSecondary to "–"
    }
    Text(
        "$arrow ${formatPercent(changePct, LocalAppLocale.current)}",
        style = style,
        color = color,
        fontWeight = FontWeight.SemiBold,
    )
}

@Composable
fun unitLabel(unit: String): String = when (unit) {
    "IRT" -> stringResource(R.string.unit_irt)
    "IRR" -> stringResource(R.string.unit_irr)
    "USD" -> stringResource(R.string.unit_usd)
    "EUR" -> stringResource(R.string.unit_eur)
    else -> unit
}

@Composable
fun priceWithUnit(quote: MarketQuote, priceSizeSp: Int): AnnotatedString {
    val unit = unitLabel(quote.unit)
    val secondary = LocalAurexColors.current.textSecondary
    return buildAnnotatedString {
        withStyle(SpanStyle(fontSize = priceSizeSp.sp, fontWeight = FontWeight.Bold)) {
            append(formatPrice(quote.price, LocalAppLocale.current))
        }
        append("  ")
        withStyle(SpanStyle(fontSize = 13.sp, color = secondary)) {
            append(unit)
        }
    }
}

@Composable
fun quoteTimeText(quote: MarketQuote): String? {
    val sourceMs = parseIsoUtcMillis(quote.sourceTimestamp)
    val fetchedMs = parseIsoUtcMillis(quote.fetchedAt)
    return when {
        sourceMs != null -> stringResource(R.string.updated_at, formatLocalTime(sourceMs, LocalAppLocale.current))
        fetchedMs != null -> stringResource(R.string.fetched_at, formatLocalTime(fetchedMs, LocalAppLocale.current))
        else -> null
    }
}

@Composable
fun SourceLine(quote: MarketQuote) {
    val colors = LocalAurexColors.current
    val uriHandler = LocalUriHandler.current
    val isTalasanj = quote.source.equals("Talasanj", ignoreCase = true)
    val text = listOfNotNull(
        stringResource(R.string.source_label, quote.source),
        quoteTimeText(quote),
    ).joinToString("  •  ")
    Text(
        text,
        style = MaterialTheme.typography.labelSmall,
        color = if (isTalasanj) colors.gold else colors.textSecondary,
        maxLines = 2,
        overflow = TextOverflow.Ellipsis,
        modifier = if (isTalasanj) {
            Modifier.clickable { uriHandler.openUri("https://talasanj.info") }
        } else {
            Modifier
        },
    )
}

@Composable
fun UnavailableText(loading: Boolean) {
    Text(
        stringResource(if (loading) R.string.loading_short else R.string.unavailable),
        style = MaterialTheme.typography.bodySmall,
        color = LocalAurexColors.current.textSecondary,
    )
}

@Composable
fun ChipLabel(text: String) {
    val colors = LocalAurexColors.current
    Text(
        text,
        style = MaterialTheme.typography.labelSmall,
        color = colors.gold,
        modifier = Modifier
            .clip(RoundedCornerShape(50))
            .background(colors.gold.copy(alpha = 0.12f))
            .padding(horizontal = 10.dp, vertical = 4.dp),
    )
}

@Composable
fun SpreadRow(
    modifier: Modifier = Modifier,
    content: @Composable () -> Unit,
) {
    Row(
        modifier = modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) { content() }
}
