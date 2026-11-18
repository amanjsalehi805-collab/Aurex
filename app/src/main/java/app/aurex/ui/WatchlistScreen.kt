package app.aurex.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import app.aurex.R
import app.aurex.data.MarketQuote

@Composable
fun WatchlistScreen(
    state: DashboardState,
    onToggleFavorite: (String) -> Unit,
) {
    val favorites = MarketWatchAssets.filter { it.id in state.favorites }
    val available = MarketWatchAssets.filter { it.id !in state.favorites }

    LazyColumn(
        modifier = Modifier.fillMaxWidth(),
        contentPadding = androidx.compose.foundation.layout.PaddingValues(
            horizontal = 16.dp,
            vertical = 16.dp,
        ),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            SectionHeader(R.string.watchlist_title)
        }

        if (favorites.isEmpty()) {
            item {
                AurexCard(modifier = Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(16.dp)) {
                        Text(
                            stringResource(R.string.watchlist_empty),
                            style = MaterialTheme.typography.titleMedium,
                        )
                        Text(
                            stringResource(R.string.watchlist_empty_body),
                            style = MaterialTheme.typography.bodyMedium,
                            color = LocalAurexColors.current.textSecondary,
                            modifier = Modifier.padding(top = 6.dp),
                        )
                    }
                }
            }
        } else {
            items(favorites, key = { it.id }) { asset ->
                WatchlistAssetRow(
                    asset = asset,
                    quote = state.quotes[asset.id],
                    loading = state.loading,
                    isFavorite = true,
                    onToggle = { onToggleFavorite(asset.id) },
                )
            }
        }

        item {
            SectionHeader(R.string.watchlist_available)
        }

        items(available, key = { it.id }) { asset ->
            WatchlistAssetRow(
                asset = asset,
                quote = state.quotes[asset.id],
                loading = state.loading,
                isFavorite = false,
                onToggle = { onToggleFavorite(asset.id) },
            )
        }
    }
}

@Composable
private fun WatchlistAssetRow(
    asset: AssetSpec,
    quote: MarketQuote?,
    loading: Boolean,
    isFavorite: Boolean,
    onToggle: () -> Unit,
) {
    AurexCard(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        stringResource(asset.nameRes),
                        style = MaterialTheme.typography.titleSmall,
                    )
                    if (quote != null) {
                        Text(
                            priceWithUnit(quote, 20),
                            style = MaterialTheme.typography.bodyMedium,
                        )
                    } else {
                        UnavailableText(loading)
                    }
                }

                TextButton(onClick = onToggle) {
                    Text(
                        stringResource(
                            if (isFavorite) R.string.watchlist_remove
                            else R.string.watchlist_add
                        )
                    )
                }
            }

            if (quote != null) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = 8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    FreshnessChip(quote.freshness)
                    Spacer(Modifier.width(10.dp))
                    ChangeText(quote.changePct)
                }
                SourceLine(quote)
            }
        }
    }
}
