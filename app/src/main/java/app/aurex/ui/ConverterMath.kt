package app.aurex.ui

import java.math.BigDecimal
import java.math.RoundingMode

/** Exact decimal conversion logic, independent of Android. */
object ConverterMath {
    const val TOMAN_ID = "irt_toman"
    const val USD_ID = "usd_free_irt"
    const val EUR_ID = "eur_free_irt"
    const val GOLD18_ID = "gold18_irt"
    const val COIN_ID = "coin_irt"
    const val GLOBAL_GOLD_ID = "gold_oz_usd"
    const val GLOBAL_SILVER_ID = "silver_oz_usd"

    private val persianDigits = "۰۱۲۳۴۵۶۷۸۹"
    private val arabicDigits = "٠١٢٣٤٥٦٧٨٩"

    /** Normalize Persian and Arabic digits and common decimal/grouping separators. */
    fun normalize(input: String): String {
        val trimmed = input.trim()
        val commaCount = trimmed.count { it == ',' || it == '،' }
        val lastComma = maxOf(trimmed.lastIndexOf(','), trimmed.lastIndexOf('،'))
        val trailingDigits = if (lastComma >= 0) {
            trimmed.substring(lastComma + 1).count { it.isDigit() }
        } else {
            0
        }
        val commaIsDecimal =
            !trimmed.contains('.') && commaCount == 1 && trailingDigits != 3

        val sb = StringBuilder()
        for (ch in trimmed) {
            val p = persianDigits.indexOf(ch)
            val a = arabicDigits.indexOf(ch)
            when {
                p >= 0 -> sb.append((48 + p).toChar())
                a >= 0 -> sb.append((48 + a).toChar())
                ch == '٫' || ch == '.' || ch == '/' -> sb.append('.')
                (ch == ',' || ch == '،') && commaIsDecimal -> sb.append('.')
                ch == '٬' || ch == ',' || ch == '،' ||
                    ch == ' ' || ch == '\u00A0' || ch == '\u200C' -> Unit
                else -> sb.append(ch)
            }
        }
        return sb.toString()
    }

    /** Parse a non-negative decimal amount, or return null for invalid input. */
    fun parseAmount(input: String): BigDecimal? {
        val s = normalize(input)
        if (s.isEmpty()) return null
        if (!Regex("^\\d*\\.?\\d*$").matches(s)) return null
        if (s.none { it.isDigit() }) return null
        return try {
            BigDecimal(if (s.startsWith(".")) "0$s" else s)
        } catch (_: NumberFormatException) {
            null
        }
    }

    /** Convert a foreign amount to Toman by multiplying, or Toman to foreign by dividing. */
    fun convert(amount: BigDecimal, rate: BigDecimal, foreignToToman: Boolean): BigDecimal? {
        if (amount.signum() < 0 || rate.signum() <= 0) return null
        return if (foreignToToman) amount.multiply(rate)
        else amount.divide(rate, 18, RoundingMode.HALF_EVEN).stripTrailingZeros()
    }

    /** Convert between any two assets after both prices have been normalized to Toman. */
    fun convertAssets(
        amount: BigDecimal,
        sourceValueInToman: BigDecimal,
        targetValueInToman: BigDecimal
    ): BigDecimal? {
        if (amount.signum() < 0 ||
            sourceValueInToman.signum() <= 0 ||
            targetValueInToman.signum() <= 0
        ) return null

        if (sourceValueInToman.compareTo(targetValueInToman) == 0) return amount
        return amount.multiply(sourceValueInToman)
            .divide(targetValueInToman, 18, RoundingMode.HALF_EVEN)
            .stripTrailingZeros()
    }

    /**
     * Return the Toman value of one unit of an asset.
     * Local quotes must be IRT-denominated; global metals require a USD quote
     * and a valid USD-to-Toman rate. Unsupported assets are not convertible.
     */
    fun valueInToman(
        assetId: String,
        quotePrice: BigDecimal?,
        quoteUnit: String?,
        usdToToman: BigDecimal?
    ): BigDecimal? {
        if (assetId == TOMAN_ID) return BigDecimal.ONE

        val price = quotePrice?.takeIf { it.signum() > 0 } ?: return null
        val unit = quoteUnit?.trim()?.uppercase() ?: return null

        return when (assetId) {
            USD_ID, EUR_ID, GOLD18_ID, COIN_ID ->
                price.takeIf { unit == "IRT" }
            GLOBAL_GOLD_ID, GLOBAL_SILVER_ID -> {
                if (unit != "USD") return null
                val usdRate = usdToToman?.takeIf { it.signum() > 0 } ?: return null
                price.multiply(usdRate)
            }
            else -> null
        }
    }
}
