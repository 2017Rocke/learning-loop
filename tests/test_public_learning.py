"""Reusable course manifests, arbitrary subjects, and migration without personal data."""
from copy import deepcopy
from datetime import timedelta
from io import BytesIO, StringIO
import json
from pathlib import Path
import runpy
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import learning_loop as ll
from test_learning_loop import lesson_fixture, START


def course_fixture(course_id='brush-intro', subject='technology', kind='project'):
    project = kind == 'project'
    return dict(id=course_id, title='高斯溅射' if project else '观察植物细胞',
                topic_id='gaussian-splatting' if project else 'cell-structure',
                subject=subject, kind=kind,
                repo_full_name='ArthurBrussee/brush' if project else '',
                repo_url='https://github.com/ArthurBrussee/brush' if project else '',
                lesson_file=course_id + '.json')


class PublicLearningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'content').mkdir()
        self.root_patch = patch.object(ll, 'ROOT', self.root)
        self.root_patch.start(); self.addCleanup(self.root_patch.stop)
        clock = patch.object(ll, 'now', return_value=START)
        clock.start(); self.addCleanup(clock.stop)
        network = patch.object(ll, 'urlopen', side_effect=AssertionError('No network expected'))
        network.start(); self.addCleanup(network.stop)
        self.db = self.root / 'private.sqlite3'

    def manifest(self, courses):
        data = dict(schema_version=1, courses=courses)
        (self.root / 'content/courses.json').write_text(json.dumps(data))
        for course in courses:
            if not (self.root / 'content' / course['lesson_file']).exists():
                lesson = lesson_fixture()
                if course['kind'] == 'subject':
                    lesson['code_insight'] = None
                (self.root / 'content' / course['lesson_file']).write_text(json.dumps(lesson))
        return data

    def test_course_manifest_seeds_multiple_disciplines_without_learning_claims(self):
        self.manifest([course_fixture(), course_fixture('biology', 'biology', 'subject')])
        store = ll.Store(self.db)
        state = store.state(START)
        self.assertEqual({t['subject'] for t in state['tracks']}, {'technology','biology'})
        self.assertEqual({t['kind'] for t in state['tracks']}, {'project','subject'})
        self.assertTrue(all(t['status'] == 'exploring' and t['lesson_status'] == 'ready' for t in state['tracks']))
        self.assertEqual(state['reviews'], [])
        self.assertEqual(state['pending_jobs'], [])
        self.assertEqual(state['stats']['mastered_tracks'], 0)

    def test_manifest_expansion_does_not_replace_existing_material_or_history(self):
        first = course_fixture()
        self.manifest([first])
        store = ll.Store(self.db)
        updated = lesson_fixture(); updated['summary'] = '用户已有的经过核实的教材版本。'
        store.import_lesson(first['id'], updated)
        store.add_evidence(first['id'], 'experiment', '我改变变量并记录观察结果。', at=START)
        card = store.state(START)['reviews'][0]
        store.answer(card['id'], 'good', '我能闭卷解释这个机制。', at=START + timedelta(days=1))
        before = store.export()['tables']
        self.manifest([first, course_fixture('biology', 'biology', 'subject')])
        reopened = ll.Store(self.db)
        after = reopened.export()['tables']
        for name in ('evidence','cards','review_events'):
            self.assertEqual(before[name], after[name])
        old_track = next(t for t in reopened.state()['tracks'] if t['id'] == first['id'])
        self.assertEqual(old_track['lesson'], updated)
        self.assertEqual(old_track['status'], 'learning')
        self.assertEqual(len(after['tracks']), 2)

    def test_previous_brush_install_without_manifest_still_opens(self):
        (self.root / 'content/brush.json').write_text(json.dumps(lesson_fixture()))
        store = ll.Store(self.db)
        self.assertEqual(store.state()['tracks'][0]['id'], 'brush-intro')
        self.assertEqual(len(ll.Store(self.db).state()['tracks']), 1)

    def test_sample_subject_migration_keeps_user_material_and_custom_metadata(self):
        first = course_fixture()
        self.manifest([first])
        store = ll.Store(self.db)
        before = store.state()['tracks'][0]
        first['subject'] = 'computer-science'
        self.manifest([first])
        after = ll.Store(self.db).state()['tracks'][0]
        self.assertEqual(after['subject'], 'computer-science')
        for field in ('lesson','status','evidence','progress_note'):
            self.assertEqual(before[field], after[field])
        first['subject'] = 'another-discipline'
        self.manifest([first])
        self.assertEqual(ll.Store(self.db).state()['tracks'][0]['subject'],'computer-science')

    def test_corrected_recall_text_updates_without_rescheduling_or_erasing_history(self):
        store = ll.Store(self.db, seed=False)
        track = store.request_track('细胞结构','cells','biology','subject')
        lesson = dict(lesson_fixture(), code_insight=None)
        store.import_lesson(track,lesson)
        store.add_evidence(track,'experiment','我记录了实际观察。',at=START)
        card = store.state()['reviews'][0]
        store.answer(card['id'],'good','我能够闭卷说明结构。',at=START+timedelta(days=1))
        before = store.export()['tables']
        lesson['questions'][0].update(prompt='修正后的明确问题？',answer='依据新证据修正的参考答案。')
        store.import_lesson(track,lesson)
        after = store.export()['tables']
        old,new = before['cards'][0],after['cards'][0]
        self.assertEqual(new['question'],'修正后的明确问题？')
        self.assertEqual(new['answer'],'依据新证据修正的参考答案。')
        for field in ('id','due_at','interval_days','repetitions','lapses'):
            self.assertEqual(old[field],new[field])
        self.assertEqual(before['review_events'],after['review_events'])
        self.assertEqual(before['evidence'],after['evidence'])

    def test_catalog_rejects_duplicates_unknown_fields_and_paths(self):
        valid = self.manifest([course_fixture()])
        changes = [dict(schema_version=True), dict(schema_version=2), dict(extra=True),
                   dict(courses=[course_fixture(), course_fixture()])]
        for change in changes:
            data = deepcopy(valid); data.update(change)
            (self.root / 'content/courses.json').write_text(json.dumps(data))
            with self.subTest(change=change), self.assertRaises(ValueError):
                ll.load_courses()
        for path in ('../private.json','/tmp/private.json','%2e%2e/private.json','dir\\private.json'):
            data = deepcopy(valid); data['courses'][0]['lesson_file'] = path
            (self.root / 'content/courses.json').write_text(json.dumps(data))
            with self.subTest(path=path), self.assertRaises(ValueError):
                ll.load_courses()
        private = self.root / 'private.json'; private.write_text('{}')
        (self.root / 'content/outside.json').symlink_to(private)
        valid['courses'][0]['lesson_file'] = 'outside.json'
        (self.root / 'content/courses.json').write_text(json.dumps(valid))
        with self.assertRaises(ValueError): ll.load_courses()

    def test_legacy_track_schema_migrates_without_rewriting_records(self):
        with sqlite3.connect(self.db) as db:
            db.execute('CREATE TABLE tracks(id TEXT PRIMARY KEY,title TEXT NOT NULL,topic_id TEXT NOT NULL,repo_full_name TEXT NOT NULL,repo_url TEXT NOT NULL,status TEXT NOT NULL,lesson_status TEXT NOT NULL,lesson TEXT,created_at TEXT NOT NULL,progress_note TEXT NOT NULL)')
            original = ('legacy','原有主线','existing-topic','','','practicing','ready',ll.dump(lesson_fixture()),ll.stamp(START),'保留这份用户说明')
            db.execute('INSERT INTO tracks VALUES(?,?,?,?,?,?,?,?,?,?)', original)
        store = ll.Store(self.db, seed=False)
        with store.connect() as db:
            row = db.execute('SELECT * FROM tracks').fetchone()
            self.assertEqual(tuple(row)[:10], original)
            self.assertEqual((row['subject'],row['kind']), ('technology','project'))
        self.assertEqual(len(ll.Store(self.db, seed=False).state()['tracks']), 1)

    def test_request_any_subject_or_small_project_deduplicates_without_reset(self):
        store = ll.Store(self.db, seed=False)
        subject = store.request_track('植物细胞', ' BIOLOGY-CELL ', 'biology', 'subject')
        project = store.request_track('很小的项目', 'tiny-project', 'computing', 'project', 'https://github.com/Example/Tiny.git/')
        self.assertEqual(store.request_track('再次请求', 'biology-cell', 'other', 'subject'), subject)
        self.assertEqual(store.request_track('同仓库', 'another-topic', 'computing', 'project', 'https://github.com/example/tiny'), project)
        state = store.state()
        self.assertEqual(len(state['tracks']), 2)
        self.assertEqual(len(state['pending_jobs']), 2)
        self.assertTrue(all(t['status'] == 'exploring' and t['lesson_status'] == 'queued' for t in state['tracks']))
        self.assertEqual(state['stats']['active_tracks'], 0)
        self.assertEqual(state['known_topics'], [])
        self.assertEqual(state['reviews'], [])
        store.import_lesson(subject, dict(lesson_fixture(), code_insight=None))
        store.add_evidence(subject, 'experiment', '我已观察并描述两个细胞的区别。', at=START)
        before = store.export()['tables']
        self.assertEqual(store.request_track('重复', 'biology-cell', 'biology', 'subject'), subject)
        after = store.export()['tables']
        for name in ('tracks','evidence','cards','jobs'):
            self.assertEqual(before[name], after[name])

    def test_invalid_requests_never_create_jobs_or_tracks(self):
        store = ll.Store(self.db, seed=False)
        for change in [dict(title=''),dict(topic_id=''),dict(subject=''),dict(kind='course'),dict(kind=[]),
                       dict(repo_url='http://github.com/example/repo'),dict(repo_url='https://github.com/example/repo/issues')]:
            args = dict(title='主题',topic_id='topic',subject='biology',kind='subject',repo_url=''); args.update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                store.request_track(**args)
        self.assertEqual(store.state()['tracks'], [])
        self.assertEqual(store.state()['pending_jobs'], [])

    def test_noncode_lesson_still_requires_sources_and_real_tasks(self):
        lesson = dict(lesson_fixture(), code_insight=None)
        ll.validate_lesson(lesson)
        for name, value in [('source_refs', []), ('experiment', None), ('questions', [])]:
            broken = deepcopy(lesson); broken[name] = value
            with self.subTest(name=name), self.assertRaises(ValueError): ll.validate_lesson(broken)

    def test_draft_has_no_invented_source_and_cannot_be_marked_ready(self):
        store = ll.Store(self.db, seed=False)
        track = store.request_track('植物细胞', 'biology-cell', 'biology', 'subject')
        draft = store.draft_lesson(track)
        self.assertEqual(draft['source_refs'], [])
        self.assertIsNone(draft['code_insight'])
        with self.assertRaisesRegex(ValueError, '草稿'):
            store.import_lesson(track, draft)
        self.assertEqual(store.state()['tracks'][0]['lesson_status'], 'queued')
        self.assertEqual(store.state()['pending_jobs'][0]['status'], 'queued')

    def test_coach_prioritizes_retrieval_then_missing_evidence_without_answers(self):
        store = ll.Store(self.db, seed=False)
        self.assertEqual(store.state(START)['coach']['next_step']['kind'], 'choose')
        track = store.request_track('植物细胞', 'biology-cell', 'biology', 'subject')
        self.assertEqual(store.state(START)['coach']['next_step']['kind'], 'prepare')
        store.import_lesson(track, dict(lesson_fixture(), code_insight=None))
        self.assertEqual(store.state(START)['coach']['next_step']['kind'], 'experiment')
        store.add_evidence(track, 'experiment', '实际观察与解释。', at=START)
        self.assertEqual(store.state(START)['coach']['next_step']['kind'], 'application')
        future = store.state(START + timedelta(days=1))['coach']
        self.assertEqual(future['next_step']['kind'], 'review')
        self.assertEqual(future['due_count'], 1)
        self.assertNotIn('SECRET_REFERENCE', ll.dump(future))
        before = store.export()['tables']
        store.state(START + timedelta(days=1))
        self.assertEqual(before, store.export()['tables'])

    def test_readonly_commands_do_not_create_a_database(self):
        self.manifest([course_fixture('biology', 'biology', 'subject')])
        missing = self.root / 'must-not-create.sqlite3'
        cases = [['list-courses'], ['doctor'], ['validate-lesson','--file',str(self.root/'content/biology.json')]]
        for command in cases:
            output = StringIO()
            with patch.object(ll.sys, 'argv', ['learning_loop.py','--db',str(missing)] + command), patch('sys.stdout', output):
                self.assertEqual(ll.main(), 0)
            self.assertFalse(missing.exists())
            json.loads(output.getvalue())

    def test_doctor_reports_missing_assets_without_installing_or_writing(self):
        from test_visual_lessons import visual_fixture
        self.manifest([course_fixture('biology', 'biology', 'subject')])
        lesson = dict(lesson_fixture(), code_insight=None, visual_lesson=visual_fixture())
        (self.root/'content/biology.json').write_text(json.dumps(lesson))
        report = ll.doctor()
        self.assertFalse(report['ok'])
        self.assertFalse(report['database_accessed'])
        self.assertTrue(any(c['name'] == 'lesson:biology' and not c['ok'] for c in report['checks']))
        self.assertFalse((self.root/'data').exists())

    def test_missing_iana_database_has_current_shanghai_fallback(self):
        source = Path(ll.__file__)
        with patch('zoneinfo.ZoneInfo', side_effect=ll.ZoneInfoNotFoundError('no IANA data')):
            module = runpy.run_path(str(source))
        self.assertEqual(module['LOCAL'].utcoffset(None), timedelta(hours=8))
        self.assertIn('fallback', module['TIMEZONE_SOURCE'])


