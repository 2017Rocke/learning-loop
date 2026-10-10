package cn.learningloop.app;

import java.io.ByteArrayInputStream;
import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

/** Run with javac/java; uses temporary fixtures, no Android SDK, network, or learner data. */
public final class CourseContentRulesTest {
    private static int assertions;
    private static final String VERSION = repeat("a", 64);
    private static final String SVG = "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"100\" height=\"100\"><circle cx=\"50\" cy=\"50\" r=\"20\"/></svg>";
    interface Attempt { void run() throws Exception; }

    public static void main(String[] args) throws Exception {
        jsonChecks(); pathAndNetworkChecks(); catalogChecks(); packageChecks();
        if (args.length > 0) {
            byte[] actual = Files.readAllBytes(new File(args[0]).toPath());
            truth(CourseContentRules.catalog(actual, null).questions.size() >= 2, "real public course catalog validates");
        }
        if (args.length > 2) {
            CourseContentRules.Manifest manifest = CourseContentRules.manifest(Files.readAllBytes(new File(args[1]).toPath()));
            Path stage = Files.createTempDirectory("learning-loop-real-course-");
            try {
                byte[] old = Files.readAllBytes(new File(args[0]).toPath());
                CourseContentRules.Catalog catalog = CourseContentRules.extract(new File(args[2]), stage.toFile(), manifest, old);
                truth(catalog.questions.size() == manifest.courseCount, "real release archive verifies and preserves old questions");
            } finally { remove(stage.toFile()); }
        }
        System.out.println("CourseContentRules: " + assertions + " checks passed (no network, temporary files only).");
    }

    private static void jsonChecks() throws Exception {
        truth(ContentJson.parse("{\"x\":[null,true,false,-12.5e2,\"汉字\\ud83d\\ude42\"]}") instanceof Map, "strict JSON accepts valid Unicode and numbers");
        for (String invalid : Arrays.asList("{\"a\":1,\"a\":2}", "{\"a\":{\"x\":null,\"x\":1}}", "[1,]", "{\"a\":1,}", "01", "1.", "1e", "+2", "NaN", "true junk", "\"\\uD800\"", "\"line\nbreak\""))
            rejects(() -> ContentJson.parse(invalid), "reject malformed JSON " + invalid.replace('\n', ' '));
        rejects(() -> ContentJson.parse(repeat("[", 60) + "0" + repeat("]", 60)), "bounded JSON nesting");
        rejects(() -> CourseContentRules.utf8(new byte[]{(byte) 0xc3, 0x28}), "strict UTF-8");
        rejects(() -> CourseContentRules.readBounded(new ByteArrayInputStream(new byte[101]), 100), "bounded stream");
    }

    private static void pathAndNetworkChecks() throws Exception {
        truth(CourseContentRules.safePath("courses.json").equals("courses.json"), "catalog path");
        truth(CourseContentRules.safePath("media/topic/audio-v2.m4a").endsWith("m4a"), "media path");
        for (String path : Arrays.asList("../courses.json", "/media/a.png", "media/../a.png", "media/./a.png", "media//a.png", "media/%2e%2e/a.png", "media\\a.png", "media/a.js", "media/a.html", "media/a.json", "media/a.SVG", "media/a.svg?x", "media/a.svg#x", "media/a:img.png", "media/a\n.png", "media/", "media/.hidden.png"))
            rejects(() -> CourseContentRules.safePath(path), "reject unsafe/executable path " + path.replace('\n', ' '));
        for (String url : Arrays.asList("https://github.com/o/r/releases/download/course-content/manifest.json", "https://release-assets.githubusercontent.com/object?token=public-signature", "https://objects.githubusercontent.com/a", "https://github-releases.githubusercontent.com/a")) {
            CourseContentRules.githubUrl(java.net.URI.create(url)); assertions++;
        }
        for (String url : Arrays.asList("http://github.com/a", "https://evil.example/a", "https://github.com.evil.example/a", "https://user:secret@github.com/a", "https://github.com:444/a", "https://github.com/a#fragment", "file:///tmp/a"))
            rejects(() -> CourseContentRules.githubUrl(java.net.URI.create(url)), "reject unsafe redirect " + url);
        truth(CourseContentRules.repository("Example-Owner", "learning.loop-app").equals("Example-Owner/learning.loop-app"), "valid repository");
        for (String repo : Arrays.asList("../repo", "a/b", "repo?token=x", ".", "..", "", "repo%2fsecret"))
            rejects(() -> CourseContentRules.repository("owner", repo), "reject repository injection");
        rejects(() -> CourseContentRules.repository("-owner", "repo"), "owner must be valid GitHub login");
    }

