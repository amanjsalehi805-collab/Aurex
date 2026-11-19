package app.aurex.ui

import java.math.BigDecimal
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

class ConverterMathTest {
    @Test fun parsesDecimals() {
        assertEquals(BigDecimal("2.5"), ConverterMath.parseAmount("2.5"))
        assertEquals(BigDecimal("0.5"), ConverterMath.parseAmount(".5"))
        assertEquals(BigDecimal("1234567"), ConverterMath.parseAmount("1,234,567"))
    }

    @Test fun parsesPersianAndArabicDigits() {
        assertEquals(BigDecimal("12.5"), ConverterMath.parseAmount("۱۲٫۵"))
        assertEquals(BigDecimal("340"), ConverterMath.parseAmount("٣٤٠"))
    }

    @Test fun rejectsInvalid() {
        assertNull(ConverterMath.parseAmount(""))
        assertNull(ConverterMath.parseAmount("."))
        assertNull(ConverterMath.parseAmount("1.2.3"))
        assertNull(ConverterMath.parseAmount("abc"))
        assertNull(ConverterMath.parseAmount("-5"))
    }

    // Synthetic rate used only by this test.
    private val rate = BigDecimal("100000")

    @Test fun convertsBothWaysExactly() {
        assertEquals(0, BigDecimal("250000").compareTo(ConverterMath.convert(BigDecimal("2.5"), rate, true)))
        assertEquals(0, BigDecimal("2.5").compareTo(ConverterMath.convert(BigDecimal("250000"), rate, false)))
    }

    @Test fun roundTripHasNoFloatingPointNoise() {
        val toman = ConverterMath.convert(BigDecimal("0.1"), BigDecimal("3"), true)
        assertEquals(0, BigDecimal("0.3").compareTo(toman))
    }

    @Test fun refusesNonPositiveRate() {
        assertNull(ConverterMath.convert(BigDecimal.ONE, BigDecimal.ZERO, true))
        assertNotNull(ConverterMath.convert(BigDecimal.ONE, BigDecimal.ONE, false))
    }
}
