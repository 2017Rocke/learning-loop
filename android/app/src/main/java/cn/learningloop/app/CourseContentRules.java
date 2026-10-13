package cn.learningloop.app;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.math.BigDecimal;
import java.net.URI;
import java.nio.ByteBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.Enumeration;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;
import javax.xml.parsers.DocumentBuilderFactory;
import org.w3c.dom.NamedNodeMap;
import org.w3c.dom.Node;
import org.xml.sax.InputSource;

/** Data-only course package validation. No Android, network, or learner-state access. */
public final class CourseContentRules {
    public static final long MAX_PACKAGE_BYTES = 512L * 1024 * 1024;
    public static final int MAX_MANIFEST_BYTES = 2 * 1024 * 1024;
    public static final int MAX_COURSES_BYTES = 8 * 1024 * 1024;
    public static final int MAX_FILES = 4096;
    private static final Set<String> SUFFIXES = set("svg", "png", "jpg", "jpeg", "webp", "m4a", "mp3", "wav", "mp4", "webm", "vtt");
    private static final Set<String> HOSTS = set("github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com", "github-releases.githubusercontent.com");

    private CourseContentRules() { }

    public static final class FileSpec {
        public final String path, sha256;
        public final long size;
        FileSpec(String path, String sha256, long size) { this.path = path; this.sha256 = sha256; this.size = size; }
    }
    public static final class Manifest {
        public final String version, archiveName, archiveHash, reminderTime;
        public final long archiveSize;
        public final int minAppVersion, courseCount, reminderMinutes;
        public final Map<String, FileSpec> files;
        public final byte[] bytes;
        private Manifest(String version, String name, String hash, long size, int min, int count,
                         String time, int minutes, Map<String, FileSpec> files, byte[] bytes) {
            this.version = version; this.archiveName = name; this.archiveHash = hash; this.archiveSize = size;
            this.minAppVersion = min; this.courseCount = count; this.reminderTime = time;
            this.reminderMinutes = minutes; this.files = Collections.unmodifiableMap(files); this.bytes = bytes.clone();
        }
    }
    public static final class Catalog {
        public final Map<String, Set<String>> questions;
        public final Set<String> media;
        Catalog(Map<String, Set<String>> questions, Set<String> media) { this.questions = questions; this.media = media; }
    }

    public static Manifest manifest(byte[] bytes) throws IOException {
        check(bytes.length > 0 && bytes.length <= MAX_MANIFEST_BYTES, "课程版本清单过大或为空。");
        Map<String, Object> root = object(ContentJson.parse(utf8(bytes)), "版本清单");
        keys(root, "schema_version", "version", "min_app_version", "archive", "files", "course_count", "reminder");
        number(root.get("schema_version"), 1, 1, "版本清单格式");
        String version = hash(root.get("version"));
        int min = (int) number(root.get("min_app_version"), 1, Integer.MAX_VALUE, "最低应用版本");
        int count = (int) number(root.get("course_count"), 1, 1000, "课程数量");
        Map<String, Object> archive = object(root.get("archive"), "压缩包");
        keys(archive, "name", "sha256", "size");
        String name = text(archive.get("name"), 100, "压缩包名称");
        check(name.equals("courses-" + version + ".zip"), "压缩包名称与课程版本不一致。");
        String archiveHash = hash(archive.get("sha256"));
        long archiveSize = number(archive.get("size"), 1, MAX_PACKAGE_BYTES, "课程下载大小");
        Map<String, Object> reminder = object(root.get("reminder"), "复习建议");
        keys(reminder, "time", "minutes");
        String time = text(reminder.get("time"), 5, "复习时间");
        check(time.matches("(?:[01][0-9]|2[0-3]):[0-5][0-9]"), "复习时间格式不正确。");
        int minutes = (int) number(reminder.get("minutes"), 1, 60, "复习分钟数");
        List<Object> entries = list(root.get("files"), 1, MAX_FILES, "课程文件列表");
        Map<String, FileSpec> files = new LinkedHashMap<>();
        Set<String> folded = new HashSet<>();
        long total = 0;
        for (Object entry : entries) {
            Map<String, Object> item = object(entry, "课程文件");
            keys(item, "path", "sha256", "size");
            String path = safePath(text(item.get("path"), 500, "课程文件路径"));
            check(folded.add(path.toLowerCase(Locale.ROOT)), "课程包存在重复文件路径。");
            long size = number(item.get("size"), 1, path.equals("courses.json") ? MAX_COURSES_BYTES : MAX_PACKAGE_BYTES, "课程文件大小");
            total += size;
            check(total <= MAX_PACKAGE_BYTES, "课程解压总大小超过 512 MB。");
            files.put(path, new FileSpec(path, hash(item.get("sha256")), size));
        }
        check(files.containsKey("courses.json"), "课程包缺少 courses.json。");
        return new Manifest(version, name, archiveHash, archiveSize, min, count, time, minutes, files, bytes);
    }

