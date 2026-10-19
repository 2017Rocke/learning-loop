'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const M = require('../web/lab/mosfet/model.js');
const close = (actual, expected, tolerance = 1e-10) => assert.ok(Math.abs(actual - expected) < tolerance, `${actual} vs ${expected}`);

test('0% stays open and 100% stays conducting, including exact cycle boundaries', () => {
  for (const time of [0, 1, 249, 500, 999, 1000, 2000]) {
    const off = M.sample({ duty: 0 }, time), on = M.sample({ duty: 1 }, time);
    assert.equal(off.on, false); close(off.currentA, 0); close(off.switchV, 5);
    assert.equal(on.on, true); close(on.currentA, 5 / 10.1);
  }
});

test('duty changes the open interval rather than the conducting current', () => {
  const a = M.averages({ duty: .25 }), b = M.averages({ duty: .5 });
  close(a.onCurrentA, b.onCurrentA); close(a.loadAverageW * 2, b.loadAverageW);
  assert.equal(M.sample({ duty: .25 }, 249.99).on, true);
  assert.equal(M.sample({ duty: .25 }, 250).on, false);
  assert.equal(M.sample({ duty: .5 }, 250).on, true);
  assert.equal(M.sample({ duty: .25 }, 1000).on, true);
});

test('voltage and power conservation include the nonzero MOS on resistance', () => {
  for (const duty of [0, .25, .5, .75, 1]) {
    const p = { duty }, average = M.averages(p);
    close(average.sourceAverageW, average.loadAverageW + average.switchAverageW);
    for (const time of [0, 300, 700]) {
      const s = M.sample(p, time);
      close(s.loadV + s.switchV, 5);
      close(5 * s.currentA, s.loadW + s.switchW);
    }
  }
});

test('time integration of instantaneous load power agrees with the reported average', () => {
  for (const duty of [0, .25, .5, .75, 1]) {
    const p = { duty }, count = 10000;
    let total = 0;
    for (let i = 0; i < count; i++) total += M.sample(p, (i + .5) / count * 1000).loadW;
    close(total / count, M.averages(p).loadAverageW, 1e-9);
  }
});

test('valid ideal-switch limit and invalid circuit quantities remain explicit', () => {
  const ideal = M.averages({ onOhm: 0, duty: 1 });
  close(ideal.switchAverageW, 0); close(ideal.onCurrentA, .5);
  for (const p of [{ duty: -.1 }, { duty: 1.1 }, { loadOhm: 0 }, { onOhm: -1 }, { supplyV: NaN }, { periodUs: 0 }]) assert.throws(() => M.averages(p), RangeError);
  assert.throws(() => M.sample({}, Infinity), RangeError);
  assert.throws(() => M.sample({}, -1), RangeError);
});
