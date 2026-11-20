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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
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
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.text.TextRange
import androidx.compose.ui.unit.dp
import app.aurex.R
import app.aurex.data.MarketQuote
import java.math.BigDecimal

private const val USD_ID = "usd_free_irt"
private val CONVERTER_ASSET_IDS = listOf(
    ConverterMath.TOMAN_ID,
    ConverterMath.USD_ID,
    ConverterMath.EUR_ID,
    ConverterMath.GOLD18_ID,
    ConverterMath.COIN_ID,
    ConverterMath.GLOBAL_GOLD_ID,
    ConverterMath.GLOBAL_SILVER_ID,
)

@Composable
fun ConverterScreen(
    state: DashboardState,
    onBack: () -> Unit,
    onRefresh: () -> Unit,
) {
    val colors = LocalAurexColors.current
    val locale = LocalAppLocale.current
    var input by rememberSaveable(stateSaver = TextFieldValue.Saver) { mutableStateOf(TextFieldValue("")) }
    var sourceId by rememberSaveable { mutableStateOf(USD_ID) }
    var targetId by rememberSaveable { mutableStateOf(ConverterMath.TOMAN_ID) }

    fun validQuote(id: String): MarketQuote? {
        val expectedUnit =
            if (id == ConverterMath.GLOBAL_GOLD_ID || id == ConverterMath.GLOBAL_SILVER_ID) "USD" else "IRT"
        return state.quotes[id]?.takeIf {
            it.price.isFinite() && it.price > 0.0 && it.unit.trim().uppercase() == expectedUnit
        }
    }

    val usdQuote = validQuote(USD_ID)
    val usdToToman = usdQuote?.let { BigDecimal.valueOf(it.price) }
    val sourceQuote = if (sourceId == ConverterMath.TOMAN_ID) null else validQuote(sourceId)
    val targetQuote = if (targetId == ConverterMath.TOMAN_ID) null else validQuote(targetId)

    fun valueInToman(id: String): BigDecimal? {
        val quote = validQuote(id)
        return ConverterMath.valueInToman(
            assetId = id,
            quotePrice = quote?.let { BigDecimal.valueOf(it.price) },
            quoteUnit = quote?.unit,
            usdToToman = usdToToman,
        )
    }

    val sourceValue = valueInToman(sourceId)
    val targetValue = valueInToman(targetId)
    val amount = ConverterMath.parseAmount(input.text)
    val result = when {
        amount == null -> null
        sourceId == targetId -> amount
        sourceValue != null && targetValue != null ->
            ConverterMath.convertAssets(amount, sourceValue, targetValue)
        else -> null
    }

    val needsUsdCrossRate =
        sourceId == ConverterMath.GLOBAL_GOLD_ID ||
        sourceId == ConverterMath.GLOBAL_SILVER_ID ||
        targetId == ConverterMath.GLOBAL_GOLD_ID ||
        targetId == ConverterMath.GLOBAL_SILVER_ID

    val usedQuotes = listOfNotNull(
        sourceQuote,
        targetQuote,
        if (needsUsdCrossRate) usdQuote else null,
    ).distinctBy { it.assetId }
    val hasStaleQuote = usedQuotes.any {
        state.freshnessOf(it) in setOf("delayed", "stale", "cached")
    }

    Column(
        Modifier.fillMaxSize()
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

        AurexCard(Modifier.fillMaxWidth(), borderColor = colors.gold.copy(alpha = 0.35f)) {
            Column(
                Modifier.padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Row(
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                    verticalAlignment = Alignment.Top,
                ) {
                    Column(Modifier.weight(1f)) {
                        Text(
                            stringResource(R.string.converter_from),
                            style = MaterialTheme.typography.labelMedium,
                            color = colors.gold,
                        )
                        Spacer(Modifier.height(6.dp))
                        ConverterAssetSelector(sourceId, { sourceId = it }, Modifier.fillMaxWidth())
                    }
                    Column(Modifier.weight(1f)) {
                        Text(
                            stringResource(R.string.converter_to),
                            style = MaterialTheme.typography.labelMedium,
                            color = colors.gold,
                        )
                        Spacer(Modifier.height(6.dp))
                        ConverterAssetSelector(targetId, { targetId = it }, Modifier.fillMaxWidth())
                    }
                }

                Box(Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
                    Row(
                        Modifier.size(42.dp)
                            .clip(CircleShape)
                            .background(colors.gold.copy(alpha = 0.12f))
                            .border(1.dp, colors.gold.copy(alpha = 0.5f), CircleShape)
                            .clickable {
                                val oldSource = sourceId
                                sourceId = targetId
                                targetId = oldSource
                                if (result != null) {
                                    val formatted = formatForInput(result)
                                    input = formatGroupedInput(
                                        TextFieldValue(formatted, selection = TextRange(formatted.length))
                                    )
                                }
                            },
                        horizontalArrangement = Arrangement.Center,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        ArrowGlyph(up = true, tint = colors.gold, modifier = Modifier.size(16.dp))
                        ArrowGlyph(up = false, tint = colors.gold, modifier = Modifier.size(16.dp))
                    }
                }

                Text(
                    stringResource(R.string.converter_amount),
                    style = MaterialTheme.typography.labelMedium,
                    color = colors.textSecondary,
                )
                OutlinedTextField(
                    value = input,
                    onValueChange = { input = formatGroupedInput(it) },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    isError = input.text.isNotBlank() && amount == null,
                    label = { Text(converterAssetName(sourceId)) },
                    suffix = { Text(converterUnitName(sourceId)) },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                )

                Text(
                    stringResource(R.string.converter_to),
                    style = MaterialTheme.typography.labelMedium,
                    color = colors.gold,
                )
                when {
                    input.text.isBlank() -> Text(
                        stringResource(R.string.converter_empty),
                        style = MaterialTheme.typography.bodyMedium,
                        color = colors.textSecondary,
                    )
                    amount == null -> Text(
                        stringResource(R.string.converter_invalid),
                        style = MaterialTheme.typography.bodyMedium,
                        color = colors.negative,
                    )
                    result == null -> Text(
                        stringResource(
                            R.string.converter_rate_unavailable,
                            converterAssetName(
                                when {
                                    needsUsdCrossRate && usdQuote == null -> USD_ID
                                    sourceValue == null -> sourceId
                                    else -> targetId
                                },
                            ),
                        ),
                        style = MaterialTheme.typography.bodyMedium,
                        color = colors.negative,
                    )
                    else -> Text(
                        "${formatDecimal(result, if (targetId == ConverterMath.TOMAN_ID) 2 else 8, locale)}  ${converterUnitName(targetId)}",
                        style = MaterialTheme.typography.headlineSmall,
                        fontWeight = FontWeight.Bold,
                    )
                }

                if (sourceId == targetId && amount != null) {
                    Text(
                        stringResource(R.string.converter_same_asset),
                        style = MaterialTheme.typography.labelSmall,
                        color = colors.textSecondary,
                    )
                }
            }
        }

        if (usedQuotes.isNotEmpty()) {
            AurexCard(Modifier.fillMaxWidth()) {
                Column(
                    Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    Text(
                        stringResource(R.string.converter_rate_title),
                        style = MaterialTheme.typography.titleSmall,
                        color = colors.gold,
                    )
                    usedQuotes.forEach { quote ->
                        Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            SpreadRow {
                                Text(
                                    converterAssetName(quote.assetId),
                                    style = MaterialTheme.typography.labelMedium,
                                    fontWeight = FontWeight.SemiBold,
                                )
                                FreshnessChip(state.freshnessOf(quote))
                            }
                            val quoteUnitName =
                                if (quote.unit.trim().uppercase() == "USD") {
                                    stringResource(R.string.unit_usd)
                                } else {
                                    stringResource(R.string.unit_irt)
                                }
                            Text(
                                stringResource(
                                    R.string.converter_rate,
                                    "1 ${converterUnitName(quote.assetId)}",
                                    formatPrice(quote.price, locale),
                                    quoteUnitName,
                                ),
                                style = MaterialTheme.typography.bodySmall,
                            )
                            SourceLine(quote)
                        }
                    }
                    if (hasStaleQuote) {
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

@Composable
private fun ConverterAssetSelector(
    selectedId: String,
    onSelect: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    val colors = LocalAurexColors.current
    var expanded by rememberSaveable { mutableStateOf(false) }
    Box(modifier) {
        Column(
            Modifier.fillMaxWidth()
                .clip(RoundedCornerShape(10.dp))
                .background(colors.elevated)
                .border(1.dp, colors.textSecondary.copy(alpha = 0.35f), RoundedCornerShape(10.dp))
                .clickable { expanded = true }
                .padding(horizontal = 10.dp, vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            Text(
                converterAssetName(selectedId),
                style = MaterialTheme.typography.labelMedium,
                maxLines = 2,
            )
            Text(
                converterUnitName(selectedId),
                style = MaterialTheme.typography.labelSmall,
                color = colors.textSecondary,
            )
        }
        DropdownMenu(
            expanded = expanded,
            onDismissRequest = { expanded = false },
        ) {
            CONVERTER_ASSET_IDS.forEach { id ->
                DropdownMenuItem(
                    text = {
                        Text(
                            converterAssetName(id),
                            style = MaterialTheme.typography.bodyMedium,
                        )
                    },
                    onClick = {
                        onSelect(id)
                        expanded = false
                    },
                )
            }
        }
    }
}

@Composable
private fun converterAssetName(id: String): String =
    if (id == ConverterMath.TOMAN_ID) {
        stringResource(R.string.unit_irt)
    } else {
        stringResource(assetNameRes(id))
    }

@Composable
private fun converterUnitName(id: String): String = stringResource(
    when (id) {
        ConverterMath.TOMAN_ID -> R.string.unit_irt
        USD_ID -> R.string.unit_usd
        ConverterMath.EUR_ID -> R.string.unit_eur
        ConverterMath.GOLD18_ID -> R.string.unit_gram
        ConverterMath.COIN_ID -> R.string.unit_coin
        ConverterMath.GLOBAL_GOLD_ID, ConverterMath.GLOBAL_SILVER_ID -> R.string.unit_troy_oz
        else -> R.string.unavailable
    },
)


private fun formatGroupedInput(value: TextFieldValue): TextFieldValue {
    val normalized = ConverterMath.normalize(value.text)
    if (normalized.count { it == '.' } > 1) return value

    val candidate = normalized.filter { it.isDigit() || it == '.' }.take(32)
    val oldCursor = value.selection.start.coerceIn(0, value.text.length)
    val beforeCursor = ConverterMath.normalize(value.text.take(oldCursor))
    val digitsBefore = beforeCursor.count { it.isDigit() }
    val decimalBefore = beforeCursor.contains('.')
    val fractionDigitsBefore = beforeCursor.substringAfter('.', "").count { it.isDigit() }

    val parts = candidate.split('.', limit = 2)
    val integer = parts[0]
    val groupedInteger = integer.reversed().chunked(3).joinToString(",").reversed()
    val formatted = groupedInteger +
        if (candidate.contains('.')) "." + parts.getOrElse(1) { "" } else ""

    val cursor = if (decimalBefore && formatted.contains('.')) {
        (formatted.indexOf('.') + 1 + fractionDigitsBefore).coerceAtMost(formatted.length)
    } else {
        var seen = 0
        var position = 0
        while (position < formatted.length && seen < digitsBefore) {
            if (formatted[position].isDigit()) seen++
            position++
        }
        position
    }

    return TextFieldValue(formatted, selection = TextRange(cursor))
}

private fun formatForInput(value: BigDecimal): String =
    value.stripTrailingZeros().toPlainString()
