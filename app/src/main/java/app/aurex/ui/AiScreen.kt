package app.aurex.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
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
import androidx.compose.ui.draw.clip
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import app.aurex.R
import app.aurex.data.AnalysisResult
import app.aurex.data.AnalysisRow

private const val MAX_INPUT = 2000

@Composable
fun AiScreen(
    state: AiUiState,
    onTab: (Int) -> Unit,
    onSend: (String, String) -> Unit,
    onRetryChat: (String) -> Unit,
    onNewChat: () -> Unit,
    onLoadAnalysis: (String, Boolean) -> Unit,
) {
    val colors = LocalAurexColors.current
    val lang = languageTag(LocalAppLocale.current)
    Column(Modifier.fillMaxSize()) {
        Row(
            Modifier.fillMaxWidth().padding(start = 16.dp, end = 8.dp, top = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            AurexLogo(size = 28.dp)
            Spacer(Modifier.width(10.dp))
            Text(
                stringResource(R.string.nav_ai),
                style = MaterialTheme.typography.titleLarge,
                modifier = Modifier.weight(1f),
            )
            if (state.tab == 0 && state.messages.isNotEmpty()) {
                TextButton(
                    onClick = onNewChat,
                    colors = ButtonDefaults.textButtonColors(contentColor = colors.gold),
                ) { Text(stringResource(R.string.ai_new_chat)) }
            }
        }
        TabSwitch(selected = state.tab, onSelect = onTab)
        if (state.tab == 0) {
            AssistantTab(state, lang, onSend, onRetryChat)
        } else {
            AnalysisTab(state.analysis, lang, onLoadAnalysis)
        }
    }
}

@Composable
private fun TabSwitch(selected: Int, onSelect: (Int) -> Unit) {
    val colors = LocalAurexColors.current
    Row(
        Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 10.dp)
            .clip(RoundedCornerShape(10.dp))
            .background(MaterialTheme.colorScheme.surface)
            .border(1.dp, colors.border, RoundedCornerShape(10.dp))
            .padding(4.dp),
    ) {
        listOf(R.string.ai_tab_assistant, R.string.ai_tab_analysis).forEachIndexed { index, labelRes ->
            val active = index == selected
            Box(
                Modifier
                    .weight(1f)
                    .clip(RoundedCornerShape(8.dp))
                    .background(if (active) colors.gold.copy(alpha = 0.18f) else androidx.compose.ui.graphics.Color.Transparent)
                    .clickable { onSelect(index) }
                    .padding(vertical = 9.dp),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    stringResource(labelRes),
                    style = MaterialTheme.typography.titleSmall,
                    color = if (active) colors.gold else colors.textSecondary,
                )
            }
        }
    }
}

// ----------------------------------------------------------------------------- assistant

@Composable
private fun AssistantTab(
    state: AiUiState,
    lang: String,
    onSend: (String, String) -> Unit,
    onRetry: (String) -> Unit,
) {
    val colors = LocalAurexColors.current
    var draft by rememberSaveable { mutableStateOf("") }
    val listState = rememberLazyListState()
    val starters = listOf(R.string.ai_starter_1, R.string.ai_starter_2, R.string.ai_starter_3)

    LaunchedEffect(state.messages.size, state.sending, state.chatError) {
        val extra = (if (state.sending) 1 else 0) + (if (state.chatError != null) 1 else 0)
        val last = state.messages.size + extra - 1
        if (last >= 0) listState.animateScrollToItem(last)
    }

    Column(Modifier.fillMaxSize().imePadding()) {
        if (state.messages.isEmpty()) {
            Column(
                Modifier.weight(1f).fillMaxWidth().verticalScroll(rememberScrollState()).padding(20.dp),
                verticalArrangement = Arrangement.Center,
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                AurexLogo(size = 64.dp)
                Spacer(Modifier.height(14.dp))
                Text(
                    stringResource(R.string.ai_empty_title),
                    style = MaterialTheme.typography.titleMedium,
                    textAlign = TextAlign.Center,
                )
                Spacer(Modifier.height(6.dp))
                Text(
                    stringResource(R.string.ai_empty_body),
                    style = MaterialTheme.typography.bodyMedium,
                    color = colors.textSecondary,
                    textAlign = TextAlign.Center,
                )
                Spacer(Modifier.height(16.dp))
                starters.forEach { res ->
                    val text = stringResource(res)
                    Text(
                        text,
                        style = MaterialTheme.typography.bodySmall,
                        color = colors.gold,
                        textAlign = TextAlign.Center,
                        modifier = Modifier
                            .padding(vertical = 4.dp)
                            .clip(RoundedCornerShape(50))
                            .border(1.dp, colors.gold.copy(alpha = 0.45f), RoundedCornerShape(50))
                            .clickable(enabled = !state.sending) { onSend(text, lang) }
                            .padding(horizontal = 14.dp, vertical = 8.dp),
                    )
                }
            }
        } else {
            LazyColumn(
                state = listState,
                modifier = Modifier.weight(1f).fillMaxWidth(),
                contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                items(state.messages, key = { it.id }) { msg -> Bubble(msg) }
                if (state.sending) item(key = "typing") { TypingRow() }
                if (state.chatError != null) item(key = "error") {
                    ErrorBanner(
                        messageRes = aiErrorRes(state.chatError),
                        hasData = false,
                        onRetry = { onRetry(lang) },
                    )
                }
            }
        }

        Text(
            stringResource(R.string.ai_disclaimer),
            style = MaterialTheme.typography.labelSmall,
            color = colors.textSecondary,
            textAlign = TextAlign.Center,
            modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp),
        )
        Row(
            Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 8.dp),
            verticalAlignment = Alignment.Bottom,
        ) {
            OutlinedTextField(
                value = draft,
                onValueChange = { draft = it.take(MAX_INPUT) },
                modifier = Modifier.weight(1f),
                placeholder = { Text(stringResource(R.string.ai_input_hint)) },
                maxLines = 4,
            )
            Spacer(Modifier.width(8.dp))
            val canSend = draft.isNotBlank() && !state.sending
            val sendLabel = stringResource(R.string.ai_send)
            Box(
                Modifier
                    .padding(bottom = 6.dp)
                    .size(48.dp)
                    .clip(CircleShape)
                    .background(if (canSend) colors.gold else colors.gold.copy(alpha = 0.25f))
                    .clickable(enabled = canSend, onClickLabel = sendLabel) {
                        onSend(draft, lang)
                        draft = ""
                    },
                contentAlignment = Alignment.Center,
            ) {
                ArrowGlyph(up = true, tint = MaterialTheme.colorScheme.onPrimary)
            }
        }
    }
}

