package cn.learningloop.app;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.List;
import java.util.stream.Collectors;
import java.util.stream.Stream;

/** Host-side model of WebView's available → range calculation → skip → read sequence. */
public final class WebViewMediaResponseCheck {
    private static int checks;
    private interface Attempt { void run() throws Exception; }

    private static void truth(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
        checks++;
    }

    private static void bytes(byte[] actual, byte[] expected, String message) {
        truth(Arrays.equals(actual, expected), message + " (actual " + actual.length + ", expected " + expected.length + " bytes)");
    }

    private static void ioFailure(Attempt attempt, String message) throws Exception {
        try { attempt.run(); } catch (IOException expected) { checks++; return; }
        throw new AssertionError(message);
    }

    private static byte[] sha256(byte[] data) throws Exception {
        return MessageDigest.getInstance("SHA-256").digest(data);
    }

    /** Model the consumer independently; do not reuse the production ByteRanges parser. */
    private static byte[] chromiumRead(InputStream stream, String range) throws IOException {
        long resourceSize = stream.available();
        long start = 0;
        if (range != null) {
            String[] fields = range.substring("bytes=".length()).split("-", -1);
            if (fields[0].isEmpty()) start = Math.max(0, resourceSize - Long.parseLong(fields[1]));
            else start = Long.parseLong(fields[0]);
            if (start >= resourceSize) throw new IOException("Consumer computed an unsatisfiable range");
        }
        long remaining = start;
        while (remaining > 0) {
            long skipped = stream.skip(remaining);
            if (skipped <= 0) throw new IOException("Consumer seek did not make progress");
            remaining -= skipped;
        }
        // Chromium does not enforce a closed range's end at each Java stream read.
        // Uneven read sizes exercise both the body limit and partial final buffers.
        ByteArrayOutputStream body = new ByteArrayOutputStream();
        byte[] buffer = new byte[4099];
        int count;
        while ((count = stream.read(buffer, 3, buffer.length - 3)) != -1) {
            if (count == 0) throw new IOException("Consumer read did not make progress");
            body.write(buffer, 3, count);
        }
        return body.toByteArray();
    }

    private static byte[] response(InputStream input, byte[] original, String range, int start, int end,
                                   String label) throws Exception {
        WebViewMediaResponse response = WebViewMediaResponse.prepare(input, original.length, range, false);
        truth(response.status == (range == null ? 200 : 206), label + " status");
        truth(response.reason.equals(range == null ? "OK" : "Partial Content"), label + " reason");
        truth(response.contentLength == end - start + 1L, label + " Content-Length");
        truth(range == null ? response.contentRange == null
                : response.contentRange.equals("bytes " + start + "-" + end + "/" + original.length),
                label + " Content-Range");
        truth(response.stream.available() == original.length, label + " reports the original resource size before Chromium seeks");
        byte[] actual;
        try (InputStream stream = response.stream) {
            truth(stream.read(new byte[4], 2, 0) == 0, label + " zero-length read before seeking");
            actual = chromiumRead(stream, range);
            truth(stream.read(new byte[4], 2, 0) == 0, label + " zero-length read at EOF");
            truth(stream.read() == -1, label + " single-byte read at range end");
            truth(stream.skip(10) == 0, label + " skip at range end");
        }
        bytes(actual, Arrays.copyOfRange(original, start, end + 1), label + " exact source slice");
        return actual;
    }

    private static void proveOldFailure() throws Exception {
        byte[] original = new byte[128];
        for (int i = 0; i < original.length; i++) original[i] = (byte) i;
        ByteArrayInputStream preSkipped = new ByteArrayInputStream(original);
        truth(preSkipped.skip(32) == 32, "legacy pre-skip fixture");
        // Old BoundedInputStream inherited available/skip, so Chromium saw the
        // remaining size (96) and then skipped 32 again before its first read.
        truth(preSkipped.available() == 96, "old response exposes a shortened resource size");
        byte[] oldBody = chromiumRead(preSkipped, "bytes=32-");
        truth(oldBody.length == 64 && oldBody[0] == 64, "old nonzero range starts twice as far into the asset");
        truth(!Arrays.equals(oldBody, Arrays.copyOfRange(original, 32, 128)), "old response violates the requested slice and advertised length");
        response(new ByteArrayInputStream(original), original, "bytes=32-", 32, 127, "fixed synthetic nonzero range");
        response(new ByteArrayInputStream(original), original, "bytes=-24", 104, 127, "fixed synthetic suffix");
        response(new ByteArrayInputStream(original), original, "bytes=32-47", 32, 47, "fixed synthetic closed range");
    }

    private static final class TrackedStream extends ByteArrayInputStream {
        boolean closed;
        final boolean refuseSkip;
        TrackedStream(byte[] data, boolean refuseSkip) { super(data); this.refuseSkip = refuseSkip; }
        @Override public synchronized long skip(long count) { return refuseSkip ? 0 : super.skip(count); }
        @Override public void close() throws IOException { closed = true; super.close(); }
    }

