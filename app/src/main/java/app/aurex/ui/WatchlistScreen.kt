package app.aurex.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
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

/** Uses exactly the same quotes (and freshness logic) as Markets; it never produces separate data. */
@Composable
fun WatchlistScreen(
    state: DashboardState,
    onRefresh: () -> Unit,
    onToggleFavorite: (String) -> Unit,
    onMoveFavorite: (String, Int) -> Unit,
    onOpenAsset: (String) -> Unit,
) {
    val favorites = state.favorites.mapNotNull { id -> MarketWatchAssets.find { it.id == id } }
    val available = MarketWatchAssets.filter { it.id !in state.favorites }

    LazyColumn(
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            Text(stringResource(R.string.watchlist_title), style = MaterialTheme.typography.titleLarge)
        }
        item { StatusRow(state, onRefresh) }

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
            itemsIndexed(favorites, key = { _, asset -> "fav_" + asset.id }) { index, asset ->
                WatchlistAssetRow(
                    nameRes = asset.nameRes,
                    quote = state.quotes[asset.id],
                    freshness = state.quotes[asset.id]?.let { state.freshnessOf(it) },
                    loading = state.loading && state.quotes.isEmpty(),
                    isFavorite = true,
                    canMoveUp = index > 0,
                    canMoveDown = index < favorites.lastIndex,
                    onMoveUp = { onMoveFavorite(asset.id, -1) },
                    onMoveDown = { onMoveFavorite(asset.id, 1) },
                    onToggle = { onToggleFavorite(asset.id) },
                    onOpen = { onOpenAsset(asset.id) },
                )
            }
        }

        if (available.isNotEmpty()) {
            item { SectionHeader(R.string.watchlist_available) }
            items(available, key = { "add_" + it.id }) { asset ->
                WatchlistAssetRow(
                    nameRes = asset.nameRes,
                    quote = state.quotes[asset.id],
                    freshness = state.quotes[asset.id]?.let { state.freshnessOf(it) },
                    loading = state.loading && state.quotes.isEmpty(),
                    isFavorite = false,
                    onToggle = { onToggleFavorite(asset.id) },
                    onOpen = { onOpenAsset(asset.id) },
                )
            }
        }
    }
}

@Composable
private fun WatchlistAssetRow(
    nameRes: Int,
    quote: MarketQuote?,
    freshness: String?,
    loading: Boolean,
    isFavorite: Boolean,
    canMoveUp: Boolean = false,
    canMoveDown: Boolean = false,
    onMoveUp: () -> Unit = {},
    onMoveDown: () -> Unit = {},
    onToggle: () -> Unit,
    onOpen: () -> Unit,
) {
    AurexCard(modifier = Modifier.fillMaxWidth().clickable(onClick = onOpen)) {
        Column(Modifier.padding(14.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(stringResource(nameRes), style = MaterialTheme.typography.titleSmall)
                    if (quote != null) {
                        Text(priceWithUnit(quote, 20), style = MaterialTheme.typography.bodyMedium)
                    } else {
                        UnavailableText(loading)
                    }
                }
                if (isFavorite) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Row {
                            TextButton(
                                onClick = onMoveUp,
                                enabled = canMoveUp,
                            ) { Text(stringResource(R.string.watchlist_move_up)) }
                            TextButton(
                                onClick = onMoveDown,
                                enabled = canMoveDown,
                            ) { Text(stringResource(R.string.watchlist_move_down)) }
                        }
                        TextButton(onClick = onToggle) {
                            Text(stringResource(R.string.watchlist_remove))
                        }
                    }
                } else {
                    TextButton(onClick = onToggle) {
                        Text(stringResource(R.string.watchlist_add))
                    }
                }
            }

            if (quote != null && freshness != null) {
                Row(
                    modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    FreshnessChip(freshness)
                    Spacer(Modifier.width(10.dp))
                    ChangeText(quote.changePct)
                }
                SourceLine(quote)
            }
        }
    }
}
