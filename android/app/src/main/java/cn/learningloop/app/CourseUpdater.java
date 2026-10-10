package cn.learningloop.app;

import android.content.Context;
import android.content.res.AssetManager;
import android.util.AtomicFile;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileNotFoundException;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.SocketTimeoutException;
import java.net.URI;
import java.net.UnknownHostException;
import java.nio.charset.StandardCharsets;
import java.util.UUID;

/** Public GitHub course updates; never downloads HTML/JS, calls a model, or accesses learner records. */
public final class CourseUpdater {
    private static final String TAG = "course-content";
    private static final int CONNECT_TIMEOUT_MS = 15000;
    private static final int READ_TIMEOUT_MS = 30000;
    private final AssetManager assets;
    private final File base;
    private final Object stateLock = new Object();
    private final Object downloadLock = new Object();

    public CourseUpdater(Context context) {
        Context app = context.getApplicationContext();
        assets = app.getAssets();
        base = new File(app.getFilesDir(), "course-content");
    }

    public interface ProgressListener { void onProgress(long downloaded, long total); }

    public static final class Asset implements java.io.Closeable {
        public final InputStream stream;
        public final long length;
        public final String mimeType;
        private Asset(InputStream stream, long length, String mimeType) {
            this.stream = stream; this.length = length; this.mimeType = mimeType;
        }
        @Override public void close() throws IOException { stream.close(); }
    }

    /** Keep one snapshot for a top-level WebView page, including all its later media requests. */
    public final class Snapshot {
        public final String version;
        public final String reminderTime;
        public final int reminderMinutes;
        private final File directory;
        private final CourseContentRules.Manifest manifest;
        private Snapshot(File directory, CourseContentRules.Manifest manifest) {
            this.directory = directory; this.manifest = manifest; this.version = manifest.version;
            this.reminderTime = manifest.reminderTime; this.reminderMinutes = manifest.reminderMinutes;
        }
        /** Relative courses.json or media/* only; null means this snapshot does not provide that file. */
        public Asset open(String relativePath) throws IOException {
            if (relativePath == null || !(relativePath.equals("courses.json") || relativePath.startsWith("media/"))) return null;
            String path = CourseContentRules.safePath(relativePath);
            CourseContentRules.FileSpec spec = manifest.files.get(path);
            if (spec == null) return null;
            InputStream stream;
            if (directory == null) {
                stream = assets.open("site/" + path, AssetManager.ACCESS_STREAMING);
            } else {
                File file = new File(directory, path);
                CourseContentRules.check(file.getCanonicalPath().startsWith(directory.getCanonicalPath() + File.separator)
                        && file.isFile() && file.length() == spec.size, "已安装的课程文件不可用，请重新下载课程包。");
                stream = new FileInputStream(file);
            }
            return new Asset(stream, spec.size, CourseContentRules.mimeType(path));
        }
    }

    public static final class ReleaseInfo {
        public final String version;
        public final String label;
        public final String notes;
        public final boolean requiresAppUpgrade;
        public final int minAppVersion;
        public final int courseCount;
        public final long archiveSize;
        private final String repository;
        private final CourseContentRules.Manifest manifest;
        private ReleaseInfo(String repository, CourseContentRules.Manifest manifest) {
            this.repository = repository; this.manifest = manifest; this.version = manifest.version;
            this.minAppVersion = manifest.minAppVersion; this.courseCount = manifest.courseCount;
            this.archiveSize = manifest.archiveSize;
            this.requiresAppUpgrade = minAppVersion > BuildConfig.VERSION_CODE;
            this.label = "课程版本 " + version.substring(0, 12);
            this.notes = requiresAppUpgrade ? "此课程包需要应用版本 " + minAppVersion + " 或更高版本，请先升级 APK。"
                    : "包含 " + courseCount + " 门课程；下载大小约 " + Math.max(1, (archiveSize + 1048575) / 1048576) + " MB。下载并校验后可刷新使用，学习记录保留。";
        }
    }

