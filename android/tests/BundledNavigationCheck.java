package cn.learningloop.app;

/** Checks the actual page policy without an Android device or a WebView. */
public final class BundledNavigationCheck {
    private static void check(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }

    public static void main(String[] args) {
        String[] documents = {"index.html", "credits.html", "lab/index.html", "lab/capacitor/index.html", "lab/mosfet/index.html"};
        for (String path : documents) {
            check(BundledNavigation.allowsDocument(path), "Bundled page must open and restore: " + path);
            check(BundledNavigation.allowsNativeBridge(path) == "index.html".equals(path),
                  "Only the main learning page may receive the native bridge: " + path);
        }
        String[] blocked = {null, "", "lab/", "lab/capacitor/", "lab/capacitor.html",
            "lab/capacitor/index.html/", "lab/capacitor/other.html", "lab/other/index.html",
            "lab/capacitor/../index.html", "lab/mosfet/", "lab/mosfet/other.html", "lab/mosfet/index.html/",
            "lab/mosfet/../index.html", "media/index.html", "courses.json", "app.js",
            "/index.html", "INDEX.html", "https://example.com/index.html"};
        for (String path : blocked) {
            check(!BundledNavigation.allowsDocument(path), "No directory or prefix expansion: " + path);
            check(!BundledNavigation.allowsNativeBridge(path), "Unexpected native bridge page: " + path);
        }
        System.out.println("Bundled navigation checks passed: exact page paths, main-page-only native bridge.");
    }
}
