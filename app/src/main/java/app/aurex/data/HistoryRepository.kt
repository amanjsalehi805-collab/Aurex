package app.aurex.data

import java.util.concurrent.ConcurrentHashMap
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

data class HistoryPoint(val ts: Long, val price: Double)

data class HistorySummary(
    val points: Int,
    val sufficient: Boolean,
    val changePct: Double?,
    val min: Double?,
    val max: Double?,
    val spanSeconds: Long,
)

data class HistoryData(val points: List<HistoryPoint>, val summary: HistorySummary)

class HistoryRepository(
    private val cacheTtlMillis: Long = 5 * 60 * 1000L,
    private val nowMillis: () -> Long = System::currentTimeMillis,
    private val loader: suspend (String, Int) -> HistoryData = { assetId, hours ->
        fetchFromApi(assetId, hours)
    },
) {
    private data class CacheEntry(val data: HistoryData, val savedAt: Long)

    private val cache = ConcurrentHashMap<String, CacheEntry>()
    private val locks = ConcurrentHashMap<String, Mutex>()

    suspend fun fetch(assetId: String, hours: Int): HistoryData {
        val key = "$assetId|$hours"
        fun cachedResult(): HistoryData? {
            val entry = cache[key] ?: return null
            val age = nowMillis() - entry.savedAt
            return entry.data.takeIf { age >= 0 && age < cacheTtlMillis }
        }

        cachedResult()?.let { return it }

        return locks.getOrPut(key) { Mutex() }.withLock {
            cachedResult() ?: loader(assetId, hours).also {
                cache[key] = CacheEntry(it, nowMillis())
            }
        }
    }

    companion object {
        private suspend fun fetchFromApi(assetId: String, hours: Int): HistoryData {
            val root = Api.get("/v1/history/$assetId?hours=$hours")
            val arr = root.getJSONArray("points")
            val points = buildList {
                for (i in 0 until arr.length()) {
                    val p = arr.getJSONObject(i)
                    val price = p.getDouble("price")
                    if (price.isFinite() && price > 0) {
                        add(HistoryPoint(p.getLong("ts"), price))
                    }
                }
            }
            val s = root.optJSONObject("summary")
            val summary = HistorySummary(
                points = s?.optInt("points", points.size) ?: points.size,
                sufficient = s?.optBoolean("sufficient", false) ?: false,
                changePct = s?.optDoubleOrNull("change_pct"),
                min = s?.optDoubleOrNull("min"),
                max = s?.optDoubleOrNull("max"),
                spanSeconds = s?.optLong("span_s", 0L) ?: 0L,
            )
            return HistoryData(points, summary)
        }
    }
}