    private static void catalogChecks() throws Exception {
        byte[] base = bytes(catalog("course-one", "q-one"));
        CourseContentRules.Catalog old = CourseContentRules.catalog(base, null);
        truth(old.questions.size() == 1, "subject with code_insight null");
        CourseContentRules.compatible(old, CourseContentRules.catalog(bytes(catalog("course-one", "q-one", "q-two")), null)); assertions++;
        rejects(() -> CourseContentRules.compatible(old, CourseContentRules.catalog(bytes(catalog("course-one", "new-q")), null)), "protect removed/renamed question");
        rejects(() -> CourseContentRules.compatible(old, CourseContentRules.catalog(bytes(catalog("new-course", "q-one")), null)), "protect old course on source change");
        Map<String, Object> invalid = catalog("course-one", "q-one", "q-one");
        rejects(() -> CourseContentRules.catalog(bytes(invalid), null), "duplicate question ID");
        rejects(() -> CourseContentRules.catalog(bytes(catalog("course\nwith\ncontrols", "q-one")), null), "stable IDs reject multiple control characters");
        Map<String, Object> noSources = catalog("course-one", "q-one"); lesson(noSources).put("source_refs", new ArrayList<>());
        rejects(() -> CourseContentRules.catalog(bytes(noSources), null), "source citations remain required for non-code subject");
        Map<String, Object> noExperiment = catalog("course-one", "q-one"); lesson(noExperiment).remove("experiment");
        rejects(() -> CourseContentRules.catalog(bytes(noExperiment), null), "required teaching stages");
        Map<String, Object> scriptLink = catalog("course-one", "q-one"); lesson(scriptLink).put("source_refs", Arrays.asList(map("title", "Bad", "url", "javascript:alert(1)")));
        rejects(() -> CourseContentRules.catalog(bytes(scriptLink), null), "no script URLs");
        Map<String, Object> draft = catalog("course-one", "q-one"); lesson(draft).put("_draft", true);
        rejects(() -> CourseContentRules.catalog(bytes(draft), null), "draft cannot be installed");
        Map<String, Object> badAudio = catalog("course-one", "q-one");
        lesson(badAudio).put("audio_lesson", map("voice", "合成语音", "clips", Arrays.asList(map("chapter", "code", "walkthrough_id", "missing", "title", "听懂", "src", "/media/a.m4a", "duration_seconds", 60, "transcript", "讲解"))));
        rejects(() -> CourseContentRules.catalog(bytes(badAudio), null), "audio cannot reference nonexistent code walkthrough");
    }

