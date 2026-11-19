package app.aurex

import android.os.Bundle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import androidx.appcompat.app.AppCompatActivity
import androidx.appcompat.app.AppCompatDelegate
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.core.os.LocaleListCompat
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.lifecycleScope
import app.aurex.data.AppSettings
import app.aurex.data.PreferencesRepository
import app.aurex.ui.AiViewModel
import app.aurex.ui.AurexApp
import app.aurex.ui.AurexTheme
import app.aurex.ui.DashboardViewModel
import app.aurex.ui.SettingsActions
import kotlinx.coroutines.launch

class MainActivity : AppCompatActivity() {
    private val dashboardViewModel: DashboardViewModel by viewModels()
    private val aiViewModel: AiViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        // System splash (logo on black). No artificial delay: it ends with the first frame.
        installSplashScreen()
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val repo = PreferencesRepository(applicationContext)
        setContent {
            val settings by repo.settings.collectAsStateWithLifecycle(initialValue = AppSettings())
            val actions = remember {
                SettingsActions(
                    onTheme = { lifecycleScope.launch { repo.setTheme(it) } },
                    onLanguage = { tag ->
                        // Persisted by AppCompat (AppLocalesMetadataHolderService) and applied app-wide.
                        AppCompatDelegate.setApplicationLocales(LocaleListCompat.forLanguageTags(tag))
                    },
                    onFont = { script, id -> lifecycleScope.launch { repo.setFont(script, id) } },
                    onRefreshMinutes = { lifecycleScope.launch { repo.setRefreshMinutes(it) } },
                )
            }
            AurexTheme(settings) {
                AurexApp(
                    settings = settings,
                    actions = actions,
                    dashboardViewModel = dashboardViewModel,
                    aiViewModel = aiViewModel,
                )
            }
        }
    }
}
