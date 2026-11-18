package app.aurex.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import app.aurex.data.MarketQuote
import app.aurex.data.QuoteRepository
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class DashboardState(
    val quotes: Map<String, MarketQuote> = emptyMap(),
    val loading: Boolean = true,
    val error: String? = null,
    val lastLoadedAtMillis: Long? = null,
)

class DashboardViewModel : ViewModel() {
    private val repository = QuoteRepository()
    private val _state = MutableStateFlow(DashboardState())
    val state: StateFlow<DashboardState> = _state.asStateFlow()
    private var job: Job? = null

    init {
        refresh()
    }

    fun refresh() {
        if (job?.isActive == true) return
        job = viewModelScope.launch {
            _state.update { it.copy(loading = true, error = null) }
            try {
                val quotes = repository.fetchQuotes()
                _state.update {
                    it.copy(
                        quotes = quotes.associateBy { q -> q.assetId },
                        loading = false,
                        lastLoadedAtMillis = System.currentTimeMillis(),
                    )
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                // Keep previously loaded quotes so the user still sees the last known data.
                _state.update { it.copy(loading = false, error = e.message ?: "Connection failed") }
            }
        }
    }
}