    private static void packageChecks() throws Exception {
        Path work = Files.createTempDirectory("learning-loop-course-rules-");
        try {
            Map<String, byte[]> contents = files(bytes(catalog("course-one", "q-one")));
            contents.put("media/a.svg", SVG.getBytes(StandardCharsets.UTF_8));
            File zip = zip(work.resolve("valid.zip"), contents);
            Map<String, Object> raw = manifest(zip, contents);
            CourseContentRules.Manifest manifest = CourseContentRules.manifest(bytes(raw));
            CourseContentRules.Catalog result = CourseContentRules.extract(zip, directory(work.resolve("valid")), manifest, contents.get("courses.json"));
            truth(result.questions.containsKey("course-one"), "valid complete package extracts");
            truth(new File(work.toFile(), "valid/media/a.svg").isFile(), "media extracted under stage");
            rejects(() -> CourseContentRules.extract(zip, new File(work.toFile(), "valid"), manifest, null), "refuse nonempty stage");

            Map<String, Object> badHash = manifest(zip, contents); object(badHash.get("archive")).put("sha256", repeat("0", 64));
            rejects(() -> CourseContentRules.extract(zip, directory(work.resolve("bad-hash")), CourseContentRules.manifest(bytes(badHash)), null), "whole archive hash required");
            Map<String, Object> badSize = manifest(zip, contents); object(badSize.get("archive")).put("size", zip.length() + 1);
            rejects(() -> CourseContentRules.extract(zip, directory(work.resolve("bad-size")), CourseContentRules.manifest(bytes(badSize)), null), "whole archive size required");
            Map<String, Object> badFileHash = manifest(zip, contents); object(list(badFileHash.get("files")).get(0)).put("sha256", repeat("0", 64));
            rejects(() -> CourseContentRules.extract(zip, directory(work.resolve("bad-file-hash")), CourseContentRules.manifest(bytes(badFileHash)), null), "per-file hash required");
            Map<String, Object> badFileSize = manifest(zip, contents); object(list(badFileSize.get("files")).get(0)).put("size", 1);
            rejects(() -> CourseContentRules.extract(zip, directory(work.resolve("bad-file-size")), CourseContentRules.manifest(bytes(badFileSize)), null), "per-file size required");
            Map<String, Object> tooBig = manifest(zip, contents); object(tooBig.get("archive")).put("size", CourseContentRules.MAX_PACKAGE_BYTES + 1);
            rejects(() -> CourseContentRules.manifest(bytes(tooBig)), "download maximum");
            Map<String, Object> tooMuch = manifest(zip, contents); object(list(tooMuch.get("files")).get(1)).put("size", CourseContentRules.MAX_PACKAGE_BYTES);
            rejects(() -> CourseContentRules.manifest(bytes(tooMuch)), "total unzip maximum");
            Map<String, Object> duplicate = manifest(zip, contents); list(duplicate.get("files")).add(list(duplicate.get("files")).get(0));
            rejects(() -> CourseContentRules.manifest(bytes(duplicate)), "duplicate manifest entry");
            Map<String, Object> folded = manifest(zip, contents); list(folded.get("files")).add(map("path", "media/A.svg", "size", 1, "sha256", repeat("0", 64)));
            rejects(() -> CourseContentRules.manifest(bytes(folded)), "case-insensitive path collisions rejected");
            Map<String, Object> badName = manifest(zip, contents); object(badName.get("archive")).put("name", "courses.zip");
            rejects(() -> CourseContentRules.manifest(bytes(badName)), "immutable archive name");
            Map<String, Object> newerApp = manifest(zip, contents); newerApp.put("min_app_version", 99);
            truth(CourseContentRules.manifest(bytes(newerApp)).minAppVersion == 99, "retain minimum APK version for blocking download");
            Map<String, Object> badSchema = manifest(zip, contents); badSchema.put("schema_version", 2);
            rejects(() -> CourseContentRules.manifest(bytes(badSchema)), "reject unknown manifest schema");
            Map<String, Object> wrongCount = manifest(zip, contents); wrongCount.put("course_count", 2);
            rejects(() -> CourseContentRules.extract(zip, directory(work.resolve("wrong-count")), CourseContentRules.manifest(bytes(wrongCount)), null), "course count verified");
            Map<String, Object> reminder = manifest(zip, contents); reminder.put("reminder", map("time", "25:99", "minutes", 5));
            rejects(() -> CourseContentRules.manifest(bytes(reminder)), "reminder suggestion validated");

            Map<String, byte[]> malicious = files(contents.get("courses.json")); malicious.put("../outside.mp4", new byte[]{1});
            File traversalZip = zip(work.resolve("traversal.zip"), malicious);
            Map<String, Object> traversal = manifest(traversalZip, malicious); object(list(traversal.get("files")).get(1)).put("path", "media/outside.mp4");
            rejects(() -> CourseContentRules.extract(traversalZip, directory(work.resolve("traversal")), CourseContentRules.manifest(bytes(traversal)), null), "ZIP traversal rejected independently of manifest");
            truth(!work.resolve("outside.mp4").toFile().exists(), "ZIP traversal wrote no outside file");

            Map<String, byte[]> hidden = new LinkedHashMap<>(contents); hidden.put("media/app.js", "alert(1)".getBytes(StandardCharsets.UTF_8));
            File extraZip = zip(work.resolve("extra.zip"), hidden);
            Map<String, Object> extra = manifest(extraZip, contents);
            rejects(() -> CourseContentRules.extract(extraZip, directory(work.resolve("extra")), CourseContentRules.manifest(bytes(extra)), null), "unlisted executable ZIP entry rejected");

            Map<String, byte[]> duplicateFiles = new LinkedHashMap<>(contents); duplicateFiles.put("media/b.svg", SVG.getBytes(StandardCharsets.UTF_8));
            File duplicateZip = zip(work.resolve("duplicate.zip"), duplicateFiles);
            byte[] duplicateBytes = Files.readAllBytes(duplicateZip.toPath());
            replaceAscii(duplicateBytes, "media/b.svg", "media/a.svg"); Files.write(duplicateZip.toPath(), duplicateBytes);
            CourseContentRules.Manifest duplicateManifest = CourseContentRules.manifest(bytes(manifest(duplicateZip, duplicateFiles)));
            rejects(() -> CourseContentRules.extract(duplicateZip, directory(work.resolve("duplicate")), duplicateManifest, null), "duplicate ZIP entries rejected");

            Map<String, byte[]> compressed = files(contents.get("courses.json")); compressed.put("media/big.mp4", new byte[1024 * 1024]);
            File compressedZip = zip(work.resolve("compressed.zip"), compressed);
            byte[] compressedBytes = Files.readAllBytes(compressedZip.toPath());
            forgeCentralSize(compressedBytes, "media/big.mp4", 1); Files.write(compressedZip.toPath(), compressedBytes);
            Map<String, Object> compressionManifest = manifest(compressedZip, compressed); object(list(compressionManifest.get("files")).get(1)).put("size", 1);
            CourseContentRules.Manifest forgedSize = CourseContentRules.manifest(bytes(compressionManifest));
            rejects(() -> CourseContentRules.extract(compressedZip, directory(work.resolve("compressed")), forgedSize, null), "actual inflated bytes bounded despite forged central-directory size");

            Map<String, Object> referenced = catalog("course-one", "q-one");
            lesson(referenced).put("audio_lesson", map("voice", "合成语音", "clips", Arrays.asList(map("chapter", "logic", "walkthrough_id", null, "title", "听懂", "src", "/media/missing.m4a", "duration_seconds", 60, "transcript", "讲解"))));
            Map<String, byte[]> missing = files(bytes(referenced)); File missingZip = zip(work.resolve("missing.zip"), missing);
            CourseContentRules.Manifest missingManifest = CourseContentRules.manifest(bytes(manifest(missingZip, missing)));
            rejects(() -> CourseContentRules.extract(missingZip, directory(work.resolve("missing")), missingManifest, null), "referenced media must exist in complete archive");

            String[] svgAttacks = {
                "<svg xmlns=\"http://www.w3.org/2000/svg\"><script>alert(1)</script></svg>",
                "<svg xmlns=\"http://www.w3.org/2000/svg\" onload=\"alert(1)\"/>",
                "<svg xmlns=\"http://www.w3.org/2000/svg\"><foreignObject><html/></foreignObject></svg>",
                "<svg xmlns=\"http://www.w3.org/2000/svg\"><use href=\"https://evil.example/a.svg#x\"/></svg>",
                "<svg xmlns=\"http://www.w3.org/2000/svg\"><rect fill=\"url(https://evil.example/a.svg)\"/></svg>",
                "<!DOCTYPE svg [<!ENTITY x SYSTEM 'file:///etc/passwd'>]><svg xmlns=\"http://www.w3.org/2000/svg\">&x;</svg>",
                "<?xml-stylesheet href='https://evil.example/x.css'?><svg xmlns=\"http://www.w3.org/2000/svg\"/>",
                "<svg xmlns=\"http://www.w3.org/2000/svg\"><rect style=\"fill:red\"/></svg>"
            };
            for (int i = 0; i < svgAttacks.length; i++) {
                Map<String, byte[]> attack = files(contents.get("courses.json")); attack.put("media/a.svg", svgAttacks[i].getBytes(StandardCharsets.UTF_8));
                File attackZip = zip(work.resolve("svg-" + i + ".zip"), attack);
                File stage = directory(work.resolve("svg-" + i));
                CourseContentRules.Manifest attackManifest = CourseContentRules.manifest(bytes(manifest(attackZip, attack)));
                rejects(() -> CourseContentRules.extract(attackZip, stage, attackManifest, null), "unsafe SVG rejected " + i);
            }
            Map<String, byte[]> changed = files(bytes(catalog("course-one", "renamed-question")));
            File changedZip = zip(work.resolve("changed.zip"), changed);
            CourseContentRules.Manifest changedManifest = CourseContentRules.manifest(bytes(manifest(changedZip, changed)));
            rejects(() -> CourseContentRules.extract(changedZip, directory(work.resolve("changed")), changedManifest, contents.get("courses.json")), "full package blocks destructive question change");
            truth(Files.readString(work.resolve("valid/courses.json")).contains("q-one"), "failed update preserves existing installed fixture");
        } finally { remove(work.toFile()); }
    }

