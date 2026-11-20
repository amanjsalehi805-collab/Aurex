package app.aurex.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import app.aurex.data.ApiException
import app.aurex.data.HistoryData
import app.aurex.data.HistoryRepository
import app.aurex.data.MarketQuote
import app.aurex.data.PreferencesRepository
import app.aurex.data.QuoteRepository
import app.aurex.data.StocksRepository
import app.aurex.data.StocksStatus
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class HistoryUi(
    val loading: Boolean = false,
    val data: HistoryData? = null,
    val error: Boolean = false,
)

data class StocksUi(
    val loading: Boolean = true,
    val status: StocksStatus? = null,
    val error: Boolean = false,
)

data class DashboardState(
    val quotes: Map<String, MarketQuote> = emptyMap(),
    val unavailable: Set<String> = emptySet(),
    val staleAfterSeconds: Long = 900L,
    val favorites: List<String> = emptyList(),
    val loading: Boolean = true,
    /** Stable error code from [ApiException] (e.g. "network", "timeout"). */
    val error: String? = null,
    val lastLoadedAtMillis: Long? = null,
    val isFromCache: Boolean = false,
    val nowMillis: Long = System.currentTimeMillis(),
    /** key = "assetId|hours" */
    val history: Map<String, HistoryUi> = emptyMap(),
    val stocks: StocksUi = StocksUi(),
)

fun historyKey(assetId: String, hours: Int) = "$assetId|$hours"

/**
 * What the UI should call this quote's freshness. A cached or old quote is never presented as live:
 *  - data restored from the offline cache is always "cached"
 *  - a quote whose source/fetch time is older than the server's stale threshold is "stale"
 */
fun DashboardState.freshnessOf(quote: MarketQuote): String {
    if (isFromCache) return "cached"
    val ref = parseIsoUtcMillis(quote.sourceTimestamp) ?: parseIsoUtcMillis(quote.fetchedAt)
    if (ref != null && nowMillis - ref > staleAfterSeconds * 1000L) return "stale"
    return quote.freshness
}

class DashboardViewModel(application: Application) : AndroidViewModel(application) {
    private val repository = QuoteRepository()
    private val historyRepository = HistoryRepository()
    private val stocksRepository = StocksRepository()
    private val preferences = PreferencesRepository(application)

    private val _state = MutableStateFlow(DashboardState())
    val state: StateFlow<DashboardState> = _state.asStateFlow()

    private var job: Job? = null

    init {
        viewModelScope.launch {
            preferences.favorites.collect { favorites ->
                _state.update { it.copy(favorites = favorites) }
            }
        }

        // Lets "stale" be re-evaluated while the app stays open.
        viewModelScope.launch {
            while (true) {
                delay(30_000)
                _state.update { it.copy(nowMillis = System.currentTimeMillis()) }
            }
        }

        viewModelScope.launch {
            try {
                val cached = preferences.loadQuotesCache()
                if (cached != null) {
                    _state.update {
                        it.copy(
                            quotes = cached.quotes.associateBy { quote -> quote.assetId },
                            lastLoadedAtMillis = cached.savedAtMillis,
                            isFromCache = true,
                        )
                    }
                }
            } catch (e: CancellationException) {
                throw e
            } catch (_: Exception) {
                // A cache problem must not prevent a network refresh.
            }

            refresh()
        }
        loadStocks()
    }

    fun toggleFavorite(assetId: String) {
        val currentlyFavorite = assetId in _state.value.favorites
        viewModelScope.launch {
            preferences.setFavorite(assetId, !currentlyFavorite)
        }
    }

    fun moveFavorite(assetId: String, offset: Int) {
        viewModelScope.launch {
            preferences.moveFavorite(assetId, offset)
        }
    }

    fun refresh() {
        if (job?.isActive == true) return

        job = viewModelScope.launch {
            _state.update { it.copy(loading = true, error = null) }

            try {
                val result = repository.fetchQuotes()
                if (result.quotes.isNotEmpty()) {
                    preferences.saveQuotesCache(result.quotes)
                }
                _state.update {
                    it.copy(
                        quotes = result.quotes.associateBy { quote -> quote.assetId },
                        unavailable = result.unavailable,
                        staleAfterSeconds = result.staleAfterSeconds,
                        loading = false,
                        lastLoadedAtMillis = System.currentTimeMillis(),
                        nowMillis = System.currentTimeMillis(),
                        isFromCache = false,
                        error = null,
                    )
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                // Keep whatever we already show (cache or last good data) and say that refresh failed.
                _state.update {
                    it.copy(loading = false, error = (e as? ApiException)?.code ?: "network")
                }
            }
        }
    }

    fun loadHistory(assetId: String, hours: Int) {
        val key = historyKey(assetId, hours)
        if (_state.value.history[key]?.loading == true) return
        _state.update { it.copy(history = it.history + (key to HistoryUi(loading = true, data = it.history[key]?.data))) }
        viewModelScope.launch {
            try {
                val data = historyRepository.fetch(assetId, hours)
                _state.update { it.copy(history = it.history + (key to HistoryUi(data = data))) }
            } catch (e: CancellationException) {
                throw e
            } catch (_: Exception) {
                _state.update {
                    it.copy(history = it.history + (key to HistoryUi(data = it.history[key]?.data, error = true)))
                }
            }
        }
    }

    fun loadStocks() {
        viewModelScope.launch {
            _state.update { it.copy(stocks = it.stocks.copy(loading = true, error = false)) }
            try {
                val status = stocksRepository.status()
                _state.update { it.copy(stocks = StocksUi(loading = false, status = status)) }
            } catch (e: CancellationException) {
                throw e
            } catch (_: Exception) {
                _state.update { it.copy(stocks = StocksUi(loading = false, status = null, error = true)) }
            }
        }
    }
}
