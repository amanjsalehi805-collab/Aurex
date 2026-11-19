package app.aurex.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import app.aurex.R
import java.math.BigDecimal

private const val USD_ID = "usd_free_irt"
private const val EUR_ID = "eur_free_irt"

@Composable
fun ConverterScreen(
    state: DashboardState,
    onBack: () -> Unit,
    onRefresh: () -> Unit,
) {
    val colors = LocalAurexColors.current
    val locale = LocalAppLocale.current

    var input by rememberSaveable { mutableStateOf("") }
    var foreignToToman by rememberSaveable { mutableStateOf(true) }
    var currency by rememberSaveable { mutableStateOf("usd") }

    // Only a quote that is explicitly in IRT (Toman) may be used as a rate.
    fun rateQuote(id: String) = state.quotes[id]?.takeIf { it.unit == "IRT" && it.price > 0 }
    val usdQuote = rateQuote(USD_ID)
    val eurQuote = rateQuote(EUR_ID)
    val quote = if (currency == "eur") eurQuote else usdQuote

    val foreignName = stringResource(if (currency == "eur") R.string.unit_eur else R.string.unit_usd)
    val tomanName = stringResource(R.string.unit_irt)

    val amount = ConverterMath.parseAmount(input)
    val rate = quote?.let { BigDecimal.valueOf(it.price) }
    val result = if (amount != null && rate != null) ConverterMath.convert(amount, rate, foreignToToman) else null

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
                stringResource(R.string.converter_title),
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
        }

        // Currency choice. EUR is offered only when the server really has a rate for it.
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
            FilterChip(
                selected = currency == "usd",
                onClick = { currency = "usd" },
                label = { Text(stringResource(R.string.unit_usd)) },
                colors = FilterChipDefaults.filterChipColors(
                    selectedContainerColor = colors.gold.copy(alpha = 0.18f),
                    selectedLabelColor = colors.gold,
                ),
            )
            FilterChip(
                selected = currency == "eur",
                onClick = { currency = "eur" },
                enabled = eurQuote != null,
                label = { Text(stringResource(R.string.unit_eur)) },
                colors = FilterChipDefaults.filterChipColors(
                    selectedContainerColor = colors.gold.copy(alpha = 0.18f),
                    selectedLabelColor = colors.gold,
                ),
            )
            if (eurQuote == null) {
                Text(
                    stringResource(R.string.converter_currency_unavailable, stringResource(R.string.unit_eur)),
                    style = MaterialTheme.typography.labelSmall,
                    color = colors.textSecondary,
                )
            }
        }

        AurexCard(Modifier.fillMaxWidth(), borderColor = colors.gold.copy(alpha = 0.35f)) {
            Column(Modifier.padding(16.dp)) {
                Text(
                    stringResource(R.string.converter_from),
                    style = MaterialTheme.typography.labelMedium,
                    color = colors.gold,
                )
                Spacer(Modifier.height(6.dp))
                OutlinedTextField(
                    value = input,
                    onValueChange = { input = it.take(24) },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    isError = input.isNotBlank() && amount == null,
                    label = { Text(stringResource(R.string.converter_amount)) },
                    suffix = { Text(if (foreignToToman) foreignName else tomanName) },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                )

                Box(Modifier.fillMaxWidth().padding(vertical = 10.dp), contentAlignment = Alignment.Center) {
                    val swapDescription = stringResource(R.string.converter_swap)
                    Row(
                        Modifier
                            .size(44.dp)
                            .clip(CircleShape)
                            .background(colors.gold.copy(alpha = 0.12f))
                            .border(1.dp, colors.gold.copy(alpha = 0.5f), CircleShape)
                            .clickable(onClickLabel = swapDescription) {
                                // Keep the number that is on screen as the next input.
                                if (result != null) {
                                    input = formatForInput(result, if (foreignToToman) 2 else 4)
                                }
                                foreignToToman = !foreignToToman
                            },
                        horizontalArrangement = Arrangement.Center,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        ArrowGlyph(up = true, tint = colors.gold, modifier = Modifier.size(16.dp))
                        ArrowGlyph(up = false, tint = colors.gold, modifier = Modifier.size(16.dp))
                    }
                }

                Text(
                    stringResource(R.string.converter_to),
                    style = MaterialTheme.typography.labelMedium,
                    color = colors.gold,
                )
                Spacer(Modifier.height(6.dp))
                when {
                    quote == null -> Text(
                        stringResource(R.string.converter_rate_unavailable, foreignName),
                        style = MaterialTheme.typography.bodyMedium,
                        color = colors.negative,
                    )
                    input.isBlank() -> Text(
                        stringResource(R.string.converter_empty),
                        style = MaterialTheme.typography.bodyMedium,
                        color = colors.textSecondary,
                    )
                    amount == null -> Text(
                        stringResource(R.string.converter_invalid),
                        style = MaterialTheme.typography.bodyMedium,
                        color = colors.negative,
                    )
                    result != null -> {
                        val shown = formatDecimal(result, if (foreignToToman) 2 else 4, locale)
                        Text(
                            shown + "  " + (if (foreignToToman) tomanName else foreignName),
                            style = MaterialTheme.typography.headlineSmall,
                            fontWeight = FontWeight.Bold,
                        )
                    }
                }
            }
        }

        if (quote != null) {
            AurexCard(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp)) {
                    SpreadRow {
                        Text(
                            stringResource(R.string.converter_rate_title),
                            style = MaterialTheme.typography.labelMedium,
                            color = colors.gold,
                        )
                        FreshnessChip(state.freshnessOf(quote))
                    }
                    Spacer(Modifier.height(6.dp))
                    Text(
                        stringResource(R.string.converter_rate, foreignName, formatPrice(quote.price, locale), tomanName),
                        style = MaterialTheme.typography.bodyMedium,
                    )
                    Spacer(Modifier.height(6.dp))
                    SourceLine(quote)
                    if (state.freshnessOf(quote) in listOf("stale", "cached")) {
                        Spacer(Modifier.height(8.dp))
                        Text(
                            stringResource(R.string.converter_stale_warning),
                            style = MaterialTheme.typography.labelSmall,
                            color = colors.warning,
                        )
                    }
                }
            }
        }

        Text(
            stringResource(R.string.converter_hint),
            style = MaterialTheme.typography.labelSmall,
            color = colors.textSecondary,
        )
    }
}

/** Plain digits/decimal point (no grouping) so the parser can read it back on swap. */
private fun formatForInput(value: BigDecimal, maxFrac: Int): String =
    value.setScale(maxFrac, java.math.RoundingMode.HALF_EVEN).stripTrailingZeros().toPlainString()
