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
 * Google verifies Android OAuth clients by application package + signing
 * certificate SHA-1. The Windows Desktop OAuth JSON cannot replace that
 * server-side Android client registration.
 *
 * 13.0.10 deliberately starts with the canonical AuthorizationClient request
 * without forcing an account prompt. The requested scopes include explicit
 * Google Sheets read/write access plus per-file Drive and appData access. Some
 * devices/Play-services versions can return INTERNAL_ERROR while a forced prompt
 * is used. If the standard request itself returns status 8, one controlled retry
 * with SELECT_ACCOUNT is made.
 */
class GoogleAuthorizationManager(private val activity: Activity) {
    private val client = Identity.getAuthorizationClient(activity)
    private var successCallback: ((String) -> Unit)? = null
    private var errorCallback: ((String) -> Unit)? = null
    private var resolutionLauncher: ((IntentSenderRequest) -> Unit)? = null
    private var accountPickerRetryUsed = false
    private var authorizationInProgress = false

    fun authorize(
        launchResolution: (IntentSenderRequest) -> Unit,
        onSuccess: (String) -> Unit,
        onError: (String) -> Unit,
    ) {
        if (authorizationInProgress) {
            onError("Google-Anmeldung läuft bereits. Bitte kurz warten.")
            return
        }
        authorizationInProgress = true
        successCallback = onSuccess
        errorCallback = onError
        resolutionLauncher = launchResolution
        accountPickerRetryUsed = false

        val availability = GoogleApiAvailability.getInstance().isGooglePlayServicesAvailable(activity)
        if (availability != ConnectionResult.SUCCESS) {
            val readable = GoogleApiAvailability.getInstance().getErrorString(availability)
            completeError(
                "Google Play-Dienste sind nicht einsatzbereit ($readable, Code $availability). " +
                    "Bitte Google Play-Dienste aktualisieren und erneut versuchen.",
            )
            return
        }

        authorizeRequest(forceAccountPicker = false)
    }

    private fun authorizeRequest(forceAccountPicker: Boolean) {
        val builder = AuthorizationRequest.builder()
            .setRequestedScopes(CloudContract.SCOPES.map(::Scope))
        if (forceAccountPicker) {
            builder.setPrompt(AuthorizationRequest.Prompt.SELECT_ACCOUNT)
        }
        val request = builder.build()

        client.authorize(request)
            .addOnSuccessListener { result ->
                if (result.hasResolution()) {
                    val pending = result.pendingIntent
                    val launcher = resolutionLauncher
                    if (pending == null || launcher == null) {
                        completeError("Google-Anmeldung konnte nicht geöffnet werden.")
                    } else {
                        runCatching {
                            launcher(IntentSenderRequest.Builder(pending.intentSender).build())
                        }.onFailure { error ->
                            if (!retryStatus8(error)) completeError(describeError(error))
                        }
                    }
                } else {
                    result.accessToken?.takeIf(String::isNotBlank)?.let(::completeSuccess)
                        ?: completeError("Google hat kein Zugriffstoken zurückgegeben.")
                }
            }
            .addOnFailureListener { error ->
                if (!retryStatus8(error)) completeError(describeError(error))
            }
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
            if (!retryStatus8(error)) completeError(describeError(error))
        }
    }

    private fun retryStatus8(error: Throwable): Boolean {
        val apiError = error as? ApiException ?: return false
        if (apiError.statusCode != CommonStatusCodes.INTERNAL_ERROR || accountPickerRetryUsed) {
            return false
        }
        accountPickerRetryUsed = true
        authorizeRequest(forceAccountPicker = true)
        return true
    }

    private fun completeSuccess(token: String) {
        val callback = successCallback
        successCallback = null
        errorCallback = null
        resolutionLauncher = null
        accountPickerRetryUsed = false
        authorizationInProgress = false
        callback?.invoke(token)
    }

    private fun completeError(message: String) {
        val callback = errorCallback
        successCallback = null
        errorCallback = null
        resolutionLauncher = null
        accountPickerRetryUsed = false
        authorizationInProgress = false
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
                "Google-Autorisierung ist auch nach dem automatischen Wiederholungsversuch fehlgeschlagen " +
                    "(Status 8). Bitte den Android-OAuth-Client in Google Cloud exakt mit dem unten genannten " +
                    "Paketnamen und SHA-1 registrieren. ${oauthIdentityHint()}"
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
        return "Android-OAuth benötigt Paket ${activity.packageName} und SHA-1 $sha1."
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
