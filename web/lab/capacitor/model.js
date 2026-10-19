(function (root, factory) {
  'use strict';
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.CapacitorLabModel = api;
})(typeof globalThis === 'object' ? globalThis : this, function () {
  'use strict';
  const DEFAULTS = Object.freeze({ capacitanceUf: 10, extraMa: 100, pulseUs: 100 });
  const SUPPLY_V = 3.3;
  const MIN_V = 3.0;
  const BASE_MA = 40;
  const TAU_US = 40;
  const START_US = 50;

  function parameters(input = {}) {
    const p = { ...DEFAULTS, ...input };
    for (const [name, low, high] of [['capacitanceUf', 4.7, 100], ['extraMa', 0, 120], ['pulseUs', 20, 400]]) {
      if (!Number.isFinite(p[name]) || p[name] < low || p[name] > high) throw new RangeError(`Invalid ${name}`);
    }
    return p;
  }

  // Educational current-source approximation, not a regulator design model.
  // Supply current follows load current with a fixed first-order time constant.
  // With charge into the positive plate defined positive, C dV/dt = Is - Il.
  // mA * microseconds / microfarads = millivolts, hence the / 1000 below.
  function sample(input, timeUs) {
    const p = parameters(input);
    if (!Number.isFinite(timeUs) || timeUs < 0) throw new RangeError('Invalid time');
    const age = timeUs - START_US;
    let supplyExtraMa = 0;
    let loadExtraMa = 0;
    let deficitMaUs = 0;
    let phase = 'steady';
    if (age >= 0 && age < p.pulseUs) {
      const remaining = Math.exp(-age / TAU_US);
      supplyExtraMa = p.extraMa * (1 - remaining);
      loadExtraMa = p.extraMa;
      deficitMaUs = p.extraMa * TAU_US * (1 - remaining);
      phase = 'support';
    } else if (age >= p.pulseUs) {
      const pulseResponse = 1 - Math.exp(-p.pulseUs / TAU_US);
      const remaining = Math.exp(-(age - p.pulseUs) / TAU_US);
      supplyExtraMa = p.extraMa * pulseResponse * remaining;
      deficitMaUs = p.extraMa * TAU_US * pulseResponse * remaining;
      phase = 'recharge';
    }
    const supplyMa = BASE_MA + supplyExtraMa;
    const loadMa = BASE_MA + loadExtraMa;
    const voltage = SUPPLY_V - deficitMaUs / p.capacitanceUf / 1000;
    return { timeUs, supplyMa, loadMa, capacitorMa: supplyMa - loadMa, voltage, phase, belowMinimum: voltage < MIN_V };
  }

  function minimum(input) {
    const p = parameters(input);
    return sample(p, START_US + p.pulseUs).voltage;
  }

  function duration(input) { return START_US + parameters(input).pulseUs + TAU_US * 7; }

  function series(input, endUs = duration(input), count = 240) {
    const p = parameters(input);
    if (!Number.isInteger(count) || count < 2 || count > 5000) throw new RangeError('Invalid sample count');
    if (!Number.isFinite(endUs) || endUs < 0) throw new RangeError('Invalid end time');
    const times = Array.from({ length: count + 1 }, (_, i) => endUs * i / count);
    // Include both sides of abrupt load changes, and the exact minimum voltage.
    for (const edge of [START_US, START_US + p.pulseUs]) {
      if (edge <= endUs) times.push(Math.max(0, edge - 1e-6), edge);
    }
    return [...new Set(times)].sort((a, b) => a - b).map(time => sample(p, time));
  }

  return Object.freeze({ DEFAULTS, SUPPLY_V, MIN_V, BASE_MA, TAU_US, START_US, parameters, sample, minimum, duration, series });
});
