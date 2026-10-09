"""Line alignment, provenance and safe course upgrades in temporary ledgers."""
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import learning_loop as ll
from test_learning_loop import lesson_fixture, repo_fixture, snapshot_fixture, START


def section_fixture(kind='source'):
    return dict(id='update',title='更新参数',kind=kind,language='rust',
        snippet='let current = state;\n\nupdate(current);',
        source_url='https://github.com/example/project/blob/'+'a'*40+'/src/train.rs',
        source_path='src/train.rs' if kind == 'source' else None,
        source_commit='a'*40 if kind == 'source' else None,
        source_start_line=120 if kind == 'source' else None,
        notes=[dict(line=1,comment='保留本轮输入状态。',why='后续更新需要明确输入。'),
               dict(line=3,comment='用本轮状态调用更新。',why='这一调用推进计算过程。')])


class CodeWalkthroughTests(unittest.TestCase):
    def test_legacy_and_annotated_lessons_both_importable(self):
        lesson = lesson_fixture()
        ll.validate_lesson(lesson)
        lesson['code_insight']['walkthroughs'] = [section_fixture(),section_fixture('pseudocode')]
        lesson['code_insight']['walkthroughs'][1]['id'] = 'teaching'
        ll.validate_lesson(lesson)

    def test_line_notes_cannot_shift_skip_or_duplicate_code(self):
        for numbers in [[1], [1,2], [1,4], [3,1], [1,1], [True,3]]:
            section = section_fixture()
            section['notes'] = [dict(line=n,comment='中文注释',why='说明原因') for n in numbers]
            with self.subTest(numbers=numbers), self.assertRaises(ValueError):
                ll.validate_code_walkthroughs([section])

    def test_closing_braces_and_original_comments_are_explained(self):
        section = section_fixture()
        section['snippet'] = '// upstream comment\nif ready {\n  update();\n}'
        section['notes'] = [dict(line=n,comment='说明当前行',why='说明上下文') for n in range(1,5)]
        ll.validate_code_walkthroughs([section])
        section['notes'].pop()
        with self.assertRaises(ValueError):
            ll.validate_code_walkthroughs([section])

    def test_source_requires_matching_frozen_provenance(self):
        changes = [dict(source_commit='main'),dict(source_start_line=0),dict(source_start_line=True),
                   dict(source_path='../train.rs'),dict(source_path='/src/train.rs'),
                   dict(source_url='https://github.com/example/project/blob/main/src/train.rs'),
                   dict(source_path='other.rs'),dict(source_url='javascript:alert(1)')]
        for change in changes:
            section = section_fixture()
            section.update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                ll.validate_code_walkthroughs([section])

    def test_pseudocode_cannot_claim_upstream_line_numbers(self):
        for field, value in [('source_commit','a'*40),('source_path','src/train.rs'),('source_start_line',120)]:
            section = section_fixture('pseudocode')
            section[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                ll.validate_code_walkthroughs([section])

    def test_notes_require_explanation_and_unique_section_ids(self):
        for field in ['comment','why']:
            section = section_fixture()
            section['notes'][0][field] = ''
            with self.subTest(field=field), self.assertRaises(ValueError):
                ll.validate_code_walkthroughs([section])
        with self.assertRaises(ValueError):
            ll.validate_code_walkthroughs([section_fixture(),section_fixture()])

    def test_upgrade_preserves_real_review_history_and_failed_upgrade_keeps_material(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(ll.Store,'taxonomy',return_value={}):
            store = ll.Store(Path(tmp)/'ledger.sqlite3',seed=False)
            store.import_snapshot(snapshot_fixture([repo_fixture()]))
            track_id = store.add_track('example/project-1')
            lesson = lesson_fixture()
            store.import_lesson(track_id,lesson)
            store.add_evidence(track_id,'experiment','我改变输入并记录了实际结果。',at=START)
            card = store.state(START)['reviews'][0]
            store.answer(card['id'],'good','我能解释输入与状态的联系。',at=START+timedelta(days=1))
            with store.connect() as db:
                before = {table:[tuple(r) for r in db.execute('SELECT * FROM '+table)]
                          for table in ['evidence','cards','review_events']}
            lesson['code_insight']['walkthroughs'] = [section_fixture()]
            store.import_lesson(track_id,lesson)
            with store.connect() as db:
                after = {table:[tuple(r) for r in db.execute('SELECT * FROM '+table)] for table in before}
            self.assertEqual(before,after)
            self.assertEqual(len(after['review_events']),1)
            broken = deepcopy(lesson)
            broken['code_insight']['walkthroughs'][0]['notes'].pop()
            with self.assertRaises(ValueError):
                store.import_lesson(track_id,broken)
            self.assertEqual(store.state()['tracks'][0]['lesson'],lesson)


def audio_fixture(chapter='logic', walkthrough_id=None):
    return dict(voice='本机合成中文语音',clips=[dict(chapter=chapter,walkthrough_id=walkthrough_id,
        title='听懂核心过程',src='/media/demo/logic.m4a',duration_seconds=60,
        transcript='先理解输入和输出，再观察参数改变时会发生什么。')])


class AudioLessonTests(unittest.TestCase):
    def test_chapter_and_existing_source_excerpt_can_have_narration(self):
        lesson = lesson_fixture()
        lesson['code_insight']['walkthroughs'] = [section_fixture()]
        lesson['audio_lesson'] = audio_fixture()
        lesson['audio_lesson']['clips'] += audio_fixture('code','update')['clips']
        ll.validate_lesson(lesson)

    def test_audio_cannot_point_at_unknown_or_duplicate_sections(self):
        for chapter,section in [('unknown',None),('logic','update'),('code','missing')]:
            with self.subTest(chapter=chapter,section=section), self.assertRaises(ValueError):
                ll.validate_audio_lesson(audio_fixture(chapter,section),[section_fixture()])
        audio = audio_fixture()
        audio['clips'] *= 2
        with self.assertRaises(ValueError):
            ll.validate_audio_lesson(audio,[])

    def test_audio_requires_local_media_actual_duration_and_transcript(self):
        for change in [dict(src='https://remote.test/voice.mp3'),dict(src='/media/../private.m4a'),
                       dict(src='/media/voice.html'),dict(duration_seconds=0),dict(duration_seconds=True),
                       dict(duration_seconds=float('nan')),dict(transcript='')]:
            audio = audio_fixture()
            audio['clips'][0].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                ll.validate_audio_lesson(audio,[])

    def test_missing_or_empty_audio_does_not_replace_saved_course(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(ll,'ROOT',root), patch.object(ll.Store,'taxonomy',return_value={}):
                store = ll.Store(root/'ledger.sqlite3',seed=False)
                store.import_snapshot(snapshot_fixture([repo_fixture()]))
                track_id = store.add_track('example/project-1')
                previous = lesson_fixture()
                store.import_lesson(track_id,previous)
                lesson = deepcopy(previous)
                lesson['audio_lesson'] = audio_fixture()
                with self.assertRaises(ValueError):
                    store.import_lesson(track_id,lesson)
                media = root/'web/media/demo/logic.m4a'
                media.parent.mkdir(parents=True)
                media.write_bytes(b'')
                with self.assertRaises(ValueError):
                    store.import_lesson(track_id,lesson)
                self.assertEqual(store.state()['tracks'][0]['lesson'],previous)
                # Existence only: decoding is verified separately on real generated media.
                media.write_bytes(b'temporary test media')
                store.import_lesson(track_id,lesson)
                self.assertEqual(store.state()['tracks'][0]['lesson'],lesson)
                self.assertEqual(store.state()['tracks'][0]['evidence'],[])


if __name__ == '__main__':
    unittest.main()