    private static void streamContracts() throws Exception {
        byte[] original = new byte[64];
        for (int i = 0; i < original.length; i++) original[i] = (byte) (i * 3 + 1);
        TrackedStream inefficient = new TrackedStream(original, true);
        response(inefficient, original, "bytes=31-47", 31, 47, "stream whose skip always returns zero");
        truth(inefficient.closed, "body close reaches the underlying asset stream");

        for (String range : new String[]{null, "bytes=23-31", "bytes=-7"}) {
            TrackedStream source = new TrackedStream(original, false);
            WebViewMediaResponse head = WebViewMediaResponse.prepare(source, original.length, range, true);
            truth(source.closed, "HEAD closes source immediately");
            truth(head.stream.read() == -1, "HEAD has no body");
            truth(head.status == (range == null ? 200 : 206), "HEAD status");
            truth(head.reason.equals(range == null ? "OK" : "Partial Content"), "HEAD reason");
            truth(head.contentLength == (range == null ? 64 : range.startsWith("bytes=-") ? 7 : 9), "HEAD retains requested Content-Length");
            truth(range == null ? head.contentRange == null : head.contentRange.equals(range.startsWith("bytes=-")
                    ? "bytes 57-63/64" : "bytes 23-31/64"), "HEAD Content-Range");
            head.stream.close();
        }
        for (String invalid : new String[]{"bytes=64-", "bytes=19-4", "bytes=-0", "bytes=0-2,9-12", "items=0-9"}) {
            TrackedStream source = new TrackedStream(original, false);
            WebViewMediaResponse rejected = WebViewMediaResponse.prepare(source, original.length, invalid, false);
            truth(source.closed, "invalid range closes source");
            truth(rejected.status == 416 && rejected.reason.equals("Range Not Satisfiable"), "invalid range status/reason");
            truth(rejected.contentLength == 0 && "bytes */64".equals(rejected.contentRange), "invalid range headers");
            truth(rejected.stream.read() == -1, "invalid range has no media body");
            rejected.stream.close();
        }

        try (InputStream stream = WebViewMediaResponse.prepare(new ByteArrayInputStream(original), 64, "bytes=0-7", false).stream) {
            truth(stream.skip(-1) == 0 && stream.skip(0) == 0, "nonpositive skip leaves stream in place");
            for (int i = 0; i < 8; i++) truth(stream.read() == (original[i] & 255), "single-byte reads stay in order");
            truth(stream.read() == -1, "single-byte read enforces closed endpoint");
        }
        try (InputStream stream = WebViewMediaResponse.prepare(new ByteArrayInputStream(new byte[3]), 20, null, false).stream) {
            ioFailure(() -> chromiumRead(stream, null), "truncated source must not look like successful EOF");
        }
        try (InputStream stream = WebViewMediaResponse.prepare(new TrackedStream(new byte[3], true), 20, "bytes=10-", false).stream) {
            ioFailure(() -> chromiumRead(stream, "bytes=10-"), "seek beyond truncated source must fail");
        }
        try (InputStream stream = WebViewMediaResponse.prepare(new ByteArrayInputStream(new byte[0]), 1, null, false).stream) {
            ioFailure(() -> stream.read(), "single-byte read must reject truncated source");
        }
        InputStream brokenClose = new ByteArrayInputStream(original) {
            @Override public void close() throws IOException { throw new IOException("synthetic close failure"); }
        };
        InputStream closeAdapter = WebViewMediaResponse.prepare(brokenClose, original.length, null, false).stream;
        ioFailure(closeAdapter::close, "close exceptions must propagate");

        WebViewMediaResponse empty = WebViewMediaResponse.prepare(new ByteArrayInputStream(new byte[0]), 0, null, false);
        truth(empty.status == 200 && empty.contentLength == 0 && empty.contentRange == null, "empty resource metadata");
        truth(empty.stream.available() == 0 && empty.stream.read(new byte[1], 0, 0) == 0 && empty.stream.read() == -1, "empty resource stream");
        empty.stream.close();
    }

    private static void assetChecks(Path assets) throws Exception {
        List<Path> audio;
        try (Stream<Path> paths = Files.walk(assets.resolve("media"))) {
            audio = paths.filter(Files::isRegularFile).filter(path -> path.toString().matches(".*\\.(m4a|mp3|wav|ogg)$"))
                    .sorted().collect(Collectors.toList());
        }
        truth(!audio.isEmpty(), "bundled audio fixtures are present");
        for (Path file : audio) {
            String label = assets.relativize(file).toString();
            byte[] original = Files.readAllBytes(file);
            truth(original.length > 8192, label + " is large enough for real seek checks");
            int end = original.length - 1;
            byte[] full = response(Files.newInputStream(file), original, null, 0, end, label + " full stream");
            bytes(sha256(full), sha256(original), label + " continuous playback SHA-256");
            response(Files.newInputStream(file), original, "bytes=0-", 0, end, label + " zero-start open range");
            response(Files.newInputStream(file), original, "bytes=" + (original.length / 3) + "-", original.length / 3, end, label + " middle open range");
            response(Files.newInputStream(file), original, "bytes=" + (original.length * 4 / 5) + "-", original.length * 4 / 5, end, label + " late open range");
            response(Files.newInputStream(file), original, "bytes=-4096", original.length - 4096, end, label + " suffix range");
            response(Files.newInputStream(file), original, "bytes=257-4353", 257, 4353, label + " closed range");
            response(Files.newInputStream(file), original, "bytes=" + end + "-" + (end + 8192L), end, end, label + " clipped final byte");
            ByteArrayOutputStream joined = new ByteArrayOutputStream(original.length);
            for (int start = 0; start < original.length; ) {
                int segmentEnd = Math.min(end, start + 131070);
                joined.write(response(Files.newInputStream(file), original, "bytes=" + start + "-" + segmentEnd,
                        start, segmentEnd, label + " stitched segment " + start));
                start = segmentEnd + 1;
            }
            bytes(sha256(joined.toByteArray()), sha256(original), label + " stitched ranges SHA-256");
        }
        System.out.println("WebView media assets verified: " + audio.size() + " (all bundled audio files)");
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 1) throw new IllegalArgumentException("Pass the bundled site assets directory");
        proveOldFailure();
        streamContracts();
        assetChecks(Path.of(args[0]));
        System.out.println("WebView media response checks passed: " + checks + " (consumer model, not Android-device playback)");
    }
}