    /** Reads at most a small manifest. Returns null if the active course version is unchanged. */
    public ReleaseInfo check(String owner, String repo) throws IOException {
        String repository = CourseContentRules.repository(owner, repo);
        HttpURLConnection connection = null;
        try {
            connection = connect(downloadUrl(repository, "manifest.json"));
            long length = connection.getContentLengthLong();
            CourseContentRules.check(length <= CourseContentRules.MAX_MANIFEST_BYTES, "课程版本清单超过允许大小。");
            CourseContentRules.Manifest manifest;
            try (InputStream in = connection.getInputStream()) {
                manifest = CourseContentRules.manifest(CourseContentRules.readBounded(in, CourseContentRules.MAX_MANIFEST_BYTES));
            }
            ReleaseInfo result = new ReleaseInfo(repository, manifest);
            if (!result.requiresAppUpgrade && manifest.version.equals(currentVersion())) return null;
            return result;
        } catch (SocketTimeoutException ex) { throw new IOException("检查课程更新超时，请稍后重试；原有课程仍可使用。", ex); }
        catch (UnknownHostException ex) { throw new IOException("无法连接 GitHub，请检查网络后重试；原有课程仍可使用。", ex); }
        finally { if (connection != null) connection.disconnect(); }
    }

    /** Caller runs on its executor after a deliberate download action. No activation occurs on failure. */
    public void download(ReleaseInfo info, ProgressListener listener) throws IOException {
        CourseContentRules.check(info != null, "请先检查课程更新。");
        CourseContentRules.check(!info.requiresAppUpgrade && info.minAppVersion <= BuildConfig.VERSION_CODE,
                "此课程包需要升级 APK 后才能下载，请先更新应用。");
        synchronized (downloadLock) {
            CourseContentRules.interrupted();
            Snapshot previous = captureSnapshot();
            if (previous.version.equals(info.version)) return;
            File temporaryRoot = new File(base, "temporary");
            File versions = new File(base, "versions");
            ensureDirectory(temporaryRoot); ensureDirectory(versions);
            File work = new File(temporaryRoot, UUID.randomUUID().toString());
            ensureDirectory(work);
            File archive = new File(work, "download.zip");
            File stage = new File(work, "content");
            try {
                CourseContentRules.check(base.getUsableSpace() >= info.archiveSize + uncompressedSize(info.manifest) + 16L * 1024 * 1024,
                        "手机剩余空间不足，请先释放空间；已有课程和学习记录不会改变。");
                downloadArchive(info, archive, listener);
                byte[] previousCourses;
                try (Asset asset = previous.open("courses.json")) {
                    CourseContentRules.check(asset != null, "当前课程目录缺失，无法安全核对复习题。");
                    previousCourses = CourseContentRules.readBounded(asset.stream, CourseContentRules.MAX_COURSES_BYTES);
                }
                ensureDirectory(stage);
                CourseContentRules.extract(archive, stage, info.manifest, previousCourses);
                writeSynced(new File(stage, "_manifest.json"), info.manifest.bytes);
                CourseContentRules.interrupted();
                synchronized (stateLock) {
                    // The only mutable state is the pointer. Old directories remain valid for open pages.
                    CourseContentRules.check(captureSnapshot().version.equals(previous.version), "课程版本已改变，请重新检查更新。");
                    File target = new File(versions, info.version);
                    if (target.exists()) {
                        CourseContentRules.Manifest stored;
                        try (InputStream in = new FileInputStream(new File(target, "_manifest.json"))) {
                            stored = CourseContentRules.manifest(CourseContentRules.readBounded(in, CourseContentRules.MAX_MANIFEST_BYTES));
                        }
                        CourseContentRules.check(stored.version.equals(info.version) && stored.archiveHash.equals(info.manifest.archiveHash)
                                && stored.archiveSize == info.manifest.archiveSize, "同一课程版本对应不同内容，请发布新的课程版本。");
                        for (CourseContentRules.FileSpec file : info.manifest.files.values())
                            CourseContentRules.verifyFile(new File(target, file.path), file.size, file.sha256);
                    } else {
                        CourseContentRules.check(stage.renameTo(target), "无法保存已验证的课程，原有课程保持不变。");
                    }
                    activate(info.version);
                }
            } catch (SocketTimeoutException ex) { throw new IOException("课程下载超时，原有课程未改变，请稍后重试。", ex); }
            catch (UnknownHostException ex) { throw new IOException("无法连接 GitHub，原有课程未改变，请检查网络。", ex); }
            finally { deleteTemporary(work); }
        }
    }

