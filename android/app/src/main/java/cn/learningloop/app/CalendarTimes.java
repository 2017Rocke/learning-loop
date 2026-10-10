package cn.learningloop.app;

import java.time.Instant;
import java.time.LocalDate;
import java.time.LocalTime;
import java.time.ZoneId;
import java.time.ZonedDateTime;

/** Calendar planning is local-time aware; actual review due instants retain their timezone. */
public final class CalendarTimes {
    private CalendarTimes() { }
    public static long dailyStart(String time, Long firstDue, long nowMillis, ZoneId zone) {
        ZonedDateTime now = Instant.ofEpochMilli(nowMillis).atZone(zone);
        LocalDate date = firstDue != null && firstDue > nowMillis ? Instant.ofEpochMilli(firstDue).atZone(zone).toLocalDate() : now.toLocalDate();
        ZonedDateTime start = date.atTime(LocalTime.parse(time)).atZone(zone);
        if (!start.isAfter(now)) start = start.plusDays(1);
        return start.toInstant().toEpochMilli();
    }
    public static long reviewStart(long dueMillis, String time, long nowMillis, ZoneId zone) {
        return dueMillis > nowMillis ? dueMillis : dailyStart(time, null, nowMillis, zone);
    }
}
