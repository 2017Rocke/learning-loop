package cn.learningloop.app;

import java.io.ByteArrayInputStream;
import java.io.EOFException;
import java.io.IOException;
import java.io.InputStream;

/** WebView seeks intercepted streams itself, before reading the HTTP response headers. */
final class WebViewMediaResponse {
    final int status;
    final String reason, contentRange;
    final long contentLength;
    final InputStream stream;

    private WebViewMediaResponse(int status, String reason, String contentRange,
                                long contentLength, InputStream stream) {
        this.status = status; this.reason = reason; this.contentRange = contentRange;
        this.contentLength = contentLength; this.stream = stream;
    }

    static WebViewMediaResponse prepare(InputStream input, long length, String range, boolean head) throws IOException {
        long end = length - 1;
        long start = 0;
        if (range != null) {
            try {
                long[] bounds = ByteRanges.parse(range, length);
                start = bounds[0]; end = bounds[1];
            } catch (IllegalArgumentException invalid) {
                input.close();
                return new WebViewMediaResponse(416, "Range Not Satisfiable", "bytes */" + length,
                        0, new ByteArrayInputStream(new byte[0]));
            }
        }
        String contentRange = range == null ? null : "bytes " + start + "-" + end + "/" + length;
        InputStream body;
        if (head) { input.close(); body = new ByteArrayInputStream(new byte[0]); }
        else body = new SeekableResponseStream(input, length, end + 1);
        return new WebViewMediaResponse(range == null ? 200 : 206,
                range == null ? "OK" : "Partial Content", contentRange, Math.max(0, end - start + 1), body);
    }

    /**
     * This is a WebResourceResponse adapter, not an already-sliced HTTP body.
     * Chromium InputStreamReader first calls available() to compute range bounds,
     * then skip(start), and finally read(). Keep the original size and position
     * until that seek; pre-skipping would corrupt nonzero and suffix requests.
     * Chromium does not stop read() at a closed range's end, so we enforce it here.
     */
    private static final class SeekableResponseStream extends InputStream {
        private final InputStream input;
        private final long totalLength, endExclusive;
        private long position;

        SeekableResponseStream(InputStream input, long totalLength, long endExclusive) {
            this.input = input; this.totalLength = totalLength; this.endExclusive = endExclusive;
        }
        @Override public int available() {
            // WebView uses this as resource size, including bytes outside a closed range.
            return (int) Math.min(Integer.MAX_VALUE, Math.max(0, totalLength - position));
        }
        @Override public long skip(long count) throws IOException {
            if (count <= 0 || position >= endExclusive) return 0;
            long limit = Math.min(count, endExclusive - position);
            long skipped = input.skip(limit);
            if (skipped == 0) {
                if (input.read() < 0) throw new EOFException("Short local media stream");
                skipped = 1;
            }
            position += skipped;
            return skipped;
        }
        @Override public int read() throws IOException {
            if (position >= endExclusive) return -1;
            int value = input.read();
            if (value < 0) throw new EOFException("Short local media stream");
            position++;
            return value;
        }
        @Override public int read(byte[] bytes, int offset, int count) throws IOException {
            if (bytes == null) throw new NullPointerException();
            if (offset < 0 || count < 0 || count > bytes.length - offset) throw new IndexOutOfBoundsException();
            if (count == 0) return 0;
            if (position >= endExclusive) return -1;
            int read = input.read(bytes, offset, (int) Math.min(count, endExclusive - position));
            if (read < 0) throw new EOFException("Short local media stream");
            position += read;
            return read;
        }
        @Override public void close() throws IOException { input.close(); }
    }
}
