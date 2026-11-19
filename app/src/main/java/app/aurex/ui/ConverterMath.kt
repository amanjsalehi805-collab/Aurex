package app.aurex.ui

import java.math.BigDecimal
import java.math.RoundingMode

/** Pure conversion logic (no Android imports) so it can be unit tested. Uses BigDecimal, never Double math. */
object ConverterMath {
    private val persianDigits = "۰۱۲۳۴۵۶۷۸۹"
    private val arabicDigits = "٠١٢٣٤٥٦٧٨٩"

    /** Persian/Arabic-Indic digits to ASCII; '٫' (and '/') count as decimal point; '٬' ',' '،' are grouping. */
    fun normalize(input: String): String {
        val sb = StringBuilder()
        for (ch in input.trim()) {
            val p = persianDigits.indexOf(ch)
            val a = arabicDigits.indexOf(ch)
            when {
                p >= 0 -> sb.append(('0' + p))
                a >= 0 -> sb.append(('0' + a))
                ch == '٫' || ch == '.' || ch == '/' -> sb.append('.')
                ch == '٬' || ch == ',' || ch == '،' || ch == ' ' || ch == '\u00A0' || ch == '\u200C' -> Unit
                else -> sb.append(ch)
            }
        }
        return sb.toString()
    }

    /** Returns null for empty or invalid input (letters, two decimal points, negatives, no digits). */
    fun parseAmount(input: String): BigDecimal? {
        val s = normalize(input)
        if (s.isEmpty()) return null
        if (!Regex("^\\d*\\.?\\d*$").matches(s)) return null
        if (s.none { it.isDigit() }) return null
        return try {
            BigDecimal(if (s.startsWith(".")) "0$s" else s)
        } catch (e: NumberFormatException) {
            null
        }
    }

    /** foreign -> Toman multiplies by rate; Toman -> foreign divides by rate. */
    fun convert(amount: BigDecimal, rate: BigDecimal, foreignToToman: Boolean): BigDecimal? {
        if (rate.signum() <= 0) return null
        return if (foreignToToman) {
            amount.multiply(rate)
        } else {
            amount.divide(rate, 8, RoundingMode.HALF_EVEN)
        }
    }
}
