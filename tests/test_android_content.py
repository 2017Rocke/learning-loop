import importlib.util
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('android_content', ROOT / 'scripts/build_android_content.py')
content = importlib.util.module_from_spec(spec)
spec.loader.exec_module(content)


class AndroidContentTests(unittest.TestCase):
    def test_package_is_deterministic_data_only_and_every_byte_is_hashed(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / 'feed'
            with patch.object(content.build_site.app, 'Store', side_effect=AssertionError('No private DB')):
                result = content.build(target)
            manifest = json.loads((target / 'manifest.json').read_text())
            # Older clients reject these new experiment kinds. The small manifest
            # must ask for a compatible APK before offering the content download.
            self.assertEqual(manifest['min_app_version'], 4)
            archive = target / manifest['archive']['name']
            self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(), manifest['archive']['sha256'])
            self.assertEqual(archive.stat().st_size, manifest['archive']['size'])
            with zipfile.ZipFile(archive) as package:
                self.assertEqual(set(package.namelist()), {item['path'] for item in manifest['files']})
                for item in manifest['files']:
                    self.assertTrue(item['path'] == 'courses.json' or item['path'].startswith('media/'))
                    self.assertNotIn(Path(item['path']).suffix, {'.js', '.html', '.sqlite3', '.py'})
                    data = package.read(item['path'])
                    self.assertEqual(len(data), item['size'])
                    self.assertEqual(hashlib.sha256(data).hexdigest(), item['sha256'])
                actual_courses = json.loads(package.read('courses.json'))['courses']
                expected_courses = []
                for entry in content.build_site.app.load_courses()['courses']:
                    course = {key: value for key, value in entry.items() if key != 'lesson_file'}
                    course['lesson'] = json.loads((ROOT / 'content' / entry['lesson_file']).read_text())
                    expected_courses.append(course)
                self.assertEqual(actual_courses, expected_courses)
            before = (target / 'manifest.json').read_bytes()
            self.assertEqual(result['version'], content.build(target)['version'])
            self.assertEqual(before, (target / 'manifest.json').read_bytes())

    def test_invalid_reminder_and_unsafe_assets_do_not_overwrite_sources(self):
        with self.assertRaises(ValueError):
            content.build(ROOT / 'content')
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            (target / 'keep.txt').write_text('keep')
            with self.assertRaises(ValueError):
                content.build(target)
            self.assertEqual((target / 'keep.txt').read_text(), 'keep')
            with self.assertRaises(ValueError):
                content.build(target / 'feed', target / 'assets')

    def test_svg_rejects_scripts_external_resources_and_events(self):
        for data in [b'<svg><script>bad()</script></svg>', b'<svg onload="bad()"/>',
                     b'<svg><image href="https://example.test/a.png"/></svg>',
                     b'<svg><path fill="url(https://example.test)"/></svg>']:
            with self.assertRaises(ValueError):
                content.validate_svg(data)
        content.validate_svg(b'<svg xmlns="http://www.w3.org/2000/svg"><path fill="url(#gradient)" d="M0 0"/></svg>')


if __name__ == '__main__':
    unittest.main()