@Composable
private fun Bubble(msg: ChatMsg) {
    val colors = LocalAurexColors.current
    val mine = msg.role == "user"
    Row(
        Modifier.fillMaxWidth(),
        horizontalArrangement = if (mine) Arrangement.End else Arrangement.Start,
    ) {
        Column(
            Modifier
                .widthIn(max = 320.dp)
                .clip(RoundedCornerShape(14.dp))
                .background(if (mine) colors.gold.copy(alpha = 0.16f) else MaterialTheme.colorScheme.surface)
                .border(
                    1.dp,
                    if (mine) colors.gold.copy(alpha = 0.4f) else colors.border,
                    RoundedCornerShape(14.dp),
                )
                .padding(horizontal = 14.dp, vertical = 10.dp)
        ) {
            Text(msg.text, style = MaterialTheme.typography.bodyMedium)
        }
    }
}

@Composable
private fun TypingRow() {
    val colors = LocalAurexColors.current
    Row(verticalAlignment = Alignment.CenterVertically) {
        CircularProgressIndicator(Modifier.size(16.dp), strokeWidth = 2.dp, color = colors.gold)
        Spacer(Modifier.width(8.dp))
        Text(
            stringResource(R.string.ai_thinking),
            style = MaterialTheme.typography.labelMedium,
            color = colors.textSecondary,
        )
    }
}

// ----------------------------------------------------------------------------- analysis

@Composable
private fun AnalysisTab(ui: AnalysisUi, lang: String, onLoad: (String, Boolean) -> Unit) {
    val colors = LocalAurexColors.current
    LaunchedEffect(Unit) {
        if (ui.result == null && !ui.loading) onLoad(lang, false)
    }
    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 16.dp, vertical = 4.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(
                stringResource(R.string.analysis_title),
                style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.weight(1f),
            )
            if (ui.loading) {
                CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp, color = colors.gold)
            } else {
                IconButton(onClick = { onLoad(lang, true) }) {
                    Icon(
                        Icons.Filled.Refresh,
                        contentDescription = stringResource(R.string.analysis_refresh),
                        tint = colors.gold,
                    )
                }
            }
        }

        if (ui.errorCode != null) {
            ErrorBanner(aiErrorRes(ui.errorCode), hasData = ui.result != null, onRetry = { onLoad(lang, true) })
        }

        val result = ui.result
        if (result == null) {
            if (ui.loading) UnavailableText(loading = true)
        } else {
            AnalysisBody(result)
        }
        Text(
            stringResource(R.string.ai_disclaimer),
            style = MaterialTheme.typography.labelSmall,
            color = colors.textSecondary,
        )
        Spacer(Modifier.height(8.dp))
    }
}