    public static String safePath(String path) throws IOException {
        check(path != null && path.length() <= 500 && !path.startsWith("/") && !path.contains("\\") && !path.contains("%")
                && !path.contains(":") && !path.contains("?") && !path.contains("#"), "课程文件路径不安全。");
        for (String segment : path.split("/", -1))
            check(segment.matches("[A-Za-z0-9_-][A-Za-z0-9._-]*") && !segment.equals(".") && !segment.equals(".."), "课程文件路径不安全。");
        if (path.equals("courses.json")) return path;
        int dot = path.lastIndexOf('.');
        check(path.startsWith("media/") && dot >= 0 && SUFFIXES.contains(path.substring(dot + 1)), "课程包只允许课程数据、图片、音视频和字幕。");
        return path;
    }

    public static void githubUrl(URI uri) throws IOException {
        check(uri != null && "https".equalsIgnoreCase(uri.getScheme()) && uri.getHost() != null
                && HOSTS.contains(uri.getHost().toLowerCase(Locale.ROOT)) && uri.getUserInfo() == null
                && (uri.getPort() == -1 || uri.getPort() == 443) && uri.getFragment() == null, "更新地址必须是允许的 GitHub HTTPS 下载地址。");
    }

    public static String repository(String owner, String repo) throws IOException {
        check(owner != null && owner.matches("[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?")
                && repo != null && repo.matches("[A-Za-z0-9_.-]{1,100}") && !repo.equals(".") && !repo.equals(".."),
                "请填写公开 GitHub 仓库的拥有者和仓库名，不要填写网址或令牌。");
        return owner + "/" + repo;
    }

    /** Extract only a complete, bounded, verified data package into an empty private directory. */
    public static Catalog extract(File archive, File stage, Manifest manifest, byte[] previousCourses) throws IOException {
        verifyFile(archive, manifest.archiveSize, manifest.archiveHash);
        check(stage.isDirectory() && stage.list() != null && stage.list().length == 0, "课程临时目录必须为空。");
        Set<String> seen = new HashSet<>();
        long total = 0;
        try (ZipFile zip = new ZipFile(archive)) {
            check(zip.size() == manifest.files.size() && zip.size() <= MAX_FILES, "压缩包文件数量与版本清单不一致。");
            Enumeration<? extends ZipEntry> entries = zip.entries();
            while (entries.hasMoreElements()) {
                ZipEntry entry = entries.nextElement();
                String path = safePath(entry.getName());
                check(!entry.isDirectory() && seen.add(path), "压缩包含目录项或重复文件。");
                FileSpec spec = manifest.files.get(path);
                check(spec != null && entry.getSize() == spec.size, "压缩包文件大小或名称与版本清单不一致。");
                total += spec.size;
                check(total <= MAX_PACKAGE_BYTES, "课程解压总大小超过 512 MB。");
                File target = new File(stage, path);
                check(target.getCanonicalPath().startsWith(stage.getCanonicalPath() + File.separator), "课程文件越过临时目录。");
                File parent = target.getParentFile();
                check(parent.isDirectory() || parent.mkdirs(), "无法创建课程文件目录。");
                MessageDigest digest = sha256();
                long written = 0;
                try (InputStream in = zip.getInputStream(entry); FileOutputStream out = new FileOutputStream(target)) {
                    byte[] buffer = new byte[32768];
                    int n;
                    while ((n = in.read(buffer)) != -1) {
                        interrupted();
                        written += n;
                        check(written <= spec.size, "压缩包解压大小超过清单限制。");
                        digest.update(buffer, 0, n); out.write(buffer, 0, n);
                    }
                    out.getFD().sync();
                }
                check(written == spec.size && hex(digest.digest()).equals(spec.sha256), "课程文件校验失败：" + path);
                if (path.endsWith(".svg")) validateSvg(target);
            }
        }
        check(seen.equals(manifest.files.keySet()), "课程包文件不完整。");
        byte[] courses;
        try (InputStream in = new FileInputStream(new File(stage, "courses.json"))) { courses = readBounded(in, MAX_COURSES_BYTES); }
        Catalog next = catalog(courses, manifest);
        if (previousCourses != null) compatible(catalog(previousCourses, null), next);
        return next;
    }

