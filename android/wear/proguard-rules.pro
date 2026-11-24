# Libreria Tailscale (gomobile): classi chiamate dal codice nativo
-keep class dev.nexus.ts.** { *; }
-keep class go.** { *; }
# servizio del Data Layer e classi caricate per nome
-keep class dev.nexus.assistant.wear.SyncService { *; }
-dontwarn org.conscrypt.**
-dontwarn org.bouncycastle.**
-dontwarn org.openjsse.**
