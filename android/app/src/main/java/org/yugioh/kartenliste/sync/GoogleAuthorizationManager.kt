package org.yugioh.kartenliste.sync

import android.app.Activity
import android.content.Intent
import androidx.activity.result.IntentSenderRequest
import com.google.android.gms.auth.api.identity.AuthorizationRequest
import com.google.android.gms.auth.api.identity.Identity
import com.google.android.gms.common.api.ApiException
import com.google.android.gms.common.api.CommonStatusCodes
import com.google.android.gms.common.api.Scope

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
        val request = AuthorizationRequest.builder()
            .setRequestedScopes(CloudContract.SCOPES.map(::Scope))
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
                "Google hat keine Autorisierungsantwort geliefert. Prüfe den Android-OAuth-Client " +
                    "für ${activity.packageName} und die SHA-1-Signatur dieser APK.",
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
                "Google-OAuth ist für diese APK nicht korrekt eingerichtet (Status 10). " +
                    "Prüfe den Android-OAuth-Client für ${activity.packageName} und die SHA-1-Signatur."
            CommonStatusCodes.NETWORK_ERROR ->
                "Google-Autorisierung ist wegen eines Netzwerkfehlers fehlgeschlagen."
            else -> {
                val status = CommonStatusCodes.getStatusCodeString(error.statusCode)
                "Google-Autorisierung fehlgeschlagen ($status, Status ${error.statusCode})."
            }
        }
    }
}
