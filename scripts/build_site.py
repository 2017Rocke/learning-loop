#!/usr/bin/env python3
"""Build a portable, public course PWA without opening the personal database.

Only the explicit course catalog, referenced media, labs, and mobile runtime are
published. Staging protects a previous working build when validation fails.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import learning_loop as app

MARKER = '.learning-loop-site'


def referenced_media(lesson):
    visual = lesson.get('visual_lesson') or {}
    paths = {step['image'] for step in visual.get('steps', [])}
    if visual.get('video'):
        paths.update(visual['video'][key] for key in ('src', 'poster', 'captions'))
    for clip in (lesson.get('audio_lesson') or {}).get('clips', []):
        paths.add(clip['src'])
    return sorted(paths)


def copy_public(source, target, allowed_root):
    if source.is_symlink() or not source.resolve().is_relative_to(allowed_root.resolve()):
        raise ValueError('发布内容不允许通过符号链接引用其他目录')
    if not source.is_file() or source.stat().st_size == 0:
        raise ValueError('缺少非空发布文件：' + str(source.relative_to(ROOT)))
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def build(output):
    raw_output = Path(output).absolute()
    if raw_output.is_symlink():
        raise ValueError('输出目录不能是符号链接')
    output = raw_output.resolve()
    # A build may only replace its own marked directory, never source or user files.
    if output == ROOT or ROOT.is_relative_to(output) or output.is_relative_to(ROOT / 'web') or output.is_relative_to(ROOT / 'content') or output.is_relative_to(ROOT / 'data'):
        raise ValueError('输出目录不能覆盖项目源码或学习档案')
    if output.exists() and (not output.is_dir() or
            (any(output.iterdir()) and not (output / MARKER).is_file())):
        raise ValueError('非空输出目录不是本站点构建产物，请选择空目录')
    catalog = app.load_courses()
    courses = []
    for entry in catalog['courses']:
        lesson_path = ROOT / 'content' / entry['lesson_file']
        lesson = app.validate_lesson(json.loads(lesson_path.read_text(encoding='utf-8')))
        app.validate_lesson_assets(lesson)
        course = {key: value for key, value in entry.items() if key != 'lesson_file'}
        course['lesson'] = lesson
        courses.append(course)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.learning-loop-build-', dir=output.parent) as temporary:
        stage = Path(temporary) / 'site'
        stage.mkdir()
        mobile = ROOT / 'web' / 'mobile'
        for source in sorted(mobile.rglob('*')):
            if source.is_dir():
                continue
            if source.suffix not in {'.html', '.js', '.css', '.json', '.webmanifest', '.svg', '.png'}:
                continue
            copy_public(source, stage / source.relative_to(mobile), mobile)
        for name in ('index.html', 'app.js', 'style.css', 'manifest.webmanifest', 'sw.js'):
            if not (stage / name).is_file():
                raise ValueError('手机端运行文件缺失：' + name)
        for name in ('lesson-visuals.js', 'lesson-visuals.css'):
            copy_public(ROOT / 'web' / name, stage / name, ROOT / 'web')
        credits = [(name, (ROOT / name).read_text(encoding='utf-8'))
                   for name in ('THIRD_PARTY_NOTICES.md', 'LICENSE')]
        for license_path in sorted((ROOT / 'licenses').glob('*.txt')):
            copy_public(license_path, stage / 'licenses' / license_path.name, ROOT / 'licenses')
            credits.append((license_path.name, license_path.read_text(encoding='utf-8')))
        body = ''.join('<h2>' + html.escape(name) + '</h2><pre>' + html.escape(content) + '</pre>'
                       for name, content in credits)
        (stage / 'credits.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1"><title>来源与许可</title>'
            '<style>body{max-width:850px;margin:2rem auto;padding:1rem;font:16px/1.6 system-ui}'
            'pre{white-space:pre-wrap;overflow-wrap:anywhere}a{color:#2d654b}</style>'
            '<a href="./#settings">← 返回学习应用</a><h1>来源与许可</h1>' + body + '</html>', encoding='utf-8')
        for course in courses:
            for path in referenced_media(course['lesson']):
                relative = path.lstrip('/')
                copy_public(ROOT / 'web' / relative, stage / relative, ROOT / 'web' / 'media')
        lab = ROOT / 'web' / 'lab'
        for source in sorted(lab.rglob('*')):
            if source.is_file() and source.suffix in {'.html', '.js', '.css', '.svg'}:
                copy_public(source, stage / 'lab' / source.relative_to(lab), lab)
        (stage / 'courses.json').write_text(json.dumps({'schema_version': 1, 'courses': courses},
            ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        (stage / '.nojekyll').write_text('', encoding='utf-8')
        payload = sorted(p for p in stage.rglob('*') if p.is_file() and p.name != 'sw.js')
        digest = hashlib.sha256()
        for path in payload:
            digest.update(path.relative_to(stage).as_posix().encode())
            digest.update(path.read_bytes())
        # Include the worker template so worker fixes invalidate old caches too.
        worker = (stage / 'sw.js').read_text(encoding='utf-8')
        if '__CACHE_VERSION__' not in worker or '__PRECACHE_URLS__' not in worker:
            raise ValueError('Service worker 缺少构建占位符')
        digest.update(worker.encode())
        version = digest.hexdigest()[:20]
        assets = ['./'] + ['./' + p.relative_to(stage).as_posix() for p in payload if p.name != '.nojekyll']
        worker = worker.replace('__CACHE_VERSION__', json.dumps(version)).replace('__PRECACHE_URLS__', json.dumps(assets, ensure_ascii=False))
        (stage / 'sw.js').write_text(worker, encoding='utf-8')
        (stage / MARKER).write_text(version + '\n', encoding='utf-8')
        file_count = sum(1 for p in stage.rglob('*') if p.is_file())
        size = sum(p.stat().st_size for p in stage.rglob('*') if p.is_file())
        previous = Path(temporary) / 'previous'
        if output.exists():
            output.rename(previous)
        try:
            stage.rename(output)
        except OSError:
            if previous.exists():
                previous.rename(output)
            raise
    return {'output': str(output), 'courses': len(courses), 'files': file_count,
            'bytes': size, 'version': version, 'private_data_included': False}


def main():
    parser = argparse.ArgumentParser(description='将已登记课程构建为可部署的手机离线网页 App')
    parser.add_argument('--output', default=str(ROOT / 'dist' / 'site'))
    args = parser.parse_args()
    try:
        print(json.dumps(build(args.output), ensure_ascii=False))
    except (ValueError, OSError, KeyError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
