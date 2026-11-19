package app.aurex.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

// Geometry is generated from the same source as the launcher icon (108 x 108 grid).
internal const val EYE_L = 25.0f
internal const val EYE_R = 83.0f
internal const val EYE_CY = 54.0f
internal const val EYE_CTRL = 29.0f
internal const val CANDLE_W = 5.2f
internal const val ORBIT_RX = 33.0f
internal const val ORBIT_RY = 12.0f
internal const val ORBIT_ROT = -25.0f
internal const val STROKE_EYE = 2.6f
internal const val STROKE_WICK = 1.5f
internal const val STROKE_ORBIT = 1.3f
internal val ORBIT_DOT = floatArrayOf(73.65f, 36.33f)
internal val CANDLES = listOf(
    floatArrayOf(46.0f, 56.0f, 65.0f, 58.0f, 63.0f),
    floatArrayOf(54.0f, 51.0f, 64.0f, 54.0f, 61.0f),
    floatArrayOf(62.0f, 46.0f, 60.0f, 49.0f, 57.0f)
)

/** The AUREX mark: abstract eye, rising candles and a thin orbit ring. */
@Composable
fun AurexLogo(
    modifier: Modifier = Modifier,
    size: Dp = 40.dp,
    color: Color = LocalAurexColors.current.gold,
) {
    Canvas(modifier.size(size)) {
        val k = this.size.minDimension / 108f
        val c = 54f * k
        rotate(ORBIT_ROT, pivot = Offset(c, c)) {
            drawOval(
                color = color.copy(alpha = 0.65f),
                topLeft = Offset((54f - ORBIT_RX) * k, (54f - ORBIT_RY) * k),
                size = Size(2 * ORBIT_RX * k, 2 * ORBIT_RY * k),
                style = Stroke(width = STROKE_ORBIT * k),
            )
        }
        drawCircle(color, radius = 2.2f * k, center = Offset(ORBIT_DOT[0] * k, ORBIT_DOT[1] * k))
        val eye = Path().apply {
            moveTo(EYE_L * k, EYE_CY * k)
            quadraticBezierTo(54f * k, EYE_CTRL * k, EYE_R * k, EYE_CY * k)
            quadraticBezierTo(54f * k, (2 * EYE_CY - EYE_CTRL) * k, EYE_L * k, EYE_CY * k)
            close()
        }
        drawPath(eye, color, style = Stroke(STROKE_EYE * k, cap = StrokeCap.Round, join = StrokeJoin.Round))
        CANDLES.forEach { cd ->
            val x = cd[0]
            drawLine(color, Offset(x * k, cd[1] * k), Offset(x * k, cd[2] * k),
                strokeWidth = STROKE_WICK * k, cap = StrokeCap.Round)
            drawRect(color, topLeft = Offset((x - CANDLE_W / 2) * k, cd[3] * k),
                size = Size(CANDLE_W * k, (cd[4] - cd[3]) * k))
        }
    }
}
