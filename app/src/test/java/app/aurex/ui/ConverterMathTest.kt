package app.aurex.ui

import java.math.BigDecimal
import org.junit.Assert.*
import org.junit.Test

class ConverterMathTest {
    private fun bd(s: String) = BigDecimal(s)

    @Test fun parsesDecimals() {
        assertEquals(bd("2.5"), ConverterMath.parseAmount("2.5"))
        assertEquals(bd("0.5"), ConverterMath.parseAmount(".5"))
        assertEquals(bd("1234567"), ConverterMath.parseAmount("1,234,567"))
    }

    @Test fun parsesCommaDecimalsAndGroupedNumbers() {
        assertEquals(bd("1.5"), ConverterMath.parseAmount("1,5"))
        assertEquals(bd("1.25"), ConverterMath.parseAmount("1,25"))
        assertEquals(bd("1234567"), ConverterMath.parseAmount("1,234,567"))
        assertEquals(bd("1234.56"), ConverterMath.parseAmount("1,234.56"))
    }

    @Test fun parsesLocalizedDigits() {
        assertEquals(bd("12.5"), ConverterMath.parseAmount("۱۲٫۵"))
        assertEquals(bd("340"), ConverterMath.parseAmount("٣٤٠"))
    }

    @Test fun rejectsInvalidAmounts() {
        listOf("", ".", "1.2.3", "abc", "-5").forEach {
            assertNull(ConverterMath.parseAmount(it))
        }
    }

    @Test fun convertsLegacyPairBothWays() {
        val rate = bd("100000")
        assertEquals(0, bd("250000").compareTo(ConverterMath.convert(bd("2.5"), rate, true)))
        assertEquals(0, bd("2.5").compareTo(ConverterMath.convert(bd("250000"), rate, false)))
    }

    @Test fun convertsArbitraryAssets() {
        val result = ConverterMath.convertAssets(bd("2"), bd("100000"), bd("5000000"))
        assertNotNull(result)
        assertEquals(0, bd("0.04").compareTo(result!!))
    }

    @Test fun convertsTomanAndUsdBothWays() {
        val usd = ConverterMath.convertAssets(bd("250000"), bd("1"), bd("100000"))
        assertNotNull(usd)
        assertEquals(0, bd("2.5").compareTo(usd!!))
        val toman = ConverterMath.convertAssets(bd("2.5"), bd("100000"), bd("1"))
        assertNotNull(toman)
        assertEquals(0, bd("250000").compareTo(toman!!))
    }

    @Test fun globalMetalNeedsUsdRate() {
        val value = ConverterMath.valueInToman(ConverterMath.GLOBAL_GOLD_ID, bd("2700"), "USD", bd("100000"))
        assertNotNull(value)
        assertEquals(0, bd("270000000").compareTo(value!!))
        assertNull(ConverterMath.valueInToman(ConverterMath.GLOBAL_GOLD_ID, bd("2700"), "USD", null))
    }

    @Test fun rejectsWrongDenominationsAndIndex() {
        assertNull(ConverterMath.valueInToman(ConverterMath.USD_ID, bd("100000"), "USD", bd("100000")))
        assertNull(ConverterMath.valueInToman(ConverterMath.GLOBAL_SILVER_ID, bd("30"), "IRT", bd("100000")))
        assertNull(ConverterMath.valueInToman("tse_index", bd("3000000"), "IRT", bd("100000")))
    }

    @Test fun tomanBaseAndInvalidRates() {
        val toman = ConverterMath.valueInToman(ConverterMath.TOMAN_ID, null, null, null)
        assertNotNull(toman)
        assertEquals(0, BigDecimal.ONE.compareTo(toman!!))
        assertNull(ConverterMath.convert(bd("1"), BigDecimal.ZERO, true))
        assertNull(ConverterMath.convertAssets(bd("1"), BigDecimal.ZERO, bd("2")))
        assertNull(ConverterMath.convertAssets(bd("1"), bd("2"), BigDecimal.ZERO))
        assertNull(ConverterMath.convertAssets(bd("-1"), bd("2"), bd("3")))
    }

    @Test fun sameValueConversionPreservesAmount() {
        val result = ConverterMath.convertAssets(bd("12.345"), bd("100"), bd("100"))
        assertNotNull(result)
        assertEquals(0, bd("12.345").compareTo(result!!))
    }
}
