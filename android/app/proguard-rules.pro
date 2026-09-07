-keepattributes Signature,*Annotation*
-keep class com.google.mlkit.** { *; }
-keep class com.google.android.gms.auth.** { *; }
-dontwarn org.conscrypt.**
-dontwarn javax.annotation.**

# Die Datenmodelle werden teilweise ueber Androids JSON-Reader befuellt.
-keepclassmembers class org.yugioh.kartenliste.data.model.** { *; }
