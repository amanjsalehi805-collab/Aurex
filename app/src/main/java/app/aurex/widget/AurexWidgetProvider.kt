package app.aurex.widget

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.widget.RemoteViews
import app.aurex.MainActivity
import app.aurex.R
import app.aurex.data.CachedQuotes
import app.aurex.data.PreferencesRepository
import app.aurex.data.QuoteRepository
import app.aurex.ui.formatLocalTime
import app.aurex.ui.formatPrice
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

/**
 * Home-screen widget: dollar, 18k gold and coin prices from the app's saved (cached) quotes.
 *  - Shown immediately from the cache, then refreshed from the AUREX server (short timeouts).
 *  - Fetches at most once per [MIN_FETCH_INTERVAL_MS] unless the user taps the refresh button.
 *  - Offline or failed fetch: keeps the saved prices, shows the real time they were fetched and says "offline".
 *  - Never shows a made-up number: a missing price reads "Unavailable".
 */
class AurexWidgetProvider : AppWidgetProvider() {

    override fun onUpdate(context: Context, manager: AppWidgetManager, appWidgetIds: IntArray) {
        refresh(context, manager, appWidgetIds, force = false)
    }

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == ACTION_REFRESH) {
            val manager = AppWidgetManager.getInstance(context)
            val ids = manager.getAppWidgetIds(ComponentName(context, AurexWidgetProvider::class.java))
            refresh(context, manager, ids, force = true)
        } else {
            super.onReceive(context, intent)
        }
    }

    private fun refresh(context: Context, manager: AppWidgetManager, ids: IntArray, force: Boolean) {
        if (ids.isEmpty()) return
        val appContext = context.applicationContext
        val pending = goAsync()
        CoroutineScope(SupervisorJob() + Dispatchers.IO).launch {
            try {
                val prefs = PreferencesRepository(appContext)
                var cached = runCatching { prefs.loadQuotesCache() }.getOrNull()
                render(appContext, manager, ids, cached, offline = false)

                val age = cached?.let { System.currentTimeMillis() - it.savedAtMillis } ?: Long.MAX_VALUE
                if (force || age > MIN_FETCH_INTERVAL_MS) {
                    try {
                        // Short timeouts: a broadcast must finish quickly.
                        val result = QuoteRepository().fetchQuotes(readTimeoutMs = 6_000, connectTimeoutMs = 4_000)
                        if (result.quotes.isNotEmpty()) {
                            prefs.saveQuotesCache(result.quotes)
                            cached = prefs.loadQuotesCache()
                            render(appContext, manager, ids, cached, offline = false)
                        } else {
                            render(appContext, manager, ids, cached, offline = true)
                        }
                    } catch (e: Exception) {
                        render(appContext, manager, ids, cached, offline = true)
                    }
                }
            } finally {
                pending.finish()
            }
        }
    }

    private fun render(
        context: Context,
        manager: AppWidgetManager,
        ids: IntArray,
        cached: CachedQuotes?,
        offline: Boolean,
    ) {
        val locale = context.resources.configuration.locales[0]
        val views = RemoteViews(context.packageName, R.layout.widget_aurex)

        val rows = listOf(
            Triple(R.id.w_name_1 to R.id.w_value_1, "usd_free_irt", R.string.w_usd),
            Triple(R.id.w_name_2 to R.id.w_value_2, "gold18_irt", R.string.w_gold18),
            Triple(R.id.w_name_3 to R.id.w_value_3, "coin_irt", R.string.w_coin),
        )
        rows.forEach { (viewIds, assetId, labelRes) ->
            val quote = cached?.quotes?.firstOrNull { it.assetId == assetId && it.unit == "IRT" }
            views.setTextViewText(viewIds.first, context.getString(labelRes))
            views.setTextViewText(
                viewIds.second,
                if (quote != null) {
                    formatPrice(quote.price, locale) + " " + context.getString(R.string.unit_irt)
                } else {
                    context.getString(R.string.unavailable)
                },
            )
        }

        val status = if (cached == null) {
            context.getString(R.string.widget_no_data)
        } else {
            val parts = mutableListOf(
                context.getString(R.string.widget_updated, formatLocalTime(cached.savedAtMillis, locale))
            )
            if (offline) parts += context.getString(R.string.widget_offline)
            if (System.currentTimeMillis() - cached.savedAtMillis > OLD_AFTER_MS) {
                parts += context.getString(R.string.widget_old)
            }
            parts.joinToString("  •  ")
        }
        views.setTextViewText(R.id.w_status, status)

        val flags = PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        val open = PendingIntent.getActivity(
            context, 0,
            Intent(context, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
            flags,
        )
        views.setOnClickPendingIntent(R.id.widget_root, open)
        val refresh = PendingIntent.getBroadcast(
            context, 1,
            Intent(context, AurexWidgetProvider::class.java).setAction(ACTION_REFRESH),
            flags,
        )
        views.setOnClickPendingIntent(R.id.widget_refresh, refresh)

        manager.updateAppWidget(ids, views)
    }

    companion object {
        const val ACTION_REFRESH = "app.aurex.widget.REFRESH"
        private const val MIN_FETCH_INTERVAL_MS = 5 * 60 * 1000L
        private const val OLD_AFTER_MS = 30 * 60 * 1000L
    }
}
