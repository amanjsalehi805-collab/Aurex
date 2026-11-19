package app.aurex.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Star
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import app.aurex.R
import app.aurex.data.MarketQuote

@Composable
fun MarketsScreen(
    state: DashboardState,
    onRefresh: () -> Unit,
    onOpenConverter: () -> Unit,
    onOpenAsset: (String) -> Unit,
    onToggleFavorite: (String) -> Unit,
    onReloadStocks: () -> Unit,
) {
    val colors = LocalAurexColors.current
    LazyColumn(
        contentPadding = PaddingValues(horizontal = 16.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    stringResource(R.string.nav_markets),
                    style = MaterialTheme.typography.titleLarge,
                    modifier = Modifier.weight(1f),
                )
                IconButton(onClick = onRefresh, enabled = !state.loading) {
                    Icon(
                        Icons.Filled.Refresh,
                        contentDescription = stringResource(R.string.refresh),
                        tint = if (state.loading) colors.textSecondary else colors.gold,
                    )
                }
                ConverterButton(onOpenConverter)
            }
        }
        item { StatusRow(state, onRefresh) }
        if (state.error != null) {
            item {
                ErrorBanner(apiErrorRes(state.error), hasData = state.quotes.isNotEmpty(), onRetry = onRefresh)
            }
        }
        items(MarketWatchAssets, key = { it.id }) { spec ->
            AssetCard(
                nameRes = spec.nameRes,
                quote = state.quotes[spec.id],
                freshness = state.quotes[spec.id]?.let { state.freshnessOf(it) },
                loading = state.loading && state.quotes.isEmpty(),
                isFavorite = spec.id in state.favorites,
                onClick = { onOpenAsset(spec.id) },
                onToggleFavorite = { onToggleFavorite(spec.id) },
            )
        }
        item { SectionHeader(R.string.markets_stocks_title) }
        item { StocksCard(state.stocks, onReloadStocks) }
    }
}

@Composable
private fun AssetCard(
    nameRes: Int,
    quote: MarketQuote?,
    freshness: String?,
    loading: Boolean,
    isFavorite: Boolean,
    onClick: () -> Unit,
    onToggleFavorite: () -> Unit,
) {
    val colors = LocalAurexColors.current
    AurexCard(modifier = Modifier.fillMaxWidth().clickable(onClick = onClick)) {
        Row(
            Modifier.padding(start = 14.dp, top = 10.dp, bottom = 10.dp, end = 4.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1f)) {
                Text(
                    stringResource(nameRes),
                    style = MaterialTheme.typography.titleSmall,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
                if (quote != null && freshness != null) {
                    Spacer(Modifier.height(5.dp))
                    FreshnessChip(freshness)
                    Spacer(Modifier.height(4.dp))
                    SourceLine(quote)
                }
            }
            Spacer(Modifier.width(10.dp))
            Column(horizontalAlignment = Alignment.End) {
                if (quote != null) {
                    Text(priceWithUnit(quote, 17), textAlign = TextAlign.End)
                    Spacer(Modifier.height(2.dp))
                    ChangeText(quote.changePct)
                } else {
                    UnavailableText(loading)
                }
            }
            IconButton(onClick = onToggleFavorite) {
                Icon(
                    Icons.Filled.Star,
                    contentDescription = stringResource(
                        if (isFavorite) R.string.watchlist_remove else R.string.watchlist_add
                    ),
                    tint = if (isFavorite) colors.gold else colors.textSecondary.copy(alpha = 0.5f),
                )
            }
        }
    }
}

@Composable
private fun StocksCard(stocks: StocksUi, onReload: () -> Unit) {
    val colors = LocalAurexColors.current
    val locale = LocalAppLocale.current
    AurexCard(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp)) {
            val status = stocks.status
            when {
                stocks.loading -> UnavailableText(loading = true)
                stocks.error || status == null -> {
                    Text(stringResource(R.string.stocks_unreachable), style = MaterialTheme.typography.bodyMedium)
                    TextButton(
                        onClick = onReload,
                        colors = ButtonDefaults.textButtonColors(contentColor = colors.gold),
                    ) { Text(stringResource(R.string.error_retry)) }
                }
                status?.providerConfigured == false -> {
                    Text(stringResource(R.string.stocks_no_provider), style = MaterialTheme.typography.bodyMedium)
                    Spacer(Modifier.height(6.dp))
                    Text(
                        stringResource(R.string.stocks_infra),
                        style = MaterialTheme.typography.bodySmall,
                        color = colors.textSecondary,
                    )
                }
                else -> Text(
                    stringResource(R.string.stocks_connected_note),
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
            if (status != null && !stocks.loading) {
                Spacer(Modifier.height(8.dp))
                Text(
                    stringResource(R.string.stocks_symbols_count, formatInt(status.symbolCount, locale)),
                    style = MaterialTheme.typography.labelSmall,
                    color = colors.textSecondary,
                )
            }
        }
    }
}

private val ranges = listOf(24 to R.string.chart_range_24h, 168 to R.string.chart_range_7d, 720 to R.string.chart_range_30d)

