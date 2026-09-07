package org.yugioh.kartenliste.scanner

import androidx.camera.core.ExperimentalGetImage
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognizer
import org.yugioh.kartenliste.data.model.ScanSignals
import java.util.concurrent.atomic.AtomicBoolean

class LiveCardAnalyzer(
    private val recognizer: TextRecognizer,
    private val intervalMillis: Long = 850L,
    private val onSignals: (ScanSignals) -> Unit,
) : ImageAnalysis.Analyzer {
    private val running = AtomicBoolean(false)
    @Volatile private var lastStartedAt = 0L
    @Volatile var paused: Boolean = false

    @ExperimentalGetImage
    override fun analyze(imageProxy: ImageProxy) {
        val now = System.currentTimeMillis()
        if (paused || now - lastStartedAt < intervalMillis || !running.compareAndSet(false, true)) {
            imageProxy.close()
            return
        }
        val mediaImage = imageProxy.image
        if (mediaImage == null) {
            running.set(false)
            imageProxy.close()
            return
        }
        lastStartedAt = now
        val input = InputImage.fromMediaImage(mediaImage, imageProxy.imageInfo.rotationDegrees)
        recognizer.process(input)
            .addOnSuccessListener { text ->
                val signals = OcrSignalParser.parse(listOf(text.text))
                if (signals.setCodes.isNotEmpty() || signals.passcodes.isNotEmpty()) onSignals(signals)
            }
            .addOnCompleteListener {
                running.set(false)
                imageProxy.close()
            }
    }
}
