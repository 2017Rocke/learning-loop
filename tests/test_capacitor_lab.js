'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const M = require('../web/lab/capacitor/model.js');
const close = (actual, expected, tolerance = 1e-9) => assert.ok(Math.abs(actual - expected) < tolerance, `${actual} vs ${expected}`);

test('steady load receives supply current while charged capacitor has no net current', () => {
  const state = M.sample({}, 20);
  close(state.voltage, 3.3); close(state.supplyMa, 40); close(state.loadMa, 40); close(state.capacitorMa, 0);
});

test('load edge is abrupt but supply current and capacitor voltage stay continuous', () => {
  for (const edge of [M.START_US, M.START_US + M.DEFAULTS.pulseUs]) {
    const before = M.sample({}, edge - 1e-7), after = M.sample({}, edge);
    close(before.voltage, after.voltage, 1e-8);
    close(before.supplyMa, after.supplyMa, 1e-6);
    close(Math.abs(before.loadMa - after.loadMa), 100);
  }
  assert.equal(M.sample({}, M.START_US).capacitorMa, -100);
});

test('instantaneous charge conservation agrees with independent numerical voltage derivative', () => {
  for (const capacitanceUf of [4.7, 10, 22, 47]) {
    const p = { capacitanceUf, pulseUs: 100, extraMa: 120 };
    for (const time of [30, 60, 100, 149, 160, 240, 350]) {
      const state = M.sample(p, time);
      close(state.supplyMa, state.loadMa + state.capacitorMa);
      const h = 1e-3;
      const derivativeVperUs = (M.sample(p, time + h).voltage - M.sample(p, time - h).voltage) / (2 * h);
      close(derivativeVperUs * capacitanceUf * 1000, state.capacitorMa, 1e-6);
    }
  }
});

test('same pulse with double capacitance halves droop and does not change supply response', () => {
  const p = { capacitanceUf: 10 }, q = { capacitanceUf: 20 };
  for (const time of [70, 120, 150, 200, 400]) {
    const a = M.sample(p, time), b = M.sample(q, time);
    close(3.3 - a.voltage, 2 * (3.3 - b.voltage));
    close(a.supplyMa, b.supplyMa); close(a.loadMa, b.loadMa);
  }
});

test('when load ends current recharges capacitor, approaching initial voltage without invented energy', () => {
  const p = M.DEFAULTS;
  const end = M.START_US + p.pulseUs;
  const atEnd = M.sample(p, end), later = M.sample(p, end + 100), settled = M.sample(p, end + 2000);
  assert.ok(atEnd.capacitorMa > 0);
  assert.ok(later.voltage > atEnd.voltage && later.voltage < 3.3);
  close(settled.voltage, 3.3);
  close(M.minimum(p), atEnd.voltage);
  // Integrate signed capacitor current by midpoint quadrature, splitting at jumps.
  const integrate = (from, to) => {
    const n = 20000, width = (to - from) / n;
    let charge = 0;
    for (let i = 0; i < n; i++) charge += M.sample(p, from + (i + .5) * width).capacitorMa * width;
    return charge;
  };
  const out = integrate(M.START_US, end), back = integrate(end, end + 2000);
  close(out + back, 0, .002);
});

test('threshold failure is a voltage constraint, not an empty capacitor', () => {
  assert.ok(M.minimum({ capacitanceUf: 10 }) < M.MIN_V);
  assert.ok(M.minimum({ capacitanceUf: 10 }) > 0);
  assert.ok(M.minimum({ capacitanceUf: 22 }) > M.MIN_V);
});

test('zero pulse amplitude keeps voltage constant and invalid quantities are rejected', () => {
  for (const state of M.series({ extraMa: 0 })) {
    close(state.voltage, M.SUPPLY_V); close(state.capacitorMa, 0);
  }
  for (const p of [{ capacitanceUf: 0 }, { extraMa: Infinity }, { pulseUs: -1 }, { capacitanceUf: '10' }]) assert.throws(() => M.sample(p, 100), RangeError);
  assert.throws(() => M.sample({}, NaN), RangeError);
  assert.throws(() => M.sample({}, -1), RangeError);
});

test('chart samples include the pulse edges and exact minimum without hidden undersampling', () => {
  const p = { pulseUs: 200, capacitanceUf: 4.7, extraMa: 120 };
  const samples = M.series(p);
  assert.ok(samples.some(item => item.timeUs === M.START_US));
  assert.ok(samples.some(item => item.timeUs === M.START_US + p.pulseUs));
  close(Math.min(...samples.map(item => item.voltage)), M.minimum(p));
  assert.ok(samples.every((item, index) => index === 0 || item.timeUs > samples[index - 1].timeUs));
});