    public static Catalog catalog(byte[] bytes, Manifest manifest) throws IOException {
        check(bytes.length > 0 && bytes.length <= MAX_COURSES_BYTES, "课程数据过大或为空。");
        Map<String, Object> root = object(ContentJson.parse(utf8(bytes)), "课程目录");
        keys(root, "schema_version", "courses");
        number(root.get("schema_version"), 1, 1, "课程格式");
        List<Object> courses = list(root.get("courses"), 1, 1000, "课程");
        if (manifest != null) check(courses.size() == manifest.courseCount, "课程数量与版本清单不一致。");
        Map<String, Set<String>> questions = new LinkedHashMap<>();
        Set<String> media = new LinkedHashSet<>();
        Set<String> topics = new HashSet<>();
        for (Object raw : courses) {
            Map<String, Object> course = object(raw, "课程");
            keys(course, "id", "title", "topic_id", "subject", "kind", "repo_full_name", "repo_url", "lesson");
            String id = stableId(course.get("id"), "课程 ID");
            check(!questions.containsKey(id), "课程 ID 重复。");
            check(topics.add(stableId(course.get("topic_id"), "主题 ID")), "课程主题重复。");
            text(course.get("title"), 200, "课程标题"); text(course.get("subject"), 100, "学科");
            check(set("project", "subject").contains(course.get("kind")), "课程类型不支持。");
            String repo = optionalText(course.get("repo_url"), 1000, "项目链接");
            optionalText(course.get("repo_full_name"), 200, "项目名称");
            if (!repo.isEmpty()) webUrl(repo);
            questions.put(id, lesson(object(course.get("lesson"), "学习包"), media));
        }
        if (manifest != null) for (String path : media) check(manifest.files.containsKey(path), "课程缺少引用媒体：" + path);
        return new Catalog(Collections.unmodifiableMap(questions), Collections.unmodifiableSet(media));
    }

    public static void compatible(Catalog old, Catalog next) throws IOException {
        for (Map.Entry<String, Set<String>> item : old.questions.entrySet()) {
            Set<String> ids = next.questions.get(item.getKey());
            check(ids != null && ids.containsAll(item.getValue()), "新课程包移除了已有课程或复习题（" + item.getKey() + "）。为保留学习记录，本次更新未启用；请发布保留原有 ID 的完整课程包。");
        }
    }

