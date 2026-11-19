package app.aurex.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONException
import org.json.JSONObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.SocketTimeoutException
import java.net.URL

/** Stable machine-readable error code; the UI maps it to a localized message. */
class ApiException(val code: String, val http: Int = 0) : Exception(code)

object Api {
    /** Existing backend. Unchanged. */
    const val BASE_URL = "https://aurex-backend-hu1t.onrender.com"

    suspend fun get(path: String, readTimeoutMs: Int = 30_000, connectTimeoutMs: Int = 20_000): JSONObject =
        request("GET", path, null, readTimeoutMs, connectTimeoutMs)

    suspend fun post(path: String, body: JSONObject, readTimeoutMs: Int = 70_000): JSONObject =
        request("POST", path, body, readTimeoutMs, 20_000)

    private suspend fun request(
        method: String,
        path: String,
        body: JSONObject?,
        readTimeoutMs: Int,
        connectTimeoutMs: Int,
    ): JSONObject = withContext(Dispatchers.IO) {
        val connection = try {
            URL(BASE_URL + path).openConnection() as HttpURLConnection
        } catch (e: IOException) {
            throw ApiException("network")
        }
        try {
            connection.requestMethod = method
            connection.connectTimeout = connectTimeoutMs
            connection.readTimeout = readTimeoutMs
            connection.setRequestProperty("Accept", "application/json")
            if (body != null) {
                connection.doOutput = true
                connection.setRequestProperty("Content-Type", "application/json; charset=utf-8")
                connection.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
            }
            val status = connection.responseCode
            val stream = if (status in 200..299) connection.inputStream else connection.errorStream
            val text = stream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() }.orEmpty()
            if (status !in 200..299) throw ApiException(errorCodeOf(text, status), status)
            try {
                JSONObject(text)
            } catch (e: JSONException) {
                throw ApiException("bad_response", status)
            }
        } catch (e: ApiException) {
            throw e
        } catch (e: SocketTimeoutException) {
            throw ApiException("timeout")
        } catch (e: IOException) {
            throw ApiException("network")
        } finally {
            connection.disconnect()
        }
    }

    private fun errorCodeOf(text: String, status: Int): String {
        val parsed = runCatching { JSONObject(text) }.getOrNull()
        val code = parsed?.optString("code").orEmpty()
        if (code.isNotBlank()) return code
        val detail = parsed?.opt("detail")
        if (detail is String && detail.isNotBlank() && detail.length < 60) return detail
        return when (status) {
            429 -> "rate_limited"
            in 500..599 -> "server_error"
            else -> "http_$status"
        }
    }
}

internal fun JSONObject.optStringOrNull(key: String): String? =
    if (!has(key) || isNull(key)) null else getString(key)

internal fun JSONObject.optDoubleOrNull(key: String): Double? =
    if (!has(key) || isNull(key)) null else optDouble(key).takeIf { it.isFinite() }
