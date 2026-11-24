# metodi chiamati dal codice nativo (JNI)
-keep class dev.nexus.llama.LlamaNative { *; }
-keep interface dev.nexus.llama.LlamaNative$TokenListener { *; }
-keepclassmembers class * implements dev.nexus.llama.LlamaNative$TokenListener { boolean onToken(java.lang.String); }
