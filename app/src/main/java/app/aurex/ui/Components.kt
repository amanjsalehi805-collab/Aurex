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
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Notifications
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
import androidx.compose.ui.graphics.Color
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
fun AurexHeader(onNotifications: () -> Unit, onSettings: () -> Unit) {
    val colors = LocalAurexColors.current
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Box(
            Modifier
                .size(40.dp)
                .clip(RoundedCornerShape(10.dp))
                .background(
                    Brush.linearGradient(
                        listOf(colors.elevated, MaterialTheme.colorScheme.background)
                    )
                )
                .border(1.dp, colors.gold.copy(alpha = 0.7f), RoundedCornerShape(10.dp)),
            contentAlignment = Alignment.Center,
        ) {
            Text("AX", color = colors.gold, fontWeight = FontWeight.Bold, fontSize = 14.sp)
        }
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            Text(
                stringResource(R.string.app_name),
                style = MaterialTheme.typography.titleLarge,
                letterSpacing = 2.sp,
            )
            Text(
                stringResource(R.string.tagline),
                style = MaterialTheme.typography.labelSmall,
                color = colors.textSecondary,
            )
        }
        IconButton(onClick = onNotifications) {
            Icon(
                Icons.Filled.Notifications,
                contentDescription = stringResource(R.string.cd_notifications),
                tint = colors.textSecondary,
            )
        }
        IconButton(onClick = onSettings) {
            Icon(
                Icons.Filled.Settings,
                contentDescription = stringResource(R.string.cd_settings),
                tint = colors.textSecondary,
            )
        }
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
        "$arrow ${formatPercent(changePct)}",
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
    else -> unit
}

@Composable
fun priceWithUnit(quote: MarketQuote, priceSizeSp: Int): AnnotatedString {
    val unit = unitLabel(quote.unit)
    val secondary = LocalAurexColors.current.textSecondary
    return buildAnnotatedString {
        withStyle(SpanStyle(fontSize = priceSizeSp.sp, fontWeight = FontWeight.Bold)) {
            append(formatPrice(quote.price))
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
        sourceMs != null -> stringResource(R.string.updated_at, formatLocalTime(sourceMs))
        fetchedMs != null -> stringResource(R.string.fetched_at, formatLocalTime(fetchedMs))
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
