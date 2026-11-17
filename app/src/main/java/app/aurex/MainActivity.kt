package app.aurex

import android.os.Bundle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.compose.runtime.getValue
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.lifecycleScope
import app.aurex.data.PreferencesRepository
import app.aurex.data.ThemeId
import app.aurex.ui.AurexApp
import app.aurex.ui.AurexTheme
import kotlinx.coroutines.launch

class MainActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val repo = PreferencesRepository(applicationContext)
        setContent {
            val theme by repo.theme.collectAsStateWithLifecycle(initialValue = ThemeId.MIDNIGHT)
            AurexTheme(theme) {
                AurexApp(theme = theme, onTheme = { lifecycleScope.launch { repo.setTheme(it) } })
            }
        }
    }
}
