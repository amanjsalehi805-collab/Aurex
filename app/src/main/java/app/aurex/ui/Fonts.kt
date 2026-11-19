package app.aurex.ui

import android.content.Context
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import app.aurex.R
import app.aurex.data.FONT_SYSTEM
import app.aurex.data.FontScript

data class FontOption(val id: String, val labelRes: Int)

/**
 * Per-language font choices.
 *  - "system", "serif", "mono": Android system families (no files needed).
 *  - "dejavu": bundled DejaVu Sans (verified to contain all Persian and Sorani letters).
 *  - optional fonts (Vazirmatn, Noto ...): listed only if their files exist in res/font.
 *    Run tools/fetch_fonts.sh to add them; it refuses fonts that miss Sorani letters.
 */
object FontCatalog {
    private data class Optional(val id: String, val labelRes: Int)

    private val optionalArabicScript = listOf(
        Optional("vazirmatn", R.string.font_vazirmatn),
        Optional("noto_naskh_arabic", R.string.font_noto_naskh),
        Optional("noto_sans_arabic", R.string.font_noto_sans_arabic),
    )

    fun options(context: Context, script: FontScript): List<FontOption> = buildList {
        add(FontOption(FONT_SYSTEM, R.string.font_system))
        add(FontOption("serif", R.string.font_system_serif))
        if (script == FontScript.EN) add(FontOption("mono", R.string.font_system_mono))
        add(FontOption("dejavu", R.string.font_dejavu))
        if (script != FontScript.EN) {
            optionalArabicScript.forEach {
                if (resId(context, "${it.id}_regular") != 0 && verifiedFor(context, it.id, script)) {
                    add(FontOption(it.id, it.labelRes))
                }
            }
        }
    }

    fun family(context: Context, script: FontScript, id: String): FontFamily {
        // A saved choice that is no longer available falls back to the system font.
        if (options(context, script).none { it.id == id }) return FontFamily.Default
        return when (id) {
            "serif" -> FontFamily.Serif
            "mono" -> FontFamily.Monospace
            "dejavu" -> FontFamily(
                Font(R.font.dejavu_sans_regular, FontWeight.Normal),
                Font(R.font.dejavu_sans_bold, FontWeight.Bold),
            )
            FONT_SYSTEM -> FontFamily.Default
            else -> optionalFamily(context, id) ?: FontFamily.Default
        }
    }

    private fun optionalFamily(context: Context, id: String): FontFamily? {
        val regular = resId(context, "${id}_regular")
        if (regular == 0) return null
        val bold = resId(context, "${id}_bold")
        return if (bold != 0) {
            FontFamily(Font(regular, FontWeight.Normal), Font(bold, FontWeight.Bold))
        } else {
            FontFamily(Font(regular, FontWeight.Normal))
        }
    }

    /**
     * An optional font is offered for a script only if tools/fetch_fonts.sh verified that the font file
     * really contains that script's letters and wrote a <bool name="{id}_{fa|ckb}_ok">true</bool> marker.
     */
    @Suppress("DiscouragedApi")
    private fun verifiedFor(context: Context, id: String, script: FontScript): Boolean {
        val key = "${id}_${if (script == FontScript.FA) "fa" else "ckb"}_ok"
        val res = context.resources.getIdentifier(key, "bool", context.packageName)
        return res != 0 && context.resources.getBoolean(res)
    }

    @Suppress("DiscouragedApi")
    private fun resId(context: Context, name: String): Int =
        context.resources.getIdentifier(name, "font", context.packageName)
}

fun scriptOf(language: String): FontScript = when (language) {
    "fa" -> FontScript.FA
    "ckb" -> FontScript.CKB
    else -> FontScript.EN
}
