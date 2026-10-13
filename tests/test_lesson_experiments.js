'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { bayesCounts, gradeCells, gradePosterior } = require('../web/lesson-experiments.js');

test('Bayes splits the whole population once and conditions on both alarm paths', () => {
  const result = bayesCounts(1, 90, 5);
  assert.deepEqual(result.cells, [90, 10, 495, 9405]);
  assert.equal(result.cells.reduce((a,b) => a+b), 10000);
  assert.equal(result.alarm, 585);
  assert.equal(result.posterior, 90 / 585 * 100);
  assert.equal(bayesCounts(10, 90, 5).posterior, 900 / 1350 * 100);
  assert.throws(() => bayesCounts(NaN, 90, 5));
  assert.throws(() => bayesCounts(-1, 90, 5));
});
test('empty cells are not accepted as zero; corrective hints identify the wrong branch', () => {
  const result = bayesCounts(1, 90, 5);
  const grades = gradeCells(['90', '', '5', '9405'], result);
  assert.deepEqual(grades.map(g => g.ok), [true, false, false, true]);
  assert.match(grades[2].hint, /9,900.*正常件/);
  assert.equal(gradeCells(['0', '0', '0', '10000'], bayesCounts(0, 90, 0)).every(g => g.ok), true);
  assert.equal(gradeCells(['', '0', '0', '10000'], bayesCounts(0, 90, 0))[0].ok, false);
});
test('denominator errors receive different feedback from arithmetic errors', () => {
  const r = bayesCounts(1, 90, 5);
  assert.match(gradePosterior('10000', '0.9', r).hint, /原来的总体/);
  assert.match(gradePosterior('100', '90', r).hint, /另一方向/);
  assert.match(gradePosterior('585', '90', r).hint, /分母选对/);
  assert.equal(gradePosterior('585', '15.4', r).ok, true);
  assert.equal(gradePosterior('585', '', r).ok, false);
  assert.equal(gradePosterior('', '0', bayesCounts(0, 0, 0)).ok, false);
});
test('no alarms means undefined probability, never a false zero-percent claim', () => {
  const r = bayesCounts(10, 0, 0);
  assert.equal(r.alarm, 0); assert.equal(r.posterior, null);
  assert.match(gradePosterior('0', '0', r).hint, /不能定义/);
});
