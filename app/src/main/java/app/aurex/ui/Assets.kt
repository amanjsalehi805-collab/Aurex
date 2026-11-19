package app.aurex.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.background
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import app.aurex.R
import app.aurex.data.HistoryData
import java.math.BigDecimal

data class AssetSpec(val id: String, val nameRes: Int)

/** Existing asset IDs are unchanged. */
val MarketWatchAssets = listOf(
    AssetSpec("usd_free_irt", R.string.asset_usd_free),
    AssetSpec("eur_free_irt", R.string.asset_eur_free),
    AssetSpec("gold18_irt", R.string.asset_gold18),
    AssetSpec("coin_irt", R.string.asset_coin),
    AssetSpec("gold_oz_usd", R.string.asset_global_gold),
    AssetSpec("silver_oz_usd", R.string.asset_global_silver),
    AssetSpec("tse_index", R.string.asset_tse_index),
)

fun assetNameRes(id: String): Int =
    MarketWatchAssets.firstOrNull { it.id == id }?.nameRes ?: R.string.unavailable

/** Maps stable connection error codes to localized text. */
fun apiErrorRes(code: String?): Int = when (code) {
    "network" -> R.string.err_network
    "timeout" -> R.string.err_timeout
    "rate_limited" -> R.string.err_busy
    "server_error", "bad_response" -> R.string.err_server
    else -> R.string.err_generic
}

fun aiErrorRes(code: String?): Int = when (code) {
    "ai_not_configured" -> R.string.ai_err_not_configured
    "ai_rate_limited", "ai_provider_rate_limited", "rate_limited" -> R.string.ai_err_busy
    "ai_timeout", "timeout" -> R.string.ai_err_timeout
    "network", "ai_unreachable" -> R.string.ai_err_network
    "message_too_long", "too_many_messages", "conversation_too_long", "invalid_input" ->
        R.string.ai_err_input
    "ai_auth_failed", "ai_upstream_error", "ai_bad_response", "ai_model_or_url_invalid",
    "server_error", "bad_response" -> R.string.ai_err_server
    else -> R.string.ai_err_unknown
}

@Composable
fun ErrorBanner(messageRes: Int, hasData: Boolean, onRetry: () -> Unit) {
    val colors = LocalAurexColors.current
    AurexCard(modifier = Modifier.fillMaxWidth(), borderColor = colors.negative.copy(alpha = 0.55f)) {
        Column(Modifier.padding(14.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(
                    Icons.Filled.Warning,
                    contentDescription = null,
                    tint = colors.negative,
                    modifier = Modifier.size(18.dp),
                )
                Spacer(Modifier.width(8.dp))
                Text(stringResource(R.string.error_title), style = MaterialTheme.typography.titleSmall)
            }
            Spacer(Modifier.height(6.dp))
            Text(
                stringResource(if (hasData) R.string.error_showing_previous else R.string.error_body),
                style = MaterialTheme.typography.bodySmall,
            )
            Text(
                stringResource(messageRes),
                style = MaterialTheme.typography.labelSmall,
                color = colors.textSecondary,
            )
            TextButton(
                onClick = onRetry,
                colors = ButtonDefaults.textButtonColors(contentColor = colors.gold),
            ) { Text(stringResource(R.string.error_retry)) }
        }
    }
}

/** Real chart of recorded history, or an honest message when there is not enough of it. */
@Composable
fun HistoryChart(ui: HistoryUi?, height: Dp, modifier: Modifier = Modifier) {
    val colors = LocalAurexColors.current
    val data: HistoryData? = ui?.data
    if (data != null && data.points.size >= 2) {
        PriceChart(data.points, modifier.fillMaxWidth().height(height))
        return
    }
    val messageRes = when {
        ui == null || ui.loading -> R.string.chart_loading
        ui.error -> R.string.chart_error
        else -> R.string.chart_no_history
    }
    Box(
        modifier = modifier
            .fillMaxWidth()
            .height(height)
            .clip(RoundedCornerShape(8.dp))
            .background(colors.elevated),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            stringResource(messageRes),
            style = MaterialTheme.typography.labelSmall,
            color = colors.textSecondary,
            textAlign = TextAlign.Center,
            modifier = Modifier.padding(horizontal = 12.dp),
        )
    }
}

@Composable
fun spanText(seconds: Long): String {
    val locale = LocalAppLocale.current
    val hours = seconds / 3600
    return if (hours < 48) {
        stringResource(R.string.duration_hours, formatDecimal(BigDecimal(hours), 0, locale))
    } else {
        stringResource(R.string.duration_days, formatDecimal(BigDecimal(hours / 24), 0, locale))
    }
}

@Composable
fun dashboardErrorRes(error: String?): Int = apiErrorRes(error)
