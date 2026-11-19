package app.aurex.data

data class StocksStatus(val providerConfigured: Boolean, val message: String?, val symbolCount: Int)

class StocksRepository {
    suspend fun status(): StocksStatus {
        val st = Api.get("/v1/stocks/status")
        val symbols = Api.get("/v1/stocks/symbols").optJSONArray("symbols")
        return StocksStatus(
            providerConfigured = st.optBoolean("provider_configured", false),
            message = st.optStringOrNull("message"),
            symbolCount = symbols?.length() ?: 0,
        )
    }
}
