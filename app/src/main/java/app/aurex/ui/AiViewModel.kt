package app.aurex.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import app.aurex.data.AiRepository
import app.aurex.data.AnalysisResult
import app.aurex.data.ApiException
import app.aurex.data.ChatMessage
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class ChatMsg(val id: Long, val role: String, val text: String)

data class AnalysisUi(
    val loading: Boolean = false,
    val result: AnalysisResult? = null,
    val errorCode: String? = null,
)

data class AiUiState(
    /** 0 = assistant, 1 = analysis */
    val tab: Int = 0,
    val messages: List<ChatMsg> = emptyList(),
    val sending: Boolean = false,
    val chatError: String? = null,
    val analysis: AnalysisUi = AnalysisUi(),
)

class AiViewModel : ViewModel() {
    private val repository = AiRepository()
    private val _state = MutableStateFlow(AiUiState())
    val state: StateFlow<AiUiState> = _state.asStateFlow()

    private var chatJob: Job? = null
    private var analysisJob: Job? = null
    private var nextId = 1L

    fun setTab(tab: Int) = _state.update { it.copy(tab = tab) }

    fun send(text: String, language: String) {
        val clean = text.trim()
        if (clean.isEmpty() || _state.value.sending) return
        _state.update {
            it.copy(messages = it.messages + ChatMsg(nextId++, "user", clean), chatError = null)
        }
        requestReply(language)
    }

    /** Re-sends the conversation after a failure (the last message is the user's). */
    fun retry(language: String) {
        val s = _state.value
        if (s.sending || s.messages.lastOrNull()?.role != "user") return
        _state.update { it.copy(chatError = null) }
        requestReply(language)
    }

    private fun requestReply(language: String) {
        _state.update { it.copy(sending = true) }
        chatJob = viewModelScope.launch {
            try {
                // Anthropic-style APIs require the first message to be from the user.
                val history = _state.value.messages.takeLast(12)
                    .dropWhile { it.role != "user" }
                    .map { ChatMessage(it.role, it.text) }
                val reply = repository.chat(history, language)
                _state.update {
                    it.copy(
                        messages = it.messages + ChatMsg(nextId++, "assistant", reply),
                        sending = false,
                    )
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                _state.update {
                    it.copy(sending = false, chatError = (e as? ApiException)?.code ?: "unknown")
                }
            }
        }
    }

    fun newChat() {
        chatJob?.cancel()
        _state.update { it.copy(messages = emptyList(), sending = false, chatError = null) }
    }

    fun loadAnalysis(language: String, force: Boolean) {
        if (analysisJob?.isActive == true) return
        _state.update { it.copy(analysis = it.analysis.copy(loading = true, errorCode = null)) }
        analysisJob = viewModelScope.launch {
            try {
                val result = repository.analysis(language, force)
                _state.update { it.copy(analysis = AnalysisUi(result = result)) }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                _state.update {
                    it.copy(
                        analysis = it.analysis.copy(
                            loading = false,
                            errorCode = (e as? ApiException)?.code ?: "unknown",
                        )
                    )
                }
            }
        }
    }
}
