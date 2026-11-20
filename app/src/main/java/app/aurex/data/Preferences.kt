package app.aurex.data

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.intPreferencesKey
import androidx.datastore.preferences.core.longPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import org.json.JSONArray
import org.json.JSONObject

private val Context.dataStore by preferencesDataStore(name = "aurex_prefs")

enum class ThemeId { MIDNIGHT, OBSIDIAN, ARCTIC, CYBER, FOREST }

enum class FontScript { FA, CKB, EN }

const val FONT_SYSTEM = "system"

data class AppSettings(
    val theme: ThemeId = ThemeId.MIDNIGHT,
    val fontFa: String = FONT_SYSTEM,
    val fontCkb: String = FONT_SYSTEM,
    val fontEn: String = FONT_SYSTEM,
    /** 0 = off. Automatic refresh only runs while the app is on screen. */
    val refreshMinutes: Int = 5,
)

data class CachedQuotes(
    val quotes: List<MarketQuote>,
    val savedAtMillis: Long
)

class PreferencesRepository(private val context: Context) {
    private val themeKey = stringPreferencesKey("theme")
    private val quotesCacheKey = stringPreferencesKey("quotes_cache")
    private val quotesCacheTimeKey = longPreferencesKey("quotes_cache_time")
    private val favoritesKey = stringPreferencesKey("favorites")
    private val fontFaKey = stringPreferencesKey("font_fa")
    private val fontCkbKey = stringPreferencesKey("font_ckb")
    private val fontEnKey = stringPreferencesKey("font_en")
    private val refreshKey = intPreferencesKey("refresh_minutes")

    val theme: Flow<ThemeId> = context.dataStore.data.map { prefs ->
        prefs[themeKey]?.let {
            runCatching { ThemeId.valueOf(it) }.getOrNull()
        } ?: ThemeId.MIDNIGHT
    }

    val settings: Flow<AppSettings> = context.dataStore.data.map { prefs ->
        AppSettings(
            theme = prefs[themeKey]?.let { runCatching { ThemeId.valueOf(it) }.getOrNull() }
                ?: ThemeId.MIDNIGHT,
            fontFa = prefs[fontFaKey] ?: FONT_SYSTEM,
            fontCkb = prefs[fontCkbKey] ?: FONT_SYSTEM,
            fontEn = prefs[fontEnKey] ?: FONT_SYSTEM,
            refreshMinutes = (prefs[refreshKey] ?: 5).takeIf { it in listOf(0, 1, 5, 15) } ?: 5,
        )
    }

    val favorites: Flow<List<String>> = context.dataStore.data.map { prefs ->
        runCatching {
            val json = JSONArray(prefs[favoritesKey] ?: "[]")
            buildList {
                for (i in 0 until json.length()) {
                    val id = json.optString(i)
                    if (id.isNotBlank() && id !in this) add(id)
                }
            }
        }.getOrDefault(emptyList())
    }

    suspend fun setTheme(theme: ThemeId) {
        context.dataStore.edit { it[themeKey] = theme.name }
    }

    suspend fun setFont(script: FontScript, fontId: String) {
        context.dataStore.edit {
            when (script) {
                FontScript.FA -> it[fontFaKey] = fontId
                FontScript.CKB -> it[fontCkbKey] = fontId
                FontScript.EN -> it[fontEnKey] = fontId
            }
        }
    }

    suspend fun setRefreshMinutes(minutes: Int) {
        context.dataStore.edit { it[refreshKey] = minutes }
    }

    suspend fun setFavorite(assetId: String, favorite: Boolean) {
        context.dataStore.edit { prefs ->
            val current = readFavoriteIds(prefs[favoritesKey])
            if (favorite) {
                if (assetId !in current) current.add(assetId)
            } else {
                current.remove(assetId)
            }
            prefs[favoritesKey] = JSONArray(current).toString()
        }
    }

    suspend fun moveFavorite(assetId: String, offset: Int) {
        if (offset == 0) return
        context.dataStore.edit { prefs ->
            val current = readFavoriteIds(prefs[favoritesKey])
            val from = current.indexOf(assetId)
            val to = from + offset
            if (from >= 0 && to in current.indices) {
                val item = current.removeAt(from)
                current.add(to, item)
                prefs[favoritesKey] = JSONArray(current).toString()
            }
        }
    }

    suspend fun saveQuotesCache(quotes: List<MarketQuote>) {
        if (quotes.isEmpty()) return

        val json = JSONArray()
        quotes.forEach { quote ->
            json.put(JSONObject().apply {
                put("assetId", quote.assetId)
                put("price", quote.price)
                put("unit", quote.unit)
                put("changePct", quote.changePct ?: JSONObject.NULL)
                put("freshness", quote.freshness)
                put("source", quote.source)
                put("sourceTimestamp", quote.sourceTimestamp ?: JSONObject.NULL)
                put("fetchedAt", quote.fetchedAt ?: JSONObject.NULL)
                put("flags", JSONArray(quote.flags))
            })
        }

        context.dataStore.edit { prefs ->
            prefs[quotesCacheKey] = json.toString()
            prefs[quotesCacheTimeKey] = System.currentTimeMillis()
        }
    }

    suspend fun loadQuotesCache(): CachedQuotes? = runCatching {
        val prefs = context.dataStore.data.first()
        val raw = prefs[quotesCacheKey] ?: return null
        val savedAt = prefs[quotesCacheTimeKey] ?: return null
        val json = JSONArray(raw)

        val quotes = buildList {
            for (i in 0 until json.length()) {
                val item = json.getJSONObject(i)
                val price = item.optDouble("price", Double.NaN)
                if (!price.isFinite()) continue

                val flagsArray = item.optJSONArray("flags")
                val flags = buildList {
                    if (flagsArray != null) {
                        for (j in 0 until flagsArray.length()) {
                            add(flagsArray.getString(j))
                        }
                    }
                }

                add(
                    MarketQuote(
                        assetId = item.getString("assetId"),
                        price = price,
                        unit = item.optString("unit", ""),
                        changePct = if (item.isNull("changePct")) null
                        else item.optDouble("changePct"),
                        freshness = item.optString("freshness", "unknown"),
                        source = item.optString("source", "Unknown"),
                        sourceTimestamp = item.cacheStringOrNull("sourceTimestamp"),
                        fetchedAt = item.cacheStringOrNull("fetchedAt"),
                        flags = flags
                    )
                )
            }
        }

        if (quotes.isEmpty()) null else CachedQuotes(quotes, savedAt)
    }.getOrNull()
}

private fun JSONObject.cacheStringOrNull(key: String): String? =
    if (!has(key) || isNull(key)) null else optString(key)

private fun readFavoriteIds(raw: String?): MutableList<String> {
    return runCatching {
        val json = JSONArray(raw ?: "[]")
        buildList {
            for (i in 0 until json.length()) {
                val id = json.optString(i)
                if (id.isNotBlank() && id !in this) add(id)
            }
        }.toMutableList()
    }.getOrDefault(mutableListOf())
}