    public Snapshot captureSnapshot() throws IOException {
        synchronized (stateLock) {
            AtomicFile pointer = new AtomicFile(new File(base, "active-version"));
            String version;
            try (InputStream in = pointer.openRead()) {
                version = CourseContentRules.utf8(CourseContentRules.readBounded(in, 80)).trim();
            } catch (FileNotFoundException missing) {
                if (pointer.getBaseFile().exists() || new File(base, "active-version.bak").exists())
                    throw new IOException("无法读取当前课程版本，请重新打开应用。", missing);
                try (InputStream in = assets.open("site/content-manifest.json")) {
                    return new Snapshot(null, CourseContentRules.manifest(CourseContentRules.readBounded(in, CourseContentRules.MAX_MANIFEST_BYTES)));
                }
            }
            CourseContentRules.check(version.matches("[0-9a-f]{64}"), "已安装的课程版本信息损坏，学习记录未修改。");
            File directory = new File(new File(base, "versions"), version);
            CourseContentRules.Manifest manifest;
            try (InputStream in = new FileInputStream(new File(directory, "_manifest.json"))) {
                manifest = CourseContentRules.manifest(CourseContentRules.readBounded(in, CourseContentRules.MAX_MANIFEST_BYTES));
            }
            CourseContentRules.check(version.equals(manifest.version), "已安装的课程版本与目录不一致。");
            return new Snapshot(directory, manifest);
        }
    }

    public String currentVersion() throws IOException { return captureSnapshot().version; }
    public InputStream readCurrentCourses() throws IOException {
        Asset asset = captureSnapshot().open("courses.json");
        if (asset == null) throw new IOException("当前课程目录缺失。");
        return asset.stream;
    }
    public Asset openActive(String relativePath) throws IOException { return captureSnapshot().open(relativePath); }

    private void downloadArchive(ReleaseInfo info, File target, ProgressListener listener) throws IOException {
        HttpURLConnection connection = null;
        try {
            connection = connect(downloadUrl(info.repository, info.manifest.archiveName));
            long length = connection.getContentLengthLong();
            CourseContentRules.check(length == -1 || length == info.archiveSize, "下载大小与版本清单不符，请重新检查更新。");
            long received = 0;
            if (listener != null) listener.onProgress(0, info.archiveSize);
            try (InputStream in = connection.getInputStream(); FileOutputStream out = new FileOutputStream(target)) {
                byte[] buffer = new byte[32768]; int n; long lastProgress = 0;
                while ((n = in.read(buffer)) != -1) {
                    CourseContentRules.interrupted();
                    received += n;
                    CourseContentRules.check(received <= info.archiveSize, "课程下载大小超过清单限制，已停止更新。");
                    out.write(buffer, 0, n);
                    long now = System.nanoTime();
                    if (listener != null && (now - lastProgress > 100000000L || received == info.archiveSize)) {
                        listener.onProgress(received, info.archiveSize); lastProgress = now;
                    }
                }
                out.getFD().sync();
            }
            CourseContentRules.check(received == info.archiveSize, "课程下载不完整，请重新下载。");
        } finally { if (connection != null) connection.disconnect(); }
    }

    private static URI downloadUrl(String repository, String name) {
        return URI.create("https://github.com/" + repository + "/releases/download/" + TAG + "/" + name);
    }

