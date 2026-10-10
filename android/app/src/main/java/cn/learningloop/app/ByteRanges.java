package cn.learningloop.app;

/** Pure parser shared by WebView media responses and a host-side verification harness. */
public final class ByteRanges {
    private ByteRanges() { }
    public static long[] parse(String header, long length) {
        if (length <= 0 || header == null || !header.matches("bytes=\\d*-\\d*")) throw new IllegalArgumentException("Invalid byte range");
        String[] parts = header.substring(6).split("-", -1);
        if (parts[0].isEmpty() && parts[1].isEmpty()) throw new IllegalArgumentException("Empty range");
        try {
            long start, end;
            if (parts[0].isEmpty()) { long suffix = Long.parseLong(parts[1]); if (suffix <= 0) throw new IllegalArgumentException("Invalid suffix"); start = Math.max(0, length - suffix); end = length - 1; }
            else { start = Long.parseLong(parts[0]); end = parts[1].isEmpty() ? length - 1 : Long.parseLong(parts[1]); }
            if (start < 0 || start >= length || end < start) throw new IllegalArgumentException("Unsatisfiable range");
            return new long[]{start, Math.min(end, length - 1)};
        } catch (NumberFormatException error) { throw new IllegalArgumentException("Invalid range integer", error); }
    }
}
