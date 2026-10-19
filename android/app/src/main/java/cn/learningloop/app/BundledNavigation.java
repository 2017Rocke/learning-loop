package cn.learningloop.app;

/** Exact bundled page paths, after the Activity validates origin and path. */
final class BundledNavigation {
    private BundledNavigation() { }

    static boolean allowsDocument(String path) {
        return "index.html".equals(path)
            || "credits.html".equals(path)
            || "lab/index.html".equals(path)
            || "lab/capacitor/index.html".equals(path)
            || "lab/mosfet/index.html".equals(path);
    }

    static boolean allowsNativeBridge(String path) {
        // Standalone labs can navigate, but never receive calendar/backup access.
        return "index.html".equals(path);
    }
}
