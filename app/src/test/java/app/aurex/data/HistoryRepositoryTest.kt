package app.aurex.data

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.async
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.yield
import org.junit.Assert.assertEquals
import org.junit.Assert.assertSame
import org.junit.Test

class HistoryRepositoryTest {
    private fun sample(price: Double) = HistoryData(
        points = listOf(HistoryPoint(1000L, price)),
        summary = HistorySummary(1, false, null, null, null, 0L),
    )

    @Test
    fun cachesSuccessfulResultPerAssetAndRange() = runBlocking {
        var calls = 0
        val repository = HistoryRepository(
            nowMillis = { 1000L },
            loader = { _, _ -> calls++; sample(100.0) },
        )

        val first = repository.fetch("usd", 24)
        val second = repository.fetch("usd", 24)

        assertSame(first, second)
        repository.fetch("usd", 168)
        repository.fetch("eur", 24)
        assertEquals(3, calls)
    }

    @Test
    fun reloadsAfterCacheExpires() = runBlocking {
        var now = 1000L
        var calls = 0
        val repository = HistoryRepository(
            cacheTtlMillis = 300_000L,
            nowMillis = { now },
            loader = { _, _ -> calls++; sample(calls.toDouble()) },
        )

        repository.fetch("usd", 24)
        now += 300_001L
        val refreshed = repository.fetch("usd", 24)

        assertEquals(2, calls)
        assertEquals(2.0, refreshed.points.first().price, 0.0)
    }

    @Test
    fun concurrentRequestsForSameKeyShareOneFetch() = runBlocking {
        var calls = 0
        val started = CompletableDeferred<Unit>()
        val release = CompletableDeferred<HistoryData>()
        val repository = HistoryRepository(
            loader = { _, _ ->
                calls++
                started.complete(Unit)
                release.await()
            },
        )

        val first = async { repository.fetch("usd", 24) }
        started.await()
        val second = async { repository.fetch("usd", 24) }
        yield()

        assertEquals(1, calls)
        release.complete(sample(150.0))

        assertSame(first.await(), second.await())
        assertEquals(1, calls)
    }

    @Test
    fun failedFetchIsNotCachedAndCanRetry() = runBlocking {
        var calls = 0
        val repository = HistoryRepository(
            nowMillis = { 1000L },
            loader = { _, _ ->
                calls++
                if (calls == 1) error("network")
                sample(200.0)
            },
        )

        try {
            repository.fetch("usd", 24)
            throw AssertionError("Expected first request to fail")
        } catch (expected: IllegalStateException) {
            assertEquals("network", expected.message)
        }

        val result = repository.fetch("usd", 24)
        assertEquals(2, calls)
        assertEquals(200.0, result.points.first().price, 0.0)
    }
}
