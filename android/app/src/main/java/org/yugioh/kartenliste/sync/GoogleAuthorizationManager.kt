package org.yugioh.kartenliste.sync

import android.app.Activity
import android.content.Intent
import androidx.activity.result.IntentSenderRequest
import com.google.android.gms.auth.api.identity.AuthorizationRequest
import com.google.android.gms.auth.api.identity.Identity
import com.google.android.gms.common.api.Scope

class GoogleAuthorizationManager(private val activity: Activity) {
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
        Identity.getAuthorizationClient(activity).authorize(request)
            .addOnSuccessListener { result ->
                if (result.hasResolution()) {
                    val pending = result.pendingIntent
                    if (pending == null) onError("Google-Anmeldung konnte nicht geöffnet werden.")
                    else launchResolution(IntentSenderRequest.Builder(pending.intentSender).build())
                } else {
                    result.accessToken?.takeIf(String::isNotBlank)?.let(onSuccess)
                        ?: onError("Google hat kein Zugriffstoken zurückgegeben.")
                }
            }
            .addOnFailureListener { onError(it.message ?: "Google-Autorisierung fehlgeschlagen.") }
    }

    fun handleResult(data: Intent?) {
        try {
            val result = Identity.getAuthorizationClient(activity)
                .getAuthorizationResultFromIntent(requireNotNull(data) { "Google-Antwort ist leer." })
            val token = result.accessToken
            if (token.isNullOrBlank()) errorCallback?.invoke("Google hat kein Zugriffstoken zurückgegeben.")
            else successCallback?.invoke(token)
        } catch (error: Throwable) {
            errorCallback?.invoke(error.message ?: "Google-Autorisierung wurde abgebrochen.")
        } finally {
            successCallback = null
            errorCallback = null
        }
    }

    fun cancel() {
        errorCallback?.invoke("Google-Autorisierung wurde abgebrochen.")
        successCallback = null
        errorCallback = null
    }
}
