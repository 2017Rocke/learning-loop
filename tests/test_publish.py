"""Public exports cannot read learner records or capture local authoring files."""
import importlib.util
from html.parser import HTMLParser
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urljoin, urlparse

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('build_site', ROOT / 'scripts' / 'build_site.py')
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


class HTMLAssets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        value = attrs.get('src') if tag in {'script', 'img', 'source', 'iframe'} else attrs.get('href') if tag == 'link' else None
        if value and not urlparse(value).scheme and not value.startswith('#'):
            self.paths.append(value)


class PublishTests(unittest.TestCase):
    def test_public_build_has_courses_and_assets_but_no_personal_files(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'site'
            with patch.object(publisher.app, 'Store', side_effect=AssertionError('must not read learner DB')):
                result = publisher.build(target)
            payload = json.loads((target / 'courses.json').read_text())
            self.assertGreaterEqual(len(payload['courses']), 2)
            self.assertFalse(result['private_data_included'])
            for course in payload['courses']:
                for media in publisher.referenced_media(course['lesson']):
                    self.assertGreater((target / media.lstrip('/')).stat().st_size, 0)
            names = [p.relative_to(target).as_posix() for p in target.rglob('*') if p.is_file()]
            self.assertFalse(any(p.startswith(('data/', 'docs/', 'content/')) for p in names))
            self.assertFalse(any('generation-record' in p or '.sqlite' in p for p in names))
            for path in target.rglob('*'):
                if path.suffix in {'.json', '.js', '.html', '.css', '.webmanifest'}:
                    text = path.read_text()
                    self.assertNotIn('/Users/', text)
                    self.assertNotIn('__PRECACHE_URLS__', text)
            for path in target.rglob('*.html'):
                parser = HTMLAssets()
                parser.feed(path.read_text())
                base = 'https://example.test/learning-loop/' + path.relative_to(target).as_posix()
                for link in parser.paths:
                    resolved = urlparse(urljoin(base, link)).path
                    self.assertTrue(resolved.startswith('/learning-loop/'), link)
                    self.assertTrue((target / resolved[len('/learning-loop/'):]).is_file(), link)
            manifest = json.loads((target / 'manifest.webmanifest').read_text())
            self.assertEqual(manifest['scope'], './')
            for icon in manifest['icons']:
                self.assertTrue((target / icon['src']).is_file(), icon['src'])
            self.assertEqual(result['version'], publisher.build(target)['version'])

    def test_rejects_source_and_unowned_destination(self):
        with self.assertRaises(ValueError):
            publisher.build(ROOT / 'web')
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            existing = target / 'my-file.txt'
            existing.write_text('keep me')
            with self.assertRaises(ValueError):
                publisher.build(target)
            self.assertEqual(existing.read_text(), 'keep me')

    def test_invalid_course_does_not_destroy_previous_build(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'site'
            publisher.build(target)
            before = (target / 'courses.json').read_bytes()
            with patch.object(publisher.app, 'load_courses', side_effect=ValueError('invalid course')):
                with self.assertRaises(ValueError):
                    publisher.build(target)
            self.assertEqual(before, (target / 'courses.json').read_bytes())


if __name__ == '__main__':
    unittest.main()
