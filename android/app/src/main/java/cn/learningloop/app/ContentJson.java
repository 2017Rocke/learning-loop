package cn.learningloop.app;

import java.io.IOException;
import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Strict, bounded JSON reader shared with the dependency-free JVM checks. */
final class ContentJson {
    private final String input;
    private int offset;
    private int values;

    private ContentJson(String input) { this.input = input; }

    static Object parse(String input) throws IOException {
        if (input == null || input.length() > CourseContentRules.MAX_COURSES_BYTES)
            throw new IOException("课程 JSON 超出允许大小。");
        ContentJson parser = new ContentJson(input);
        Object value = parser.value(0);
        parser.space();
        if (parser.offset != input.length()) parser.fail();
        return value;
    }

    private Object value(int depth) throws IOException {
        if (depth > 48 || ++values > 200000) throw new IOException("课程 JSON 层级或记录数过多。");
        space();
        if (offset >= input.length()) return fail();
        char c = input.charAt(offset);
        if (c == '"') return string();
        if (c == '{') {
            offset++;
            Map<String, Object> map = new LinkedHashMap<>();
            space();
            if (take('}')) return map;
            do {
                space();
                if (offset >= input.length() || input.charAt(offset) != '"') return fail();
                String key = string();
                space();
                if (!take(':') || map.containsKey(key)) return fail();
                map.put(key, value(depth + 1));
                space();
                if (take('}')) return map;
            } while (take(','));
            return fail();
        }
        if (c == '[') {
            offset++;
            List<Object> list = new ArrayList<>();
            space();
            if (take(']')) return list;
            do {
                list.add(value(depth + 1));
                space();
                if (take(']')) return list;
            } while (take(','));
            return fail();
        }
        if (input.startsWith("true", offset)) { offset += 4; return Boolean.TRUE; }
        if (input.startsWith("false", offset)) { offset += 5; return Boolean.FALSE; }
        if (input.startsWith("null", offset)) { offset += 4; return null; }
        int start = offset;
        take('-');
        if (!take('0')) {
            if (offset >= input.length() || input.charAt(offset) < '1' || input.charAt(offset) > '9') return fail();
            while (digit()) offset++;
        }
        if (take('.')) {
            if (!digit()) return fail();
            while (digit()) offset++;
        }
        if (take('e') || take('E')) {
            if (!take('+')) take('-');
            if (!digit()) return fail();
            while (digit()) offset++;
        }
        if (offset - start > 100) return fail();
        try { return new BigDecimal(input.substring(start, offset)); }
        catch (NumberFormatException ex) { return fail(); }
    }

    private boolean digit() { return offset < input.length() && input.charAt(offset) >= '0' && input.charAt(offset) <= '9'; }
    private boolean take(char c) {
        if (offset < input.length() && input.charAt(offset) == c) { offset++; return true; }
        return false;
    }
    private void space() {
        while (offset < input.length()) {
            char c = input.charAt(offset);
            if (c != ' ' && c != '\t' && c != '\n' && c != '\r') break;
            offset++;
        }
    }
    private String string() throws IOException {
        offset++;
        StringBuilder out = new StringBuilder();
        boolean ended = false;
        while (offset < input.length()) {
            char c = input.charAt(offset++);
            if (c == '"') { ended = true; break; }
            if (c < 0x20) return fail();
            if (c == '\\') {
                if (offset >= input.length()) return fail();
                c = input.charAt(offset++);
                switch (c) {
                    case '"': case '\\': case '/': out.append(c); break;
                    case 'b': out.append('\b'); break;
                    case 'f': out.append('\f'); break;
                    case 'n': out.append('\n'); break;
                    case 'r': out.append('\r'); break;
                    case 't': out.append('\t'); break;
                    case 'u':
                        if (offset + 4 > input.length()) return fail();
                        int unit = 0;
                        for (int i = 0; i < 4; i++) {
                            int nibble = Character.digit(input.charAt(offset++), 16);
                            if (nibble < 0) return fail();
                            unit = (unit << 4) | nibble;
                        }
                        out.append((char) unit); break;
                    default: return fail();
                }
            } else out.append(c);
        }
        if (!ended || out.length() > 1000000) return fail();
        for (int i = 0; i < out.length(); i++) {
            char c = out.charAt(i);
            if (Character.isHighSurrogate(c)) {
                if (++i >= out.length() || !Character.isLowSurrogate(out.charAt(i))) return fail();
            } else if (Character.isLowSurrogate(c)) return fail();
        }
        return out.toString();
    }
    private <T> T fail() throws IOException { throw new IOException("课程 JSON 格式无效或含重复字段。"); }
}
