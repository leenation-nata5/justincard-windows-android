-keep class org.yugioh.kartenliste.data.** { *; }
-keep class org.yugioh.kartenliste.cloud.** { *; }
-keepattributes Signature,*Annotation*
-dontwarn org.conscrypt.**

# Gson data models used by cloud backup and YGOPRODeck
-keepattributes Signature
-keepattributes *Annotation*
-keep class org.yugioh.kartenliste.data.** { *; }
-dontwarn org.conscrypt.**