class LocalPublicRouteTests(unittest.TestCase):
    """Run HTTP handlers directly; no listening socket or real ledger is started."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        root = patch.object(ll,'ROOT',self.root); root.start(); self.addCleanup(root.stop)
        self.store = ll.Store(self.root/'test.sqlite3',seed=False)
        handlers = []
        def server(address, handler):
            handlers.append(handler)
            return SimpleNamespace(server_port=8765,serve_forever=lambda:None,server_close=lambda:None)
        with patch.object(ll,'ThreadingHTTPServer',side_effect=server), patch('sys.stdout',StringIO()):
            ll.serve(self.store,8765)
        self.handler = handlers[0]

    def request(self, path, method='GET', body=None, headers=None):
        handler = self.handler.__new__(self.handler)
        handler.path=path; handler.command=method; handler.server=SimpleNamespace(server_port=8765)
        handler.headers={'Host':'127.0.0.1:8765'} | (headers or {})
        handler.wfile=BytesIO(); handler.sent_headers={}; handler.end_headers=lambda:None
        handler.send_response=lambda status:setattr(handler,'status',status)
        handler.send_header=lambda key,value:handler.sent_headers.update({key:value})
        if body is not None:
            encoded=json.dumps(body).encode(); handler.rfile=BytesIO(encoded)
            handler.headers.update({'Content-Type':'application/json','Content-Length':str(len(encoded))})
        getattr(handler,'do_'+method)()
        return handler

    def test_request_route_returns_state_and_stable_track_id(self):
        body=dict(title='细胞结构',topic_id='cells',subject='biology',kind='subject')
        first=self.request('/api/tracks/request','POST',body)
        again=self.request('/api/tracks/request','POST',body)
        a=json.loads(first.wfile.getvalue()); b=json.loads(again.wfile.getvalue())
        self.assertEqual(first.status,200)
        self.assertEqual(a['requested_track_id'],b['requested_track_id'])
        self.assertEqual(len(b['tracks']),1)
        self.assertEqual(b['tracks'][0]['lesson_status'],'queued')

    def test_mobile_uses_build_output_and_blocks_path_escape(self):
        self.assertEqual(self.request('/mobile').sent_headers['Location'],'/mobile/')
        self.assertEqual(self.request('/mobile/').status,404)
        site=self.root/'dist/site'; site.mkdir(parents=True)
        (site/'index.html').write_text('<h1>Public learning</h1>')
        (site/'manifest.webmanifest').write_text('{}')
        (site/'courses.json').write_text('{"courses":[]}')
        (site/'licenses').mkdir()
        (site/'licenses/brush-LICENSE.txt').write_text('Apache License')
        (self.root/'private.html').write_text('private')
        (site/'leak.html').symlink_to(self.root/'private.html')
        self.assertEqual(self.request('/mobile/').wfile.getvalue(),b'<h1>Public learning</h1>')
        manifest=self.request('/mobile/manifest.webmanifest','HEAD')
        self.assertEqual(manifest.sent_headers['Content-Type'],'application/manifest+json')
        self.assertEqual(manifest.wfile.getvalue(),b'')
        self.assertEqual(self.request('/mobile/courses.json').status,200)
        license_file=self.request('/mobile/licenses/brush-LICENSE.txt')
        self.assertEqual(license_file.status,200)
        self.assertEqual(license_file.sent_headers['Content-Type'],'text/plain; charset=utf-8')
        self.assertEqual(self.request('/mobile/leak.html').status,404)
        self.assertEqual(self.request('/mobile/../../private.html').status,404)


if __name__ == '__main__':
    unittest.main()
