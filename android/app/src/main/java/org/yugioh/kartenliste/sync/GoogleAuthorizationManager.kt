package org.yugioh.kartenliste.sync

import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.activity.result.IntentSenderRequest
import com.google.android.gms.auth.api.identity.AuthorizationRequest
import com.google.android.gms.auth.api.identity.Identity
import com.google.android.gms.common.ConnectionResult
import com.google.android.gms.common.GoogleApiAvailability
import com.google.android.gms.common.api.ApiException
import com.google.android.gms.common.api.CommonStatusCodes
import com.google.android.gms.common.api.Scope
import java.security.MessageDigest

/**
 * Native Google authorization for Android.
 *
 * Important: Android OAuth is identified by package name + signing-certificate
 * SHA-1. A Desktop OAuth client JSON (the format used by the Windows build) is
 * intentionally not embedded here because Google does not support treating a
 * Desktop client secret as the Android app identity.
 */
class GoogleAuthorizationManager(private val activity: Activity) {
    private val client = Identity.getAuthorizationClient(activity)
    private var successCallback: ((String) -> Unit)? = null
    private var errorCallback: ((String) -> Unit)? = null

    fun authorize(
        launchResolution: (IntentSenderRequest) -> Unit,
        onSuccess: (String) -> Unit,
        onError: (String) -> Unit,
    ) {
        successCallback = onSuccess
        errorCallback = onError

        val availability = GoogleApiAvailability.getInstance().isGooglePlayServicesAvailable(activity)
        if (availability != ConnectionResult.SUCCESS) {
            val readable = GoogleApiAvailability.getInstance().getErrorString(availability)
            completeError(
                "Google Play-Dienste sind nicht einsatzbereit ($readable, Code $availability). " +
                    "Bitte Google Play-Dienste aktualisieren und erneut versuchen.",
            )
            return
        }

        val request = AuthorizationRequest.builder()
            .setRequestedScopes(CloudContract.SCOPES.map(::Scope))
            // Always use Google's account picker. This avoids a stale cached
            // account selection and makes the flow deterministic after updates.
            .setPrompt(AuthorizationRequest.Prompt.SELECT_ACCOUNT)
            .build()

        client.authorize(request)
            .addOnSuccessListener { result ->
                if (result.hasResolution()) {
                    val pending = result.pendingIntent
                    if (pending == null) {
                        completeError("Google-Anmeldung konnte nicht geöffnet werden.")
                    } else {
                        runCatching {
                            launchResolution(IntentSenderRequest.Builder(pending.intentSender).build())
                        }.onFailure { completeError(describeError(it)) }
                    }
                } else {
                    result.accessToken?.takeIf(String::isNotBlank)?.let(::completeSuccess)
                        ?: completeError("Google hat kein Zugriffstoken zurückgegeben.")
                }
            }
            .addOnFailureListener { completeError(describeError(it)) }
    }

    fun handleResult(data: Intent?) {
        if (data == null) {
            completeError(
                "Google hat keine Autorisierungsantwort geliefert. ${oauthIdentityHint()}",
            )
            return
        }
        try {
            val result = client.getAuthorizationResultFromIntent(data)
            val token = result.accessToken
            if (token.isNullOrBlank()) completeError("Google hat kein Zugriffstoken zurückgegeben.")
            else completeSuccess(token)
        } catch (error: Throwable) {
            completeError(describeError(error))
        }
    }

    private fun completeSuccess(token: String) {
        val callback = successCallback
        successCallback = null
        errorCallback = null
        callback?.invoke(token)
    }

    private fun completeError(message: String) {
        val callback = errorCallback
        successCallback = null
        errorCallback = null
        callback?.invoke(message)
    }

    private fun describeError(error: Throwable): String {
        if (error !is ApiException) {
            return error.message ?: "Google-Autorisierung fehlgeschlagen."
        }
        return when (error.statusCode) {
            CommonStatusCodes.CANCELED -> "Google-Autorisierung wurde abgebrochen."
            CommonStatusCodes.DEVELOPER_ERROR ->
                "Google-OAuth ist für diese APK nicht korrekt eingerichtet (Status 10). ${oauthIdentityHint()}"
            CommonStatusCodes.INTERNAL_ERROR ->
                "Google-Autorisierung ist intern fehlgeschlagen (Status 8). " +
                    "Dieser Fehler entsteht auf Android typischerweise, wenn die installierte APK in Google Cloud " +
                    "nicht mit exakt ihrem Paketnamen und ihrer SHA-1-Signatur als OAuth-Client vom Typ Android " +
                    "registriert ist oder Google Play-Dienste auf dem Gerät fehlerhaft sind. ${oauthIdentityHint()}"
            CommonStatusCodes.NETWORK_ERROR ->
                "Google-Autorisierung ist wegen eines Netzwerkfehlers fehlgeschlagen."
            else -> {
                val status = CommonStatusCodes.getStatusCodeString(error.statusCode)
                "Google-Autorisierung fehlgeschlagen ($status, Status ${error.statusCode}). ${oauthIdentityHint()}"
            }
        }
    }

    private fun oauthIdentityHint(): String {
        val sha1 = signingCertificateSha1().ifBlank { "nicht ermittelbar" }
        return "Android-OAuth-Client benötigt Paket ${activity.packageName} und SHA-1 $sha1. " +
            "Die Desktop-OAuth-JSON aus Windows ist dafür nicht der richtige Clienttyp."
    }

    @Suppress("DEPRECATION")
    private fun signingCertificateSha1(): String = runCatching {
        val packageInfo = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            activity.packageManager.getPackageInfo(
                activity.packageName,
                PackageManager.GET_SIGNING_CERTIFICATES,
            )
        } else {
            activity.packageManager.getPackageInfo(activity.packageName, PackageManager.GET_SIGNATURES)
        }
        val certificates = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            val signingInfo = packageInfo.signingInfo ?: return@runCatching ""
            if (signingInfo.hasMultipleSigners()) {
                signingInfo.apkContentsSigners.toList()
            } else {
                signingInfo.signingCertificateHistory.toList()
            }
        } else {
            packageInfo.signatures?.toList().orEmpty()
        }
        val signature = certificates.firstOrNull() ?: return@runCatching ""
        MessageDigest.getInstance("SHA-1")
            .digest(signature.toByteArray())
            .joinToString(":") { byte -> "%02X".format(byte.toInt() and 0xFF) }
    }.getOrDefault("")
}
