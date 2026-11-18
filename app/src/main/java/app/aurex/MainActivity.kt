package app.aurex

import android.os.Bundle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import androidx.appcompat.app.AppCompatActivity
import androidx.compose.runtime.getValue
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.lifecycleScope
import app.aurex.data.PreferencesRepository
import app.aurex.data.ThemeId
import app.aurex.ui.AurexApp
import app.aurex.ui.AurexTheme
import app.aurex.ui.DashboardViewModel
import kotlinx.coroutines.launch

class MainActivity : AppCompatActivity() {
    private val dashboardViewModel: DashboardViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val repo = PreferencesRepository(applicationContext)
        setContent {
            val theme by repo.theme.collectAsStateWithLifecycle(initialValue = ThemeId.MIDNIGHT)
            AurexTheme(theme) {
                AurexApp(
                    theme = theme,
                    onTheme = { lifecycleScope.launch { repo.setTheme(it) } },
                    dashboardViewModel = dashboardViewModel,
                )
            }
        }
    }
}
