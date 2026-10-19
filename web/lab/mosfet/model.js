(function (root, factory) {
  'use strict';
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.MosfetLabModel = api;
})(typeof globalThis === 'object' ? globalThis : this, function () {
  'use strict';
  const DEFAULTS = Object.freeze({ duty: .25, supplyV: 5, loadOhm: 10, onOhm: .1, periodUs: 1000 });
  function parameters(input = {}) {
    const p = { ...DEFAULTS, ...input };
    for (const key of Object.keys(DEFAULTS)) if (!Number.isFinite(p[key])) throw new RangeError(`Invalid ${key}`);
    if (p.duty < 0 || p.duty > 1 || p.supplyV <= 0 || p.loadOhm <= 0 || p.onOhm < 0 || p.periodUs <= 0) throw new RangeError('Invalid circuit parameters');
    return p;
  }
  // Synthetic low-side switch model. Gate HIGH is assumed to produce the fixed
  // on resistance; this is not inferred from Vgs(th), nor a device specification.
  // Resistive load only: ideal switching, no inductance, leakage or gate losses.
  function averages(input) {
    const p = parameters(input);
    const onCurrentA = p.supplyV / (p.loadOhm + p.onOhm);
    const loadOnW = onCurrentA ** 2 * p.loadOhm;
    const switchOnW = onCurrentA ** 2 * p.onOhm;
    return { onCurrentA, averageCurrentA: p.duty * onCurrentA, loadOnW, switchOnW,
      loadAverageW: p.duty * loadOnW, switchAverageW: p.duty * switchOnW,
      sourceAverageW: p.duty * p.supplyV * onCurrentA,
      onTimeUs: p.duty * p.periodUs, offTimeUs: (1 - p.duty) * p.periodUs };
  }
  function sample(input, timeUs) {
    const p = parameters(input);
    if (!Number.isFinite(timeUs) || timeUs < 0) throw new RangeError('Invalid time');
    const phase = timeUs % p.periodUs;
    const on = p.duty === 1 || (p.duty > 0 && phase < p.duty * p.periodUs);
    const a = averages(p), currentA = on ? a.onCurrentA : 0;
    return { timeUs, on, gateV: on ? 3.3 : 0, currentA, loadV: currentA * p.loadOhm,
      switchV: on ? currentA * p.onOhm : p.supplyV,
      loadW: currentA ** 2 * p.loadOhm, switchW: currentA ** 2 * p.onOhm };
  }
  return Object.freeze({ DEFAULTS, parameters, averages, sample });
});
