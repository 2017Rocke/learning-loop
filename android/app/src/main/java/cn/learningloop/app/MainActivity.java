package cn.learningloop.app;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.webkit.CookieManager;
import android.webkit.WebMessage;
import android.webkit.WebMessagePort;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;
import org.json.JSONObject;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.ByteBuffer;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Native shell. Executable UI is always bundled; downloaded courses are data only. */
public final class MainActivity extends Activity {
    private static final String ORIGIN = "https://appassets.androidplatform.net";
    private static final String HOME = ORIGIN + "/index.html";
    private static final int EXPORT_CODE = 601, IMPORT_CODE = 602;
    private static final int MAX_BACKUP_BYTES = 10_000_000;
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private final Handler main = new Handler(Looper.getMainLooper());
    private WebView web;
    private TextView status;
    private Button checkButton, downloadButton;
    private SharedPreferences preferences;
    private CourseUpdater updater;
    private volatile CourseUpdater.Snapshot snapshot;
    private CourseUpdater.ReleaseInfo available;
    private CalendarController calendar;
    private WebMessagePort nativePort;
    private JSONObject latestSchedule;
    private boolean updateBusy, offerCalendarAfterLoad, refreshPending, closing;
    private String pendingID, pendingExport, pendingFilename;
    private int pendingDocumentCode;
    private long pageGeneration, pendingGeneration;