    private static Set<String> lesson(Map<String, Object> lesson, Set<String> media) throws IOException {
        Set<String> required = set("summary", "mental_model", "core_ideas", "source_refs", "questions", "case_study", "code_insight", "experiment", "application", "recap_prompts");
        check(lesson.keySet().containsAll(required) && union(required, set("visual_lesson", "audio_lesson")).containsAll(lesson.keySet()), "学习包字段不完整或含未支持内容。");
        text(lesson.get("summary"), 20000, "概述"); text(lesson.get("mental_model"), 20000, "核心思维");
        for (Object raw : list(lesson.get("core_ideas"), 1, 100, "核心概念")) {
            Map<String, Object> idea = object(raw, "核心概念"); text(idea.get("title"), 20000, "概念标题"); text(idea.get("explanation"), 20000, "概念说明");
        }
        for (Object raw : list(lesson.get("source_refs"), 1, 100, "参考资料")) {
            Map<String, Object> ref = object(raw, "参考资料"); text(ref.get("title"), 20000, "资料标题"); webUrl(text(ref.get("url"), 2000, "资料链接"));
        }
        Set<String> ids = new HashSet<>();
        for (Object raw : list(lesson.get("questions"), 1, 1000, "复习题")) {
            Map<String, Object> q = object(raw, "复习题");
            check(ids.add(stableId(q.get("id"), "复习题 ID")), "复习题 ID 重复。");
            text(q.get("prompt"), 20000, "复习问题"); text(q.get("answer"), 20000, "参考答案");
        }
        Map<String, Object> example = object(lesson.get("case_study"), "学习案例");
        text(example.get("title"), 20000, "案例标题"); text(example.get("scenario"), 20000, "案例背景"); textList(example.get("steps"), "案例步骤");
        Map<String, Object> experiment = object(lesson.get("experiment"), "小实验");
        text(experiment.get("title"), 20000, "实验标题"); textList(experiment.get("steps"), "实验步骤"); textList(experiment.get("acceptance"), "实验检查");
        Map<String, Object> application = object(lesson.get("application"), "实际应用");
        text(application.get("prompt"), 20000, "应用任务"); textList(application.get("acceptance"), "应用检查"); textList(lesson.get("recap_prompts"), "回忆提示");
        Set<String> walkthroughs = new HashSet<>();
        if (lesson.get("code_insight") != null) {
            Map<String, Object> code = object(lesson.get("code_insight"), "代码思想");
            for (String key : Arrays.asList("title", "explanation", "snippet", "language")) text(code.get(key), 20000, "代码" + key);
            webUrl(text(code.get("source_url"), 2000, "代码来源"));
            if (code.containsKey("walkthroughs")) for (Object raw : list(code.get("walkthroughs"), 1, 8, "代码片段")) {
                Map<String, Object> part = object(raw, "代码片段");
                check(walkthroughs.add(stableId(part.get("id"), "代码片段 ID")), "代码片段 ID 重复。");
                for (String key : Arrays.asList("title", "language", "snippet")) text(part.get(key), 20000, "代码片段" + key);
                String source = text(part.get("source_url"), 2000, "片段来源"); webUrl(source);
                if ("source".equals(part.get("kind"))) {
                    String commit = text(part.get("source_commit"), 40, "源码版本");
                    check(commit.matches("[a-fA-F0-9]{40}"), "真实源码需要固定完整提交版本。");
                    String path = text(part.get("source_path"), 500, "源码路径");
                    check(!path.startsWith("/") && !path.contains("\\") && !Arrays.asList(path.split("/", -1)).contains(".."), "源码路径不正确。");
                    number(part.get("source_start_line"), 1, 10000000, "源码行号");
                    check(source.contains("/" + commit + "/") && source.endsWith("/" + path), "源码链接与固定版本不一致。");
                } else check("pseudocode".equals(part.get("kind")) && part.get("source_path") == null && part.get("source_commit") == null && part.get("source_start_line") == null, "代码片段类型不正确。");
                String[] lines = ((String) part.get("snippet")).split("\n", -1);
                check(lines.length <= 80, "代码片段超过 80 行。");
                List<Object> notes = list(part.get("notes"), 1, 80, "逐行讲解");
                int n = 0;
                for (int i = 0; i < lines.length; i++) if (!lines[i].trim().isEmpty()) {
                    check(n < notes.size(), "源码缺少逐行解释。");
                    Map<String, Object> note = object(notes.get(n++), "逐行解释");
                    number(note.get("line"), i + 1, i + 1, "解释行号");
                    text(note.get("comment"), 700, "行解释"); text(note.get("why"), 1000, "行原因");
                }
                check(n == notes.size(), "逐行解释与源码行不一致。");
            }
        }
        if (lesson.containsKey("visual_lesson")) visual(object(lesson.get("visual_lesson"), "图解课程"), media);
        if (lesson.containsKey("audio_lesson")) {
            Map<String, Object> audio = object(lesson.get("audio_lesson"), "语音课程");
            keys(audio, "voice", "clips"); text(audio.get("voice"), 200, "配音来源");
            Set<String> clips = new HashSet<>();
            for (Object raw : list(audio.get("clips"), 1, 16, "语音片段")) {
                Map<String, Object> clip = object(raw, "语音片段");
                keys(clip, "chapter", "walkthrough_id", "title", "src", "duration_seconds", "transcript");
                String chapter = text(clip.get("chapter"), 30, "语音章节");
                check(set("logic", "case", "code", "experiment", "application", "summary").contains(chapter), "语音章节不支持。");
                Object part = clip.get("walkthrough_id");
                check(part == null || ("code".equals(chapter) && walkthroughs.contains(part)), "语音引用了不存在的代码片段。");
                check(clips.add(chapter + "/" + part), "语音片段重复。");
                text(clip.get("title"), 200, "语音标题"); text(clip.get("transcript"), 12000, "语音文字");
                decimal(clip.get("duration_seconds"), 1, 1800, "语音时长");
                media(clip.get("src"), media, set("m4a", "mp3", "wav"));
            }
        }
        return Collections.unmodifiableSet(ids);
    }

