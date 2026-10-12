"""Behavior checks using temporary ledgers and mocked public sources only."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import learning_loop as ll


START = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)


def lesson_fixture(question_count=1):
    return {
        'summary': '用一个本地示例观察输入、状态与输出。',
        'mental_model': '状态变化决定下一次输出；类比只用于解释，不替代实现。',
        'core_ideas': [
            {'title': '输入', 'explanation': '明确定义输入及约束。'},
            {'title': '状态', 'explanation': '保存决定行为的最小信息。'},
            {'title': '反馈', 'explanation': '对比预测和真实输出。'},
        ],
        'source_refs': [{'title': '项目文档', 'url': 'https://github.com/example/project'}],
        'questions': [
            {'id': f'question-{i}', 'prompt': f'第{i}个条件变化时输出如何改变？',
             'answer': f'SECRET_REFERENCE_ANSWER_{i}'}
            for i in range(question_count)
        ],
        'case_study': {'title': '状态变化', 'scenario': '比较同一输入的两次输出。',
                       'steps': ['记录输入', '改变一个条件', '比较输出']},
        'code_insight': {'title': '显式状态', 'explanation': '教学伪代码，不是源码摘录。',
                         'snippet': 'next_state = update(state, input)', 'language': 'pseudocode',
                         'source_url': 'https://github.com/example/project/blob/' + 'a' * 40 + '/main.py'},
        'experiment': {'title': '十分钟预测实验', 'steps': ['先预测', '操作', '比较'],
                       'acceptance': ['保存预测和观察结果']},
        'application': {'prompt': '把这个机制用于一个真实任务。',
                        'acceptance': ['保存可使用的结果并解释约束']},
        'recap_prompts': ['闭卷解释输入如何影响输出。'],
    }


def repo_fixture(index=1, stars=100000, **changes):
    repo = {
        'id': index, 'full_name': f'example/project-{index}',
        'html_url': f'https://github.com/example/project-{index}',
        'stars': stars, 'archived': False, 'fork': False, 'license': 'MIT',
        'topics': ['software'], 'description': 'A public learning fixture',
    }
    repo.update(changes)
    return repo


def snapshot_fixture(repos, at=START, **changes):
    data = {'fetched_at_utc': ll.stamp(at), 'repositories': repos,
            'total_count': len(repos), 'incomplete_results': False}
    data.update(changes)
    return data


class LearningLoopTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = ll.Store(Path(self.temp.name) / 'learning.sqlite3', seed=False)
        self.clock = patch.object(ll, 'now', return_value=START)
        self.clock.start()
        self.addCleanup(self.clock.stop)
        taxonomy = {f'example/project-{i}': {'kind': 'software', 'topic_id': f'topic-{i}',
                                            'topic_name': f'主题{i}'} for i in range(1, 201)}
        self.taxonomy = patch.object(ll.Store, 'taxonomy', return_value=taxonomy)
        self.taxonomy.start()
        self.addCleanup(self.taxonomy.stop)
        self.network = patch.object(ll, 'urlopen', side_effect=AssertionError('Unexpected network call'))
        self.network.start()
        self.addCleanup(self.network.stop)

    def import_repos(self, repos=None, at=START):
        return self.store.import_snapshot(snapshot_fixture(repos or [repo_fixture()], at))

    def prepare_track(self, question_count=1):
        self.import_repos()
        track_id = self.store.add_track('example/project-1')
        self.store.import_lesson(track_id, lesson_fixture(question_count))
        return track_id

    def prepare_cards(self, question_count=1, all_evidence=False):
        track_id = self.prepare_track(question_count)
        kinds = ('experiment', 'application', 'summary') if all_evidence else ('experiment',)
        for kind in kinds:
            self.store.add_evidence(track_id, kind, f'{kind} 的真实观察与解释。', at=START)
        return track_id, self.store.state(START)['reviews']

    def current_card(self, card_id):
        return next(c for c in self.store.state(START)['reviews'] if c['id'] == card_id)

    def test_discovery_hard_floor_includes_exactly_100k(self):
        self.import_repos([repo_fixture(1, 99999), repo_fixture(2, 100000),
                           repo_fixture(3, 100001), repo_fixture(4, 200000, archived=True),
                           repo_fixture(5, 200000, fork=True)])
        candidates = self.store.state(START)['discovery']['candidates']
        self.assertEqual([r['id'] for r in candidates], [3, 2])

    def test_filter_and_topic_dedup_happen_before_top_twenty(self):
        repos = [repo_fixture(i, 300000 - i) for i in range(1, 36)]
        taxonomy = {r['full_name']: {'kind': 'software', 'topic_id': f'topic-{r["id"]}', 'topic_name': f'主题{r["id"]}'} for r in repos}
        for i in range(1, 7):
            taxonomy[f'example/project-{i}']['topic_id'] = 'same-core'
        with patch.object(ll.Store, 'taxonomy', return_value=taxonomy):
            self.import_repos(repos)
        self.store.mark_known('topic-7', '主题7')
        candidates = self.store.state(START)['discovery']['candidates']
        self.assertEqual(len(candidates), 20)
        self.assertEqual(len({r['topic_id'] for r in candidates}), 20)
        self.assertNotIn('topic-7', {r['topic_id'] for r in candidates})
        self.assertEqual([r['id'] for r in candidates], [1] + list(range(8, 27)))

    def test_nonsoftware_repo_cannot_hide_eligible_software_in_same_topic(self):
        taxonomy = {
            'example/project-1': {'kind': 'collection', 'topic_id': 'shared', 'topic_name': '共享主线'},
            'example/project-2': {'kind': 'software', 'topic_id': 'shared', 'topic_name': '共享主线'},
        }
        with patch.object(ll.Store, 'taxonomy', return_value=taxonomy):
            self.import_repos([repo_fixture(1, 300000), repo_fixture(2, 200000)])
        self.assertEqual([r['id'] for r in self.store.state(START)['discovery']['candidates']], [2])

    def test_snapshot_error_does_not_clear_cached_repositories(self):
        self.import_repos()
        invalid_snapshots = [
            snapshot_fixture([]),
            snapshot_fixture([repo_fixture(2)], incomplete_results=True),
            snapshot_fixture([repo_fixture(2, 99999)]),
            snapshot_fixture([repo_fixture(2), repo_fixture(3, html_url='http://unsafe.example')]),
            snapshot_fixture([repo_fixture(2), repo_fixture(2)]),
        ]
        for data in invalid_snapshots:
            with self.subTest(data=data):
                with self.assertRaises(Exception):
                    self.store.import_snapshot(data)
                self.assertEqual([r['id'] for r in self.store.state(START)['discovery']['candidates']], [1])

    def test_brush_exploration_is_not_learning_or_mastery(self):
        with self.store.connect() as db:
            db.execute('INSERT INTO tracks(id,title,topic_id,repo_full_name,repo_url,status,lesson_status,lesson,created_at,progress_note) VALUES(?,?,?,?,?,?,?,?,?,?)',
                       ('brush-intro', '高斯溅射', 'gaussian-splatting', 'ArthurBrussee/brush',
                        'https://github.com/ArthurBrussee/brush', 'exploring', 'ready',
                        ll.dump(lesson_fixture()), ll.stamp(START), '仅讨论过，尚未实操。'))
        self.store.daily(at=START)
        state = self.store.state(START)
        self.assertEqual(state['tracks'][0]['status'], 'exploring')
        self.assertEqual(state['stats']['mastered_tracks'], 0)
        self.assertEqual(state['reviews'], [])
        self.assertEqual(state['known_topics'], [])

    def test_prepared_lesson_does_not_complete_learning(self):
        track = self.prepare_track()
        state = self.store.state(START)
        self.assertEqual(state['tracks'][0]['id'], track)
        self.assertEqual(state['tracks'][0]['status'], 'learning')
        self.assertEqual(state['tracks'][0]['lesson_status'], 'ready')
        self.assertEqual(state['reviews'], [])
        self.assertEqual(state['pending_jobs'], [])

    def test_mastery_requires_all_three_evidence_kinds(self):
        track = self.prepare_track()
        for kind in (None, 'experiment', 'application'):
            if kind:
                self.store.add_evidence(track, kind, '我执行并观察了结果。', at=START)
            with self.assertRaisesRegex(ValueError, '实验|证据'):
                self.store.set_status(track, 'mastered')
        self.store.add_evidence(track, 'summary', '我可以解释输入、状态与结果的因果。', at=START)
        with self.assertRaises(ValueError):
            self.store.set_status(track, 'mastered')

    def test_mastery_requires_real_spaced_success(self):
        track, cards = self.prepare_cards(all_evidence=True)
        card_id = cards[0]['id']
        for _ in range(2):
            due = ll.parse_time(self.current_card(card_id)['due_at'])
            self.store.answer(card_id, 'good', '我用自己的话解释了机制。', at=due)
        self.store.set_status(track, 'mastered')
        self.assertEqual(self.store.state(START)['tracks'][0]['status'], 'mastered')

    def test_early_practice_on_two_dates_cannot_count_as_spaced_mastery(self):
        track, cards = self.prepare_cards(all_evidence=True)
        card_id = cards[0]['id']
        self.store.answer(card_id, 'good', '第一天的额外练习。', at=START)
        self.store.answer(card_id, 'good', '跨午夜后仍未到期的额外练习。', at=START + timedelta(hours=5))
        self.assertEqual(self.current_card(card_id)['repetitions'], 0)
        with self.assertRaises(ValueError):
            self.store.set_status(track, 'mastered')

    def test_latest_lapse_prevents_mastery_despite_older_successes(self):
        track, cards = self.prepare_cards(all_evidence=True)
        card_id = cards[0]['id']
        for _ in range(2):
            due = ll.parse_time(self.current_card(card_id)['due_at'])
            self.store.answer(card_id, 'good', '能够解释并迁移。', at=due)
        due = ll.parse_time(self.current_card(card_id)['due_at'])
        self.store.answer(card_id, 'again', '现在想不起来了。', at=due)
        with self.assertRaises(ValueError):
            self.store.set_status(track, 'mastered')

    def test_lesson_validation_accepts_complete_contract(self):
        self.assertEqual(ll.validate_lesson(lesson_fixture()), lesson_fixture())

    def test_source_license_is_preserved_and_bounded_plain_text(self):
        data = lesson_fixture()
        data['source_refs'][0]['license_text'] = 'MIT License\nCopyright example\nPermission is granted.'
        self.assertEqual(ll.validate_lesson(data), data)
        for invalid in ('', None, {}, 'x' * 60001):
            data['source_refs'][0]['license_text'] = invalid
            with self.subTest(value_type=type(invalid).__name__):
                with self.assertRaises(ValueError):
                    ll.validate_lesson(data)

    def test_lesson_validation_rejects_missing_duplicate_and_unsafe_fields(self):
        invalid = []
        data = lesson_fixture(); del data['application']; invalid.append(data)
        data = lesson_fixture(); data['questions'] *= 2; invalid.append(data)
        data = lesson_fixture(); data['experiment']['acceptance'] = []; invalid.append(data)
        data = lesson_fixture(); data['source_refs'][0]['url'] = 'javascript:alert(1)'; invalid.append(data)
        for data in invalid:
            with self.subTest(data=data):
                with self.assertRaises(ValueError):
                    ll.validate_lesson(data)

    def test_lesson_validation_rejects_extra_contract_fields(self):
        data = lesson_fixture()
        data['mastered'] = True
        with self.assertRaises(ValueError):
            ll.validate_lesson(data)

    def test_lesson_validation_rejects_non_object_entries_as_value_error(self):
        for field in ('core_ideas', 'questions', 'source_refs'):
            data = lesson_fixture()
            data[field] = ['not an object']
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    ll.validate_lesson(data)

    def test_rejected_lesson_import_preserves_previous_lesson_and_history(self):
        track, cards = self.prepare_cards()
        card_id = cards[0]['id']
        self.store.answer(card_id, 'good', '我的闭卷解释。', at=START + timedelta(days=1))
        before = self.store.state(START)
        broken = lesson_fixture(); broken['questions'] = []
        with self.assertRaises(ValueError):
            self.store.import_lesson(track, broken)
        after = self.store.state(START)
        self.assertEqual(before['tracks'], after['tracks'])
        self.assertEqual(before['reviews'], after['reviews'])
        self.assertEqual(before['stats'], after['stats'])

    def test_initial_and_successive_due_intervals(self):
        _, cards = self.prepare_cards()
        card_id = cards[0]['id']
        self.assertEqual(ll.parse_time(cards[0]['due_at']), START + timedelta(days=1))
        for days in (3, 7, 14, 30, 60):
            due = ll.parse_time(self.current_card(card_id)['due_at'])
            self.store.answer(card_id, 'good', '我的解释包含因果与边界。', at=due)
            self.assertEqual(ll.parse_time(self.current_card(card_id)['due_at']), due + timedelta(days=days))

    def test_again_schedules_retry_in_ten_minutes(self):
        _, cards = self.prepare_cards()
        card_id = cards[0]['id']
        due = ll.parse_time(cards[0]['due_at'])
        self.store.answer(card_id, 'again', '我忘了关键步骤。', at=due)
        result = self.current_card(card_id)
        self.assertEqual(ll.parse_time(result['due_at']), due + timedelta(minutes=10))
        self.assertEqual(result['repetitions'], 0)
        self.assertEqual(result['lapses'], 1)

    def test_early_practice_does_not_push_due_date_or_interval(self):
        _, cards = self.prepare_cards()
        before = deepcopy(cards[0])
        self.store.answer(before['id'], 'easy', '额外练习仍然记得。', at=START + timedelta(hours=1))
        after = self.current_card(before['id'])
        for field in ('due_at', 'interval_days', 'repetitions'):
            self.assertEqual(after[field], before[field])

    def test_duplicate_click_does_not_delay_next_review(self):
        _, cards = self.prepare_cards()
        card_id = cards[0]['id']
        due = ll.parse_time(cards[0]['due_at'])
        self.store.answer(card_id, 'good', '闭卷回答。', at=due)
        saved = self.current_card(card_id)
        with self.assertRaises(ValueError):
            self.store.answer(card_id, 'good', '闭卷回答。', at=due + timedelta(seconds=2))
        self.assertEqual(self.current_card(card_id), saved)
        self.assertEqual(self.store.state(START)['stats']['completed_reviews'], 1)

    def test_daily_limits_due_questions_and_omits_answers(self):
        self.prepare_cards(question_count=8)
        self.store.update_settings({'review_minutes': 2})
        daily = self.store.daily(at=START + timedelta(days=1))
        self.assertEqual(daily['due_total'], 8)
        self.assertEqual(len(daily['recall_questions']), 2)
        self.assertEqual(daily['remaining_due'], 6)
        self.assertNotIn('SECRET_REFERENCE_ANSWER', ll.dump(daily))
        self.assertTrue(daily['should_notify'])

    def test_daily_ack_deduplicates_same_local_date(self):
        self.prepare_cards()
        at = START + timedelta(days=1)
        first = self.store.daily(at=at)
        self.store.acknowledge(first['date'])
        repeated = self.store.daily(at=at + timedelta(hours=1))
        self.assertTrue(repeated['already_acknowledged'])
        self.assertFalse(repeated['should_notify'])
        self.assertTrue(self.store.daily(at=at + timedelta(days=1))['should_notify'])

    def test_first_candidate_list_requests_selection(self):
        self.import_repos()
        daily = self.store.daily(at=START)
        self.assertTrue(daily['should_notify'], '首次发现候选应通知用户选择，不能静默卡住循环')
        self.assertEqual(daily['pending_jobs'], [])
        self.assertEqual(self.store.state(START)['tracks'], [])

    def test_no_learning_work_keeps_daily_quiet(self):
        self.assertFalse(self.store.daily(at=START)['should_notify'])

    def test_star_count_only_change_does_not_repeat_selection_reminder(self):
        self.import_repos()
        self.store.acknowledge(self.store.daily(at=START)['date'])
        self.import_repos([repo_fixture(stars=100005)], at=START + timedelta(days=1))
        self.assertFalse(self.store.daily(at=START + timedelta(days=1))['should_notify'])

    def test_refresh_uses_cache_for_first_twenty_four_hours(self):
        self.import_repos()
        with patch.object(self.store, 'refresh') as refresh:
            self.store.daily(refresh=True, at=START + timedelta(hours=23, minutes=59))
            refresh.assert_not_called()
            self.store.daily(refresh=True, at=START + timedelta(hours=24))
            refresh.assert_called_once_with()

    def test_network_failure_keeps_previous_snapshot_and_exposes_warning(self):
        self.import_repos(at=START - timedelta(days=2))
        before = self.store.state(START)['discovery']
        with patch.object(ll, 'urlopen', side_effect=URLError('offline fixture')):
            daily = self.store.daily(refresh=True, at=START)
        after = daily['discovery']
        self.assertEqual(after['candidates'], before['candidates'])
        self.assertEqual(after['fetched_at'], before['fetched_at'])
        self.assertIn('保留', after['warning'])
        self.assertIn('offline fixture', after['warning'])
        self.assertTrue(daily['should_notify'])


class CatalogBehaviorTests(unittest.TestCase):
    """Exercise catalog persistence in an isolated copy of the real initial taxonomy."""

    def setUp(self):
        initial_catalog = (ll.ROOT / 'content' / 'catalog.json').read_bytes()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'content').mkdir()
        self.catalog_path = self.root / 'content' / 'catalog.json'
        self.catalog_path.write_bytes(initial_catalog)
        root_patch = patch.object(ll, 'ROOT', self.root)
        root_patch.start(); self.addCleanup(root_patch.stop)
        clock_patch = patch.object(ll, 'now', return_value=START)
        clock_patch.start(); self.addCleanup(clock_patch.stop)
        network_patch = patch.object(ll, 'urlopen', side_effect=AssertionError('Unexpected network call'))
        network_patch.start(); self.addCleanup(network_patch.stop)
        self.store = ll.Store(self.root / 'learning.sqlite3', seed=False)
        self.repo = repo_fixture(987650000, 150000, full_name='fixture/new-project',
                                 html_url='https://github.com/fixture/new-project')
        self.mapping = {'kind': 'software', 'topic_id': 'new-principle', 'topic_name': '新核心思想'}
        self.store.import_snapshot(snapshot_fixture([self.repo]))

    def test_new_unknown_becomes_eligible_after_verified_classification(self):
        before = self.store.state(START)['discovery']
        self.assertEqual(before['candidates'], [])
        self.assertEqual(before['unclassified'][0]['full_name'], self.repo['full_name'])
        self.store.import_catalog({self.repo['full_name']: self.mapping})
        after = self.store.state(START)['discovery']
        self.assertEqual([r['full_name'] for r in after['candidates']], [self.repo['full_name']])
        self.assertEqual(after['unclassified'], [])
        saved = json.loads(self.catalog_path.read_text())
        self.assertEqual(saved[self.repo['full_name']]['repo_id'], self.repo['id'])

    def test_bad_classification_preserves_catalog_and_existing_candidates(self):
        self.store.import_catalog({self.repo['full_name']: self.mapping})
        before_catalog = self.catalog_path.read_bytes()
        before = self.store.state(START)['discovery']
        entries = {
            self.repo['full_name']: {'kind': 'collection', 'topic_id': 'changed', 'topic_name': '不得部分写入'},
            'fixture/not-fetched': self.mapping,
        }
        with self.assertRaises(ValueError):
            self.store.import_catalog(entries)
        self.assertEqual(self.catalog_path.read_bytes(), before_catalog)
        self.assertEqual(self.store.state(START)['discovery'], before)

    def test_repository_rename_preserves_taxonomy_by_numeric_id(self):
        self.store.import_catalog({self.repo['full_name']: self.mapping})
        renamed = dict(self.repo, full_name='fixture/renamed-project',
                       html_url='https://github.com/fixture/renamed-project')
        self.store.import_snapshot(snapshot_fixture([renamed], at=START + timedelta(days=1)))
        candidates = self.store.state(START)['discovery']['candidates']
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]['full_name'], 'fixture/renamed-project')
        self.assertEqual(candidates[0]['topic_id'], 'new-principle')
        self.assertEqual(candidates[0]['kind'], 'software')


if __name__ == '__main__':
    unittest.main()