    @Override public void onCreate(Bundle savedState) {
        super.onCreate(savedState);
        preferences = getSharedPreferences("native_settings", MODE_PRIVATE);
        updater = new CourseUpdater(this);
        calendar = new CalendarController(this);
        LinearLayout layout = new LinearLayout(this); layout.setOrientation(LinearLayout.VERTICAL); layout.setBackgroundColor(Color.rgb(245, 245, 245));
        layout.setOnApplyWindowInsetsListener((v, insets) -> { v.setPadding(insets.getSystemWindowInsetLeft(), insets.getSystemWindowInsetTop(), insets.getSystemWindowInsetRight(), insets.getSystemWindowInsetBottom()); return insets; });
        LinearLayout bar = new LinearLayout(this); bar.setPadding(dp(8), dp(5), dp(8), 0); bar.setGravity(android.view.Gravity.CENTER_VERTICAL);
        Button repo = smallButton("课程仓库", v -> configureRepository());
        checkButton = smallButton("检查更新", v -> checkUpdates());
        downloadButton = smallButton("下载新课程", v -> downloadUpdate()); downloadButton.setVisibility(View.GONE);
        bar.addView(repo, new LinearLayout.LayoutParams(0, dp(42), 1)); bar.addView(checkButton, new LinearLayout.LayoutParams(0, dp(42), 1)); bar.addView(downloadButton, new LinearLayout.LayoutParams(0, dp(42), 1));
        status = new TextView(this); status.setTextColor(Color.rgb(96, 103, 111)); status.setTextSize(10); status.setPadding(dp(15), dp(3), dp(15), dp(7));
        layout.addView(bar); layout.addView(status);
        web = new WebView(this); configureWeb(); layout.addView(web, new LinearLayout.LayoutParams(-1, 0, 1)); setContentView(layout);
        offerCalendarAfterLoad = !preferences.getBoolean("calendar_intro_shown", false);
        loadLearning(savedState == null ? HOME : savedState.getString("page", HOME), false);
        if (!preferences.getString("repository", "").isEmpty()) checkUpdates(false);
    }
    private int dp(int value) { return Math.round(value * getResources().getDisplayMetrics().density); }
    private boolean alive() { return !closing && !isFinishing() && !isDestroyed(); }
    private void setStatus(String message) { if (alive()) status.setText("App " + BuildConfig.VERSION_NAME + " · " + message); }
    private String shortVersion(String version) { return version.substring(0, Math.min(12, version.length())); }
    private String updateFailure(Exception error, String fallback) {
        String message = error.getMessage();
        if (message == null || !message.matches("(?s).*[\\p{IsHan}].*")) return fallback;
        message = message.replaceAll("[\\p{Cntrl}]+", " ");
        return message.substring(0, Math.min(180, message.length()));
    }
    private Button smallButton(String text, View.OnClickListener listener) { Button button = new Button(this); button.setText(text); button.setTextSize(11); button.setAllCaps(false); button.setTextColor(Color.rgb(0, 126, 65)); button.setPadding(dp(5), 0, dp(5), 0); button.setOnClickListener(listener); return button; }
    private void configureWeb() {
        WebSettings settings = web.getSettings(); settings.setJavaScriptEnabled(true); settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false); settings.setAllowContentAccess(false); settings.setAllowFileAccessFromFileURLs(false); settings.setAllowUniversalAccessFromFileURLs(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW); settings.setJavaScriptCanOpenWindowsAutomatically(false); settings.setSupportMultipleWindows(false);
        settings.setMediaPlaybackRequiresUserGesture(true); settings.setGeolocationEnabled(false); settings.setSaveFormData(false); settings.setSafeBrowsingEnabled(true);
        settings.setUserAgentString(settings.getUserAgentString() + " LearningLoopAndroid/" + BuildConfig.VERSION_NAME);
        CookieManager.getInstance().setAcceptCookie(false); CookieManager.getInstance().setAcceptThirdPartyCookies(web, false);
        WebView.setWebContentsDebuggingEnabled(false);
        web.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                if (trusted(uri)) {
                    String path = safePath(uri);
                    if (path == null) return true;
                    // Only bundled documents may become top-level pages; course data is never executable.
                    if (request.isForMainFrame() && !(path.equals("index.html") || path.equals("credits.html") || path.equals("lab/index.html"))) return true;
                    return false;
                }
                if (request.isForMainFrame() && request.hasGesture() && "https".equals(uri.getScheme())) openExternal(uri);
                return true;
            }
            @Override public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) { return resource(request); }
            @Override public void onPageStarted(WebView view, String url, android.graphics.Bitmap favicon) { pageGeneration++; closePort(); }
            @Override public void onPageFinished(WebView view, String url) {
                Uri uri = Uri.parse(url);
                if (trusted(uri) && "index.html".equals(safePath(uri))) connectBridge();
            }
        });
        web.setDownloadListener((url, userAgent, disposition, mime, size) -> toast("请使用课程设置中的“导出学习记录”，通过系统文件选择器保存。"));
    }
    private boolean trusted(Uri uri) { return "https".equals(uri.getScheme()) && "appassets.androidplatform.net".equals(uri.getHost()) && (uri.getPort() == -1 || uri.getPort() == 443) && uri.getUserInfo() == null; }
    private String safePath(Uri uri) {
        if (!trusted(uri)) return null;
        String path = uri.getPath(); if (path == null || path.equals("/")) return "index.html";
        if (!path.startsWith("/") || path.contains("\\") || path.contains("\u0000")) return null;
        String clean = path.substring(1);
        for (String segment : clean.split("/", -1)) if (segment.equals("..") || segment.equals(".") || segment.isEmpty()) return null;
        return clean;
    }
    private String mime(String path) {
        if (path.endsWith(".html")) return "text/html"; if (path.endsWith(".js")) return "application/javascript"; if (path.endsWith(".css")) return "text/css";
        if (path.endsWith(".json") || path.endsWith(".webmanifest")) return "application/json"; if (path.endsWith(".svg")) return "image/svg+xml";
        if (path.endsWith(".png")) return "image/png"; if (path.endsWith(".webp")) return "image/webp"; if (path.endsWith(".jpg") || path.endsWith(".jpeg")) return "image/jpeg";
        if (path.endsWith(".m4a")) return "audio/mp4"; if (path.endsWith(".mp3")) return "audio/mpeg"; if (path.endsWith(".wav")) return "audio/wav";
        if (path.endsWith(".mp4")) return "video/mp4"; if (path.endsWith(".webm")) return "video/webm"; if (path.endsWith(".vtt")) return "text/vtt"; return "application/octet-stream";
    }
    private WebResourceResponse resource(WebResourceRequest request) {
        String path = safePath(request.getUrl());
        if (path == null || !(request.getMethod().equals("GET") || request.getMethod().equals("HEAD"))) return error(403, "Forbidden", "Only bundled UI and local course assets are available");
        if (path.equals("sw.js")) return error(404, "Not Found", "Native app does not use service workers");
        try {
            InputStream stream; long length; String type;
            CourseUpdater.Asset active = snapshot == null ? null : snapshot.open(path);
            if (active != null) { stream = active.stream; length = active.length; type = active.mimeType; }
            else {
                if (path.equals("courses.json") || path.startsWith("media/")) return error(404, "Not Found", "Course asset unavailable");
                byte[] bytes; try (InputStream input = getAssets().open("site/" + path)) { bytes = readLimited(input); }
                stream = new ByteArrayInputStream(bytes); length = bytes.length; type = mime(path);
            }
            Map<String, String> headers = new HashMap<>(); headers.put("X-Content-Type-Options", "nosniff"); headers.put("Cache-Control", "no-store"); headers.put("Accept-Ranges", "bytes");
            headers.put("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; media-src 'self'; connect-src 'self'; frame-src 'self'; object-src 'none'; base-uri 'self'; form-action 'none'; worker-src 'none'");
            String range = request.getRequestHeaders().get("Range");
            if (range == null) range = request.getRequestHeaders().get("range");
            WebViewMediaResponse response = WebViewMediaResponse.prepare(stream, length, range, request.getMethod().equals("HEAD"));
            headers.put("Content-Length", Long.toString(response.contentLength));
            if (response.contentRange != null) headers.put("Content-Range", response.contentRange);
            return new WebResourceResponse(type, type.startsWith("text/") || type.contains("javascript") || type.contains("json") ? "UTF-8" : null, response.status, response.reason, headers, response.stream);
        } catch (Exception ignored) { return error(404, "Not Found", "Local resource unavailable"); }
    }
    private WebResourceResponse error(int code, String reason, String text) { return new WebResourceResponse("text/plain", "UTF-8", code, reason, java.util.Collections.singletonMap("X-Content-Type-Options", "nosniff"), new ByteArrayInputStream(text.getBytes(StandardCharsets.UTF_8))); }
    private void loadLearning(String requestedURL, boolean offerCalendar) {
        if (!alive()) return;
        try { snapshot = updater.captureSnapshot(); } catch (Exception error) { setStatus("课程资源无法读取，请重新打开应用"); toast("课程资源无法读取，请重新打开应用。"); return; }
        available = null; refreshPending = false; downloadButton.setVisibility(View.GONE); resetDownloadButton(); setStatus("本机课程 " + shortVersion(snapshot.version) + " · 学习记录仅留在此设备");
        offerCalendarAfterLoad |= offerCalendar;
        Uri uri = Uri.parse(requestedURL);
        String path = safePath(uri);
        web.loadUrl(trusted(uri) && path != null && (path.equals("index.html") || path.equals("credits.html") || path.equals("lab/index.html")) ? requestedURL : HOME);
    }
    private void connectBridge() {
        if (!alive() || snapshot == null) return;
        closePort();
        WebMessagePort[] ports = web.createWebMessageChannel(); nativePort = ports[0];
        final long generation = pageGeneration;
        nativePort.setWebMessageCallback(new WebMessagePort.WebMessageCallback() {
            @Override public void onMessage(WebMessagePort port, WebMessage message) {
                if (generation != pageGeneration || !trusted(Uri.parse(web.getUrl() == null ? "" : web.getUrl())) || !"index.html".equals(safePath(Uri.parse(web.getUrl())))) return;
                handleMessage(message.getData(), generation);
            }
        }, main);
        try {
            JSONObject reminder = new JSONObject().put("time", snapshot.reminderTime).put("minutes", snapshot.reminderMinutes);
            JSONObject hello = new JSONObject().put("type", "learning-loop-native-ready").put("reminder", reminder);
            web.postWebMessage(new WebMessage(hello.toString(), new WebMessagePort[]{ports[1]}), Uri.parse(ORIGIN));
        } catch (Exception error) { closePort(); toast("手机功能连接未完成，请重新打开应用。"); }
    }
    private void closePort() { if (nativePort != null) { nativePort.close(); nativePort = null; } }
    private void handleMessage(String text, long generation) {
        if (!alive() || text == null || text.length() > MAX_BACKUP_BYTES + 2000) return;
        String id = "";
        try {
            JSONObject command = new JSONObject(text); id = command.optString("id", "");
            if (!id.matches("[a-zA-Z0-9_-]{1,100}")) return;
            String action = command.optString("action"); JSONObject payload = command.optJSONObject("payload"); if (payload == null) payload = new JSONObject();
            final String requestID = id;
            switch (action) {
                case "scheduleState":
                    new CalendarController.Schedule(payload); latestSchedule = payload;
                    reply(id, true, new JSONObject().put("native", true), null, generation);
                    if (offerCalendarAfterLoad) { offerCalendarAfterLoad = false; preferences.edit().putBoolean("calendar_intro_shown", true).apply(); calendar.request(latestSchedule, (ok, message) -> toast(message)); }
                    break;
                case "schedule": calendar.request(payload, (ok, message) -> { toast(message); reply(requestID, ok, null, message, generation); }); break;
                case "export": exportBackup(id, payload, generation); break;
                case "import": importBackup(id, generation); break;
                case "update": checkUpdates(); reply(id, true, null, null, generation); break;
                default: reply(id, false, null, "不支持的操作", generation);
            }
        } catch (Exception error) { if (!id.isEmpty()) reply(id, false, null, "无法处理此操作，请检查输入后重试", generation); }
    }
    private void reply(String id, boolean ok, JSONObject data, String message, long generation) {
        if (!alive() || generation != pageGeneration || nativePort == null) return;
        try { JSONObject result = new JSONObject().put("id", id).put("ok", ok); if (data != null) result.put("data", data); if (message != null) result.put(ok ? "message" : "error", message); nativePort.postMessage(new WebMessage(result.toString())); } catch (Exception ignored) { }
    }
    private void exportBackup(String id, JSONObject payload, long generation) throws Exception {
        if (pendingID != null) { reply(id, false, null, "请先完成正在进行的文件操作", generation); return; }
        String text = payload.optString("text"); if (text.getBytes(StandardCharsets.UTF_8).length > MAX_BACKUP_BYTES) throw new IllegalArgumentException("Backup too large");
        String filename = payload.optString("filename", "zhixing-learning-backup.json"); if (!filename.matches("[a-zA-Z0-9._-]{1,100}\\.json")) filename = "zhixing-learning-backup.json";
        // Preserve raw recovery text too: a damaged backup must remain exportable.
        pendingID = id; pendingExport = text; pendingFilename = filename; pendingGeneration = generation; pendingDocumentCode = EXPORT_CODE;
        Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("application/json").putExtra(Intent.EXTRA_TITLE, filename);
        try { startActivityForResult(intent, EXPORT_CODE); } catch (Exception error) { clearDocument(); reply(id, false, null, "未找到系统文件保存器", generation); }
    }
    private void importBackup(String id, long generation) {
        if (pendingID != null) { reply(id, false, null, "请先完成正在进行的文件操作", generation); return; }
        pendingID = id; pendingGeneration = generation; pendingDocumentCode = IMPORT_CODE;
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("application/json");
        try { startActivityForResult(intent, IMPORT_CODE); } catch (Exception error) { clearDocument(); reply(id, false, null, "未找到系统文件选择器", generation); }
    }
    @Override protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (!alive() || (requestCode != EXPORT_CODE && requestCode != IMPORT_CODE)) return;
        if (pendingID == null || pendingDocumentCode != requestCode) {
            toast(requestCode == EXPORT_CODE ? "文件保存已中断，请重新导出；如果已创建文件，请检查它是否为空。" : "文件读取已中断，请重新选择备份；学习记录没有改变。");
            return;
        }
        String id = pendingID, text = pendingExport; long generation = pendingGeneration;
        if (resultCode != RESULT_OK || data == null || data.getData() == null) { clearDocument(); reply(id, false, null, "已取消文件操作，学习记录没有改变", generation); return; }
        Uri uri = data.getData();
        worker.execute(() -> {
            try {
                JSONObject result = new JSONObject();
                if (requestCode == EXPORT_CODE) { try (OutputStream output = getContentResolver().openOutputStream(uri, "wt")) { if (output == null) throw new IOException("No output"); output.write(text.getBytes(StandardCharsets.UTF_8)); output.flush(); } result.put("saved", true); }
                else {
                    byte[] bytes; try (InputStream input = getContentResolver().openInputStream(uri)) { if (input == null) throw new IOException("No input"); bytes = readLimited(input); }
                    String imported = StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT).onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(bytes)).toString();
                    result.put("text", imported);
                }
                main.post(() -> { if (!alive()) return; clearDocument(); reply(id, true, result, null, generation); });
            } catch (Exception error) { main.post(() -> { if (!alive()) return; clearDocument(); reply(id, false, null, "文件操作未完成，请检查文件和存储空间；学习记录没有改变", generation); }); }
        });
    }
    private byte[] readLimited(InputStream input) throws IOException { ByteArrayOutputStream output = new ByteArrayOutputStream(); byte[] buffer = new byte[8192]; int count; while ((count = input.read(buffer)) != -1) { if (output.size() + count > MAX_BACKUP_BYTES) throw new IOException("File too large"); output.write(buffer, 0, count); } return output.toByteArray(); }
    private void clearDocument() { pendingID = null; pendingExport = null; pendingFilename = null; pendingDocumentCode = 0; }
    private void configureRepository() {
        if (!alive()) return;
        if (updateBusy) { toast("正在处理课程更新，请完成后再修改仓库"); return; }
        EditText input = new EditText(this); input.setSingleLine(true); input.setText(preferences.getString("repository", "")); input.setHint("owner/repository（公开仓库）"); input.setPadding(dp(20), dp(12), dp(20), dp(12));
        AlertDialog dialog = new AlertDialog.Builder(this).setTitle("配置公开课程仓库").setMessage("只需 GitHub 的 owner/repository，不需要登录、密码或令牌。课程包按 Release 校验后下载，App 程序不会随课程包更新。")
                .setView(input).setPositiveButton("保存", null).setNegativeButton("取消", null).create();
        dialog.setOnShowListener(v -> dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(clicked -> {
            if (!alive()) return;
            String repo = input.getText().toString().trim();
            if (!repo.matches("[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9][A-Za-z0-9._-]{0,99}")) { input.setError("请输入 owner/repository"); return; }
            preferences.edit().putString("repository", repo).apply(); available = null; downloadButton.setVisibility(View.GONE); resetDownloadButton(); dialog.dismiss(); checkUpdates(false);
        })); dialog.show();
    }
    private void checkUpdates() { checkUpdates(true); }
    private void checkUpdates(boolean manual) {
        if (!alive()) return;
        if (updateBusy) { if (manual) toast("正在处理课程更新，请稍候"); return; }
        String repo = preferences.getString("repository", ""); if (repo.isEmpty()) { if (manual) configureRepository(); return; }
        String[] parts = repo.split("/");
        updateBusy = true; checkButton.setEnabled(false); downloadButton.setVisibility(View.GONE); resetDownloadButton(); setStatus("正在检查公开课程 Release…");
        worker.execute(() -> {
            try {
                CourseUpdater.ReleaseInfo info = updater.check(parts[0], parts[1]);
                main.post(() -> { if (!alive()) return; updateBusy = false; checkButton.setEnabled(true); available = info;
                if (info == null) { setStatus(refreshPending ? "新课程已就绪，刷新后使用" : snapshot == null ? "本机课程暂不可读取，请重新打开应用" : "当前课程已经是最新版本 · " + shortVersion(snapshot.version)); if (refreshPending) showRefreshButton(); }
                    else if (info.requiresAppUpgrade) { setStatus("课程包需要更新版本的 APK，请先更新应用"); if (refreshPending) showRefreshButton(); if (manual) new AlertDialog.Builder(this).setTitle("需要更新应用").setMessage("这份课程使用了较新的课程格式。请从可信的应用发布渠道安装新版 APK，当前课程仍可使用。").setPositiveButton("知道了", null).show(); }
                    else { setStatus("发现课程更新：" + info.label); resetDownloadButton(); downloadButton.setVisibility(View.VISIBLE); }
                });
            } catch (Exception error) { main.post(() -> { if (!alive()) return; updateBusy = false; checkButton.setEnabled(true); String message = updateFailure(error, "更新检查失败，请检查网络后重试；原有课程仍可使用。"); setStatus(message); if (refreshPending) showRefreshButton(); if (manual) toast(message); }); }
        });
    }
    private void downloadUpdate() {
        if (!alive()) return;
        final CourseUpdater.ReleaseInfo release = available;
        if (updateBusy || release == null || release.requiresAppUpgrade) return;
        new AlertDialog.Builder(this).setTitle("下载课程更新？").setMessage("将下载并校验「" + release.label + "」。只更新课程文字和媒体，保留本机学习记录。完成后由你确认何时刷新当前页面。")
                .setNegativeButton("取消", null).setPositiveButton("下载更新", (dialog, which) -> {
                    if (!alive()) return;
                    updateBusy = true; checkButton.setEnabled(false); downloadButton.setEnabled(false); setStatus("正在下载并校验课程…");
                    worker.execute(() -> {
                        try {
                            updater.download(release, (downloaded, total) -> main.post(() -> setStatus(total > 0 ? "下载课程 " + Math.min(100, downloaded * 100 / total) + "%" : "正在下载课程…")));
                            main.post(() -> { if (!alive()) return; updateBusy = false; refreshPending = true; checkButton.setEnabled(true); downloadButton.setEnabled(true); available = null; showRefreshButton(); setStatus("新课程已就绪，刷新后使用");
                                new AlertDialog.Builder(this).setTitle("课程已下载完成").setMessage("先保存当前页面中尚未提交的输入。现在刷新会读取新课程，本机记录会保留；旧页面继续使用原课程快照。刷新后可确认是否同步日历提醒。")
                                        .setPositiveButton("刷新并检查提醒", (d, w) -> loadLearning(HOME, true)).setNegativeButton("稍后再刷新", null).show();
                            });
                        } catch (Exception error) { main.post(() -> { if (!alive()) return; updateBusy = false; checkButton.setEnabled(true); downloadButton.setEnabled(true); String message = updateFailure(error, "下载或校验失败，继续使用原课程，可稍后重试。"); setStatus(message); toast(message); }); }
                    });
                }).show();
    }
    private void confirmRefresh() { if (!alive()) return; new AlertDialog.Builder(this).setTitle("刷新到新课程？").setMessage("请先保存未提交的输入。已保存的学习记录会保留。").setPositiveButton("刷新", (d, w) -> loadLearning(HOME, true)).setNegativeButton("取消", null).show(); }
    private void resetDownloadButton() { downloadButton.setText("下载新课程"); downloadButton.setOnClickListener(v -> downloadUpdate()); }
    private void showRefreshButton() { downloadButton.setText("刷新课程"); downloadButton.setVisibility(View.VISIBLE); downloadButton.setOnClickListener(v -> confirmRefresh()); }
    private void openExternal(Uri uri) { if (!alive()) return; try { startActivity(new Intent(Intent.ACTION_VIEW, uri)); } catch (Exception error) { toast("未找到可以打开此链接的浏览器"); } }
    private void toast(String message) { if (alive()) Toast.makeText(this, message, Toast.LENGTH_LONG).show(); }
    @Override public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] results) { super.onRequestPermissionsResult(requestCode, permissions, results); if (alive() && requestCode == CalendarController.PERMISSION_CODE) calendar.permissionResult(); }
    @Override public void onBackPressed() { if (web.canGoBack()) web.goBack(); else super.onBackPressed(); }
    @Override protected void onSaveInstanceState(Bundle out) { super.onSaveInstanceState(out); out.putString("page", web.getUrl()); }
    @Override protected void onDestroy() { closing = true; main.removeCallbacksAndMessages(null); if (calendar != null) calendar.dispose(); closePort(); clearDocument(); if (web != null) { web.stopLoading(); web.destroy(); } worker.shutdown(); super.onDestroy(); }
}
