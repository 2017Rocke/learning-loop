#!/usr/bin/env python3
"""Publish data-only course updates and prepare trusted Android bundled assets.

Python standard library only. No private ledger, credentials, or executable code
enters the downloadable update ZIP. The APK's UI changes require a new APK.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_site

MARKER = '.learning-loop-content'
SUFFIXES = {'.svg', '.png', '.jpg', '.jpeg', '.webp', '.m4a', '.mp3', '.wav', '.mp4', '.webm', '.vtt'}
MAX_BYTES = 512 * 1024 * 1024


def digest(data):
    return hashlib.sha256(data).hexdigest()


def validate_svg(data):
    """SVG media is illustrative data: no scripting or external resource loads."""
    if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
        raise ValueError('SVG 不允许文档类型或外部实体')
    if re.search(br'<\?(?!xml(?:\s|\?))', data, re.I):
        raise ValueError('SVG 不允许处理指令')
    tree = ET.fromstring(data)
    allowed = {'svg', 'g', 'defs', 'rect', 'circle', 'ellipse', 'path', 'line', 'polyline',
               'polygon', 'text', 'tspan', 'title', 'desc', 'linearGradient', 'radialGradient',
               'stop', 'clipPath', 'mask', 'marker', 'use'}
    if tree.tag != '{http://www.w3.org/2000/svg}svg':
        raise ValueError('SVG 根元素与命名空间不正确')
    nodes = list(tree.iter())
    if len(nodes) > 20000 or len(data) > 8 * 1024 * 1024:
        raise ValueError('SVG 图像过于复杂')
    def depth(element, value=0):
        if value > 60:
            raise ValueError('SVG 图像层级过深')
        for child in element:
            depth(child, value + 1)
    depth(tree)
    for element in nodes:
        tag = element.tag.removeprefix('{http://www.w3.org/2000/svg}')
        if not element.tag.startswith('{http://www.w3.org/2000/svg}') or tag not in allowed:
            raise ValueError('SVG 只能包含静态原创图形')
        for key, value in element.attrib.items():
            name = key.rsplit('}', 1)[-1].lower()
            if name.startswith('on') or name in {'style', 'base'} or (name == 'href' and not re.fullmatch(r'#[A-Za-z0-9_.-]+', value)):
                raise ValueError('SVG 不允许事件或外部链接')
            if 'url' in value.lower() and not re.fullmatch(r'url\(#[A-Za-z0-9_.-]+\)', value):
                raise ValueError('SVG 不允许外部资源引用')


def destination(path, marker, forbidden):
    raw = Path(path).absolute()
    if raw.is_symlink():
        raise ValueError('输出目录不能为符号链接')
    target = raw.resolve()
    if target == ROOT or ROOT.is_relative_to(target) or any(target == p or target.is_relative_to(p) for p in forbidden):
        raise ValueError('输出路径不能覆盖源码或私人数据')
    if target.exists() and (not target.is_dir() or (any(target.iterdir()) and not (target / marker).is_file())):
        raise ValueError('只能覆盖已标识的构建目录，请指定新的空目录')
    return target


def replace_tree(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.learning-loop-stage-', dir=target.parent) as temporary:
        stage = Path(temporary) / 'new'
        shutil.copytree(source, stage)
        previous = Path(temporary) / 'old'
        if target.exists():
            target.rename(previous)
        try:
            stage.rename(target)
        except OSError:
            if previous.exists():
                previous.rename(target)
            raise


def build(output=None, assets=None):
    output = destination(output or ROOT / 'dist' / 'android-content', MARKER,
                         [ROOT / 'content', ROOT / 'web', ROOT / 'data', ROOT / 'android'])
    asset_target = None
    if assets:
        asset_target = Path(assets).absolute().resolve()
        expected = ROOT / 'android' / 'app' / 'src' / 'main' / 'assets' / 'site'
        if asset_target != expected.resolve():
            raise ValueError('--assets 仅可写入 android/app/src/main/assets/site')
        asset_target = destination(assets, build_site.MARKER, [ROOT / 'content', ROOT / 'web', ROOT / 'data'])
    reminder = json.loads((ROOT / 'content' / 'reminder.json').read_text(encoding='utf-8'))
    if (not isinstance(reminder, dict) or set(reminder) != {'time', 'minutes'} or
            not isinstance(reminder['time'], str) or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', reminder['time']) or
            type(reminder['minutes']) is not int or not 1 <= reminder['minutes'] <= 60):
        raise ValueError('提醒配置必须包含有效 time(HH:MM) 与 minutes(1~60)')
    with tempfile.TemporaryDirectory(prefix='learning-loop-content-') as temporary:
        temp = Path(temporary)
        site = temp / 'site'
        build_site.build(site)
        course_data = json.loads((site / 'courses.json').read_text(encoding='utf-8'))
        paths = [site / 'courses.json'] + sorted(p for p in (site / 'media').rglob('*') if p.is_file())
        files = []
        for path in paths:
            name = path.relative_to(site).as_posix()
            if len(name) > 500 or not all(re.fullmatch(r'[A-Za-z0-9_-][A-Za-z0-9._-]*', part) for part in name.split('/')):
                raise ValueError('安卓资源文件名仅支持英文字母、数字、下划线、点与横线')
            if name != 'courses.json' and (not name.startswith('media/') or path.suffix not in SUFFIXES):
                raise ValueError('更新包只能包含课程数据及允许的媒体文件')
            data = path.read_bytes()
            if name == 'courses.json' and len(data) > 8 * 1024 * 1024:
                raise ValueError('课程JSON超过客户端8MB上限')
            if path.suffix == '.svg':
                validate_svg(data)
            files.append(dict(path=name, sha256=digest(data), size=len(data)))
        if len(files) > 2000 or sum(item['size'] for item in files) > MAX_BYTES:
            raise ValueError('课程包超过当前客户端支持的资源上限')
        needs_practice_ui = any(((course['lesson'].get('visual_lesson') or {}).get('interactive') or {}).get('kind')
                               in {'bayes-counts', 'voice-ab'} for course in course_data['courses'])
        basis = dict(schema_version=1, min_app_version=4 if needs_practice_ui else 1, files=files,
                     course_count=len(course_data['courses']), reminder=reminder)
        version = digest(json.dumps(basis, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8'))
        release = temp / 'release'
        release.mkdir()
        archive = release / ('courses-' + version + '.zip')
        # Media is already compressed. STORE avoids zlib-version-dependent bytes:
        # one content version always has one immutable archive hash on every OS.
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_STORED) as package:
            for path in paths:
                info = zipfile.ZipInfo(path.relative_to(site).as_posix(), date_time=(2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_STORED
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                package.writestr(info, path.read_bytes())
        manifest = dict(basis, version=version,
                        archive=dict(name=archive.name, sha256=digest(archive.read_bytes()), size=archive.stat().st_size))
        manifest_text = json.dumps(manifest, ensure_ascii=False, indent=2) + '\n'
        if len(manifest_text.encode('utf-8')) > 2 * 1024 * 1024:
            raise ValueError('版本清单超过客户端2MB上限')
        (release / 'manifest.json').write_text(manifest_text, encoding='utf-8')
        (release / MARKER).write_text(version + '\n', encoding='utf-8')
        # Included in the APK so the bundled courses have the same version identity.
        (site / 'content-manifest.json').write_text(manifest_text, encoding='utf-8')
        replace_tree(release, output)
        if asset_target:
            replace_tree(site, asset_target)
        return dict(output=str(output), version=version, archive=archive.name,
                    courses=manifest['course_count'], files=len(files), bytes=manifest['archive']['size'],
                    assets=str(asset_target) if asset_target else None, private_data_included=False)


def main():
    parser = argparse.ArgumentParser(description='制作安卓只含课程数据的更新包，或准备APK内置课程')
    parser.add_argument('--output')
    parser.add_argument('--assets')
    args = parser.parse_args()
    try:
        print(json.dumps(build(args.output, args.assets), ensure_ascii=False))
    except (OSError, ValueError, KeyError, ET.ParseError) as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
