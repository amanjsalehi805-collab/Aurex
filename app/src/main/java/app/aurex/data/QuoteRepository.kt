package app.aurex.data

import org.json.JSONObject

data class MarketQuote(
    val assetId: String,
    val price: Double,
    val unit: String,
    val changePct: Double?,
    val freshness: String,
    val source: String,
    val sourceTimestamp: String? = null,
    val fetchedAt: String? = null,
    val flags: List<String> = emptyList()
)

data class QuotesResult(
    val quotes: List<MarketQuote>,
    val unavailable: Set<String>,
    val staleAfterSeconds: Long,
)

class QuoteRepository {

    suspend fun fetchQuotes(readTimeoutMs: Int = 30_000, connectTimeoutMs: Int = 20_000): QuotesResult {
        val root = Api.get("/v1/quotes", readTimeoutMs, connectTimeoutMs)
        val array = root.getJSONArray("quotes")
        val quotes = buildList {
            for (i in 0 until array.length()) {
                val item = array.getJSONObject(i)
                val price = item.getDouble("price")
                if (!price.isFinite() || price <= 0) continue
                add(
                    MarketQuote(
                        assetId = item.getString("asset_id"),
                        price = price,
                        unit = item.optString("unit", ""),
                        changePct = item.optDoubleOrNull("change_pct"),
                        freshness = item.optString("freshness", "unknown"),
                        source = item.optString("source", "Unknown"),
                        sourceTimestamp = item.optStringOrNull("source_timestamp"),
                        fetchedAt = item.optStringOrNull("fetched_at"),
                        flags = item.flagList(),
                    )
                )
            }
        }
        val unavailable = buildSet {
            val arr = root.optJSONArray("unavailable")
            if (arr != null) for (i in 0 until arr.length()) add(arr.getString(i))
        }
        val staleAfter = root.optLong("stale_after_s", 900L).takeIf { it > 0 } ?: 900L
        return QuotesResult(quotes, unavailable, staleAfter)
    }
}

private fun JSONObject.flagList(): List<String> {
    val arr = optJSONArray("flags") ?: return emptyList()
    return buildList { for (i in 0 until arr.length()) add(arr.getString(i)) }
}
