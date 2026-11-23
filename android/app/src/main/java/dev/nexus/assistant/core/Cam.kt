package dev.nexus.assistant.core

import android.annotation.SuppressLint
import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.ImageFormat
import android.graphics.Matrix
import android.hardware.camera2.CameraCaptureSession
import android.hardware.camera2.CameraCharacteristics
import android.hardware.camera2.CameraDevice
import android.hardware.camera2.CameraManager
import android.hardware.camera2.CaptureRequest
import android.media.ImageReader
import android.os.Handler
import android.os.HandlerThread
import android.util.Base64
import android.util.Size
import kotlinx.coroutines.delay
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withTimeout
import java.io.ByteArrayOutputStream
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

/** Scatta una foto (frontale o posteriore) senza aprire l'app Fotocamera e la restituisce in JPEG base64. */
object Cam {
    @SuppressLint("MissingPermission")
    suspend fun captureB64(ctx: Context, front: Boolean, maxW: Int = 768): String = withTimeout(15_000) {
        val cm = ctx.getSystemService(Context.CAMERA_SERVICE) as CameraManager
        val facing = if (front) CameraCharacteristics.LENS_FACING_FRONT else CameraCharacteristics.LENS_FACING_BACK
        val id = cm.cameraIdList.firstOrNull { cm.getCameraCharacteristics(it).get(CameraCharacteristics.LENS_FACING) == facing }
            ?: cm.cameraIdList.first()
        val chars = cm.getCameraCharacteristics(id)
        val sizes = chars.get(CameraCharacteristics.SCALER_STREAM_CONFIGURATION_MAP)!!.getOutputSizes(ImageFormat.JPEG)
        val size = sizes.filter { it.width <= 1600 }.maxByOrNull { it.width * it.height } ?: Size(1280, 720)
        val sensor = chars.get(CameraCharacteristics.SENSOR_ORIENTATION) ?: 0

        val thread = HandlerThread("nexus-cam").apply { start() }
        val handler = Handler(thread.looper)
        val reader = ImageReader.newInstance(size.width, size.height, ImageFormat.JPEG, 2)
        try {
            val device = suspendCancellableCoroutine<CameraDevice> { cont ->
                cm.openCamera(id, object : CameraDevice.StateCallback() {
                    override fun onOpened(d: CameraDevice) { cont.resume(d) }
                    override fun onDisconnected(d: CameraDevice) { d.close() }
                    override fun onError(d: CameraDevice, e: Int) { d.close(); if (cont.isActive) cont.resumeWithException(IllegalStateException("fotocamera non disponibile ($e)")) }
                }, handler)
            }
            try {
                @Suppress("DEPRECATION")
                val session = suspendCancellableCoroutine<CameraCaptureSession> { cont ->
                    device.createCaptureSession(listOf(reader.surface), object : CameraCaptureSession.StateCallback() {
                        override fun onConfigured(s: CameraCaptureSession) { cont.resume(s) }
                        override fun onConfigureFailed(s: CameraCaptureSession) { cont.resumeWithException(IllegalStateException("configurazione fotocamera fallita")) }
                    }, handler)
                }
                // qualche fotogramma di "riscaldamento" per esposizione e messa a fuoco
                val preview = device.createCaptureRequest(CameraDevice.TEMPLATE_PREVIEW).apply { addTarget(reader.surface) }.build()
                session.setRepeatingRequest(preview, null, handler)
                delay(700)
                session.stopRepeating()
                while (true) { reader.acquireLatestImage()?.close() ?: break }
                val still = device.createCaptureRequest(CameraDevice.TEMPLATE_STILL_CAPTURE).apply {
                    addTarget(reader.surface); set(CaptureRequest.JPEG_ORIENTATION, sensor)
                }.build()
                val bytes = suspendCancellableCoroutine<ByteArray> { cont ->
                    reader.setOnImageAvailableListener({ r ->
                        val img = r.acquireLatestImage() ?: return@setOnImageAvailableListener
                        val buf = img.planes[0].buffer; val b = ByteArray(buf.remaining()); buf.get(b); img.close()
                        if (cont.isActive) cont.resume(b)
                    }, handler)
                    session.capture(still, null, handler)
                }
                session.close()
                // ruota/rimpicciolisce e ricomprime
                var bmp = BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
                if (bmp.width > maxW) bmp = Bitmap.createScaledBitmap(bmp, maxW, bmp.height * maxW / bmp.width, true)
                if (front) bmp = Bitmap.createBitmap(bmp, 0, 0, bmp.width, bmp.height, Matrix().apply { preScale(-1f, 1f) }, true)
                val out = ByteArrayOutputStream(); bmp.compress(Bitmap.CompressFormat.JPEG, 82, out)
                Base64.encodeToString(out.toByteArray(), Base64.NO_WRAP)
            } finally { device.close() }
        } finally { reader.close(); thread.quitSafely() }
    }
}