    static Map<String, Object> catalog(String id, String... questions) {
        List<Object> qs = new ArrayList<>(); for (String q : questions) qs.add(map("id", q, "prompt", "为什么？", "answer", "用证据回答。"));
        Map<String, Object> lesson = map("summary", "本节概述", "mental_model", "核心思维", "core_ideas", Arrays.asList(map("title", "概念", "explanation", "因果关系")),
                "source_refs", Arrays.asList(map("title", "教材", "url", "https://example.org/textbook")), "questions", qs,
                "case_study", map("title", "案例", "scenario", "模拟数据", "steps", Arrays.asList("预测", "计算")), "code_insight", null,
                "experiment", map("title", "小实验", "steps", Arrays.asList("亲自计算"), "acceptance", Arrays.asList("解释变化")),
                "application", map("prompt", "迁移一个实际问题", "acceptance", Arrays.asList("提供证据")), "recap_prompts", Arrays.asList("闭卷回忆"));
        return map("schema_version", 1, "courses", Arrays.asList(map("id", id, "title", "学习概率", "topic_id", "probability", "subject", "概率与统计", "kind", "subject", "repo_full_name", "", "repo_url", "", "lesson", lesson)));
    }
    static Map<String, Object> lesson(Map<String, Object> catalog) { return object(object(list(catalog.get("courses")).get(0)).get("lesson")); }
    static Map<String, Object> manifest(File zip, Map<String, byte[]> files) throws Exception {
        List<Object> entries = new ArrayList<>();
        for (Map.Entry<String, byte[]> file : files.entrySet()) entries.add(map("path", file.getKey(), "size", file.getValue().length, "sha256", digest(file.getValue())));
        return map("schema_version", 1, "version", VERSION, "min_app_version", 1,
                "archive", map("name", "courses-" + VERSION + ".zip", "sha256", digest(Files.readAllBytes(zip.toPath())), "size", zip.length()),
                "files", entries, "course_count", 1, "reminder", map("time", "20:00", "minutes", 5));
    }
    static Map<String, byte[]> files(byte[] courses) { Map<String, byte[]> result = new LinkedHashMap<>(); result.put("courses.json", courses); return result; }
    static File zip(Path path, Map<String, byte[]> files) throws Exception {
        try (ZipOutputStream zip = new ZipOutputStream(Files.newOutputStream(path))) {
            for (Map.Entry<String, byte[]> file : files.entrySet()) { zip.putNextEntry(new ZipEntry(file.getKey())); zip.write(file.getValue()); zip.closeEntry(); }
        }
        return path.toFile();
    }
    static File directory(Path path) throws Exception { return Files.createDirectory(path).toFile(); }
    static String digest(byte[] bytes) { return CourseContentRules.hex(CourseContentRules.sha256().digest(bytes)); }
    static byte[] bytes(Object value) { return json(value).getBytes(StandardCharsets.UTF_8); }
    static Map<String, Object> map(Object... args) { Map<String, Object> map = new LinkedHashMap<>(); for (int i = 0; i < args.length; i += 2) map.put((String) args[i], args[i + 1]); return map; }
    @SuppressWarnings("unchecked") static Map<String, Object> object(Object value) { return (Map<String, Object>) value; }
    @SuppressWarnings("unchecked") static List<Object> list(Object value) { return (List<Object>) value; }
    static String json(Object value) {
        if (value == null) return "null";
        if (value instanceof String) return "\"" + ((String) value).replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t") + "\"";
        if (value instanceof Map) { List<String> parts = new ArrayList<>(); for (Map.Entry<String, Object> e : object(value).entrySet()) parts.add(json(e.getKey()) + ":" + json(e.getValue())); return "{" + String.join(",", parts) + "}"; }
        if (value instanceof List) { List<String> parts = new ArrayList<>(); for (Object e : list(value)) parts.add(json(e)); return "[" + String.join(",", parts) + "]"; }
        return value.toString();
    }
    static String repeat(String text, int n) { StringBuilder out = new StringBuilder(); for (int i = 0; i < n; i++) out.append(text); return out.toString(); }
    static void rejects(Attempt attempt, String name) throws Exception { try { attempt.run(); } catch (IOException expected) { assertions++; return; } throw new AssertionError("Expected rejection: " + name); }
    static void truth(boolean value, String name) { if (!value) throw new AssertionError(name); assertions++; }
    static void remove(File file) { File[] children = file.listFiles(); if (children != null) for (File child : children) remove(child); if (file.exists() && !file.delete()) throw new AssertionError("Could not clean test fixture"); }
    static void replaceAscii(byte[] bytes, String old, String replacement) {
        byte[] from = old.getBytes(StandardCharsets.US_ASCII), to = replacement.getBytes(StandardCharsets.US_ASCII);
        if (from.length != to.length) throw new AssertionError();
        for (int i = 0; i <= bytes.length - from.length; i++) {
            boolean match = true; for (int j = 0; j < from.length; j++) if (bytes[i + j] != from[j]) { match = false; break; }
            if (match) { System.arraycopy(to, 0, bytes, i, to.length); i += to.length - 1; }
        }
    }
    static void forgeCentralSize(byte[] bytes, String target, int size) {
        for (int i = 0; i + 46 < bytes.length; i++) {
            if (bytes[i] != 0x50 || bytes[i + 1] != 0x4b || bytes[i + 2] != 0x01 || bytes[i + 3] != 0x02) continue;
            int length = (bytes[i + 28] & 255) | ((bytes[i + 29] & 255) << 8);
            if (i + 46 + length > bytes.length) continue;
            String name = new String(bytes, i + 46, length, StandardCharsets.UTF_8);
            if (name.equals(target)) { for (int j = 0; j < 4; j++) bytes[i + 24 + j] = (byte) (size >>> (8 * j)); return; }
        }
        throw new AssertionError("Central directory fixture entry missing");
    }
}
