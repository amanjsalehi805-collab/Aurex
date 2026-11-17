package app.aurex.data

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

private val Context.dataStore by preferencesDataStore(name = "aurex_prefs")

enum class ThemeId { MIDNIGHT, OBSIDIAN, ARCTIC, CYBER, FOREST }

class PreferencesRepository(private val context: Context) {
    private val themeKey = stringPreferencesKey("theme")

    val theme: Flow<ThemeId> = context.dataStore.data.map { prefs ->
        prefs[themeKey]?.let { runCatching { ThemeId.valueOf(it) }.getOrNull() } ?: ThemeId.MIDNIGHT
    }

    suspend fun setTheme(theme: ThemeId) {
        context.dataStore.edit { it[themeKey] = theme.name }
    }
}
