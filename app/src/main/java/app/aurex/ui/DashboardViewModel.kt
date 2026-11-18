package app.aurex.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import app.aurex.data.MarketQuote
import app.aurex.data.PreferencesRepository
import app.aurex.data.QuoteRepository
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class DashboardState(
    val quotes: Map<String, MarketQuote> = emptyMap(),
    val favorites: Set<String> = emptySet(),
    val loading: Boolean = true,
    val error: String? = null,
    val lastLoadedAtMillis: Long? = null,
    val isFromCache: Boolean = false,
)

class DashboardViewModel(application: Application) : AndroidViewModel(application) {
    private val repository = QuoteRepository()
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
    }

    fun toggleFavorite(assetId: String) {
        val currentlyFavorite = assetId in _state.value.favorites
        viewModelScope.launch {
            preferences.setFavorite(assetId, !currentlyFavorite)
        }
    }

    fun refresh() {
        if (job?.isActive == true) return

        job = viewModelScope.launch {
            _state.update { it.copy(loading = true, error = null) }

            try {
                val quotes = repository.fetchQuotes()
                if (quotes.isNotEmpty()) {
                    preferences.saveQuotesCache(quotes)
                }

                _state.update {
                    it.copy(
                        quotes = quotes.associateBy { quote -> quote.assetId },
                        loading = false,
                        lastLoadedAtMillis = System.currentTimeMillis(),
                        isFromCache = false,
                        error = null,
                    )
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                _state.update {
                    it.copy(
                        loading = false,
                        error = e.message ?: "Connection failed",
                    )
                }
            }
        }
    }
}