@Composable
private fun AnalysisBody(result: AnalysisResult) {
    val colors = LocalAurexColors.current
    val locale = LocalAppLocale.current
    val unavailableNames = mutableListOf<String>()
    for (item in result.unavailable) {
        unavailableNames.add(stringResource(assetNameRes(item)))
    }

    if (result.generatedAtSeconds > 0) {
        Text(
            stringResource(R.string.analysis_generated, formatLocalDateTime(result.generatedAtSeconds * 1000, locale)),
            style = MaterialTheme.typography.labelSmall,
            color = colors.textSecondary,
        )
    }

    // 1) REAL data, exactly as received from the server.
    AurexCard(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp)) {
            Text(
                stringResource(R.string.analysis_data_title),
                style = MaterialTheme.typography.labelMedium,
                color = colors.positive,
            )
            Spacer(Modifier.height(8.dp))
            if (result.status == "no_data" || result.rows.isEmpty()) {
                Text(stringResource(R.string.analysis_no_data), style = MaterialTheme.typography.bodyMedium)
            } else {
                result.rows.forEachIndexed { i, row ->
                    DataRow(row)
                    if (i < result.rows.lastIndex) {
                        HorizontalDivider(Modifier.padding(vertical = 8.dp), color = colors.border)
                    }
                }
            }
            if (result.unavailable.isNotEmpty()) {
                Spacer(Modifier.height(10.dp))
                Text(
                    stringResource(
                        R.string.analysis_unavailable_assets,
                        unavailableNames.joinToString("، "),
                    ),
                    style = MaterialTheme.typography.labelSmall,
                    color = colors.textSecondary,
                )
            }
            if (result.sources.isNotEmpty()) {
                Spacer(Modifier.height(6.dp))
                Text(
                    stringResource(R.string.analysis_sources, result.sources.joinToString(", ")),
                    style = MaterialTheme.typography.labelSmall,
                    color = colors.textSecondary,
                )
            }
        }
    }

    if (result.status != "no_data" && !result.historySufficient) {
        Text(
            stringResource(R.string.analysis_insufficient_history),
            style = MaterialTheme.typography.bodySmall,
            color = colors.warning,
        )
    }

    // 2) AI interpretation, visibly separate and labelled as unverified.
    AurexCard(Modifier.fillMaxWidth(), borderColor = colors.gold.copy(alpha = 0.4f)) {
        Column(Modifier.padding(16.dp)) {
            Text(
                stringResource(R.string.analysis_ai_title),
                style = MaterialTheme.typography.labelMedium,
                color = colors.gold,
            )
            Spacer(Modifier.height(8.dp))
            when (result.aiStatus) {
                "ok" -> {
                    Text(result.aiText.orEmpty(), style = MaterialTheme.typography.bodyMedium)
                    Spacer(Modifier.height(8.dp))
                    Text(
                        stringResource(R.string.analysis_ai_note),
                        style = MaterialTheme.typography.labelSmall,
                        color = colors.textSecondary,
                    )
                    val meta = listOfNotNull(
                        result.aiModel?.let { stringResource(R.string.analysis_model, it) },
                        if (result.aiCached) stringResource(R.string.analysis_cached) else null,
                    ).joinToString("  •  ")
                    if (meta.isNotEmpty()) {
                        Text(meta, style = MaterialTheme.typography.labelSmall, color = colors.textSecondary)
                    }
                }
                "not_configured" -> Text(
                    stringResource(R.string.analysis_not_configured),
                    style = MaterialTheme.typography.bodyMedium,
                )
                "rate_limited" -> Text(
                    stringResource(R.string.analysis_ai_rate_limited),
                    style = MaterialTheme.typography.bodyMedium,
                )
                "no_data" -> Text(
                    stringResource(R.string.analysis_no_data),
                    style = MaterialTheme.typography.bodyMedium,
                )
                else -> Text(
                    stringResource(R.string.analysis_ai_failed),
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
        }
    }
}

@Composable
private fun DataRow(row: AnalysisRow) {
    val colors = LocalAurexColors.current
    val locale = LocalAppLocale.current
    Column {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(
                stringResource(assetNameRes(row.assetId)),
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.weight(1f),
            )
            Text(
                formatPrice(row.price, locale) + "  " + unitLabel(row.unit),
                style = MaterialTheme.typography.bodyMedium,
            )
        }
        Spacer(Modifier.height(4.dp))
        Row(verticalAlignment = Alignment.CenterVertically) {
            FreshnessChip(row.freshness)
            Spacer(Modifier.width(10.dp))
            ChangeText(row.providerChangePct)
        }
        Spacer(Modifier.height(2.dp))
        if (row.historyChangePct != null) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    stringResource(R.string.analysis_hist_change),
                    style = MaterialTheme.typography.labelSmall,
                    color = colors.textSecondary,
                )
                Spacer(Modifier.width(6.dp))
                ChangeText(row.historyChangePct, MaterialTheme.typography.labelSmall)
            }
        } else {
            Text(
                stringResource(R.string.analysis_hist_none),
                style = MaterialTheme.typography.labelSmall,
                color = colors.textSecondary,
            )
        }
    }
}
