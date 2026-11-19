package app.aurex.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import app.aurex.R
import app.aurex.data.Api
import app.aurex.data.AppSettings
import app.aurex.data.FontScript
import app.aurex.data.FONT_SYSTEM
import app.aurex.data.ThemeId

data class SettingsActions(
    val onTheme: (ThemeId) -> Unit,
    val onLanguage: (String) -> Unit,
    val onFont: (FontScript, String) -> Unit,
    val onRefreshMinutes: (Int) -> Unit,
)

private val themeOptions = listOf(
    ThemeId.MIDNIGHT to R.string.theme_midnight,
    ThemeId.OBSIDIAN to R.string.theme_obsidian,
    ThemeId.ARCTIC to R.string.theme_arctic,
    ThemeId.CYBER to R.string.theme_cyber,
    ThemeId.FOREST to R.string.theme_forest,
)

private val languageOptions = listOf(
    "en" to R.string.lang_en,
    "fa" to R.string.lang_fa,
    "ckb" to R.string.lang_ckb,
)

private val refreshOptions = listOf(
    0 to R.string.interval_off,
    1 to R.string.interval_1,
    5 to R.string.interval_5,
    15 to R.string.interval_15,
)

@Composable
private fun RadioRow(selected: Boolean, label: String, onClick: () -> Unit, sample: String? = null,
                     family: androidx.compose.ui.text.font.FontFamily? = null) {
    Row(
        Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(horizontal = 8.dp, vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        RadioButton(selected = selected, onClick = null)
        Spacer(Modifier.size(12.dp))
        Column {
            Text(label)
            if (sample != null) {
                Text(
                    sample,
                    style = MaterialTheme.typography.bodySmall,
                    color = LocalAurexColors.current.textSecondary,
                    fontFamily = family,
                )
            }
        }
    }
}

@Composable
private fun FontSection(
    titleRes: Int,
    script: FontScript,
    selectedId: String,
    sampleRes: Int,
    onSelect: (String) -> Unit,
) {
    val context = LocalContext.current
    val options = remember(context, script) { FontCatalog.options(context, script) }
    // A saved font that is no longer available is shown as the system font (that is what is applied).
    val effective = if (options.any { it.id == selectedId }) selectedId else FONT_SYSTEM
    val colors = LocalAurexColors.current
    Column {
        SectionHeader(titleRes)
        Spacer(Modifier.size(10.dp))
        AurexCard(modifier = Modifier.fillMaxWidth()) {
            options.forEach { option ->
                RadioRow(
                    selected = option.id == effective,
                    label = stringResource(option.labelRes),
                    onClick = { onSelect(option.id) },
                    sample = stringResource(sampleRes),
                    family = remember(context, script, option.id) { FontCatalog.family(context, script, option.id) },
                )
            }
        }
        Text(
            stringResource(R.string.settings_font_note),
            style = MaterialTheme.typography.labelSmall,
            color = colors.textSecondary,
            modifier = Modifier.padding(top = 6.dp),
        )
    }
}

@Composable
fun SettingsScreen(settings: AppSettings, actions: SettingsActions) {
    val context = LocalContext.current
    val currentLanguage = languageTag(LocalAppLocale.current)
    val colors = LocalAurexColors.current
    val version = remember(context) {
        runCatching { context.packageManager.getPackageInfo(context.packageName, 0).versionName }
            .getOrNull() ?: "?"
    }

    LazyColumn(
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        item { Text(stringResource(R.string.nav_settings), style = MaterialTheme.typography.titleLarge) }

        item { SectionHeader(R.string.settings_language) }
        item {
            AurexCard(modifier = Modifier.fillMaxWidth()) {
                languageOptions.forEach { (tag, label) ->
                    RadioRow(currentLanguage == tag, stringResource(label), { actions.onLanguage(tag) })
                }
            }
        }

        item { SectionHeader(R.string.settings_theme) }
        item {
            AurexCard(modifier = Modifier.fillMaxWidth()) {
                themeOptions.forEach { (id, label) ->
                    RadioRow(id == settings.theme, stringResource(label), { actions.onTheme(id) })
                }
            }
        }

        item {
            FontSection(R.string.settings_font_fa, FontScript.FA, settings.fontFa, R.string.font_sample_fa) {
                actions.onFont(FontScript.FA, it)
            }
        }
        item {
            FontSection(R.string.settings_font_ckb, FontScript.CKB, settings.fontCkb, R.string.font_sample_ckb) {
                actions.onFont(FontScript.CKB, it)
            }
        }
        item {
            FontSection(R.string.settings_font_en, FontScript.EN, settings.fontEn, R.string.font_sample_en) {
                actions.onFont(FontScript.EN, it)
            }
        }

        item { SectionHeader(R.string.settings_data) }
        item {
            AurexCard(modifier = Modifier.fillMaxWidth()) {
                Text(
                    stringResource(R.string.settings_refresh_interval),
                    style = MaterialTheme.typography.titleSmall,
                    modifier = Modifier.padding(start = 14.dp, top = 12.dp, end = 14.dp),
                )
                refreshOptions.forEach { (minutes, label) ->
                    RadioRow(settings.refreshMinutes == minutes, stringResource(label), { actions.onRefreshMinutes(minutes) })
                }
                Text(
                    stringResource(R.string.settings_refresh_note),
                    style = MaterialTheme.typography.labelSmall,
                    color = colors.textSecondary,
                    modifier = Modifier.padding(start = 14.dp, end = 14.dp, bottom = 12.dp),
                )
            }
        }

        item { SectionHeader(R.string.settings_sources) }
        item {
            AurexCard(modifier = Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(stringResource(R.string.sources_body), style = MaterialTheme.typography.bodyMedium)
                    Text(
                        stringResource(R.string.settings_server, Api.BASE_URL),
                        style = MaterialTheme.typography.labelSmall,
                        color = colors.textSecondary,
                    )
                }
            }
        }

        item { SectionHeader(R.string.settings_about) }
        item {
            AurexCard(modifier = Modifier.fillMaxWidth()) {
                Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                    AurexLogo(size = 48.dp)
                    Spacer(Modifier.size(14.dp))
                    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text(stringResource(R.string.app_name), style = MaterialTheme.typography.titleMedium)
                        Text(
                            stringResource(R.string.tagline),
                            style = MaterialTheme.typography.labelSmall,
                            color = colors.gold,
                        )
                        Text(
                            stringResource(R.string.about_version, version),
                            style = MaterialTheme.typography.labelSmall,
                            color = colors.textSecondary,
                        )
                    }
                }
                Column(Modifier.padding(start = 16.dp, end = 16.dp, bottom = 16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(stringResource(R.string.about_body), style = MaterialTheme.typography.bodySmall)
                    Text(
                        stringResource(R.string.about_fonts),
                        style = MaterialTheme.typography.labelSmall,
                        color = colors.textSecondary,
                    )
                }
            }
        }
    }
}
