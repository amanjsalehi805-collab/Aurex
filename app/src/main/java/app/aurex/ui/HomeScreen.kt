package app.aurex.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import app.aurex.R
import app.aurex.data.MarketQuote

private data class OverviewSpec(val titleRes: Int, val assetId: String)

private val OverviewItems = listOf(
    OverviewSpec(R.string.overview_currency, "usd_free_irt"),
    OverviewSpec(R.string.overview_gold, "gold18_irt"),
    OverviewSpec(R.string.overview_global, "gold_oz_usd"),
)

private val FeaturedPriority = listOf("usd_free_irt", "gold18_irt", "coin_irt", "gold_oz_usd")

@Composable
private fun overallStatus(state: DashboardState): Pair<String, Color> {
    val c = LocalAurexColors.current
    if (state.quotes.isEmpty()) {
        return when {
            state.loading -> stringResource(R.string.status_connecting) to c.textSecondary
            state.error != null -> stringResource(R.string.status_offline) to c.negative
            else -> stringResource(R.string.status_no_data) to c.textSecondary
        }
    }
    val values = state.quotes.values.map { state.freshnessOf(it) }
    return when {
        "cached" in values -> stringResource(R.string.status_cached) to c.warning
        "stale" in values -> stringResource(R.string.status_stale) to c.negative
        "delayed" in values -> stringResource(R.string.status_delayed) to c.warning
        values.all { it == "live" || it == "fresh" } ->
            stringResource(R.string.status_live) to c.positive
        else -> stringResource(R.string.status_unknown) to c.textSecondary
    }
}

