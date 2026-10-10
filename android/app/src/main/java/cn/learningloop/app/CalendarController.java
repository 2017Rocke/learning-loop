package cn.learningloop.app;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.ContentProviderOperation;
import android.content.ContentProviderResult;
import android.content.ContentUris;
import android.content.ContentValues;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.database.Cursor;
import android.provider.CalendarContract;
import org.json.JSONArray;
import org.json.JSONObject;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Instant;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.UUID;

/** Only explicitly confirmed writes to events identifiable as belonging to this app. */
final class CalendarController {
    static final int PERMISSION_CODE = 501;
    interface Result { void complete(boolean ok, String message); }
    private final Activity activity;
    private final SharedPreferences preferences;
    private Schedule pending;
    private Result callback;
    private boolean busy, disposed;
    private AlertDialog dialog;
    static final class Review {
        final String courseID, title;
        final long dueAt;
        final int count;
        Review(JSONObject json) throws Exception {
            courseID = json.getString("course_id"); title = json.getString("title");
            if (courseID.trim().isEmpty() || courseID.length() > 400 || title.trim().isEmpty() || title.length() > 250 || courseID.matches("(?s).*[\\p{Cntrl}].*")) throw new IllegalArgumentException("Invalid course");
            dueAt = Instant.parse(json.getString("due_at")).toEpochMilli(); count = json.getInt("count");
            if (count < 1 || count > 10000) throw new IllegalArgumentException("Invalid count");
        }
    }
    static final class Schedule {
        final String time;
        final int minutes;
        final Long dueAt;
        final List<Review> reviews = new ArrayList<>();
        Schedule(JSONObject json) throws Exception {
            time = json.optString("time", "20:00");
            if (!time.matches("([01]\\d|2[0-3]):[0-5]\\d")) throw new IllegalArgumentException("Invalid reminder time");
            minutes = json.optInt("minutes", 5);
            if (minutes < 1 || minutes > 60) throw new IllegalArgumentException("Invalid review duration");
            String due = json.optString("due_at", ""); dueAt = due.isEmpty() || due.equals("null") ? null : Instant.parse(due).toEpochMilli();
            JSONArray rows = json.optJSONArray("reviews");
            if (rows != null) {
                if (rows.length() > 20) throw new IllegalArgumentException("Too many review reminders");
                Set<String> ids = new HashSet<>();
                for (int i = 0; i < rows.length(); i++) { Review review = new Review(rows.getJSONObject(i)); if (!ids.add(review.courseID)) throw new IllegalArgumentException("Duplicate course"); reviews.add(review); }
            }
        }
    }
    CalendarController(Activity activity) { this.activity = activity; preferences = activity.getSharedPreferences("calendar", Activity.MODE_PRIVATE); }
    private boolean alive() { return !disposed && !activity.isFinishing() && !activity.isDestroyed(); }
    void dispose() { disposed = true; callback = null; pending = null; busy = false; if (dialog != null) { dialog.dismiss(); dialog = null; } }
    void request(JSONObject json, Result result) {
        if (!alive()) return;
        if (busy) { result.complete(false, "请先完成当前日历操作"); return; }
        try { pending = new Schedule(json); } catch (Exception error) { result.complete(false, "无法识别复习提醒设置"); return; }
        busy = true; callback = result;
        String reviews = pending.reviews.isEmpty() ? "当前没有已排期的复习题，先安排每日复习时段。" : "同时更新 " + pending.reviews.size() + " 门课程各自最早到期的一条提醒，不包含你的答案。";
        dialog = new AlertDialog.Builder(activity).setTitle("同步手机日历提醒？")
                .setMessage("每天 " + pending.time + " 留 " + pending.minutes + " 分钟主动回忆。" + reviews + "\n\n下一步会按需请求日历权限。选择日历后，点击“同步提醒”才会写入。只创建或更新知行自己的提醒。系统日历是否响铃取决于手机设置；下次学习计划变化后，可在 App 再同步。")
                .setPositiveButton("下一步：选择日历", (dialog, which) -> ensurePermission())
                .setNegativeButton("暂不设置", (dialog, which) -> finish(false, "未同步日历提醒，可以继续学习"))
                .setOnCancelListener(dialog -> finish(false, "已取消，日历没有改变")).show();
    }
    private void ensurePermission() {
        if (!alive() || !busy || pending == null) return;
        if (activity.checkSelfPermission(Manifest.permission.READ_CALENDAR) != PackageManager.PERMISSION_GRANTED || activity.checkSelfPermission(Manifest.permission.WRITE_CALENDAR) != PackageManager.PERMISSION_GRANTED) activity.requestPermissions(new String[]{Manifest.permission.READ_CALENDAR, Manifest.permission.WRITE_CALENDAR}, PERMISSION_CODE);
        else chooseCalendar();
    }
    void permissionResult() {
        if (!alive() || !busy || pending == null) return;
        if (activity.checkSelfPermission(Manifest.permission.READ_CALENDAR) == PackageManager.PERMISSION_GRANTED && activity.checkSelfPermission(Manifest.permission.WRITE_CALENDAR) == PackageManager.PERMISSION_GRANTED) chooseCalendar();
        else finish(false, "日历权限未授予，学习功能不受影响。可在系统设置授权后再试。");
    }
    private void chooseCalendar() {
        if (!alive() || !busy || pending == null) return;
        List<Long> ids = new ArrayList<>(); List<String> names = new ArrayList<>();
        try (Cursor cursor = activity.getContentResolver().query(CalendarContract.Calendars.CONTENT_URI,
                new String[]{CalendarContract.Calendars._ID, CalendarContract.Calendars.CALENDAR_DISPLAY_NAME, CalendarContract.Calendars.ACCOUNT_NAME, CalendarContract.Calendars.ALLOWED_REMINDERS},
                CalendarContract.Calendars.CALENDAR_ACCESS_LEVEL + ">=?", new String[]{String.valueOf(CalendarContract.Calendars.CAL_ACCESS_CONTRIBUTOR)}, CalendarContract.Calendars.CALENDAR_DISPLAY_NAME + " ASC")) {
            while (cursor != null && cursor.moveToNext()) {
                String allowed = cursor.getString(3);
                if (allowed != null && !allowed.isEmpty() && !("," + allowed.replace(" ", "") + ",").contains("," + CalendarContract.Reminders.METHOD_ALERT + ",")) continue;
                ids.add(cursor.getLong(0)); names.add(calendarLabel(cursor.getString(1), cursor.getString(2)));
            }
        } catch (Exception error) { finish(false, "无法读取可写日历，请检查日历应用和权限"); return; }
        if (ids.isEmpty()) { finish(false, "手机上没有支持提醒的可写日历。请先在日历应用中添加日历，再重试。"); return; }
        // Selecting a row only changes the radio selection; the explicit button performs the write.
        int[] selected = {ids.size() == 1 ? 0 : -1};
        AlertDialog picker = new AlertDialog.Builder(activity).setTitle("选择保存提醒的日历")
                .setSingleChoiceItems(names.toArray(new String[0]), selected[0], (choiceDialog, which) -> {
                    selected[0] = which;
                    ((AlertDialog) choiceDialog).getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(true);
                })
                .setPositiveButton("同步提醒", (choiceDialog, which) -> {
                    if (selected[0] >= 0 && selected[0] < ids.size()) sync(ids.get(selected[0]));
                    else finish(false, "尚未选择日历，提醒未同步");
                })
                .setNegativeButton("取消", (dialog, which) -> finish(false, "已取消，日历没有改变"))
                .setOnCancelListener(dialog -> finish(false, "已取消，日历没有改变")).create();
        dialog = picker;
        picker.show();
        picker.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(selected[0] >= 0);
    }
    private static String calendarLabel(String displayName, String accountName) {
        String name = displayName == null ? "" : displayName.trim();
        String account = accountName == null ? "" : accountName.trim();
        // Some Xiaomi providers expose these local-calendar resource names verbatim.
        // Translate only the known placeholders; real calendar/account names still distinguish choices.
        if ("calendar_displayname_local".equals(name)) name = "本机日历";
        if ("account_name_local".equals(account)) {
            if (name.isEmpty()) name = "本机日历";
            account = "";
        }
        if (name.isEmpty()) name = "未命名日历";
        return account.isEmpty() || name.equals(account) ? name : name + " · " + account;
    }
    private String courseKey(String id) throws Exception {
        byte[] hash = MessageDigest.getInstance("SHA-256").digest(id.getBytes(StandardCharsets.UTF_8)); StringBuilder out = new StringBuilder("course-"); for (byte value : hash) out.append(String.format(java.util.Locale.ROOT, "%02x", value & 255)); return out.toString();
    }
    private long findOwnedEvent(String marker, String key) {
        // The stable marker is committed BEFORE writing events. Query recovery also handles
        // process death between applyBatch success and saving the resulting event IDs.
        String prefix = marker + "\n提醒键：" + key + "\n";
        try (Cursor c = activity.getContentResolver().query(CalendarContract.Events.CONTENT_URI,
                new String[]{CalendarContract.Events._ID, CalendarContract.Events.DESCRIPTION},
                CalendarContract.Events.CUSTOM_APP_PACKAGE + "=? AND " + CalendarContract.Events.DELETED + "=0 AND " + CalendarContract.Events.DESCRIPTION + " LIKE ?",
                new String[]{activity.getPackageName(), prefix + "%"}, CalendarContract.Events._ID + " ASC")) {
            while (c != null && c.moveToNext()) if (c.getString(1) != null && c.getString(1).startsWith(prefix)) return c.getLong(0);
        }
        return -1;
    }
    private void sync(long calendarID) {
        if (!alive() || !busy || pending == null) return;
        try {
            String marker = preferences.getString("owner_marker", null);
            if (marker == null) { marker = "知行专属提醒：" + UUID.randomUUID(); if (!preferences.edit().putString("owner_marker", marker).commit()) throw new IllegalStateException("Unable to persist event ownership"); }
            ArrayList<ContentProviderOperation> ops = new ArrayList<>();
            List<String> keys = new ArrayList<>(); List<Long> existing = new ArrayList<>(); List<Integer> insertIndexes = new ArrayList<>();
            long now = System.currentTimeMillis(); ZoneId zone = ZoneId.systemDefault();
            addEvent(ops, keys, existing, insertIndexes, marker, "daily", calendarID,
                    CalendarTimes.dailyStart(pending.time, null, now, zone), true,
                    "打开知行，先回答再看参考答案。复习题以 App 内到期计划为准。", pending.minutes);
            for (Review review : pending.reviews) addEvent(ops, keys, existing, insertIndexes, marker, courseKey(review.courseID), calendarID,
                    CalendarTimes.reviewStart(review.dueAt, pending.time, now, zone), false,
                    "课程：" + review.title + "\n本课复习计划共 " + review.count + " 道题，本条对应最早到期时间，并非所有题目同时到期。打开知行查看当前到期题目。", pending.minutes);
            ContentProviderResult[] results = activity.getContentResolver().applyBatch(CalendarContract.AUTHORITY, ops);
            SharedPreferences.Editor editor = preferences.edit();
            for (int i = 0; i < keys.size(); i++) { long eventID = existing.get(i); if (eventID <= 0) { if (results[insertIndexes.get(i)].uri == null) throw new IllegalStateException("No event id"); eventID = ContentUris.parseId(results[insertIndexes.get(i)].uri); } editor.putLong("event_" + keys.get(i), eventID); }
            // Marker lookup above remains sufficient even if this advisory ID cache cannot persist.
            editor.apply();
            finish(true, "已同步每日时段和 " + pending.reviews.size() + " 门课程提醒。请在手机日历检查通知设置。");
        } catch (Exception error) { finish(false, "日历同步没有确认成功。请检查手机日历后再试，学习记录未受影响。"); }
    }
    private void addEvent(ArrayList<ContentProviderOperation> ops, List<String> keys, List<Long> existing, List<Integer> inserts,
                          String marker, String key, long calendarID, long start, boolean daily, String description, int minutes) {
        long eventID = findOwnedEvent(marker, key);
        ContentValues values = new ContentValues();
        values.put(CalendarContract.Events.CALENDAR_ID, calendarID); values.put(CalendarContract.Events.TITLE, daily ? "知行 · 每日回忆复习" : "知行 · 课程到期复习");
        values.put(CalendarContract.Events.DESCRIPTION, marker + "\n提醒键：" + key + "\n" + description);
        values.put(CalendarContract.Events.DTSTART, start); values.put(CalendarContract.Events.EVENT_TIMEZONE, ZoneId.systemDefault().getId());
        if (daily) { values.putNull(CalendarContract.Events.DTEND); values.put(CalendarContract.Events.DURATION, "PT" + minutes + "M"); values.put(CalendarContract.Events.RRULE, "FREQ=DAILY"); }
        else { values.put(CalendarContract.Events.DTEND, start + minutes * 60000L); values.putNull(CalendarContract.Events.DURATION); values.putNull(CalendarContract.Events.RRULE); }
        values.put(CalendarContract.Events.ALL_DAY, 0); values.put(CalendarContract.Events.HAS_ALARM, 1); values.put(CalendarContract.Events.CUSTOM_APP_PACKAGE, activity.getPackageName());
        keys.add(key); existing.add(eventID); inserts.add(ops.size());
        if (eventID > 0) {
            ops.add(ContentProviderOperation.newUpdate(ContentUris.withAppendedId(CalendarContract.Events.CONTENT_URI, eventID)).withValues(values).withExpectedCount(1).build());
            ops.add(ContentProviderOperation.newDelete(CalendarContract.Reminders.CONTENT_URI).withSelection(CalendarContract.Reminders.EVENT_ID + "=?", new String[]{String.valueOf(eventID)}).build());
            ops.add(ContentProviderOperation.newInsert(CalendarContract.Reminders.CONTENT_URI).withValue(CalendarContract.Reminders.EVENT_ID, eventID).withValue(CalendarContract.Reminders.MINUTES, 0).withValue(CalendarContract.Reminders.METHOD, CalendarContract.Reminders.METHOD_ALERT).build());
        } else {
            int index = ops.size(); ops.add(ContentProviderOperation.newInsert(CalendarContract.Events.CONTENT_URI).withValues(values).build());
            ops.add(ContentProviderOperation.newInsert(CalendarContract.Reminders.CONTENT_URI).withValueBackReference(CalendarContract.Reminders.EVENT_ID, index).withValue(CalendarContract.Reminders.MINUTES, 0).withValue(CalendarContract.Reminders.METHOD, CalendarContract.Reminders.METHOD_ALERT).build());
        }
    }
    private void finish(boolean ok, String message) { Result result = callback; callback = null; pending = null; busy = false; if (result != null && alive()) result.complete(ok, message); }
}
