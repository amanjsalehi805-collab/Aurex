package app.aurex.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

data class MarketQuote(
    val assetId: String,
    val price: Double,
    val unit: String,
    val changePct: Double?,
    val freshness: String,
    val source: String
)

class QuoteRepository {

    private val baseUrl =
        "https://aurex-backend-hu1t.onrender.com"

    suspend fun fetchQuotes(): List<MarketQuote> =
        withContext(Dispatchers.IO) {

            val connection = URL("$baseUrl/v1/quotes")
                .openConnection() as HttpURLConnection

            try {
                connection.requestMethod = "GET"
                connection.connectTimeout = 20000
                connection.readTimeout = 30000
                connection.setRequestProperty(
                    "Accept", "application/json"
                )

                if (connection.responseCode != 200) {
                    throw Exception(
                        "Server error: ${connection.responseCode}"
                    )
                }

                val response = connection.inputStream
                    .bufferedReader()
                    .use { it.readText() }

                val root = JSONObject(response)
                val quotes = root.getJSONArray("quotes")

                buildList {
                    for (i in 0 until quotes.length()) {
                        val item = quotes.getJSONObject(i)

                        add(
                            MarketQuote(
                                assetId = item.getString("asset_id"),
                                price = item.getDouble("price"),
                                unit = item.optString("unit", ""),
                                changePct = if (
                                    item.isNull("change_pct")
                                ) null else item.getDouble("change_pct"),
                                freshness = item.optString(
                                    "freshness", "unknown"
                                ),
                                source = item.optString(
                                    "source", "Unknown"
                                )
                            )
                        )
                    }
                }
            } finally {
                connection.disconnect()
            }
        }
}
