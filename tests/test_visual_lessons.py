"""Visual teaching contracts and media seeking, without touching user records."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import learning_loop as ll
from test_learning_loop import lesson_fixture, repo_fixture, snapshot_fixture, START


def visual_fixture():
    return dict(hook='看见输入如何变成输出', duration_minutes=10,
        video=dict(src='/media/demo/intro.mp4', poster='/media/demo/poster.jpg', captions='/media/demo/zh.vtt',
                   title='原理动画', duration_seconds=48, attribution='原创教学示意',
                   transcript=[dict(time=0,text='从多个角度观察'),dict(time=24,text='用误差改进结果')]),
        steps=[dict(id='capture',title='换一个观察位置',caption='位移带来视差',image='/media/demo/capture.svg',
                    alt='两台相机从不同位置观察物体',question=dict(prompt='怎样获得视差？',
                    options=['移动相机','原地变焦'],correct_index=0,explanation='相机位置变化带来不同投影关系。'))],
        interactive=dict(kind='gaussian-viewer',title='转动观察',prompt='比较点和软边投影'),
        takeaways=['先观察，再预测'],watch_more=[dict(title='官方资料',url='https://example.com/docs',description='查看真实例子')])


class VisualLessonTests(unittest.TestCase):
    def test_mobile_experiments_validate_and_reject_remote_audio(self):
        visual = visual_fixture()
        visual['interactive'] = dict(kind='bayes-counts', title='四格', prompt='先数人')
        ll.validate_visual_lesson(visual)
        sample = dict(label='甲', src='/media/voice/a.mp3', transcript='同样的文字', duration_seconds=10)
        visual['interactive'] = dict(kind='voice-ab', title='听辨', prompt='先预测', samples=[sample, dict(sample, label='乙', src='/media/voice/b.mp3')])
        ll.validate_visual_lesson(visual)
        for change in [dict(src='https://example.com/a.mp3'), dict(duration_seconds=True), dict(transcript='')]:
            invalid = deepcopy(visual)
            invalid['interactive']['samples'][0].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                ll.validate_visual_lesson(invalid)
        visual['interactive']['samples'].pop()
        with self.assertRaises(ValueError):
            ll.validate_visual_lesson(visual)

    def test_legacy_and_visual_courses_are_both_supported(self):
        lesson = lesson_fixture()
        ll.validate_lesson(lesson)
        lesson['visual_lesson'] = visual_fixture()
        ll.validate_lesson(lesson)

    def test_steps_remain_valid_when_video_unavailable(self):
        lesson = lesson_fixture()
        lesson['visual_lesson'] = visual_fixture()
        lesson['visual_lesson']['video'] = None
        lesson['visual_lesson']['interactive'] = None
        ll.validate_lesson(lesson)

    def test_media_cannot_escape_local_media_directory(self):
        for url in ['https://remote.test/clip.mp4','/media/../data/clip.mp4','/media/%2e%2e/clip.mp4',
                    '//remote.test/media/clip.mp4','/media/clip.mp4?token=x','/media/clip.mp4#fragment',
                    '/media/clip.html','/media/..\\clip.mp4']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                ll.media_path(url, {'.mp4'})

    def test_prediction_question_requires_real_answer_and_reason(self):
        for edit in [dict(correct_index=2), dict(correct_index=True), dict(options=['only']), dict(explanation='')]:
            visual = visual_fixture()
            visual['steps'][0]['question'].update(edit)
            with self.subTest(edit=edit), self.assertRaises(ValueError):
                ll.validate_visual_lesson(visual)

    def test_transcript_timecodes_must_match_video(self):
        for times in [[0,48],[10,5],[-1,24],[-0.5,24],[0,0]]:
            visual = visual_fixture()
            visual['video']['transcript'] = [dict(time=t,text='讲解') for t in times]
            with self.subTest(times=times), self.assertRaises(ValueError):
                ll.validate_visual_lesson(visual)

    def test_missing_media_import_preserves_previous_material(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(ll, 'ROOT', root), patch.object(ll.Store, 'taxonomy', return_value={}):
                store = ll.Store(root/'ledger.sqlite3', seed=False)
                store.import_snapshot(snapshot_fixture([repo_fixture()]))
                track_id = store.add_track('example/project-1')
                old = lesson_fixture()
                store.import_lesson(track_id, old)
                update = deepcopy(old)
                update['visual_lesson'] = visual_fixture()
                with self.assertRaises(ValueError):
                    store.import_lesson(track_id, update)
                self.assertEqual(store.state()['tracks'][0]['lesson'], old)
                self.assertEqual(store.state()['stats']['completed_reviews'], 0)

    def test_existing_assets_import_without_changing_learning_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            media = root/'web/media/demo'
            media.mkdir(parents=True)
            for name in ['intro.mp4','poster.jpg','zh.vtt','capture.svg']:
                (media/name).write_text('Test fixture, not a decoded-media test.')
            with patch.object(ll, 'ROOT', root), patch.object(ll.Store, 'taxonomy', return_value={}):
                store = ll.Store(root/'ledger.sqlite3', seed=False)
                store.import_snapshot(snapshot_fixture([repo_fixture()]))
                track_id = store.add_track('example/project-1')
                lesson = lesson_fixture()
                store.import_lesson(track_id, lesson)
                store.add_evidence(track_id,'experiment','原有实验记录',at=START)
                before = store.state()
                lesson['visual_lesson'] = visual_fixture()
                store.import_lesson(track_id,lesson)
                after = store.state()
                self.assertEqual(before['tracks'][0]['evidence'],after['tracks'][0]['evidence'])
                self.assertEqual(before['reviews'],after['reviews'])
                self.assertEqual(before['tracks'][0]['status'],after['tracks'][0]['status'])

    def test_symlink_cannot_reference_private_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            media = root/'web/media/demo'
            media.mkdir(parents=True)
            private = root/'secret.svg'
            private.write_text('<svg/>')
            (media/'capture.svg').symlink_to(private)
            lesson = lesson_fixture()
            lesson['visual_lesson'] = visual_fixture()
            lesson['visual_lesson']['video'] = None
            with patch.object(ll,'ROOT',root), self.assertRaises(ValueError):
                ll.validate_lesson_assets(lesson)


class MediaRangeTests(unittest.TestCase):
    def test_full_request_does_not_select_a_range(self):
        self.assertIsNone(ll.parse_byte_range(None,100))

    def test_seek_open_ended_and_suffix_ranges(self):
        for header, expected in [('bytes=0-0',(0,0)),('bytes=20-49',(20,49)),('bytes=50-',(50,99)),
                                 ('bytes=-20',(80,99)),('bytes=-200',(0,99)),('bytes=90-500',(90,99))]:
            with self.subTest(header=header):
                self.assertEqual(ll.parse_byte_range(header,100), expected)

    def test_invalid_or_unsatisfiable_ranges_are_rejected(self):
        for header in ['bytes=100-','bytes=50-20','bytes=-0','bytes=-','bytes=0-1,2-3','items=0-2']:
            with self.subTest(header=header), self.assertRaises(ValueError):
                ll.parse_byte_range(header,100)
        with self.assertRaises(ValueError):
            ll.parse_byte_range('bytes=0-',0)


if __name__ == '__main__':
    unittest.main()
