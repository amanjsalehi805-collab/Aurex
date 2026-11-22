package app.aurex.data

import org.junit.Assert.assertEquals
import org.junit.Test

class HistoryChartSegmentsTest {

    private fun point(ts: Long, price: Double = 100.0) =
        HistoryPoint(ts = ts, price = price)

    @Test
    fun continuousPointsStayInOneSegment() {
        val result = splitHistoryPoints(
            listOf(point(1000), point(1060), point(1120), point(1180))
        )
        assertEquals(1, result.size)
        assertEquals(4, result.first().size)
    }

    @Test
    fun unusualLargeGapCreatesNewSegment() {
        val result = splitHistoryPoints(
            listOf(
                point(1000),
                point(1060),
                point(1120),
                point(10000),
                point(10060)
            )
        )
        assertEquals(2, result.size)
        assertEquals(3, result[0].size)
        assertEquals(2, result[1].size)
    }

    @Test
    fun twoPointsDoNotAssumeGapPattern() {
        val result = splitHistoryPoints(
            listOf(point(1000), point(100000))
        )
        assertEquals(1, result.size)
        assertEquals(2, result.first().size)
    }

    @Test
    fun invalidPointsAreRemovedAndPointsAreSorted() {
        val result = splitHistoryPoints(
            listOf(
                point(1120),
                point(1000),
                point(1060, Double.NaN),
                point(1180, -1.0),
                point(1060)
            )
        )
        assertEquals(1, result.size)
        assertEquals(listOf(1000L, 1060L, 1120L), result.first().map { it.ts })
    }

    @Test
    fun regularTwelveHourIntervalsStayTogether() {
        val twelveHours = 12 * 60 * 60L
        val result = splitHistoryPoints(
            listOf(
                point(1000),
                point(1000 + twelveHours),
                point(1000 + 2 * twelveHours),
                point(1000 + 3 * twelveHours)
            )
        )
        assertEquals(1, result.size)
        assertEquals(4, result.first().size)
    }
}