    private static void visual(Map<String, Object> visual, Set<String> media) throws IOException {
        keys(visual, "hook", "duration_minutes", "video", "steps", "interactive", "takeaways", "watch_more");
        text(visual.get("hook"), 200, "学习目标"); number(visual.get("duration_minutes"), 1, 60, "图解时长");
        Set<String> ids = new HashSet<>();
        for (Object raw : list(visual.get("steps"), 1, 8, "图解步骤")) {
            Map<String, Object> step = object(raw, "图解步骤");
            keys(step, "id", "title", "caption", "image", "alt", "question");
            check(ids.add(stableId(step.get("id"), "图解 ID")), "图解 ID 重复。");
            text(step.get("title"), 100, "图解标题"); text(step.get("caption"), 400, "图解结论"); text(step.get("alt"), 500, "图像说明");
            media(step.get("image"), media, set("svg", "png", "jpg", "jpeg", "webp"));
            Map<String, Object> q = object(step.get("question"), "预测题");
            keys(q, "prompt", "options", "correct_index", "explanation");
            text(q.get("prompt"), 300, "预测题"); text(q.get("explanation"), 700, "预测解释");
            List<Object> options = list(q.get("options"), 2, 4, "预测选项");
            for (Object option : options) text(option, 200, "选项"); number(q.get("correct_index"), 0, options.size() - 1, "预测答案");
        }
        if (visual.get("video") != null) {
            Map<String, Object> video = object(visual.get("video"), "视频");
            keys(video, "src", "poster", "captions", "title", "duration_seconds", "attribution", "transcript");
            media(video.get("src"), media, set("mp4", "webm")); media(video.get("poster"), media, set("svg", "png", "jpg", "jpeg")); media(video.get("captions"), media, set("vtt"));
            text(video.get("title"), 200, "视频标题"); text(video.get("attribution"), 500, "视频来源");
            double duration = decimal(video.get("duration_seconds"), 1, 600, "视频时长"); double previous = -1;
            for (Object raw : list(video.get("transcript"), 1, 1000, "视频文字")) {
                Map<String, Object> line = object(raw, "视频文字"); keys(line, "time", "text");
                double time = decimal(line.get("time"), 0, duration, "视频章节时间");
                check(time > previous && time < duration, "视频章节时间必须递增且位于时长以内。"); previous = time; text(line.get("text"), 1000, "视频文字");
            }
        }
        if (visual.get("interactive") != null) {
            Map<String, Object> interactive = object(visual.get("interactive"), "交互演示");
            boolean voice = "voice-ab".equals(interactive.get("kind"));
            if (voice) keys(interactive, "kind", "title", "prompt", "samples");
            else keys(interactive, "kind", "title", "prompt");
            check(set("gaussian-viewer", "bayes-counts", "voice-ab").contains(interactive.get("kind")), "此演示需要升级应用后使用。");
            text(interactive.get("title"), 100, "演示标题"); text(interactive.get("prompt"), 400, "演示提示");
            if (voice) for (Object raw : list(interactive.get("samples"), 2, 2, "听辨样例")) {
                Map<String, Object> sample = object(raw, "听辨样例"); keys(sample, "label", "src", "transcript", "duration_seconds");
                text(sample.get("label"), 100, "听辨名称"); text(sample.get("transcript"), 1000, "听辨原文");
                decimal(sample.get("duration_seconds"), 1, 300, "听辨时长");
                media(sample.get("src"), media, set("mp3", "m4a", "wav"));
            }
        }
        for (Object item : list(visual.get("takeaways"), 1, 5, "课后结论")) text(item, 200, "结论");
        for (Object raw : list(visual.get("watch_more"), 0, 100, "延伸资料")) {
            Map<String, Object> item = object(raw, "延伸资料"); keys(item, "title", "url", "description");
            text(item.get("title"), 200, "延伸标题"); text(item.get("description"), 400, "观看目的"); webUrl(text(item.get("url"), 2000, "延伸链接"));
        }
    }

    private static void media(Object value, Set<String> paths, Set<String> suffixes) throws IOException {
        String path = text(value, 500, "教学媒体路径");
        check(path.startsWith("/media/"), "教学媒体必须引用课程包中的 /media/ 文件。");
        path = safePath(path.substring(1));
        check(suffixes.contains(path.substring(path.lastIndexOf('.') + 1)), "教学媒体格式不正确。"); paths.add(path);
    }

