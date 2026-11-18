package app.aurex.data

import android.content.Context
import androidx.datastore.preferences.core.edit
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

data class CachedQuotes(
    val quotes: List<MarketQuote>,
    val savedAtMillis: Long
)

class PreferencesRepository(private val context: Context) {
    private val themeKey = stringPreferencesKey("theme")
    private val quotesCacheKey = stringPreferencesKey("quotes_cache")
    private val quotesCacheTimeKey = longPreferencesKey("quotes_cache_time")

    val theme: Flow<ThemeId> = context.dataStore.data.map { prefs ->
        prefs[themeKey]?.let {
            runCatching { ThemeId.valueOf(it) }.getOrNull()
        } ?: ThemeId.MIDNIGHT
    }

    suspend fun setTheme(theme: ThemeId) {
        context.dataStore.edit { it[themeKey] = theme.name }
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

                add(MarketQuote(
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
                ))
            }
        }

        if (quotes.isEmpty()) null else CachedQuotes(quotes, savedAt)
    }.getOrNull()
}

private fun JSONObject.cacheStringOrNull(key: String): String? =
    if (!has(key) || isNull(key)) null else optString(key)
