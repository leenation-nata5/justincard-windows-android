package org.yugioh.kartenliste.scanner

import android.annotation.SuppressLint
import android.util.Size
import android.view.MotionEvent
import androidx.camera.core.CameraSelector
import androidx.camera.core.FocusMeteringAction
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.latin.TextRecognizerOptions
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean

/**
 * CameraX live view retained from the Android product line. Heavy OCR is
 * throttled and ImageAnalysis uses KEEP_ONLY_LATEST, so the preview stays fluid.
 */
@SuppressLint("ClickableViewAccessibility")
@Composable
fun LiveScanner(
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    onCandidate: (ScannerTextParser.Candidate) -> Unit,
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val executor = remember { Executors.newSingleThreadExecutor() }
    val recognizer = remember { TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS) }
    val busy = remember { AtomicBoolean(false) }
    val lastScan = remember { longArrayOf(0L) }

    AndroidView(
        modifier = modifier.fillMaxSize(),
        factory = { ctx ->
            PreviewView(ctx).apply {
                implementationMode = PreviewView.ImplementationMode.PERFORMANCE
                scaleType = PreviewView.ScaleType.FILL_CENTER
            }
        },
        update = { previewView ->
            if (!enabled) return@AndroidView
            val future = ProcessCameraProvider.getInstance(context)
            future.addListener({
                val provider = runCatching { future.get() }.getOrNull() ?: return@addListener
                val preview = Preview.Builder().build().also { it.setSurfaceProvider(previewView.surfaceProvider) }
                val analysis = ImageAnalysis.Builder()
                    .setTargetResolution(Size(960, 540))
                    .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                    .build()
                analysis.setAnalyzer(executor) { proxy ->
                    val now = System.currentTimeMillis()
                    if (now - lastScan[0] < 750L || !busy.compareAndSet(false, true)) {
                        proxy.close(); return@setAnalyzer
                    }
                    lastScan[0] = now
                    val media = proxy.image
                    if (media == null) {
                        busy.set(false); proxy.close(); return@setAnalyzer
                    }
                    val image = InputImage.fromMediaImage(media, proxy.imageInfo.rotationDegrees)
                    recognizer.process(image)
                        .addOnSuccessListener { result ->
                            ScannerTextParser.best(result.text)?.let(onCandidate)
                        }
                        .addOnCompleteListener {
                            busy.set(false)
                            proxy.close()
                        }
                }
                provider.unbindAll()
                val camera = runCatching {
                    provider.bindToLifecycle(lifecycleOwner, CameraSelector.DEFAULT_BACK_CAMERA, preview, analysis)
                }.getOrNull()
                previewView.setOnTouchListener { _, event ->
                    if (event.action == MotionEvent.ACTION_UP && camera != null) {
                        val point = previewView.meteringPointFactory.createPoint(event.x, event.y)
                        val action = FocusMeteringAction.Builder(point)
                            .setAutoCancelDuration(2, TimeUnit.SECONDS)
                            .build()
                        camera.cameraControl.startFocusAndMetering(action)
                    }
                    true
                }
            }, ContextCompat.getMainExecutor(context))
        }
    )

    DisposableEffect(Unit) {
        onDispose {
            runCatching { ProcessCameraProvider.getInstance(context).get().unbindAll() }
            runCatching { recognizer.close() }
            executor.shutdownNow()
        }
    }
}