    /** SVG is served only as an image; also reject scripts, embedded documents and external fetches. */
    private static void validateSvg(File file) throws IOException {
        byte[] bytes;
        try (InputStream in = new FileInputStream(file)) { bytes = readBounded(in, MAX_COURSES_BYTES); }
        String xml = utf8(bytes);
        String lower = xml.toLowerCase(Locale.ROOT);
        check(!lower.contains("<!doctype") && !lower.contains("<!entity"), "SVG 图像不能包含外部实体或文档定义。");
        try {
            DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
            factory.setNamespaceAware(true); factory.setExpandEntityReferences(false);
            javax.xml.parsers.DocumentBuilder builder = factory.newDocumentBuilder();
            builder.setEntityResolver((publicId, systemId) -> { throw new org.xml.sax.SAXException("禁止外部实体"); });
            builder.setErrorHandler(new org.xml.sax.helpers.DefaultHandler() {
                @Override public void error(org.xml.sax.SAXParseException e) throws org.xml.sax.SAXException { throw e; }
                @Override public void fatalError(org.xml.sax.SAXParseException e) throws org.xml.sax.SAXException { throw e; }
            });
            org.w3c.dom.Document doc = builder.parse(new InputSource(new java.io.StringReader(xml)));
            check("svg".equals(doc.getDocumentElement().getLocalName()), "SVG 根元素不正确。");
            svgNode(doc, 0, new int[]{0});
        } catch (IOException ex) { throw ex; }
        catch (Exception ex) { throw new IOException("SVG 图像格式不安全或无法解析。", ex); }
    }

    private static void svgNode(Node node, int depth, int[] count) throws IOException {
        check(depth <= 64 && ++count[0] <= 50000, "SVG 图像结构过于复杂。");
        check(node.getNodeType() != Node.PROCESSING_INSTRUCTION_NODE && node.getNodeType() != Node.ENTITY_REFERENCE_NODE && node.getNodeType() != Node.DOCUMENT_TYPE_NODE, "SVG 含不允许的动态内容。");
        if (node.getNodeType() == Node.ELEMENT_NODE) {
            check("http://www.w3.org/2000/svg".equals(node.getNamespaceURI()) && set("svg", "g", "defs", "rect", "circle", "ellipse", "path", "line", "polyline", "polygon", "text", "tspan", "title", "desc", "linearGradient", "radialGradient", "stop", "clipPath", "mask", "marker", "use").contains(node.getLocalName()), "SVG 只允许静态图形，不能包含脚本或网页。");
            NamedNodeMap attrs = node.getAttributes();
            for (int i = 0; i < attrs.getLength(); i++) {
                Node attribute = attrs.item(i);
                String name = attribute.getNodeName().toLowerCase(Locale.ROOT), value = attribute.getNodeValue();
                check(!name.startsWith("on") && !name.equals("style") && !name.equals("xml:base"), "SVG 含动态属性或样式。");
                if (name.equals("href") || name.endsWith(":href")) check(value.matches("#[A-Za-z0-9_.-]+"), "SVG 不能链接外部内容。");
                if (value.toLowerCase(Locale.ROOT).contains("url")) check(value.matches("url\\(#[A-Za-z0-9_.-]+\\)"), "SVG 只能引用包内图形定义。");
            }
        }
        for (Node child = node.getFirstChild(); child != null; child = child.getNextSibling()) svgNode(child, depth + 1, count);
    }