@Composable
fun HomeScreen(
    state: DashboardState,
    onRefresh: () -> Unit,
    onOpenSettings: () -> Unit,
    onOpenConverter: () -> Unit,
    onOpenAsset: (String) -> Unit,
    onOpenAnalysis: () -> Unit,
    onLoadHistory: (String, Int) -> Unit,
) {
    LazyColumn(
        contentPadding = PaddingValues(horizontal = 16.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        item { AurexHeader(onConverter = onOpenConverter, onSettings = onOpenSettings) }
        item { StatusRow(state, onRefresh) }

        if (state.error != null) {
            item {
                ErrorBanner(
                    messageRes = apiErrorRes(state.error),
                    hasData = state.quotes.isNotEmpty(),
                    onRetry = onRefresh,
                )
            }
        }

        item {
            Column {
                SectionHeader(R.string.overview_title)
                Spacer(Modifier.height(10.dp))
                LazyRow(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    items(OverviewItems) { spec -> OverviewCard(spec, state, onOpenAsset) }
                }
            }
        }

        item { FeaturedCard(state, onOpenAsset, onLoadHistory) }

        item {
            Column {
                SectionHeader(R.string.watch_title)
                Spacer(Modifier.height(10.dp))
                MarketWatchCard(state, onOpenAsset)
            }
        }

        item { AiInsightCard(onOpenAnalysis) }
    }
}

@Composable
fun StatusRow(state: DashboardState, onRefresh: () -> Unit, showRefresh: Boolean = true) {
    val colors = LocalAurexColors.current
    val locale = LocalAppLocale.current
    val (label, color) = overallStatus(state)
    Column {
        Row(verticalAlignment = Alignment.CenterVertically) {
            StatusPill(label, color)
            Spacer(Modifier.weight(1f))
            if (state.loading) {
                CircularProgressIndicator(
                    modifier = Modifier.size(18.dp),
                    strokeWidth = 2.dp,
                    color = colors.gold,
                )
                Spacer(Modifier.width(8.dp))
                Text(
                    stringResource(R.string.refreshing),
                    style = MaterialTheme.typography.labelMedium,
                    color = colors.textSecondary,
                )
            } else if (showRefresh) {
                TextButton(
                    onClick = onRefresh,
                    colors = ButtonDefaults.textButtonColors(contentColor = colors.gold),
                ) {
                    Icon(Icons.Filled.Refresh, contentDescription = null, modifier = Modifier.size(18.dp))
                    Spacer(Modifier.width(6.dp))
                    Text(stringResource(R.string.refresh))
                }
            }
        }
        state.lastLoadedAtMillis?.let {
            Text(
                stringResource(R.string.last_refreshed, formatLocalTime(it, locale)),
                style = MaterialTheme.typography.labelSmall,
                color = colors.textSecondary,
            )
        }
    }
}

@Composable
private fun OverviewCard(spec: OverviewSpec, state: DashboardState, onOpenAsset: (String) -> Unit) {
    val colors = LocalAurexColors.current
    val quote = state.quotes[spec.assetId]
    AurexCard(modifier = Modifier.width(158.dp).clickable { onOpenAsset(spec.assetId) }) {
        Column(Modifier.padding(12.dp)) {
            Text(
                stringResource(spec.titleRes),
                style = MaterialTheme.typography.labelMedium,
                color = colors.gold,
            )
            Text(
                stringResource(assetNameRes(spec.assetId)),
                style = MaterialTheme.typography.bodySmall,
                color = colors.textSecondary,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
            Spacer(Modifier.height(8.dp))
            if (quote != null) {
                Text(priceWithUnit(quote, 17))
                Spacer(Modifier.height(2.dp))
                ChangeText(quote.changePct)
            } else {
                UnavailableText(loading = state.loading && state.quotes.isEmpty())
            }
        }
    }
}

@Composable
private fun FeaturedCard(
    state: DashboardState,
    onOpenAsset: (String) -> Unit,
    onLoadHistory: (String, Int) -> Unit,
) {
    val colors = LocalAurexColors.current
    val quote = FeaturedPriority.firstNotNullOfOrNull { state.quotes[it] }
    AurexCard(
        modifier = Modifier.fillMaxWidth().clickable(enabled = quote != null) {
            quote?.let { onOpenAsset(it.assetId) }
        },
        borderColor = colors.gold.copy(alpha = 0.35f),
    ) {
        Column(Modifier.padding(16.dp)) {
            SpreadRow {
                Text(
                    stringResource(R.string.featured_label),
                    style = MaterialTheme.typography.labelMedium,
                    color = colors.gold,
                )
                if (quote != null) FreshnessChip(state.freshnessOf(quote))
            }
            Spacer(Modifier.height(8.dp))
            if (quote == null) {
                Text(stringResource(R.string.asset_usd_free), style = MaterialTheme.typography.titleMedium)
                Spacer(Modifier.height(6.dp))
                UnavailableText(loading = state.loading && state.quotes.isEmpty())
            } else {
                LaunchedEffect(quote.assetId, state.lastLoadedAtMillis) {
                    onLoadHistory(quote.assetId, 24)
                }
                Text(
                    stringResource(assetNameRes(quote.assetId)),
                    style = MaterialTheme.typography.titleMedium,
                )
                Spacer(Modifier.height(6.dp))
                Text(priceWithUnit(quote, 30))
                Spacer(Modifier.height(4.dp))
                ChangeText(quote.changePct, MaterialTheme.typography.titleSmall)
                Spacer(Modifier.height(12.dp))
                HistoryChart(state.history[historyKey(quote.assetId, 24)], 84.dp)
                Spacer(Modifier.height(10.dp))
                SourceLine(quote)
            }
        }
    }
}

@Composable
private fun MarketWatchCard(state: DashboardState, onOpenAsset: (String) -> Unit) {
    val colors = LocalAurexColors.current
    AurexCard(modifier = Modifier.fillMaxWidth()) {
        MarketWatchAssets.forEachIndexed { index, spec ->
            MarketRow(
                nameRes = spec.nameRes,
                quote = state.quotes[spec.id],
                freshness = state.quotes[spec.id]?.let { state.freshnessOf(it) },
                loading = state.loading && state.quotes.isEmpty(),
                onClick = { onOpenAsset(spec.id) },
            )
            if (index < MarketWatchAssets.lastIndex) {
                HorizontalDivider(modifier = Modifier.padding(horizontal = 14.dp), color = colors.border)
            }
        }
    }
}

@Composable
private fun MarketRow(
    nameRes: Int,
    quote: MarketQuote?,
    freshness: String?,
    loading: Boolean,
    onClick: () -> Unit,
) {
    val colors = LocalAurexColors.current
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(horizontal = 14.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Text(
                stringResource(nameRes),
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.SemiBold,
            )
            if (quote != null && freshness != null) {
                Spacer(Modifier.height(5.dp))
                FreshnessChip(freshness)
                Spacer(Modifier.height(4.dp))
                Text(
                    listOfNotNull(quote.source, quoteTimeText(quote)).joinToString("  •  "),
                    style = MaterialTheme.typography.labelSmall,
                    color = colors.textSecondary,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
        Spacer(Modifier.width(12.dp))
        Column(horizontalAlignment = Alignment.End) {
            if (quote != null) {
                Text(priceWithUnit(quote, 16), textAlign = TextAlign.End)
                Spacer(Modifier.height(2.dp))
                ChangeText(quote.changePct)
            } else {
                UnavailableText(loading = loading)
            }
        }
    }
}

@Composable
private fun AiInsightCard(onOpen: () -> Unit) {
    val colors = LocalAurexColors.current
    AurexCard(
        modifier = Modifier.fillMaxWidth().clickable(onClick = onOpen),
        borderColor = colors.gold.copy(alpha = 0.45f),
    ) {
        Column(
            Modifier
                .background(Brush.horizontalGradient(listOf(colors.gold.copy(alpha = 0.10f), Color.Transparent)))
                .padding(16.dp)
        ) {
            Text(
                stringResource(R.string.home_ai_title),
                style = MaterialTheme.typography.titleSmall,
                color = colors.gold,
            )
            Spacer(Modifier.height(4.dp))
            Text(
                stringResource(R.string.home_ai_body),
                style = MaterialTheme.typography.bodySmall,
                color = colors.textSecondary,
            )
        }
    }
}
