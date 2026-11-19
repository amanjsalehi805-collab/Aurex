package app.aurex.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.consumeWindowInsets
import androidx.compose.foundation.layout.padding
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
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.repeatOnLifecycle
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import app.aurex.R
import app.aurex.data.AppSettings
import kotlinx.coroutines.delay

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
    settings: AppSettings,
    actions: SettingsActions,
    dashboardViewModel: DashboardViewModel,
    aiViewModel: AiViewModel,
) {
    val nav = rememberNavController()
    val route = nav.currentBackStackEntryAsState().value?.destination?.route ?: "home"
    val dashboardState by dashboardViewModel.state.collectAsStateWithLifecycle()
    val aiState by aiViewModel.state.collectAsStateWithLifecycle()

    // Automatic refresh runs only while the app is on screen, so it does not drain battery or data.
    val lifecycleOwner = LocalLifecycleOwner.current
    LaunchedEffect(settings.refreshMinutes, lifecycleOwner) {
        if (settings.refreshMinutes > 0) {
            lifecycleOwner.lifecycle.repeatOnLifecycle(Lifecycle.State.STARTED) {
                while (true) {
                    delay(settings.refreshMinutes * 60_000L)
                    dashboardViewModel.refresh()
                }
            }
        }
    }

    val navigateTab: (String) -> Unit = { target ->
        nav.navigate(target) {
            popUpTo(nav.graph.findStartDestination().id) { saveState = true }
            launchSingleTop = true
            restoreState = true
        }
    }
    val openAsset: (String) -> Unit = { id -> nav.navigate("asset/$id") { launchSingleTop = true } }
    val openConverter: () -> Unit = { nav.navigate("converter") { launchSingleTop = true } }
    val back: () -> Unit = { nav.popBackStack() }

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        bottomBar = {
            AurexBottomBar(
                // Detail screens belong to the tab they were opened from (Markets).
                currentRoute = if (route.startsWith("asset") || route == "converter") "markets" else route,
                onSelect = navigateTab,
            )
        },
    ) { padding ->
        NavHost(
            nav,
            startDestination = "home",
            modifier = Modifier.padding(padding).consumeWindowInsets(padding),
        ) {
            composable("home") {
                HomeScreen(
                    state = dashboardState,
                    onRefresh = { dashboardViewModel.refresh() },
                    onOpenSettings = { navigateTab("settings") },
                    onOpenConverter = openConverter,
                    onOpenAsset = openAsset,
                    onOpenAnalysis = {
                        aiViewModel.setTab(1)
                        navigateTab("ai")
                    },
                    onLoadHistory = { id, hours -> dashboardViewModel.loadHistory(id, hours) },
                )
            }
            composable("markets") {
                MarketsScreen(
                    state = dashboardState,
                    onRefresh = { dashboardViewModel.refresh() },
                    onOpenConverter = openConverter,
                    onOpenAsset = openAsset,
                    onToggleFavorite = { dashboardViewModel.toggleFavorite(it) },
                    onReloadStocks = { dashboardViewModel.loadStocks() },
                )
            }
            composable("asset/{id}") { entry ->
                AssetDetailScreen(
                    assetId = entry.arguments?.getString("id").orEmpty(),
                    state = dashboardState,
                    onBack = back,
                    onRefresh = { dashboardViewModel.refresh() },
                    onToggleFavorite = { dashboardViewModel.toggleFavorite(it) },
                    onLoadHistory = { id, hours -> dashboardViewModel.loadHistory(id, hours) },
                )
            }
            composable("converter") {
                ConverterScreen(
                    state = dashboardState,
                    onBack = back,
                    onRefresh = { dashboardViewModel.refresh() },
                )
            }
            composable("ai") {
                AiScreen(
                    state = aiState,
                    onTab = { aiViewModel.setTab(it) },
                    onSend = { text, language -> aiViewModel.send(text, language) },
                    onRetryChat = { aiViewModel.retry(it) },
                    onNewChat = { aiViewModel.newChat() },
                    onLoadAnalysis = { language, force -> aiViewModel.loadAnalysis(language, force) },
                )
            }
            composable("watchlist") {
                WatchlistScreen(
                    state = dashboardState,
                    onRefresh = { dashboardViewModel.refresh() },
                    onToggleFavorite = { dashboardViewModel.toggleFavorite(it) },
                    onOpenAsset = openAsset,
                )
            }
            composable("settings") { SettingsScreen(settings, actions) }
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
