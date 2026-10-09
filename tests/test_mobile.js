'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const L = require('../web/mobile/learner.js');
const START = Date.parse('2026-10-09T10:00:00.000Z');
const DAY = 86400000;
const course = { id: '统计学::贝叶斯', lesson: { questions: [{ id: '先验/证据', prompt: '如何更新判断？', answer: '组合先验与似然。' }] } };
function recorded() { return L.addEvidence(L.fresh(START), course, 'experiment', '用基准比例重新计算了一次。', 'evidence-one', START); }

test('recording enrolls once and schedules questions only once, without mutating old state', () => {
  const before = L.fresh(START); const snapshot = JSON.stringify(before);
  const once = L.addEvidence(before, course, 'experiment', '我的实际观察', 'evidence-one', START);
  const twice = L.addEvidence(once, course, 'summary', '我的独立解释', 'evidence-two', START + 1000);
  assert.equal(JSON.stringify(before), snapshot);
  assert.equal(twice.enrollments.length, 1); assert.equal(twice.reviews.length, 1);
  assert.equal(twice.reviews[0].due_at, new Date(START + DAY).toISOString());
  assert.equal(L.progress(twice, course.id).application, false);
  assert.equal(Object.hasOwn(twice, 'mastered'), false);
});
test('Chinese stable IDs round-trip and separator-containing IDs cannot collide', () => {
  const state = recorded(); assert.deepEqual(L.importBackup(JSON.stringify(state), [course]), state);
  assert.notEqual(L.reviewID('a::b', 'c'), L.reviewID('a', 'b::c'));
});
test('due success follows the same 1/3/7/14/30/60 sequence as local backend', () => {
  let review = recorded().reviews[0];
  for (const expected of [3, 7, 14, 30, 60, 60]) { review = L.scheduleReview(review, 'good', Date.parse(review.due_at)); assert.equal(review.interval_days, expected); }
  const easy = L.scheduleReview(recorded().reviews[0], 'easy', START + DAY); assert.equal(easy.interval_days, 7);
  const hard = L.scheduleReview({ ...review, interval_days: 14 }, 'hard', Date.parse(review.due_at)); assert.equal(hard.interval_days, 3);
});
test('early recall preserves due date and interval; forgotten material returns in ten minutes', () => {
  const review = recorded().reviews[0];
  const early = L.scheduleReview(review, 'easy', START + 1000);
  assert.equal(early.due_at, review.due_at); assert.equal(early.interval_days, review.interval_days); assert.equal(early.repetitions, review.repetitions);
  const failed = L.scheduleReview(review, 'again', START + 1000); assert.equal(Date.parse(failed.due_at), START + 601000); assert.equal(failed.repetitions, 0);
});
test('answer requires an independent response and double submission cannot advance the schedule', () => {
  const original = recorded(); const id = original.reviews[0].id;
  assert.throws(() => L.answerReview(original, id, ' ', 'good', 'answer-one', START + DAY));
  const first = L.answerReview(original, id, '要结合基准比例。', 'good', 'answer-one', START + DAY);
  assert.throws(() => L.answerReview(first, id, '重复回答', 'easy', 'answer-two', START + DAY + 1000));
  assert.equal(original.review_history.length, 0); assert.equal(first.review_history.length, 1);
});
test('invalid imports fail completely: unknown keys, missing questions, duplicates, bad links and invalid numbers', () => {
  const state = recorded(); const mutations = [
    item => { item.cloud_token = 'unexpected'; },
    item => { item.reviews[0].question_id = '不存在的问题'; },
    item => { item.evidence.push({ ...item.evidence[0] }); },
    item => { item.enrollments = []; },
    item => { item.reviews[0].interval_days = -1; },
    item => { item.settings.daily_minutes = 0; },
    item => { item.reviews[0].due_at = 'not-a-date'; },
    item => { item.evidence[0].course_id = 'missing-course'; },
  ];
  const snapshot = JSON.stringify(state);
  for (const mutate of mutations) { const input = JSON.parse(snapshot); mutate(input); assert.throws(() => L.importBackup(JSON.stringify(input), [course])); }
  assert.equal(JSON.stringify(state), snapshot);
  assert.throws(() => L.importBackup('{"__proto__":{}}', [course]));
});
test('offline media byte ranges return only requested bytes, including suffix and invalid cases', async () => {
  const source = fs.readFileSync(path.join(__dirname, '../web/mobile/sw.js'), 'utf8').replace('__CACHE_VERSION__', '"test-version"').replace('__PRECACHE_URLS__', '["index.html","media/audio.m4a"]');
  const handlers = {};
  const context = { self: { registration: { scope: 'https://example.com/learning/' }, addEventListener: (name, fn) => { handlers[name] = fn; } }, URL, Response, Headers, Set, fetch };
  vm.createContext(context); vm.runInContext(source, context);
  const range = vm.runInContext('rangedResponse', context);
  const run = value => range(new Request('https://example.com/learning/media/audio.m4a', { headers: { Range: value } }), new Response('0123456789', { headers: { 'Content-Type': 'audio/mp4' } }));
  const prefix = await run('bytes=0-3'); assert.equal(prefix.status, 206); assert.equal(prefix.headers.get('Content-Range'), 'bytes 0-3/10'); assert.equal(await prefix.text(), '0123');
  assert.equal(await (await run('bytes=7-')).text(), '789'); assert.equal(await (await run('bytes=-4')).text(), '6789');
  assert.equal((await run('bytes=30-40')).status, 416); assert.equal((await run('bytes=0-2,4-6')).status, 416);
  let intercepted = false; handlers.fetch({ request: new Request('https://example.com/other/private.json'), respondWith: () => { intercepted = true; } }); assert.equal(intercepted, false);
  handlers.fetch({ request: new Request('https://example.com/learning/api/write', { method: 'POST' }), respondWith: () => { intercepted = true; } }); assert.equal(intercepted, false);
});
test('shared lab and app shell assets retain relative deployment paths', () => {
  const lab = fs.readFileSync(path.join(__dirname, '../web/lab/index.html'), 'utf8');
  assert.match(lab, /href="\.\/lab\.css"/); assert.match(lab, /src="\.\/lab\.js"/); assert.doesNotMatch(lab, /(?:href|src)="\//);
  const shell = fs.readFileSync(path.join(__dirname, '../web/mobile/index.html'), 'utf8');
  assert.doesNotMatch(shell, /(?:href|src)="\//);
  const manifest = JSON.parse(fs.readFileSync(path.join(__dirname, '../web/mobile/manifest.webmanifest'), 'utf8'));
  assert.equal(manifest.scope, './'); assert.equal(manifest.start_url, './');
  for (const icon of manifest.icons) assert.ok(fs.existsSync(path.resolve(__dirname, '../web/mobile', icon.src)));
});

test('completed worker updates wait for an explicit apply message before activation', async () => {
  const source = fs.readFileSync(path.join(__dirname, '../web/mobile/sw.js'), 'utf8').replace('__CACHE_VERSION__', '"update-test"').replace('__PRECACHE_URLS__', '["index.html"]');
  const handlers = {}; let skipped = 0; let pending;
  const context = {
    self: { registration: { scope: 'https://example.com/learning/' }, addEventListener: (name, fn) => { handlers[name] = fn; }, skipWaiting: async () => { skipped++; } },
    URL, Response, Headers, Set,
    caches: { open: async () => ({ put: async () => {} }) },
    fetch: async () => new Response('Complete new build'),
  };
  vm.createContext(context); vm.runInContext(source, context);
  handlers.install({ waitUntil: promise => { pending = promise; } }); await pending;
  assert.equal(skipped, 0, 'install must not replace the worker controlling an open course');
  handlers.message({ data: { type: 'UNRELATED' }, waitUntil: promise => { pending = promise; } }); assert.equal(skipped, 0);
  handlers.message({ data: { type: 'SKIP_WAITING' }, waitUntil: promise => { pending = promise; } }); await pending;
  assert.equal(skipped, 1);
});