    /** Redirects are explicit: credentials, HTTP, arbitrary hosts, and redirect loops are rejected. */
    private static HttpURLConnection connect(URI first) throws IOException {
        URI current = first;
        for (int redirect = 0; redirect <= 5; redirect++) {
            CourseContentRules.interrupted(); CourseContentRules.githubUrl(current);
            HttpURLConnection connection = (HttpURLConnection) current.toURL().openConnection();
            connection.setInstanceFollowRedirects(false);
            connection.setConnectTimeout(CONNECT_TIMEOUT_MS); connection.setReadTimeout(READ_TIMEOUT_MS);
            connection.setUseCaches(false); connection.setRequestMethod("GET");
            connection.setRequestProperty("Accept", "application/octet-stream");
            connection.setRequestProperty("Accept-Encoding", "identity");
            connection.setRequestProperty("Cache-Control", "no-cache");
            connection.setRequestProperty("User-Agent", "LearningLoop-Android/" + BuildConfig.VERSION_CODE);
            try {
                int status = connection.getResponseCode();
                if (status == 200) {
                    String encoding = connection.getContentEncoding();
                    CourseContentRules.check(encoding == null || encoding.equalsIgnoreCase("identity"), "下载服务器返回了不支持的内容编码。");
                    return connection;
                }
                if (status == 301 || status == 302 || status == 303 || status == 307 || status == 308) {
                    String location = connection.getHeaderField("Location");
                    CourseContentRules.check(location != null && location.length() <= 8192, "GitHub 下载跳转无效。");
                    try { current = current.resolve(location); }
                    catch (IllegalArgumentException ex) { throw new IOException("GitHub 下载跳转地址无效。", ex); }
                    CourseContentRules.githubUrl(current);
                } else if (status == 404) {
                    throw new IOException("没有找到课程发布包。请确认公开仓库已发布 course-content 版本和 manifest.json。");
                } else if (status == 403 || status == 429) {
                    throw new IOException("GitHub 暂时限制了请求，请稍后重试。本版本只支持无需登录的公开仓库。");
                } else {
                    throw new IOException("GitHub 下载暂不可用（HTTP " + status + "），请稍后重试。");
                }
            } catch (IOException | RuntimeException ex) { connection.disconnect(); throw ex; }
            connection.disconnect();
        }
        throw new IOException("GitHub 下载跳转次数过多，已停止更新。");
    }

    private void activate(String version) throws IOException {
        AtomicFile pointer = new AtomicFile(new File(base, "active-version"));
        FileOutputStream out = null;
        try {
            out = pointer.startWrite(); out.write((version + "\n").getBytes(StandardCharsets.UTF_8)); out.getFD().sync();
            pointer.finishWrite(out); out = null;
            // Some Android AtomicFile implementations only log a failed final rename.
            // Confirm the durable pointer before telling the UI that the update succeeded.
            try (InputStream in = pointer.openRead()) {
                String saved = CourseContentRules.utf8(CourseContentRules.readBounded(in, 80)).trim();
                CourseContentRules.check(version.equals(saved), "课程已下载，但无法切换当前版本；请重新尝试更新。");
            }
        } finally { if (out != null) pointer.failWrite(out); }
    }
    private static long uncompressedSize(CourseContentRules.Manifest manifest) {
        long total = 0; for (CourseContentRules.FileSpec spec : manifest.files.values()) total += spec.size; return total;
    }
    private static void ensureDirectory(File directory) throws IOException {
        CourseContentRules.check(directory.isDirectory() || directory.mkdirs(), "无法创建课程存储目录。");
    }
    private static void writeSynced(File target, byte[] bytes) throws IOException {
        try (FileOutputStream out = new FileOutputStream(target)) { out.write(bytes); out.getFD().sync(); }
    }
    private static void deleteTemporary(File file) {
        File[] children = file.listFiles();
        if (children != null) for (File child : children) deleteTemporary(child);
        // Cleanup failure never replaces a successful activation with an error, and never touches versions.
        if (file.exists()) file.delete();
    }
}