    public static void verifyFile(File file, long size, String hash) throws IOException {
        check(file.isFile() && file.length() == size, "课程压缩包大小不正确，请重新下载。");
        MessageDigest digest = sha256();
        try (InputStream in = new FileInputStream(file)) {
            byte[] buf = new byte[32768]; int n;
            while ((n = in.read(buf)) != -1) { interrupted(); digest.update(buf, 0, n); }
        }
        check(hex(digest.digest()).equals(hash), "课程压缩包校验失败，请重新下载。");
    }
    public static byte[] readBounded(InputStream in, long max) throws IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream(); byte[] buf = new byte[16384]; int n; long count = 0;
        while ((n = in.read(buf)) != -1) { interrupted(); count += n; check(count <= max, "下载或读取内容超过允许大小。"); out.write(buf, 0, n); }
        return out.toByteArray();
    }
    public static String utf8(byte[] bytes) throws IOException {
        try { return StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT).onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(bytes)).toString(); }
        catch (CharacterCodingException ex) { throw new IOException("课程文件必须使用有效 UTF-8 编码。", ex); }
    }
    public static MessageDigest sha256() { try { return MessageDigest.getInstance("SHA-256"); } catch (NoSuchAlgorithmException ex) { throw new AssertionError(ex); } }
    public static String hex(byte[] digest) { StringBuilder out = new StringBuilder(); for (byte b : digest) out.append(String.format(Locale.ROOT, "%02x", b & 255)); return out.toString(); }
    public static String mimeType(String path) {
        if (path.equals("courses.json")) return "application/json";
        switch (path.substring(path.lastIndexOf('.') + 1)) {
            case "svg": return "image/svg+xml"; case "png": return "image/png"; case "jpg": case "jpeg": return "image/jpeg"; case "webp": return "image/webp";
            case "m4a": return "audio/mp4"; case "mp3": return "audio/mpeg"; case "wav": return "audio/wav";
            case "mp4": return "video/mp4"; case "webm": return "video/webm"; case "vtt": return "text/vtt"; default: return "application/octet-stream";
        }
    }
    static void interrupted() throws IOException { if (Thread.currentThread().isInterrupted()) throw new IOException("课程更新已取消，原有课程仍可使用。"); }
    static void check(boolean value, String message) throws IOException { if (!value) throw new IOException(message); }
    @SuppressWarnings("unchecked") static Map<String, Object> object(Object value, String name) throws IOException { check(value instanceof Map, name + "必须是对象。"); return (Map<String, Object>) value; }
    @SuppressWarnings("unchecked") static List<Object> list(Object value, int min, int max, String name) throws IOException { check(value instanceof List, name + "必须是列表。"); List<Object> result = (List<Object>) value; check(result.size() >= min && result.size() <= max, name + "数量超出允许范围。"); return result; }
    static String text(Object value, int max, String name) throws IOException { String result = optionalText(value, max, name); check(!result.trim().isEmpty(), name + "不能为空。"); return result; }
    static String optionalText(Object value, int max, String name) throws IOException { check(value instanceof String, name + "必须是文字。"); String text = (String) value; check(text.length() <= max && text.indexOf(0) < 0, name + "过长或含无效字符。"); return text; }
    static String stableId(Object value, String name) throws IOException {
        String id = text(value, 200, name);
        for (int i = 0; i < id.length(); i++) { char c = id.charAt(i); check(c >= 0x20 && (c < 0x7f || c > 0x9f), name + "含控制字符。"); }
        return id;
    }
    static void textList(Object value, String name) throws IOException { for (Object text : list(value, 1, 100, name)) text(text, 20000, name); }
    static long number(Object value, long min, long max, String name) throws IOException { check(value instanceof BigDecimal, name + "必须是整数。"); try { long n = ((BigDecimal) value).longValueExact(); check(n >= min && n <= max, name + "超出允许范围。"); return n; } catch (ArithmeticException ex) { throw new IOException(name + "必须是允许范围内的整数。", ex); } }
    static double decimal(Object value, double min, double max, String name) throws IOException { check(value instanceof BigDecimal, name + "必须是数字。"); double n = ((BigDecimal) value).doubleValue(); check(!Double.isNaN(n) && !Double.isInfinite(n) && n >= min && n <= max, name + "超出允许范围。"); return n; }
    static String hash(Object value) throws IOException { String hash = text(value, 64, "校验码"); check(hash.matches("[0-9a-f]{64}"), "校验码必须是 64 位小写 SHA-256。"); return hash; }
    static void keys(Map<String, Object> map, String... keys) throws IOException { check(map.keySet().equals(set(keys)), "课程数据字段缺失或包含不支持字段。"); }
    static Set<String> set(String... values) { return new HashSet<>(Arrays.asList(values)); }
    static Set<String> union(Set<String> a, Set<String> b) { Set<String> result = new HashSet<>(a); result.addAll(b); return result; }
    static void webUrl(String text) throws IOException { try { URI uri = new URI(text); check(("https".equalsIgnoreCase(uri.getScheme()) || "http".equalsIgnoreCase(uri.getScheme())) && uri.getHost() != null && uri.getUserInfo() == null, "参考资料必须使用有效网页链接。"); } catch (java.net.URISyntaxException ex) { throw new IOException("参考资料链接无效。", ex); } }
}