@Composable
fun AssetDetailScreen(
    assetId: String,
    state: DashboardState,
    onBack: () -> Unit,
    onRefresh: () -> Unit,
    onToggleFavorite: (String) -> Unit,
    onLoadHistory: (String, Int) -> Unit,
) {
    val colors = LocalAurexColors.current
    val locale = LocalAppLocale.current
    val quote = state.quotes[assetId]
    var hours by rememberSaveable { mutableStateOf(24) }
    LaunchedEffect(assetId, hours, state.lastLoadedAtMillis) { onLoadHistory(assetId, hours) }
    val history = state.history[historyKey(assetId, hours)]
    val summary = history?.data?.summary

    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 16.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = onBack) {
                Icon(
                    Icons.AutoMirrored.Filled.ArrowBack,
                    contentDescription = stringResource(R.string.cd_back),
                    tint = colors.textSecondary,
                )
            }
            Text(
                stringResource(assetNameRes(assetId)),
                style = MaterialTheme.typography.titleLarge,
                modifier = Modifier.weight(1f),
            )
            IconButton(onClick = { onToggleFavorite(assetId) }) {
                Icon(
                    Icons.Filled.Star,
                    contentDescription = stringResource(
                        if (assetId in state.favorites) R.string.watchlist_remove else R.string.watchlist_add
                    ),
                    tint = if (assetId in state.favorites) colors.gold else colors.textSecondary.copy(alpha = 0.5f),
                )
            }
        }

        AurexCard(Modifier.fillMaxWidth(), borderColor = colors.gold.copy(alpha = 0.35f)) {
            Column(Modifier.padding(16.dp)) {
                if (quote == null) {
                    Text(stringResource(R.string.unavailable), style = MaterialTheme.typography.titleMedium)
                    Spacer(Modifier.height(6.dp))
                    Text(
                        stringResource(R.string.detail_unavailable_body),
                        style = MaterialTheme.typography.bodySmall,
                        color = colors.textSecondary,
                    )
                    TextButton(
                        onClick = onRefresh,
                        colors = ButtonDefaults.textButtonColors(contentColor = colors.gold),
                    ) { Text(stringResource(R.string.refresh)) }
                } else {
                    SpreadRow {
                        Text(
                            stringResource(R.string.detail_price),
                            style = MaterialTheme.typography.labelMedium,
                            color = colors.gold,
                        )
                        FreshnessChip(state.freshnessOf(quote))
                    }
                    Spacer(Modifier.height(6.dp))
                    Text(priceWithUnit(quote, 32))
                    Spacer(Modifier.height(6.dp))
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            stringResource(R.string.detail_provider_change),
                            style = MaterialTheme.typography.labelSmall,
                            color = colors.textSecondary,
                        )
                        Spacer(Modifier.width(8.dp))
                        ChangeText(quote.changePct)
                    }
                    if ("unusual_change" in quote.flags) {
                        Spacer(Modifier.height(6.dp))
                        Text(
                            stringResource(R.string.detail_unusual_change),
                            style = MaterialTheme.typography.labelSmall,
                            color = colors.warning,
                        )
                    }
                    Spacer(Modifier.height(10.dp))
                    SourceLine(quote)
                }
            }
        }

        AurexCard(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp)) {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    ranges.forEach { (h, labelRes) ->
                        FilterChip(
                            selected = hours == h,
                            onClick = { hours = h },
                            label = { Text(stringResource(labelRes)) },
                            colors = FilterChipDefaults.filterChipColors(
                                selectedContainerColor = colors.gold.copy(alpha = 0.18f),
                                selectedLabelColor = colors.gold,
                            ),
                        )
                    }
                }
                Spacer(Modifier.height(12.dp))
                HistoryChart(history, 160.dp)
                if (summary != null && summary.points > 0) {
                    Spacer(Modifier.height(10.dp))
                    Text(
                        stringResource(
                            R.string.history_recorded,
                            formatInt(summary.points, locale),
                            spanText(summary.spanSeconds),
                        ),
                        style = MaterialTheme.typography.labelSmall,
                        color = colors.textSecondary,
                    )
                    val unit = quote?.unit
                    if (summary.sufficient && summary.min != null && summary.max != null) {
                        Spacer(Modifier.height(4.dp))
                        Text(
                            stringResource(
                                R.string.history_low_high,
                                formatPrice(summary.min, locale),
                                formatPrice(summary.max, locale),
                            ) + if (unit != null) "  " + unitLabel(unit) else "",
                            style = MaterialTheme.typography.bodySmall,
                        )
                        Spacer(Modifier.height(4.dp))
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(
                                stringResource(R.string.history_change_label),
                                style = MaterialTheme.typography.bodySmall,
                            )
                            Spacer(Modifier.width(8.dp))
                            ChangeText(summary.changePct)
                        }
                    }
                }
                Spacer(Modifier.height(8.dp))
                Text(
                    stringResource(R.string.history_note),
                    style = MaterialTheme.typography.labelSmall,
                    color = colors.textSecondary,
                    fontWeight = FontWeight.Normal,
                )
            }
        }
    }
}
