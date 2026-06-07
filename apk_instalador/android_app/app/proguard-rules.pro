# Cafetería POS — ProGuard rules
# Preserve WebView JavaScript interface names
-keepclassmembers class * {
    @android.webkit.JavascriptInterface <methods>;
}

# ZXing
-keep class com.google.zxing.** { *; }
-keep class com.journeyapps.** { *; }
