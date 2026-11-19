package app.aurex.data

import org.json.JSONArray
import org.json.JSONObject

data class ChatMessage(val role: String, val text: String)

data class AnalysisRow(
    val assetId: String,
    val price: Double,
    val unit: String,
    val freshness: String,
    val providerChangePct: Double?,
    val historyChangePct: Double?,
    val historyPoints: Int,
)

data class AnalysisResult(
    val status: String,
    val generatedAtSeconds: Long,
    val sources: List<String>,
    val historySufficient: Boolean,
    val rows: List<AnalysisRow>,
    val unavailable: List<String>,
    val aiStatus: String,
    val aiText: String?,
    val aiModel: String?,
    val aiCached: Boolean,
    val aiErrorCode: String?,
)

class AiRepository {

    suspend fun chat(messages: List<ChatMessage>, language: String): String {
        val arr = JSONArray()
        messages.forEach {
            arr.put(JSONObject().put("role", it.role).put("content", it.text))
        }
        val body = JSONObject().put("messages", arr).put("language", language)
        val root = Api.post("/v1/ai/chat", body)
        val reply = root.optString("reply", "").trim()
        if (reply.isEmpty()) throw ApiException("ai_bad_response")
        return reply
    }

    suspend fun analysis(language: String, force: Boolean): AnalysisResult {
        val body = JSONObject().put("language", language).put("force", force)
        val root = Api.post("/v1/ai/analysis", body)
        val data = root.optJSONObject("data")
        val quotes = data?.optJSONArray("quotes") ?: JSONArray()
        val rows = buildList {
            for (i in 0 until quotes.length()) {
                val q = quotes.getJSONObject(i)
                val price = q.optDouble("price", Double.NaN)
                if (!price.isFinite()) continue
                add(
                    AnalysisRow(
                        assetId = q.getString("asset_id"),
                        price = price,
                        unit = q.optString("unit", ""),
                        freshness = q.optString("freshness", "unknown"),
                        providerChangePct = q.optDoubleOrNull("provider_change_pct"),
                        historyChangePct = q.optDoubleOrNull("history_change_pct"),
                        historyPoints = q.optInt("history_points", 0),
                    )
                )
            }
        }
        val ai = root.optJSONObject("ai")
        return AnalysisResult(
            status = root.optString("status", "ok"),
            generatedAtSeconds = root.optLong("generated_at", 0L),
            sources = root.optJSONArray("sources").toStringList(),
            historySufficient = root.optBoolean("history_sufficient", false),
            rows = rows,
            unavailable = data?.optJSONArray("unavailable_assets").toStringList(),
            aiStatus = ai?.optString("status", "error") ?: "error",
            aiText = ai?.optStringOrNull("text"),
            aiModel = ai?.optStringOrNull("model"),
            aiCached = ai?.optBoolean("cached", false) ?: false,
            aiErrorCode = ai?.optStringOrNull("code"),
        )
    }
}

private fun JSONArray?.toStringList(): List<String> {
    if (this == null) return emptyList()
    return buildList { for (i in 0 until length()) add(getString(i)) }
}
