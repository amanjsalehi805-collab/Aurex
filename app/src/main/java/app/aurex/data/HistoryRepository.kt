package app.aurex.data

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

class HistoryRepository {
    suspend fun fetch(assetId: String, hours: Int): HistoryData {
        val root = Api.get("/v1/history/$assetId?hours=$hours")
        val arr = root.getJSONArray("points")
        val points = buildList {
            for (i in 0 until arr.length()) {
                val p = arr.getJSONObject(i)
                val price = p.getDouble("price")
                if (price.isFinite() && price > 0) add(HistoryPoint(p.getLong("ts"), price))
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
