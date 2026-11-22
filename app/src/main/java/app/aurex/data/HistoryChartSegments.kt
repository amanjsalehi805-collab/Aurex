package app.aurex.data

internal fun splitHistoryPoints(
    points: List<HistoryPoint>,
    minimumGapSeconds: Long = 15 * 60L,
    gapMultiplier: Long = 3L,
): List<List<HistoryPoint>> {
    val valid = points
        .filter { it.ts > 0 && it.price.isFinite() && it.price > 0 }
        .distinctBy { it.ts }
        .sortedBy { it.ts }

    if (valid.size < 3) return listOf(valid)

    val intervals = valid.zipWithNext { a, b -> b.ts - a.ts }
        .filter { it > 0 }
        .sorted()

    if (intervals.size < 2) return listOf(valid)

    val typicalInterval = intervals[(intervals.size - 1) / 2]
    val threshold = maxOf(minimumGapSeconds, typicalInterval * gapMultiplier)

    val segments = mutableListOf<MutableList<HistoryPoint>>()
    valid.forEach { point ->
        val current = segments.lastOrNull()
        if (current == null || point.ts - current.last().ts > threshold) {
            segments.add(mutableListOf(point))
        } else {
            current.add(point)
        }
    }
    return segments
}
