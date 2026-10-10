package cn.learningloop.app;

import java.time.Instant;
import java.time.ZoneId;
import java.util.Arrays;

/** Host-side checks for media seeking and calendar time boundaries; no Android device needed. */
public final class NativeUtilityCheck {
    private static int checks;
    private static void range(String header, long length, long start, long end) {
        long[] actual = ByteRanges.parse(header, length);
        if (!Arrays.equals(actual, new long[]{start, end})) throw new AssertionError(header + " returned " + Arrays.toString(actual));
        checks++;
    }
    private static void invalid(String header, long length) {
        try { ByteRanges.parse(header, length); } catch (IllegalArgumentException expected) { checks++; return; }
        throw new AssertionError("Invalid range accepted: " + header);
    }
    private static long instant(String value) { return Instant.parse(value).toEpochMilli(); }
    private static void time(long actual, String expected) {
        if (actual != instant(expected)) throw new AssertionError("Expected " + expected + ", got " + Instant.ofEpochMilli(actual));
        checks++;
    }
    public static void main(String[] args) {
        range("bytes=0-0", 100, 0, 0);
        range("bytes=10-19", 100, 10, 19);
        range("bytes=90-", 100, 90, 99);
        range("bytes=90-120", 100, 90, 99);
        range("bytes=-10", 100, 90, 99);
        range("bytes=-200", 100, 0, 99);
        range("bytes=0-", 1, 0, 0);
        range("bytes=-9223372036854775807", 100, 0, 99);
        range("bytes=0-9223372036854775807", 100, 0, 99);
        for (String header : new String[]{null, "", "items=0-2", "bytes=-", "bytes=-0", "bytes=100-", "bytes=20-10", "bytes=0-1,3-4", "bytes= 0-2", "bytes=0-9223372036854775808", "bytes=9223372036854775808-"}) invalid(header, 100);
        invalid("bytes=0-0", 0);
        invalid("bytes=0-0", -1);

        ZoneId shanghai = ZoneId.of("Asia/Shanghai");
        time(CalendarTimes.dailyStart("20:00", null, instant("2026-10-10T11:00:00Z"), shanghai), "2026-10-10T12:00:00Z");
        time(CalendarTimes.dailyStart("20:00", null, instant("2026-10-10T12:00:00Z"), shanghai), "2026-10-11T12:00:00Z");
        time(CalendarTimes.dailyStart("20:00", null, instant("2026-10-10T13:00:00Z"), shanghai), "2026-10-11T12:00:00Z");
        time(CalendarTimes.reviewStart(instant("2026-10-12T03:15:00Z"), "20:00", instant("2026-10-10T11:00:00Z"), shanghai), "2026-10-12T03:15:00Z");
        time(CalendarTimes.reviewStart(instant("2026-10-09T03:15:00Z"), "20:00", instant("2026-10-10T11:00:00Z"), shanghai), "2026-10-10T12:00:00Z");
        time(CalendarTimes.reviewStart(instant("2026-10-10T12:00:00Z"), "20:00", instant("2026-10-10T12:00:00Z"), shanghai), "2026-10-11T12:00:00Z");
        time(CalendarTimes.dailyStart("00:05", null, instant("2026-12-31T16:10:00Z"), shanghai), "2027-01-01T16:05:00Z");

        // A daily local wall-clock slot stays 20:00 across DST changes (23/25 hour days).
        ZoneId newYork = ZoneId.of("America/New_York");
        time(CalendarTimes.dailyStart("20:00", null, instant("2026-03-08T01:30:00Z"), newYork), "2026-03-09T00:00:00Z");
        time(CalendarTimes.dailyStart("20:00", null, instant("2026-11-01T00:30:00Z"), newYork), "2026-11-02T01:00:00Z");
        time(CalendarTimes.dailyStart("02:30", null, instant("2026-03-08T05:00:00Z"), newYork), "2026-03-08T07:30:00Z");
        System.out.println("Native utility checks passed: " + checks);
    }
}
