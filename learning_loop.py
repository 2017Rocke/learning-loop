#!/usr/bin/env python3
"""Local learning ledger, public GitHub discovery, and spaced retrieval practice."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib
import json
from pathlib import Path
import re
import sqlite3
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ROOT = Path(__file__).resolve().parent
UTC = timezone.utc
try:
    LOCAL = ZoneInfo('Asia/Shanghai')
    TIMEZONE_SOURCE = 'IANA Asia/Shanghai'
except ZoneInfoNotFoundError:
    # Modern Shanghai uses UTC+08:00 without DST. Fresh Windows Python often
    # lacks an IANA database; current learning schedules need no pip package.
    LOCAL = timezone(timedelta(hours=8), name='Asia/Shanghai')
    TIMEZONE_SOURCE = 'fixed UTC+08:00 fallback for current schedules'
DEFAULTS = dict(daily_minutes=30, review_minutes=5, reminder_time='20:00',
                timezone='Asia/Shanghai', discovery_limit=20, min_stars=100000,
                max_active_tracks=1, automation_enabled=False, automation_id=None)
INTERVALS = [1, 3, 7, 14, 30, 60]
SOFTWARE_LICENSES = {'MIT', 'Apache-2.0', 'BSD-2-Clause', 'BSD-3-Clause', 'ISC', 'MPL-2.0',
                     'GPL-2.0', 'GPL-3.0', 'GPL-2.0-only', 'GPL-3.0-only', 'GPL-2.0-or-later',
                     'GPL-3.0-or-later', 'LGPL-2.1', 'LGPL-3.0', 'AGPL-3.0', 'AGPL-3.0-only',
                     'AGPL-3.0-or-later', 'Unlicense', 'CC0-1.0', 'BSL-1.0', 'Zlib', 'EPL-2.0'}
STATUSES = {'exploring', 'learning', 'practicing', 'applied', 'mastered', 'paused'}
ACTIVE = {'learning', 'practicing', 'applied'}
SCHEMA = '''
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS repositories(id INTEGER PRIMARY KEY,full_name TEXT UNIQUE NOT NULL,data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS snapshots(repo_id INTEGER NOT NULL,day TEXT NOT NULL,stars INTEGER NOT NULL,observed_at TEXT NOT NULL,PRIMARY KEY(repo_id,day));
CREATE TABLE IF NOT EXISTS tracks(id TEXT PRIMARY KEY,title TEXT NOT NULL,topic_id TEXT NOT NULL,repo_full_name TEXT NOT NULL,repo_url TEXT NOT NULL,status TEXT NOT NULL,lesson_status TEXT NOT NULL,lesson TEXT,created_at TEXT NOT NULL,progress_note TEXT NOT NULL DEFAULT '',subject TEXT NOT NULL DEFAULT 'technology',kind TEXT NOT NULL DEFAULT 'project');
CREATE TABLE IF NOT EXISTS evidence(id TEXT PRIMARY KEY,track_id TEXT NOT NULL REFERENCES tracks(id),kind TEXT NOT NULL,text TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS known_topics(topic_id TEXT PRIMARY KEY,topic_name TEXT NOT NULL,source TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS cards(id TEXT PRIMARY KEY,track_id TEXT NOT NULL REFERENCES tracks(id),question_key TEXT NOT NULL,question TEXT NOT NULL,answer TEXT NOT NULL,due_at TEXT NOT NULL,interval_days REAL NOT NULL,repetitions INTEGER NOT NULL DEFAULT 0,lapses INTEGER NOT NULL DEFAULT 0,UNIQUE(track_id,question_key));
CREATE TABLE IF NOT EXISTS review_events(id TEXT PRIMARY KEY,card_id TEXT NOT NULL REFERENCES cards(id),rating TEXT NOT NULL,response TEXT NOT NULL,created_at TEXT NOT NULL,was_due INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,track_id TEXT NOT NULL REFERENCES tracks(id),status TEXT NOT NULL,created_at TEXT NOT NULL,error TEXT);
CREATE TABLE IF NOT EXISTS notifications(id TEXT PRIMARY KEY,text TEXT NOT NULL,created_at TEXT NOT NULL);
'''


def now():
    return datetime.now(UTC)


def stamp(value=None):
    return (value or now()).astimezone(UTC).isoformat(timespec='seconds')


def parse_time(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('时间必须含时区')
    return result.astimezone(UTC)


def uid():
    return uuid.uuid4().hex[:16]


def dump(value):
    return json.dumps(value, ensure_ascii=False)


def require_text(value, label, maximum=20000):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f'{label}需要填写，且长度不能超过 {maximum} 字符')
    return value.strip()


def safe_url(value):
    parsed = urlparse(value)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('资料链接必须是有效的 HTTPS 地址')
    return value


def canonical_repo_url(value):
    """Normalize an optional public reference without fetching the remote site."""
    if value == '':
        return ''
    value = safe_url(require_text(value, '项目链接', 1000))
    parsed = urlparse(value)
    if parsed.query or parsed.fragment:
        raise ValueError('项目链接不应包含查询参数或片段')
    path = parsed.path.rstrip('/')
    if parsed.hostname.lower() == 'github.com':
        path = path.removesuffix('.git').lower()
        if not re.fullmatch(r'/[a-z0-9_.-]+/[a-z0-9_.-]+', path):
            raise ValueError('GitHub 项目链接应指向 owner/repository')
    return parsed._replace(netloc=parsed.netloc.lower(), path=path).geturl()


def load_courses(path=None):
    """Read the distributable course manifest, independently of any private ledger."""
    path = Path(path or ROOT / 'content' / 'courses.json')
    if not path.is_file():
        if path == ROOT / 'content' / 'courses.json' and (ROOT / 'content' / 'brush.json').is_file():
            data = {'schema_version': 1, 'courses': [dict(id='brush-intro',
                title='高斯溅射：从照片到可观看的场景', topic_id='gaussian-splatting',
                subject='technology', kind='project', repo_full_name='ArthurBrussee/brush',
                repo_url='https://github.com/ArthurBrussee/brush', lesson_file='brush.json')]}
        else:
            raise ValueError('找不到课程清单：' + str(path))
    else:
        data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or set(data) != {'schema_version', 'courses'} or type(data['schema_version']) is not int or data['schema_version'] != 1:
        raise ValueError('课程清单必须使用 schema_version: 1 和 courses')
    if not isinstance(data['courses'], list):
        raise ValueError('courses 必须是课程列表')
    fields = {'id','title','topic_id','subject','kind','repo_full_name','repo_url','lesson_file'}
    ids, topics = set(), set()
    content = (ROOT / 'content').resolve()
    for course in data['courses']:
        if not isinstance(course, dict) or set(course) != fields:
            raise ValueError('课程清单条目结构不完整或含未知字段')
        course_id = require_text(course['id'], '课程ID', 100)
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', course_id) or course_id in ids:
            raise ValueError('课程ID须唯一且只含字母、数字、横线或下划线')
        ids.add(course_id)
        require_text(course['title'], '课程名称', 200)
        topic = require_text(course['topic_id'], '主线ID', 200).casefold()
        if topic in topics:
            raise ValueError('课程清单不应重复同一主线')
        topics.add(topic)
        require_text(course['subject'], '学科', 100)
        if not isinstance(course['kind'], str) or course['kind'] not in {'project','subject'}:
            raise ValueError('课程类型只能是 project 或 subject')
        if not isinstance(course['repo_full_name'], str) or len(course['repo_full_name']) > 200:
            raise ValueError('仓库名称必须是字符串，可为空')
        repo_url = canonical_repo_url(course['repo_url'])
        if course['repo_full_name']:
            if not re.fullmatch(r'[^/\s]+/[^/\s]+', course['repo_full_name']):
                raise ValueError('仓库名称应为 owner/repository')
            if not repo_url:
                raise ValueError('填写仓库名称时也需要项目链接')
            if urlparse(repo_url).hostname == 'github.com' and urlparse(repo_url).path.strip('/') != course['repo_full_name'].casefold():
                raise ValueError('仓库名称与项目链接不一致')
        relative = require_text(course['lesson_file'], '教材文件', 300)
        if ('\\' in relative or '%' in relative or Path(relative).is_absolute() or
                any(part in {'', '.', '..'} for part in relative.split('/')) or Path(relative).suffix != '.json'):
            raise ValueError('教材文件必须是 content 内的相对 JSON 路径')
        target = ROOT / 'content' / relative
        if not target.resolve().is_relative_to(content) or not target.is_file():
            raise ValueError('教材文件不存在或超出 content：' + relative)
    return data


def doctor():
    """Read-only installation checks; deliberately never opens a personal database."""
    checks = []
    checks.append(dict(name='python', ok=sys.version_info >= (3, 9), detail=sys.version.split()[0], requirement='Python >= 3.9'))
    checks.append(dict(name='sqlite', ok=sqlite3.sqlite_version_info >= (3, 24), detail=sqlite3.sqlite_version))
    for module in ('sqlite3','ssl','json','urllib.request','http.server','pathlib','zoneinfo'):
        try:
            importlib.import_module(module)
            checks.append(dict(name='stdlib:' + module, ok=True, detail='available'))
        except ImportError as exc:
            checks.append(dict(name='stdlib:' + module, ok=False, detail=str(exc)))
    checks.append(dict(name='timezone', ok=True, detail=TIMEZONE_SOURCE,
                       note='固定时区回退仅用于当前上海日程，不用于历史夏令时研究。'))
    try:
        manifest = load_courses()
        checks.append(dict(name='courses', ok=True, detail=f"{len(manifest['courses'])} courses"))
        for course in manifest['courses']:
            try:
                lesson = validate_lesson(json.loads((ROOT / 'content' / course['lesson_file']).read_text(encoding='utf-8')))
                validate_lesson_assets(lesson)
                checks.append(dict(name='lesson:' + course['id'], ok=True, detail='教材结构及引用媒体存在、非空且位于允许目录；未在 doctor 中解码。'))
            except (ValueError, OSError, TypeError) as exc:
                checks.append(dict(name='lesson:' + course['id'], ok=False, detail=str(exc)))
    except (ValueError, OSError, TypeError) as exc:
        checks.append(dict(name='courses', ok=False, detail=str(exc)))
    return dict(ok=all(check['ok'] for check in checks), python=sys.version.split()[0],
                sqlite_version=sqlite3.sqlite_version, checks=checks,
                database_accessed=False, network_accessed=False)


def media_path(value, suffixes):
    value = require_text(value, '本地媒体路径', 300)
    parsed = urlparse(value)
    path = Path(parsed.path)
    if (parsed.scheme or parsed.netloc or parsed.query or parsed.fragment or
            not value.startswith('/media/') or '%' in value or '\\' in value or
            '..' in path.parts or path.suffix.lower() not in suffixes):
        raise ValueError('媒体必须位于 /media/ 下并使用允许的文件类型')
    return value


def validate_visual_lesson(visual):
    if not isinstance(visual, dict) or set(visual) != {'hook','duration_minutes','video','steps','interactive','takeaways','watch_more'}:
        raise ValueError('视觉课程结构不完整或含未知字段')
    require_text(visual['hook'], '学习目标', 200)
    if type(visual['duration_minutes']) is not int or not 1 <= visual['duration_minutes'] <= 60:
        raise ValueError('视觉课程时长需为1到60分钟')
    video = visual['video']
    if video is not None:
        if not isinstance(video, dict) or set(video) != {'src','poster','captions','title','duration_seconds','attribution','transcript'}:
            raise ValueError('讲解视频结构不完整')
        media_path(video['src'], {'.mp4','.webm'})
        media_path(video['poster'], {'.png','.jpg','.jpeg','.svg'})
        media_path(video['captions'], {'.vtt'})
        require_text(video['title'], '视频标题', 200)
        require_text(video['attribution'], '视频来源', 500)
        if type(video['duration_seconds']) not in (int, float) or not 1 <= video['duration_seconds'] <= 600:
            raise ValueError('讲解视频时长需在1到600秒之间')
        if not isinstance(video['transcript'], list) or not video['transcript']:
            raise ValueError('视频需要等价文字讲解')
        previous = -1
        for line in video['transcript']:
            if not isinstance(line, dict) or set(line) != {'time','text'}:
                raise ValueError('无效的视频文字讲解')
            time = line['time']
            if type(time) not in (int,float) or time < 0 or not previous < time < video['duration_seconds']:
                raise ValueError('视频章节时间需递增且位于视频时长以内')
            previous = time
            require_text(line['text'], '视频文字讲解', 1000)
    if not isinstance(visual['steps'], list) or not 1 <= len(visual['steps']) <= 8:
        raise ValueError('图解需要1到8个步骤')
    step_ids = set()
    for step in visual['steps']:
        if not isinstance(step, dict) or set(step) != {'id','title','caption','image','alt','question'}:
            raise ValueError('图解步骤结构不完整')
        step_id = require_text(step['id'], '步骤ID', 100)
        if step_id in step_ids:
            raise ValueError('图解步骤ID不可重复')
        step_ids.add(step_id)
        require_text(step['title'], '步骤标题', 100)
        require_text(step['caption'], '图解结论', 400)
        require_text(step['alt'], '图像文字说明', 500)
        media_path(step['image'], {'.svg','.png','.jpg','.jpeg','.webp'})
        question = step['question']
        if not isinstance(question, dict) or set(question) != {'prompt','options','correct_index','explanation'}:
            raise ValueError('每幅图需要一道预测题和解释')
        require_text(question['prompt'], '预测题', 300)
        require_text(question['explanation'], '预测题解释', 700)
        if not isinstance(question['options'], list) or not 2 <= len(question['options']) <= 4:
            raise ValueError('预测题需要2到4个选项')
        for option in question['options']:
            require_text(option, '预测题选项', 200)
        if type(question['correct_index']) is not int or not 0 <= question['correct_index'] < len(question['options']):
            raise ValueError('预测题答案索引超出选项范围')
    interactive = visual['interactive']
    if interactive is not None:
        if not isinstance(interactive, dict) or set(interactive) != {'kind','title','prompt'}:
            raise ValueError('交互演示结构不完整')
        if interactive['kind'] not in {'gaussian-viewer'}:
            raise ValueError('该交互演示尚未实现，请使用图解或添加已验证的演示模块')
        require_text(interactive['title'], '交互演示标题', 100)
        require_text(interactive['prompt'], '交互演示提示', 400)
    if not isinstance(visual['takeaways'], list) or not 1 <= len(visual['takeaways']) <= 5:
        raise ValueError('需要1到5条简短结论')
    for line in visual['takeaways']:
        require_text(line, '课后结论', 200)
    if not isinstance(visual['watch_more'], list):
        raise ValueError('延伸视频与资料应为列表')
    for ref in visual['watch_more']:
        if not isinstance(ref, dict) or set(ref) != {'title','url','description'}:
            raise ValueError('延伸资料结构不完整')
        require_text(ref['title'], '延伸资料标题', 200)
        safe_url(require_text(ref['url'], '延伸资料链接'))
        require_text(ref['description'], '观看目的', 400)


def validate_lesson_assets(lesson):
    visual = lesson.get('visual_lesson')
    paths = [s['image'] for s in visual['steps']] if visual else []
    if visual and visual['video']:
        paths += [visual['video'][key] for key in ('src','poster','captions')]
    if lesson.get('audio_lesson'):
        paths += [clip['src'] for clip in lesson['audio_lesson']['clips']]
    base = (ROOT / 'web' / 'media').resolve()
    for path in paths:
        target = ROOT / 'web' / path.lstrip('/')
        if not target.resolve().is_relative_to(base) or not target.is_file() or target.stat().st_size == 0:
            raise ValueError('缺少可用教学媒体：' + path)


def parse_byte_range(header, size):
    """Resolve a single HTTP byte range, including open-ended and suffix forms."""
    if header is None:
        return None
    match = re.fullmatch(r'bytes=(\d*)-(\d*)', header.strip())
    if not match or size <= 0 or not any(match.groups()):
        raise ValueError('无效的媒体字节范围')
    first, last = match.groups()
    if first:
        start, end = int(first), min(int(last), size - 1) if last else size - 1
    else:
        length = int(last)
        if length <= 0:
            raise ValueError('无效的媒体字节范围')
        start, end = max(0, size - length), size - 1
    if start >= size or end < start:
        raise ValueError('媒体字节范围越界')
    return start, end


def validate_code_walkthroughs(walkthroughs):
    """Keep teaching notes aligned with unchanged, traceable code excerpts."""
    if not isinstance(walkthroughs, list) or not 1 <= len(walkthroughs) <= 8:
        raise ValueError('逐行讲解需要1到8个短片段')
    ids = set()
    fields = {'id','title','kind','language','snippet','source_url','source_path',
              'source_commit','source_start_line','notes'}
    for section in walkthroughs:
        if not isinstance(section, dict) or set(section) != fields:
            raise ValueError('逐行讲解片段结构不完整或含未知字段')
        key = require_text(section['id'], '代码片段ID', 100)
        if key in ids:
            raise ValueError('代码片段ID不能重复')
        ids.add(key)
        require_text(section['title'], '代码片段标题', 200)
        require_text(section['language'], '代码语言', 50)
        require_text(section['snippet'], '代码原文')
        source_url = safe_url(require_text(section['source_url'], '源码依据'))
        if section['kind'] == 'source':
            commit = require_text(section['source_commit'], '源码完整版本', 40)
            path = require_text(section['source_path'], '仓库相对文件路径', 500)
            start = section['source_start_line']
            if not re.fullmatch(r'[0-9a-fA-F]{40}', commit):
                raise ValueError('真实源码需要完整40位提交哈希')
            if path.startswith('/') or '\\' in path or any(p in {'','.','..'} for p in path.split('/')):
                raise ValueError('源码路径必须是仓库内相对文件路径')
            if type(start) is not int or not 1 <= start <= 10000000:
                raise ValueError('真实源码需要从1开始的原文件行号')
            url_path = urlparse(source_url).path
            if '/' + commit + '/' not in url_path or not url_path.endswith('/' + path):
                raise ValueError('源码链接需对应所填版本与文件路径')
        elif section['kind'] == 'pseudocode':
            if any(section[field] is not None for field in ('source_path','source_commit','source_start_line')):
                raise ValueError('教学伪代码不能冒用真实源码的文件或行号')
        else:
            raise ValueError('代码类型只支持真实源码或教学伪代码')
        lines = section['snippet'].split('\n')
        if len(lines) > 80:
            raise ValueError('每个片段最多80行，请按机制拆成短片段')
        expected = [i for i, line in enumerate(lines, 1) if line.strip()]
        notes = section['notes']
        if not isinstance(notes, list) or len(notes) != len(expected):
            raise ValueError('每个非空代码行都需要中文注释和原因')
        for line_number, note in zip(expected, notes):
            if not isinstance(note, dict) or set(note) != {'line','comment','why'}:
                raise ValueError('逐行注释结构不完整')
            if type(note['line']) is not int or note['line'] != line_number:
                raise ValueError('注释行号需依次对应原片段的每个非空行')
            require_text(note['comment'], '这一行做什么', 700)
            require_text(note['why'], '为什么需要这一行', 1000)


def validate_audio_lesson(audio, walkthroughs):
    if not isinstance(audio, dict) or set(audio) != {'voice','clips'}:
        raise ValueError('语音课程结构不完整或含未知字段')
    require_text(audio['voice'], '配音来源', 200)
    if not isinstance(audio['clips'], list) or not 1 <= len(audio['clips']) <= 16:
        raise ValueError('语音课程需要1到16段已生成的音频')
    ids = {section['id'] for section in walkthroughs}
    keys = set()
    for clip in audio['clips']:
        if not isinstance(clip, dict) or set(clip) != {'chapter','walkthrough_id','title','src','duration_seconds','transcript'}:
            raise ValueError('语音片段结构不完整')
        chapter = clip['chapter']
        if not isinstance(chapter, str) or chapter not in {'logic','case','code','experiment','application','summary'}:
            raise ValueError('语音必须对应已有课程章节')
        section = clip['walkthrough_id']
        if section is not None and (not isinstance(section, str) or chapter != 'code' or section not in ids):
            raise ValueError('源码语音必须关联已有逐行片段')
        key = (chapter, section)
        if key in keys:
            raise ValueError('同一章节或源码片段不能重复配置语音')
        keys.add(key)
        require_text(clip['title'], '语音标题', 200)
        media_path(clip['src'], {'.m4a','.mp3','.wav'})
        duration = clip['duration_seconds']
        if type(duration) not in (int, float) or not 1 <= duration <= 1800:
            raise ValueError('语音时长需为实际的1到1800秒')
        require_text(clip['transcript'], '等价旁白文字', 12000)


def validate_lesson(lesson):
    if not isinstance(lesson, dict):
        raise ValueError('学习包必须是对象')
    if '_draft' in lesson:
        raise ValueError('这是待编辑草稿；完成真实备课并移除 _draft 标记后才能导入')
    expected = {'summary','mental_model','core_ideas','source_refs','questions','case_study','code_insight','experiment','application','recap_prompts'}
    if not expected <= set(lesson) or set(lesson) - expected - {'visual_lesson','audio_lesson'}:
        raise ValueError('学习包字段与规定结构不一致')
    if 'visual_lesson' in lesson:
        validate_visual_lesson(lesson['visual_lesson'])
    if isinstance(lesson.get('code_insight'), dict) and 'walkthroughs' in lesson['code_insight']:
        validate_code_walkthroughs(lesson['code_insight']['walkthroughs'])
    if 'audio_lesson' in lesson:
        code = lesson.get('code_insight')
        validate_audio_lesson(lesson['audio_lesson'], code.get('walkthroughs', []) if isinstance(code, dict) else [])
    for name in ('summary', 'mental_model'):
        require_text(lesson.get(name), name)
    for name in ('core_ideas', 'source_refs', 'questions'):
        if not isinstance(lesson.get(name), list) or not lesson[name]:
            raise ValueError(f'学习包缺少 {name}')
    for idea in lesson['core_ideas']:
        if not isinstance(idea, dict):
            raise ValueError('核心概念必须是对象')
        require_text(idea.get('title'), '核心概念标题')
        require_text(idea.get('explanation'), '核心概念解释')
    for ref in lesson['source_refs']:
        if not isinstance(ref, dict):
            raise ValueError('资料引用必须是对象')
        require_text(ref.get('title'), '资料标题')
        safe_url(require_text(ref.get('url'), '资料链接'))
    ids = set()
    for question in lesson['questions']:
        if not isinstance(question, dict):
            raise ValueError('回忆问题必须是对象')
        key = require_text(question.get('id'), '问题ID', 100)
        if key in ids:
            raise ValueError('问题ID不能重复')
        ids.add(key)
        require_text(question.get('prompt'), '回忆问题')
        require_text(question.get('answer'), '参考答案')
    for name, fields in {'case_study': ('title', 'scenario', 'steps'),
                         'code_insight': ('title', 'explanation', 'snippet', 'language', 'source_url'),
                         'experiment': ('title', 'steps', 'acceptance'),
                         'application': ('prompt', 'acceptance')}.items():
        item = lesson.get(name)
        if name == 'code_insight' and item is None:
            continue  # Non-code disciplines use cases, experiments and retrieval instead.
        if not isinstance(item, dict):
            raise ValueError(f'学习包缺少 {name}')
        for field in fields:
            value = item.get(field)
            if field in ('steps', 'acceptance'):
                if not isinstance(value, list) or not value:
                    raise ValueError(f'{name}.{field}必须是非空列表')
                for text in value:
                    require_text(text, field)
            elif field == 'source_url':
                safe_url(require_text(value, field))
            else:
                require_text(value, field)
    prompts = lesson.get('recap_prompts')
    if not isinstance(prompts, list) or not prompts:
        raise ValueError('缺少总结提示')
    for prompt in prompts:
        require_text(prompt, '总结提示')
    return lesson


def coach_plan(settings, tracks, reviews):
    """A small, explainable next step; viewing it never advances learning state."""
    due = [card for card in reviews if card['is_due']]
    review_limit = min(5, settings['review_minutes'], len(due))
    missing = []
    order = ('experiment', 'application', 'summary')
    for track in tracks:
        if track['lesson_status'] == 'ready' and track['status'] not in {'paused','mastered'}:
            present = {entry['kind'] for entry in track['evidence']}
            kinds = [kind for kind in order if kind not in present]
            if kinds:
                missing.append(dict(track_id=track['id'], title=track['title'], kinds=kinds))
    next_step = dict(kind='choose', track_id=None, title='选择一个想解决的问题',
                     message='可以从示例课程开始，也可以提交任意学科或项目的学习请求。', minutes=min(5, settings['daily_minutes']))
    if due:
        next_step = dict(kind='review', track_id=due[0]['track_id'], title='先闭卷回忆已学内容',
                         message=f'有 {len(due)} 道到期问题，先在预算内回答 {review_limit} 道，再查看参考答案。',
                         minutes=settings['review_minutes'])
    else:
        available = [track for track in tracks if track['status'] in ACTIVE]
        if not available:
            available = [track for track in tracks if track['status'] == 'exploring']
        if available:
            track = available[0]
            if track['lesson_status'] != 'ready':
                next_step = dict(kind='prepare', track_id=track['id'], title='先准备可信教材',
                    message='这条主线仍待备课；核对来源并完成教材后再开始实操，排队不代表已经学会。',
                    minutes=min(5, settings['daily_minutes']))
            else:
                item = next((entry for entry in missing if entry['track_id'] == track['id']), None)
                kind = item['kinds'][0] if item else 'learn'
                labels = {'experiment': ('做一个小实验', '先预测，再改变一个条件；记录实际观察和自己的解释。'),
                          'application': ('把知识用于真实问题', '换一个对象或约束，完成可检查的应用并记录结果。'),
                          'summary': ('用自己的话总结', '闭卷解释核心机制、一个限制和下次会怎样使用它。'),
                          'learn': ('留一点时间迁移和巩固', '已有学习记录仍需后续回忆检验；可再检查一个不同条件，不自动提升掌握状态。')}
                title, message = labels[kind]
                next_step = dict(kind=kind, track_id=track['id'], title=title, message=message,
                                 minutes=min(20, settings['daily_minutes']))
    return dict(daily_minutes=settings['daily_minutes'], review_minutes=settings['review_minutes'],
                due_count=len(due), review_limit=review_limit,
                active_track_count=sum(track['status'] in ACTIVE for track in tracks),
                missing_evidence=missing, next_step=next_step)


class Store:
    def __init__(self, path=None, seed=True):
        self.path = Path(path or ROOT / 'data' / 'learning.sqlite3')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript(SCHEMA)
            if 'was_due' not in {r['name'] for r in db.execute('PRAGMA table_info(review_events)')}:
                db.execute('ALTER TABLE review_events ADD COLUMN was_due INTEGER NOT NULL DEFAULT 0')
            columns = {r['name'] for r in db.execute('PRAGMA table_info(tracks)')}
            if 'subject' not in columns:
                db.execute("ALTER TABLE tracks ADD COLUMN subject TEXT NOT NULL DEFAULT 'technology'")
            if 'kind' not in columns:
                db.execute("ALTER TABLE tracks ADD COLUMN kind TEXT NOT NULL DEFAULT 'project'")
            if not self.meta(db, 'settings'):
                self.set_meta(db, 'settings', DEFAULTS)
            if seed:
                manifest = ROOT / 'content' / 'courses.json'
                if manifest.exists() or (ROOT / 'content' / 'brush.json').exists():
                    for course in load_courses()['courses']:
                        topic = course['topic_id'].strip().casefold()
                        existing = next((row for row in db.execute('SELECT id,topic_id,repo_full_name,subject,kind FROM tracks')
                            if row['id'] == course['id'] or row['topic_id'].strip().casefold() == topic or
                            (course['repo_full_name'] and row['repo_full_name'].casefold() == course['repo_full_name'].casefold())), None)
                        if existing:
                            if existing['subject'] == 'technology' and existing['kind'] == 'project':
                                db.execute('UPDATE tracks SET subject=?,kind=? WHERE id=?',
                                           (course['subject'], course['kind'], existing['id']))
                            continue  # Never overwrite imported lessons, state, evidence or review history.
                        lesson = validate_lesson(json.loads((ROOT / 'content' / course['lesson_file']).read_text(encoding='utf-8')))
                        validate_lesson_assets(lesson)
                        db.execute('INSERT INTO tracks(id,title,topic_id,repo_full_name,repo_url,status,lesson_status,lesson,created_at,progress_note,subject,kind) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                            (course['id'], course['title'], topic, course['repo_full_name'], course['repo_url'],
                             'exploring', 'ready', dump(lesson), stamp(),
                             '公开示例课程，可自由探索；尚未实操，不视为已掌握。', course['subject'], course['kind']))
                    self.set_meta(db, 'initialized', True)
            self.set_meta(db, 'schema_version', 2)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA journal_mode=WAL')
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def meta(db, key, default=None):
        row = db.execute('SELECT value FROM meta WHERE key=?', (key,)).fetchone()
        return json.loads(row['value']) if row else default

    @staticmethod
    def set_meta(db, key, value):
        db.execute('INSERT INTO meta VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, dump(value)))

    def settings(self, db):
        return DEFAULTS | self.meta(db, 'settings', {})

    @staticmethod
    def taxonomy():
        file = ROOT / 'content' / 'catalog.json'
        if file.exists():
            data = json.loads(file.read_text())
            return data if isinstance(data, dict) else {r['full_name']: r for r in data}
        return {}

    def import_snapshot(self, data):
        fetched = data.get('fetched_at_utc') or data.get('fetched_at')
        observed = parse_time(require_text(fetched, '榜单采集时间'))
        rows = data.get('repositories', [])
        if not isinstance(rows, list) or not rows:
            raise ValueError('仓库列表为空；保留原有缓存')
        if data.get('incomplete_results'):
            raise ValueError('GitHub 返回不完整搜索结果；保留原有缓存')
        taxonomy = self.taxonomy()
        taxonomy_by_id = {v['repo_id']: v for v in taxonomy.values() if v.get('repo_id') is not None}
        clean = []
        for raw in rows:
            if raw.get('archived') or raw.get('fork') or raw.get('stars', 0) < DEFAULTS['min_stars']:
                continue
            full_name = require_text(raw.get('full_name'), '仓库名', 200)
            mapping = taxonomy.get(full_name, taxonomy_by_id.get(int(raw['id']), {}))
            license_info = raw.get('license')
            license_name = license_info.get('spdx_id') if isinstance(license_info, dict) else license_info
            topics = raw.get('topics', [])
            kind = mapping.get('kind', 'collection' if any('awesome' in t for t in topics) else 'unknown')
            clean.append(dict(id=int(raw['id']), full_name=full_name,
                              html_url=safe_url(raw.get('html_url') or raw.get('url')),
                              description=raw.get('description') or '', stars=int(raw['stars']),
                              language=raw.get('language'), license=license_name,
                              license_status='needs-review' if not license_name or license_name == 'NOASSERTION' else 'identified',
                              kind=kind, topic_id=mapping.get('topic_id', 'repo:' + full_name.lower()),
                              topic_name=mapping.get('topic_name', full_name),
                              classification_pending=not bool(mapping),
                              learning_angle=mapping.get('learning_angle', ''),
                              pushed_at=raw.get('pushed_at'), topics=topics,
                              learned_core=False, delta_7d=None))
        if not clean:
            raise ValueError('没有符合门槛的结果；保留原有缓存')
        with self.connect() as db:
            db.execute('DELETE FROM repositories')
            for repo in clean:
                db.execute('INSERT INTO repositories VALUES(?,?,?)', (repo['id'], repo['full_name'], dump(repo)))
                db.execute('INSERT OR REPLACE INTO snapshots VALUES(?,?,?,?)',
                           (repo['id'], observed.date().isoformat(), repo['stars'], stamp(observed)))
            self.set_meta(db, 'discovery', dict(fetched_at=stamp(observed),
                total_eligible=data.get('total_count', len(clean)), cached_count=len(clean),
                search_query=data.get('search_query', 'stars:>=100000 archived:false fork:false'),
                search_url=data.get('search_url'), sort='stars', warning=None))
        return len(clean)

    def refresh(self):
        collected = []
        total = None
        search_url = None
        fetched = stamp()
        try:
            for page in range(1, 11):
                params = dict(q='stars:>=100000 archived:false fork:false', sort='stars', order='desc', per_page=100, page=page)
                url = 'https://api.github.com/search/repositories?' + urlencode(params)
                search_url = search_url or url
                request = Request(url, headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'LearningLoop/1.0'})
                with urlopen(request, timeout=20) as response:
                    payload = json.load(response)
                if payload.get('incomplete_results'):
                    raise ValueError('GitHub 搜索暂未返回完整结果')
                total = payload['total_count']
                if total > 1000:
                    raise ValueError('候选超过 GitHub 搜索的1000条上限，需要分段查询，未覆盖时保留缓存')
                items = payload['items']
                for item in items:
                    collected.append(dict(id=item['id'], full_name=item['full_name'], url=item['html_url'],
                        description=item.get('description'), stars=item['stargazers_count'],
                        language=item.get('language'), license=item.get('license'), topics=item.get('topics', []),
                        pushed_at=item.get('pushed_at'), archived=item['archived'], fork=item['fork']))
                if len(collected) >= total or not items:
                    break
            unique = {r['id']: r for r in collected}
            if len(unique) < (total or 0):
                raise ValueError('分页结果有重复或遗漏，未替换完整缓存，请稍后重试')
            self.import_snapshot(dict(fetched_at_utc=fetched, total_count=total, repositories=list(unique.values()),
                search_url=search_url, search_query='stars:>=100000 archived:false fork:false'))
        except (HTTPError, URLError, TimeoutError, ValueError, KeyError, OSError) as exc:
            reason = str(exc)[:400]
            with self.connect() as db:
                info = self.meta(db, 'discovery', {})
                info['warning'] = '更新失败，保留上次真实快照：' + reason
                self.set_meta(db, 'discovery', info)
            raise ValueError('GitHub 更新失败；已保留缓存。' + reason) from exc

    def state(self, at=None):
        current = at or now()
        with self.connect() as db:
            settings = self.settings(db)
            tracks = []
            for row in db.execute('SELECT * FROM tracks ORDER BY created_at DESC'):
                track = dict(row)
                track['lesson'] = json.loads(track['lesson']) if track['lesson'] else None
                track['evidence'] = [dict(r) for r in db.execute('SELECT * FROM evidence WHERE track_id=? ORDER BY created_at DESC', (track['id'],))]
                tracks.append(track)
            known = [dict(r) for r in db.execute('SELECT * FROM known_topics')]
            excluded_topics = {r['topic_id'] for r in known}
            excluded_topics |= {r['topic_id'] for r in tracks if r['status'] in ACTIVE | {'mastered'}}
            excluded_repos = {r['repo_full_name'] for r in tracks}
            repos = sorted((json.loads(r['data']) for r in db.execute('SELECT data FROM repositories')), key=lambda r: (-r['stars'], r['full_name']))
            candidates, excluded = [], 0
            info = self.meta(db, 'discovery', {})
            observed = parse_time(info['fetched_at']) if info.get('fetched_at') else current
            for repo in repos:
                if repo['topic_id'] in excluded_topics or repo['full_name'] in excluded_repos:
                    excluded += 1
                    continue
                baseline = db.execute('SELECT stars,observed_at FROM snapshots WHERE repo_id=? AND observed_at<=? AND observed_at>=? ORDER BY observed_at DESC LIMIT 1',
                    (repo['id'], stamp(observed - timedelta(days=7)), stamp(observed - timedelta(days=8)))).fetchone()
                if baseline:
                    repo['delta_7d'] = repo['stars'] - baseline['stars']
                    repo['baseline_at'] = baseline['observed_at']
                candidates.append(repo)
            all_candidates = candidates
            def distinct_topics(rows):
                seen = set()
                result = []
                for repo in rows:
                    if repo['topic_id'] not in seen:
                        seen.add(repo['topic_id'])
                        result.append(repo)
                return result
            software = distinct_topics([r for r in all_candidates if r['kind'] == 'software' and r['license'] in SOFTWARE_LICENSES])
            candidates = software[:settings['discovery_limit']]
            broader = distinct_topics([r for r in all_candidates if r['license_status'] == 'identified'])
            info |= dict(sort='stars', candidates=candidates, excluded_count=excluded,
                         broader_candidates=broader[:settings['discovery_limit']],
                         unclassified=[{k:r[k] for k in ('id','full_name','html_url','description','topics','license')} for r in repos if r.get('classification_pending', r['kind']=='unknown')],
                         available_after_filter=len(software), returned_count=len(candidates),
                         total_eligible=info.get('total_eligible', 0),
                         explanation='软件榜：十万 Star 起、已识别常见开源许可证，按累计 Star 排序；合并重复主线并排除已关注与已知主线。许可元数据不等于商用审查。近期增长需要至少7天真实快照。')
            reviews = []
            for row in db.execute('SELECT cards.*, tracks.title AS track_title, tracks.status AS track_status FROM cards JOIN tracks ON cards.track_id=tracks.id WHERE tracks.status != ? ORDER BY due_at', ('paused',)):
                card = dict(row)
                card['is_due'] = parse_time(card['due_at']) <= current
                reviews.append(card)
            return dict(settings=settings, discovery=info, tracks=tracks, reviews=reviews,
                coach=coach_plan(settings, tracks, reviews),
                review_summary=dict(due_count=sum(r['is_due'] for r in reviews)), known_topics=known,
                notifications=[dict(r) for r in db.execute('SELECT * FROM notifications ORDER BY created_at DESC LIMIT 20')],
                stats=dict(active_tracks=sum(t['status'] in ACTIVE for t in tracks),
                    mastered_tracks=sum(t['status'] == 'mastered' for t in tracks),
                    completed_reviews=db.execute('SELECT count(*) FROM review_events').fetchone()[0]),
                pending_jobs=[dict(r) for r in db.execute("SELECT * FROM jobs WHERE status IN ('queued','failed') ORDER BY created_at")],
                generated_at=stamp(current))

    def add_track(self, full_name):
        with self.connect() as db:
            if db.execute('SELECT 1 FROM tracks WHERE repo_full_name=?', (full_name,)).fetchone():
                raise ValueError('这个项目已在学习档案中')
            settings = self.settings(db)
            active = db.execute("SELECT count(*) FROM tracks WHERE status IN ('learning','practicing','applied')").fetchone()[0]
            if active >= settings['max_active_tracks']:
                raise ValueError('先完成或暂停当前主线，每次专注一条会更有效')
            row = db.execute('SELECT data FROM repositories WHERE full_name=?', (full_name,)).fetchone()
            if not row:
                raise ValueError('找不到该候选项目，请刷新榜单')
            repo = json.loads(row['data'])
            if db.execute('SELECT 1 FROM known_topics WHERE topic_id=?', (repo['topic_id'],)).fetchone():
                raise ValueError('这条核心主线已被标为已有基础')
            track_id = uid()
            db.execute('INSERT INTO tracks(id,title,topic_id,repo_full_name,repo_url,status,lesson_status,lesson,created_at,progress_note) VALUES(?,?,?,?,?,?,?,?,?,?)',
                (track_id, repo['topic_name'], repo['topic_id'], full_name, repo['html_url'],
                 'learning', 'queued', None, stamp(), '已选题，等待学习助手核对官方资料并准备学习包。'))
            db.execute('INSERT INTO jobs VALUES(?,?,?,?,?)', (uid(), track_id, 'queued', stamp(), None))
        return track_id

    def request_track(self, title, topic_id, subject, kind, repo_url=''):
        title = require_text(title, '学习主题', 200)
        topic_id = require_text(topic_id, '主线ID', 200).casefold()
        subject = require_text(subject, '学科', 100)
        if not isinstance(kind, str) or kind not in {'project','subject'}:
            raise ValueError('学习类型只能是 project 或 subject')
        repo_url = canonical_repo_url(repo_url)
        parsed = urlparse(repo_url)
        full_name = parsed.path.strip('/') if parsed.hostname == 'github.com' else ''
        with self.connect() as db:
            # Acquire the write lock before duplicate detection so concurrent clicks
            # cannot create two tracks/jobs for the same topic or public repository.
            db.execute('BEGIN IMMEDIATE')
            for row in db.execute('SELECT id,topic_id,repo_url FROM tracks'):
                same_topic = row['topic_id'].strip().casefold() == topic_id
                same_repo = bool(repo_url and row['repo_url'] and canonical_repo_url(row['repo_url']) == repo_url)
                if same_topic or same_repo:
                    return row['id']
            track_id = uid()
            db.execute('INSERT INTO tracks(id,title,topic_id,repo_full_name,repo_url,status,lesson_status,lesson,created_at,progress_note,subject,kind) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                (track_id, title, topic_id, full_name, repo_url, 'exploring', 'queued', None, stamp(),
                 '已提交学习问题，等待核实资料与备课；尚未学习或掌握。', subject, kind))
            db.execute('INSERT INTO jobs VALUES(?,?,?,?,?)', (uid(), track_id, 'queued', stamp(), None))
        return track_id

    def draft_lesson(self, track_id):
        with self.connect() as db:
            track = db.execute('SELECT * FROM tracks WHERE id=?', (track_id,)).fetchone()
            if not track:
                raise ValueError('找不到学习主线')
        return dict(_draft={'track_id': track_id, 'title': track['title'], 'subject': track['subject'],
                    'instruction': 'TODO：核实真实来源，完成教材和媒体后移除 _draft；本模板不是可导入的完成课程。'},
            summary='TODO：用真实问题说明本课输入、输出和能完成的事情。',
            mental_model='TODO：用一个准确类比解释机制并说明边界。',
            core_ideas=[dict(title='TODO：核心概念', explanation='TODO：解释因果和限制。')],
            source_refs=[], questions=[dict(id='core-recall', prompt='TODO：设计闭卷回忆问题。', answer='TODO：依据核实资料给出参考答案。')],
            case_study=dict(title='TODO：案例', scenario='TODO：具体条件', steps=['TODO：先预测，再检查结果。']),
            code_insight=None,
            experiment=dict(title='TODO：小实验', steps=['TODO：选择可观察的变量。'], acceptance=['TODO：说明什么实际证据才算完成。']),
            application=dict(prompt='TODO：把本课用于另一个真实问题。', acceptance=['TODO：可交付结果。']),
            recap_prompts=['TODO：不看教材解释机制、限制和可迁移的做法。'])

    def import_catalog(self, entries):
        if not isinstance(entries, dict):
            raise ValueError('分类输入必须是以仓库名为键的对象')
        catalog = self.taxonomy()
        validated = {}
        with self.connect() as db:
            for full_name, item in entries.items():
                if not isinstance(item, dict) or item.get('kind') not in {'software','learning-resource','collection','unknown'}:
                    raise ValueError('无效的仓库类型')
                row = db.execute('SELECT id,data FROM repositories WHERE full_name=?', (full_name,)).fetchone()
                if not row:
                    raise ValueError('只能分类已采集的真实仓库')
                mapping = dict(kind=item['kind'], topic_id=require_text(item.get('topic_id'),'主线ID',200),
                               topic_name=require_text(item.get('topic_name'),'主线名',200),repo_id=row['id'])
                validated[full_name] = mapping
                repo = json.loads(row['data'])
                repo.update({k:mapping[k] for k in ('kind','topic_id','topic_name')})
                repo['classification_pending'] = False
                db.execute('UPDATE repositories SET data=? WHERE id=?', (dump(repo), row['id']))
            catalog.update(validated)
            target = ROOT / 'content' / 'catalog.json'
            temporary = target.with_suffix('.tmp')
            temporary.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n')
            temporary.replace(target)

    def import_lesson(self, track_id, lesson):
        validate_lesson(lesson)
        validate_lesson_assets(lesson)
        with self.connect() as db:
            track = db.execute('SELECT * FROM tracks WHERE id=?', (track_id,)).fetchone()
            if not track:
                raise ValueError('找不到学习主线')
            db.execute('UPDATE tracks SET lesson=?,lesson_status=?,progress_note=? WHERE id=?',
                       (dump(lesson), 'ready', '学习包已准备；阅读完成不会自动变成已掌握。', track_id))
            db.execute('UPDATE jobs SET status=?,error=NULL WHERE track_id=?', ('done', track_id))
            # Existing recall history remains intact when teaching material is updated.
            if db.execute('SELECT 1 FROM evidence WHERE track_id=?', (track_id,)).fetchone():
                self.ensure_cards(db, track_id, lesson)
            db.execute('INSERT INTO notifications VALUES(?,?,?)', (uid(), f'「{track["title"]}」学习包已准备好', stamp()))

    @staticmethod
    def ensure_cards(db, track_id, lesson, at=None):
        for question in lesson['questions']:
            db.execute('INSERT INTO cards VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(track_id,question_key) DO UPDATE SET question=excluded.question,answer=excluded.answer',
                       (uid(), track_id, question['id'], question['prompt'], question['answer'],
                        stamp((at or now()) + timedelta(days=1)), 1, 0, 0))

    def add_evidence(self, track_id, kind, text, at=None):
        if kind not in {'experiment', 'application', 'summary'}:
            raise ValueError('不支持的学习记录类型')
        text = require_text(text, '请记录你的过程、结果或解释')
        with self.connect() as db:
            row = db.execute('SELECT * FROM tracks WHERE id=?', (track_id,)).fetchone()
            if not row:
                raise ValueError('找不到主线')
            if row['lesson_status'] != 'ready':
                raise ValueError('先等待学习包准备完成')
            if row['status'] == 'exploring':
                count = db.execute("SELECT count(*) FROM tracks WHERE status IN ('learning','practicing','applied')").fetchone()[0]
                if count >= self.settings(db)['max_active_tracks']:
                    raise ValueError('请先暂停当前主线，再开始这个实验')
                db.execute("UPDATE tracks SET status='learning' WHERE id=?", (track_id,))
            db.execute('INSERT INTO evidence VALUES(?,?,?,?,?)', (uid(), track_id, kind, text, stamp(at)))
            self.ensure_cards(db, track_id, json.loads(row['lesson']), at)

    def set_status(self, track_id, status):
        if status not in STATUSES:
            raise ValueError('无效的学习状态')
        with self.connect() as db:
            row = db.execute('SELECT * FROM tracks WHERE id=?', (track_id,)).fetchone()
            if not row:
                raise ValueError('找不到主线')
            if status in ACTIVE and row['status'] not in ACTIVE:
                count = db.execute("SELECT count(*) FROM tracks WHERE status IN ('learning','practicing','applied')").fetchone()[0]
                if count >= self.settings(db)['max_active_tracks']:
                    raise ValueError('请先暂停当前主线，每次只专注一条')
            evidence = {r['kind'] for r in db.execute('SELECT kind FROM evidence WHERE track_id=?', (track_id,))}
            if status == 'applied' and not {'experiment', 'application'} <= evidence:
                raise ValueError('先记录小实验和实际应用的结果，再标为已应用')
            if status == 'mastered':
                if not {'experiment', 'application', 'summary'} <= evidence:
                    raise ValueError('掌握需要实验、实际应用和自己的总结三类证据')
                cards = list(db.execute('SELECT * FROM cards WHERE track_id=?', (track_id,)))
                if not cards:
                    raise ValueError('请先完成间隔回忆')
                for card in cards:
                    latest = db.execute('SELECT rating FROM review_events WHERE card_id=? ORDER BY created_at DESC LIMIT 1', (card['id'],)).fetchone()
                    if card['repetitions'] < 2 or not latest or latest['rating'] not in {'good','easy'}:
                        raise ValueError('核心问题还需要成功间隔回忆；最近忘记或困难的问题应先巩固')
                    rows = db.execute("SELECT created_at FROM review_events WHERE card_id=? AND rating IN ('good','easy') AND was_due=1", (card['id'],))
                    days = {parse_time(r['created_at']).astimezone(LOCAL).date() for r in rows}
                    if len(days) < 2:
                        raise ValueError('每道核心问题至少需要在两个不同日期成功回忆；不能凭刚看过答案判定掌握')
            db.execute('UPDATE tracks SET status=? WHERE id=?', (status, track_id))

    def answer(self, card_id, rating, response, at=None):
        if rating not in {'again', 'hard', 'good', 'easy'}:
            raise ValueError('无效的复习评分')
        response = require_text(response, '先写出你的回忆，再查看答案并评分')
        current = at or now()
        with self.connect() as db:
            card = db.execute('SELECT * FROM cards WHERE id=?', (card_id,)).fetchone()
            if not card:
                raise ValueError('找不到复习卡')
            latest = db.execute('SELECT created_at FROM review_events WHERE card_id=? ORDER BY created_at DESC LIMIT 1', (card_id,)).fetchone()
            if latest and (current - parse_time(latest['created_at'])).total_seconds() < 60:
                raise ValueError('这次回答已记录，请稍后再练，避免重复点击改变复习计划')
            reps, lapses = card['repetitions'], card['lapses']
            due = parse_time(card['due_at'])
            if rating == 'again':
                reps, lapses, interval = 0, lapses + 1, 10 / 1440
            elif due > current:
                # Extra practice is useful but does not inflate spaced-success counters.
                interval = card['interval_days']
            elif rating == 'hard':
                interval = max(1, min(card['interval_days'] * 1.2, 3))
            else:
                reps = min(reps + (2 if rating == 'easy' else 1), len(INTERVALS) - 1)
                interval = INTERVALS[reps]
            next_due = due if due > current and rating != 'again' else current + timedelta(days=interval)
            db.execute('INSERT INTO review_events(id,card_id,rating,response,created_at,was_due) VALUES(?,?,?,?,?,?)',
                       (uid(), card_id, rating, response, stamp(current), int(due <= current)))
            db.execute('UPDATE cards SET due_at=?,interval_days=?,repetitions=?,lapses=? WHERE id=?',
                       (stamp(next_due), interval, reps, lapses, card_id))

    def mark_known(self, topic_id, topic_name):
        topic_id = require_text(topic_id, '主线ID', 200)
        topic_name = require_text(topic_name, '主线名称', 200)
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO known_topics VALUES(?,?,?,?)',
                       (topic_id, topic_name, 'user-reported', stamp()))

    def unmark_known(self, topic_id):
        with self.connect() as db:
            db.execute('DELETE FROM known_topics WHERE topic_id=?', (require_text(topic_id, '主线ID', 200),))

    def update_settings(self, values):
        allowed = {'daily_minutes', 'review_minutes', 'reminder_time'}
        if set(values) - allowed:
            raise ValueError('只能修改学习时长、复习时长和提醒时间')
        for key in ('daily_minutes', 'review_minutes'):
            if key in values and (type(values[key]) is not int or not 1 <= values[key] <= 180):
                raise ValueError('时长应在1到180分钟之间')
        if 'reminder_time' in values and not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', str(values['reminder_time'])):
            raise ValueError('提醒时间应为24小时制，例如20:00')
        with self.connect() as db:
            settings = self.settings(db)
            changed_time = 'reminder_time' in values and values['reminder_time'] != settings['reminder_time']
            settings.update(values)
            if changed_time:
                settings['schedule_sync_pending'] = True
            self.set_meta(db, 'settings', settings)

    def set_automation(self, automation_id):
        with self.connect() as db:
            settings = self.settings(db)
            settings.update(automation_enabled=True, automation_id=automation_id, schedule_sync_pending=False,
                            scheduled_reminder_time=settings['reminder_time'])
            self.set_meta(db, 'settings', settings)

    def daily(self, refresh=False, at=None):
        current = at or now()
        state = self.state(current)
        fetched = state['discovery'].get('fetched_at')
        if refresh and (not fetched or current - parse_time(fetched) >= timedelta(hours=24)):
            try:
                self.refresh()
            except ValueError:
                pass
            state = self.state(current)
        local_day = current.astimezone(LOCAL).date().isoformat()
        signature = [r['topic_id'] for r in state['discovery']['candidates']]
        with self.connect() as db:
            acknowledged = self.meta(db, 'last_daily_ack') == local_day
            last_signature = self.meta(db, 'last_candidate_signature', [])
            candidate_change = signature != last_signature and state['stats']['active_tracks'] == 0
        due = [r for r in state['reviews'] if r['is_due']]
        budget = max(1, state['settings']['review_minutes'])
        selected = due[:min(5, budget)]
        # Do not include reference answers in the reminder.
        public_cards = [{k: r[k] for k in ('id', 'track_id', 'track_title', 'question', 'due_at')} for r in selected]
        return dict(date=local_day, already_acknowledged=acknowledged, candidate_change=candidate_change,
                    should_notify=bool(selected or state['pending_jobs'] or candidate_change or state['discovery'].get('warning')) and not acknowledged,
                    due_total=len(due), recall_questions=public_cards, remaining_due=max(0, len(due)-len(selected)),
                    pending_jobs=state['pending_jobs'][:1], settings=state['settings'],
                    discovery=state['discovery'], instruction='用户先回忆；不要代答或自动评分。不因阅读自动标为掌握。')

    def acknowledge(self, date):
        datetime.strptime(date, '%Y-%m-%d')
        state = self.state()
        with self.connect() as db:
            self.set_meta(db, 'last_daily_ack', date)
            self.set_meta(db, 'last_candidate_signature', [r['topic_id'] for r in state['discovery']['candidates']])

    def export(self):
        with self.connect() as db:
            tables = ['meta','repositories','snapshots','tracks','evidence','known_topics','cards','review_events','jobs','notifications']
            return dict(schema_version=2, exported_at=stamp(), tables={t: [dict(r) for r in db.execute('SELECT * FROM ' + t)] for t in tables})


def serve(store, port):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def reply(self, payload, status=200, download=False):
            body = dump(payload).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            if download:
                self.send_header('Content-Disposition', 'attachment; filename="learning-loop-backup.json"')
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(body)

        def allowed_host(self):
            return self.headers.get('Host') in {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}

        def do_GET(self):
            if not self.allowed_host():
                return self.reply({'error': '只允许本机访问'}, 403)
            path = urlparse(self.path).path
            if path == '/api/state':
                return self.reply(store.state())
            if path == '/api/export':
                return self.reply(store.export(), download=True)
            if path == '/mobile':
                self.send_response(308)
                self.send_header('Location', '/mobile/')
                self.send_header('Content-Length', '0')
                self.end_headers()
                return
            mobile = path.startswith('/mobile/')
            if mobile:
                web_root = (ROOT / 'dist' / 'site').resolve()
                if not (web_root / 'index.html').is_file():
                    return self.reply({'error': '手机站尚未构建，请先运行 scripts/build_site.py'}, 404)
                target = web_root / ('index.html' if path == '/mobile/' else path[len('/mobile/'):])
            else:
                target = ROOT / 'web' / ('index.html' if path == '/' else path.lstrip('/'))
                web_root = (ROOT / 'web').resolve()
            if not target.resolve().is_relative_to(web_root) or not target.is_file():
                return self.reply({'error': '没有这个页面'}, 404)
            types = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8',
                     '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp',
                     '.mp4': 'video/mp4', '.webm': 'video/webm', '.vtt': 'text/vtt; charset=utf-8',
                     '.m4a': 'audio/mp4', '.mp3': 'audio/mpeg', '.wav': 'audio/wav'}
            if mobile:
                types.update({'.json': 'application/json; charset=utf-8', '.webmanifest': 'application/manifest+json',
                              '.txt': 'text/plain; charset=utf-8'})
            suffix = target.suffix.lower()
            if suffix not in types:
                return self.reply({'error': '不支持该文件类型'}, 404)
            size = target.stat().st_size
            try:
                selected = parse_byte_range(self.headers.get('Range'), size)
            except ValueError:
                self.send_response(416)
                self.send_header('Content-Range', f'bytes */{size}')
                self.send_header('Content-Length', '0')
                self.end_headers()
                return
            start, end = selected or (0, size - 1)
            self.send_response(206 if selected else 200)
            self.send_header('Content-Type', types[suffix])
            self.send_header('Content-Length', str(end - start + 1))
            self.send_header('Accept-Ranges', 'bytes')
            if selected:
                self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; media-src 'self'; frame-src 'self'; object-src 'none'; frame-ancestors 'self'; base-uri 'none'")
            self.end_headers()
            if self.command != 'HEAD':
                try:
                    with target.open('rb') as asset:
                        asset.seek(start)
                        remaining = end - start + 1
                        while remaining > 0:
                            chunk = asset.read(min(256 * 1024, remaining))
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                            remaining -= len(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    pass  # A media player may cancel an old range when seeking.

        def do_HEAD(self):
            if urlparse(self.path).path.startswith('/api/'):
                self.send_response(405)
                self.send_header('Content-Length', '0')
                self.end_headers()
            else:
                self.do_GET()

        def do_POST(self):
            origin = self.headers.get('Origin')
            expected = {f'http://127.0.0.1:{self.server.server_port}', f'http://localhost:{self.server.server_port}'}
            if not self.allowed_host() or (origin and origin not in expected):
                return self.reply({'error': '只允许本机页面修改学习记录'}, 403)
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                return self.reply({'error': '需要JSON请求'}, 415)
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 1024 * 1024:
                    raise ValueError('请求内容为空或过大')
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise ValueError('请求需要是对象')
                path = urlparse(self.path).path
                parts = path.strip('/').split('/')
                if path == '/api/tracks':
                    store.add_track(require_text(body.get('repo_full_name'), '项目名'))
                elif path == '/api/tracks/request':
                    if set(body) - {'title','topic_id','subject','kind','repo_url'}:
                        raise ValueError('学习请求包含未知字段')
                    track_id = store.request_track(body.get('title'), body.get('topic_id'), body.get('subject'), body.get('kind'), body.get('repo_url', ''))
                    result = store.state()
                    result['requested_track_id'] = track_id
                    return self.reply(result)
                elif len(parts) == 4 and parts[:2] == ['api','tracks'] and parts[3] == 'status':
                    store.set_status(parts[2], body.get('status'))
                elif len(parts) == 4 and parts[:2] == ['api','tracks'] and parts[3] == 'evidence':
                    store.add_evidence(parts[2], body.get('kind'), body.get('text'))
                elif len(parts) == 4 and parts[:2] == ['api','reviews'] and parts[3] == 'answer':
                    store.answer(parts[2], body.get('rating'), body.get('response'))
                elif path == '/api/settings':
                    store.update_settings(body)
                elif path == '/api/topics/known':
                    store.mark_known(body.get('topic_id'), body.get('topic_name'))
                elif path == '/api/topics/unknown':
                    store.unmark_known(body.get('topic_id'))
                elif path == '/api/discovery/refresh':
                    store.refresh()
                else:
                    return self.reply({'error': '没有这个操作'}, 404)
                self.reply(store.state())
            except (ValueError, TypeError, KeyError) as exc:
                self.reply({'error': str(exc)}, 400)
            except sqlite3.Error:
                self.reply({'error': '保存失败，请稍后重试；现有学习记录仍保留'}, 500)

    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    print(f'http://127.0.0.1:{server.server_port}/', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main():
    parser = argparse.ArgumentParser(description='Learning Loop 本地学习循环')
    parser.add_argument('--db', help='替代数据库，用于隔离测试和备份检查')
    commands = parser.add_subparsers(dest='command', required=True)
    init = commands.add_parser('init'); init.add_argument('--snapshot')
    commands.add_parser('state')
    commands.add_parser('refresh')
    daily = commands.add_parser('daily'); daily.add_argument('--refresh', action='store_true')
    ack = commands.add_parser('ack-daily'); ack.add_argument('--date', required=True)
    lesson = commands.add_parser('import-lesson'); lesson.add_argument('--track-id', required=True); lesson.add_argument('--file', required=True)
    validate = commands.add_parser('validate-lesson'); validate.add_argument('--file', required=True)
    commands.add_parser('list-courses')
    commands.add_parser('doctor')
    request = commands.add_parser('request-track')
    request.add_argument('--title', required=True); request.add_argument('--topic', required=True)
    request.add_argument('--subject', required=True); request.add_argument('--kind', choices=('project','subject'), required=True)
    request.add_argument('--repo-url', default='')
    draft = commands.add_parser('draft-lesson'); draft.add_argument('--track-id', required=True); draft.add_argument('--output', required=True)
    catalog = commands.add_parser('import-catalog'); catalog.add_argument('--file', required=True)
    export = commands.add_parser('export'); export.add_argument('--output')
    auto = commands.add_parser('set-automation'); auto.add_argument('--id', required=True)
    server = commands.add_parser('serve'); server.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    try:
        # Distribution checks must work without creating or migrating a ledger.
        if args.command == 'list-courses':
            print(dump(load_courses()))
            return 0
        if args.command == 'validate-lesson':
            content = validate_lesson(json.loads(Path(args.file).read_text(encoding='utf-8')))
            validate_lesson_assets(content)
            print(dump({'valid': True, 'file': str(Path(args.file).resolve()), 'database_accessed': False,
                        'media_check': 'exists-and-nonempty; decoding requires separate verification'}))
            return 0
        if args.command == 'doctor':
            report = doctor()
            print(dump(report))
            return 0 if report['ok'] else 1
        store = Store(args.db, seed=args.command != 'draft-lesson')
        if args.command == 'init':
            if args.snapshot:
                store.import_snapshot(json.loads(Path(args.snapshot).read_text()))
            print(dump({'initialized': True, 'database': str(store.path)}))
        elif args.command == 'state': print(dump(store.state()))
        elif args.command == 'refresh': store.refresh(); print(dump(store.state()['discovery']))
        elif args.command == 'daily': print(dump(store.daily(args.refresh)))
        elif args.command == 'ack-daily': store.acknowledge(args.date); print(dump({'acknowledged': args.date}))
        elif args.command == 'import-lesson':
            store.import_lesson(args.track_id, json.loads(Path(args.file).read_text()))
            print(dump({'imported': args.track_id}))
        elif args.command == 'request-track':
            track_id = store.request_track(args.title, args.topic, args.subject, args.kind, args.repo_url)
            print(dump({'track_id': track_id, 'instruction': '已加入或找到同一主线；请求不代表完成学习。'}))
        elif args.command == 'draft-lesson':
            content = store.draft_lesson(args.track_id)
            target = Path(args.output)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('x', encoding='utf-8') as output:
                output.write(json.dumps(content, ensure_ascii=False, indent=2) + '\n')
            print(dump({'draft_file': str(target.resolve()), 'track_id': args.track_id, 'ready': False}))
        elif args.command == 'import-catalog':
            store.import_catalog(json.loads(Path(args.file).read_text()))
            print(dump({'catalog_imported': True}))
        elif args.command == 'export':
            content = json.dumps(store.export(), ensure_ascii=False, indent=2)
            if args.output: Path(args.output).write_text(content + '\n')
            else: print(content)
        elif args.command == 'set-automation': store.set_automation(args.id); print(dump({'automation_id': args.id}))
        elif args.command == 'serve': serve(store, args.port)
    except (ValueError, OSError) as exc:
        print(dump({'error': str(exc)}), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
