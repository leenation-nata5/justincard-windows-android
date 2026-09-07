package org.yugioh.kartenliste.scanner

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import androidx.exifinterface.media.ExifInterface
import com.google.android.gms.tasks.Task
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.Text
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.TextRecognizer
import com.google.mlkit.vision.text.chinese.ChineseTextRecognizerOptions
import com.google.mlkit.vision.text.devanagari.DevanagariTextRecognizerOptions
import com.google.mlkit.vision.text.japanese.JapaneseTextRecognizerOptions
import com.google.mlkit.vision.text.korean.KoreanTextRecognizerOptions
import com.google.mlkit.vision.text.latin.TextRecognizerOptions
import kotlinx.coroutines.suspendCancellableCoroutine
import org.yugioh.kartenliste.data.model.ScanSignals
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

class OcrEngine : AutoCloseable {
    private val latin = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)
    private val chinese = TextRecognition.getClient(ChineseTextRecognizerOptions.Builder().build())
    private val devanagari = TextRecognition.getClient(DevanagariTextRecognizerOptions.Builder().build())
    private val japanese = TextRecognition.getClient(JapaneseTextRecognizerOptions.Builder().build())
    private val korean = TextRecognition.getClient(KoreanTextRecognizerOptions.Builder().build())

    fun liveRecognizer(): TextRecognizer = latin

    suspend fun scanUri(context: Context, uri: Uri, thorough: Boolean = true): ScanSignals {
        val bitmap = decodeScaledBitmap(context, uri)
        if (bitmap == null) return scanImage(InputImage.fromFilePath(context, uri), thorough)
        return try {
            scanImage(InputImage.fromBitmap(bitmap, exifRotation(context, uri)), thorough)
        } finally {
            if (!bitmap.isRecycled) bitmap.recycle()
        }
    }

    suspend fun scanImage(image: InputImage, thorough: Boolean = true): ScanSignals {
        val recognizers = if (thorough) listOf(latin, japanese, korean, chinese, devanagari) else listOf(latin)
        val texts = recognizers.mapNotNull { recognizer ->
            runCatching { recognizer.process(image).awaitResult().text }.getOrNull()?.takeIf(String::isNotBlank)
        }
        return OcrSignalParser.parse(texts)
    }

    override fun close() {
        latin.close()
        chinese.close()
        devanagari.close()
        japanese.close()
        korean.close()
    }
}

private fun decodeScaledBitmap(context: Context, uri: Uri): Bitmap? {
    val resolver = context.contentResolver
    val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
    resolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, bounds) }
    if (bounds.outWidth <= 0 || bounds.outHeight <= 0) return null
    var sample = 1
    while (maxOf(bounds.outWidth, bounds.outHeight) / sample > MAX_OCR_EDGE) sample *= 2
    val options = BitmapFactory.Options().apply {
        inSampleSize = sample
        inPreferredConfig = Bitmap.Config.ARGB_8888
    }
    return resolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, options) }
}

private fun exifRotation(context: Context, uri: Uri): Int = runCatching {
    context.contentResolver.openInputStream(uri)?.use { stream ->
        when (ExifInterface(stream).getAttributeInt(
            ExifInterface.TAG_ORIENTATION,
            ExifInterface.ORIENTATION_NORMAL,
        )) {
            ExifInterface.ORIENTATION_ROTATE_90,
            ExifInterface.ORIENTATION_TRANSPOSE -> 90
            ExifInterface.ORIENTATION_ROTATE_180,
            ExifInterface.ORIENTATION_FLIP_VERTICAL -> 180
            ExifInterface.ORIENTATION_ROTATE_270,
            ExifInterface.ORIENTATION_TRANSVERSE -> 270
            else -> 0
        }
    } ?: 0
}.getOrDefault(0)

private const val MAX_OCR_EDGE = 2560

private suspend fun <T> Task<T>.awaitResult(): T = suspendCancellableCoroutine { continuation ->
    addOnSuccessListener { value -> if (continuation.isActive) continuation.resume(value) }
    addOnFailureListener { error -> if (continuation.isActive) continuation.resumeWithException(error) }
    addOnCanceledListener { continuation.cancel() }
}
