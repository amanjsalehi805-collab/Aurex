package app.aurex.ui

import androidx.appcompat.app.AppCompatDelegate
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.core.os.LocaleListCompat
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import app.aurex.R
import app.aurex.data.ThemeId

private data class Slot(val id: String, val titleRes: Int)

private val iranSlots = listOf(
    Slot("usd_free_irt", R.string.asset_usd_free),
    Slot("eur_free_irt", R.string.asset_eur_free),
    Slot("gold18_irt", R.string.asset_gold18),
    Slot("coin_irt", R.string.asset_coin),
    Slot("tse_index", R.string.asset_tse_index),
)
private val globalSlots = listOf(
    Slot("gold_oz_usd", R.string.asset_global_gold),
    Slot("silver_oz_usd", R.string.asset_global_silver),
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AurexApp(theme: ThemeId, onTheme: (ThemeId) -> Unit) {
    val nav = rememberNavController()
    val route = nav.currentBackStackEntryAsState().value?.destination?.route ?: "dashboard"
    Scaffold(
        topBar = {
            TopAppBar(title = {
                Column {
                    Text(stringResource(R.string.app_name))
                    Text(stringResource(R.string.tagline), style = MaterialTheme.typography.labelSmall)
                }
            })
        },
        bottomBar = {
            NavigationBar {
                NavigationBarItem(
                    selected = route == "dashboard",
                    onClick = { nav.navigate("dashboard") { launchSingleTop = true } },
                    icon = { Icon(Icons.Filled.Home, contentDescription = null) },
                    label = { Text(stringResource(R.string.nav_dashboard)) })
                NavigationBarItem(
                    selected = route == "settings",
                    onClick = { nav.navigate("settings") { launchSingleTop = true } },
                    icon = { Icon(Icons.Filled.Settings, contentDescription = null) },
                    label = { Text(stringResource(R.string.nav_settings)) })
            }
        },
    ) { padding ->
        NavHost(nav, startDestination = "dashboard", modifier = Modifier.padding(padding)) {
            composable("dashboard") { DashboardScreen() }
            composable("settings") { SettingsScreen(theme, onTheme) }
        }
    }
}

@Composable
private fun DashboardScreen() {
    LazyColumn(
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        item { SectionTitle(R.string.section_iran) }
        items(iranSlots) { AssetCard(it) }
        item { SectionTitle(R.string.section_global) }
        items(globalSlots) { AssetCard(it) }
    }
}

@Composable
private fun SectionTitle(res: Int) =
    Text(stringResource(res), style = MaterialTheme.typography.titleMedium,
        color = MaterialTheme.colorScheme.primary)

@Composable
private fun AssetCard(slot: Slot) {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)) {
        Column(Modifier.fillMaxWidth().padding(16.dp)) {
            Text(stringResource(slot.titleRes), style = MaterialTheme.typography.titleSmall)
            Spacer(Modifier.height(4.dp))
            Text(stringResource(R.string.no_data_title), style = MaterialTheme.typography.bodyMedium)
            Text(stringResource(R.string.no_data_body), style = MaterialTheme.typography.bodySmall)
        }
    }
}

private val themeOptions = listOf(
    ThemeId.MIDNIGHT to R.string.theme_midnight,
    ThemeId.OBSIDIAN to R.string.theme_obsidian,
    ThemeId.ARCTIC to R.string.theme_arctic,
    ThemeId.CYBER to R.string.theme_cyber,
    ThemeId.FOREST to R.string.theme_forest,
)
private val languageOptions = listOf(
    "en" to R.string.lang_en, "fa" to R.string.lang_fa, "ckb" to R.string.lang_ckb)

@Composable
private fun SettingsScreen(theme: ThemeId, onTheme: (ThemeId) -> Unit) {
    LazyColumn(contentPadding = PaddingValues(16.dp)) {
        item { SectionTitle(R.string.settings_theme) }
        items(themeOptions) { (id, label) ->
            Row(
                Modifier.fillMaxWidth().clickable { onTheme(id) }.padding(vertical = 4.dp),
                verticalAlignment = Alignment.CenterVertically) {
                RadioButton(selected = id == theme, onClick = { onTheme(id) })
                Text(stringResource(label))
            }
        }
        item { Spacer(Modifier.height(16.dp)); SectionTitle(R.string.settings_language) }
        items(languageOptions) { (tag, label) ->
            Row(
                Modifier.fillMaxWidth().clickable {
                    AppCompatDelegate.setApplicationLocales(LocaleListCompat.forLanguageTags(tag))
                }.padding(vertical = 12.dp)) {
                Text(stringResource(label))
            }
        }
    }
}
