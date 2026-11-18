package app.aurex.ui

import androidx.appcompat.app.AppCompatDelegate
import androidx.compose.foundation.clickable
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Face
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.List
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Star
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.core.os.LocaleListCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import app.aurex.R
import app.aurex.data.ThemeId

private data class Destination(val route: String, val labelRes: Int, val icon: ImageVector)

private val destinations = listOf(
    Destination("home", R.string.nav_home, Icons.Filled.Home),
    Destination("markets", R.string.nav_markets, Icons.Filled.List),
    Destination("ai", R.string.nav_ai, Icons.Filled.Face),
    Destination("watchlist", R.string.nav_watchlist, Icons.Filled.Star),
    Destination("settings", R.string.nav_settings, Icons.Filled.Settings),
)

@Composable
fun AurexApp(
    theme: ThemeId,
    onTheme: (ThemeId) -> Unit,
    dashboardViewModel: DashboardViewModel,
) {
    val nav = rememberNavController()
    val route = nav.currentBackStackEntryAsState().value?.destination?.route ?: "home"
    val dashboardState by dashboardViewModel.state.collectAsStateWithLifecycle()

    val navigateTo: (String) -> Unit = { target ->
        nav.navigate(target) {
            popUpTo(nav.graph.findStartDestination().id) { saveState = true }
            launchSingleTop = true
            restoreState = true
        }
    }

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        bottomBar = { AurexBottomBar(currentRoute = route, onSelect = navigateTo) },
    ) { padding ->
        NavHost(nav, startDestination = "home", modifier = Modifier.padding(padding)) {
            composable("home") {
                HomeScreen(
                    state = dashboardState,
                    onRefresh = { dashboardViewModel.refresh() },
                    onOpenSettings = { navigateTo("settings") },
                )
            }
            composable("markets") {
                PlaceholderScreen(
                    Icons.Filled.List,
                    R.string.placeholder_markets_title,
                    R.string.placeholder_markets_body,
                )
            }
            composable("ai") {
                PlaceholderScreen(
                    Icons.Filled.Face,
                    R.string.placeholder_ai_title,
                    R.string.placeholder_ai_body,
                )
            }
            composable("watchlist") {
                PlaceholderScreen(
                    Icons.Filled.Star,
                    R.string.placeholder_watchlist_title,
                    R.string.placeholder_watchlist_body,
                )
            }
            composable("settings") { SettingsScreen(theme, onTheme) }
        }
    }
}

@Composable
private fun AurexBottomBar(currentRoute: String, onSelect: (String) -> Unit) {
    val colors = LocalAurexColors.current
    Column {
        HorizontalDivider(color = colors.border)
        NavigationBar(
            containerColor = MaterialTheme.colorScheme.surface,
            tonalElevation = 0.dp,
        ) {
            destinations.forEach { dest ->
                NavigationBarItem(
                    selected = currentRoute == dest.route,
                    onClick = { onSelect(dest.route) },
                    icon = { Icon(dest.icon, contentDescription = null) },
                    label = {
                        Text(
                            stringResource(dest.labelRes),
                            style = MaterialTheme.typography.labelSmall,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                    },
                    alwaysShowLabel = true,
                    colors = NavigationBarItemDefaults.colors(
                        selectedIconColor = colors.gold,
                        selectedTextColor = colors.gold,
                        unselectedIconColor = colors.textSecondary,
                        unselectedTextColor = colors.textSecondary,
                        indicatorColor = colors.gold.copy(alpha = 0.14f),
                    ),
                )
            }
        }
    }
}

@Composable
private fun PlaceholderScreen(icon: ImageVector, titleRes: Int, bodyRes: Int) {
    val colors = LocalAurexColors.current
    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(32.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Box(
            modifier = Modifier
                .size(64.dp)
                .clip(CircleShape)
                .background(colors.gold.copy(alpha = 0.12f))
                .border(1.dp, colors.gold.copy(alpha = 0.4f), CircleShape),
            contentAlignment = Alignment.Center,
        ) {
            Icon(icon, contentDescription = null, tint = colors.gold)
        }
        Spacer(Modifier.height(16.dp))
        Text(
            stringResource(titleRes),
            style = MaterialTheme.typography.titleLarge,
            textAlign = TextAlign.Center,
        )
        Spacer(Modifier.height(8.dp))
        Text(
            stringResource(bodyRes),
            style = MaterialTheme.typography.bodyMedium,
            color = colors.textSecondary,
            textAlign = TextAlign.Center,
        )
        Spacer(Modifier.height(16.dp))
        ChipLabel(stringResource(R.string.coming_soon))
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
    "en" to R.string.lang_en,
    "fa" to R.string.lang_fa,
    "ckb" to R.string.lang_ckb
)

@Composable
private fun SettingsScreen(theme: ThemeId, onTheme: (ThemeId) -> Unit) {
    val currentTag = AppCompatDelegate.getApplicationLocales().toLanguageTags()
    LazyColumn(
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        item {
            Text(
                stringResource(R.string.nav_settings),
                style = MaterialTheme.typography.titleLarge,
            )
        }
        item { SectionHeader(R.string.settings_theme) }
        item {
            AurexCard(modifier = Modifier.fillMaxWidth()) {
                themeOptions.forEach { (id, label) ->
                    Row(
                        Modifier
                            .fillMaxWidth()
                            .clickable { onTheme(id) }
                            .padding(horizontal = 8.dp, vertical = 4.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        RadioButton(selected = id == theme, onClick = null)
                        Spacer(Modifier.size(12.dp))
                        Text(stringResource(label))
                    }
                }
            }
        }
        item { SectionHeader(R.string.settings_language) }
        item {
            AurexCard(modifier = Modifier.fillMaxWidth()) {
                languageOptions.forEach { (tag, label) ->
                    Row(
                        Modifier
                            .fillMaxWidth()
                            .clickable {
                                AppCompatDelegate.setApplicationLocales(
                                    LocaleListCompat.forLanguageTags(tag)
                                )
                            }
                            .padding(horizontal = 8.dp, vertical = 4.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        RadioButton(selected = currentTag.startsWith(tag), onClick = null)
                        Spacer(Modifier.size(12.dp))
                        Text(stringResource(label))
                    }
                }
            }
        }
    }
}
