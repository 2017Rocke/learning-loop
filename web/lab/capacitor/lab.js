(function () {
  'use strict';
  const M = window.CapacitorLabModel;
  const $ = id => document.getElementById(id);
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const NS = 'http://www.w3.org/2000/svg';
  let parameters = M.parameters();
  let prediction = null;
  let reference = null;
  let elapsed = 0;
  let started = false;
  let completed = false;
  let playing = false;
  let frame = null;
  let previousTime = null;
  let lastPhase = '';
  let voltagePlot;
  let currentPlot;

  function svg(tag, attrs, value) {
    const node = document.createElementNS(NS, tag);
    Object.entries(attrs || {}).forEach(([name, text]) => node.setAttribute(name, String(text)));
    if (value !== undefined) node.textContent = value;
    return node;
  }
  function append(parent, ...nodes) { nodes.forEach(node => parent.appendChild(node)); }
  function chosen(container, value) {
    container.querySelectorAll('button').forEach(node => node.setAttribute('aria-pressed', String(node.dataset.answer === value)));
  }
  function controls() { return { capacitanceUf: Number($('capacity').value), extraMa: Number($('extra').value), pulseUs: Number($('pulse').value) }; }
  function plotBase(id, yMin, yMax, ticks, bottom) {
    const target = $(id);
    target.querySelectorAll('g').forEach(node => node.remove());
    const group = svg('g');
    const left = 43, right = 344, top = 15;
    const x = value => left + value / M.duration(parameters) * (right - left);
    const y = value => bottom - (value - yMin) / (yMax - yMin) * (bottom - top);
    append(group, svg('rect', { x: x(M.START_US), y: top, width: x(M.START_US + parameters.pulseUs) - x(M.START_US), height: bottom - top, fill: '#eee9fc', opacity: '.55' }));
    for (const tick of ticks) {
      append(group, svg('line', { x1: left, x2: right, y1: y(tick), y2: y(tick), class: 'chart-grid' }), svg('text', { x: left - 8, y: y(tick) + 4, 'text-anchor': 'end', class: 'chart-axis' }, tick.toFixed(id === 'voltage-chart' ? 1 : 0)));
    }
    for (const tick of [0, M.START_US + parameters.pulseUs, M.duration(parameters)]) {
      append(group, svg('line', { x1: x(tick), x2: x(tick), y1: bottom, y2: bottom + 4, class: 'chart-tick' }), svg('text', { x: x(tick), y: bottom + 18, 'text-anchor': tick === 0 ? 'start' : 'end', class: 'chart-axis' }, `${tick} μs`));
    }
    append(group, svg('text', { x: left, y: 10, class: 'chart-axis' }, id === 'voltage-chart' ? 'V' : 'mA'));
    const cursor = svg('line', { x1: left, x2: left, y1: top, y2: bottom, class: 'chart-cursor' });
    target.appendChild(group);
    return { group, x, y, cursor };
  }
  function path(points, axis, field) { return points.map((point, index) => `${index ? 'L' : 'M'}${axis.x(point.timeUs).toFixed(2)} ${axis.y(point[field]).toFixed(2)}`).join(' '); }
  function buildPlots() {
    const predictedMinimum = Math.min(M.minimum(parameters), reference ? M.minimum(reference) : M.SUPPLY_V);
    const lower = Math.min(2.8, Math.floor((predictedMinimum - .08) * 10) / 10);
    voltagePlot = plotBase('voltage-chart', lower, 3.4, [lower, 3.0, 3.3], 153);
    append(voltagePlot.group, svg('line', { x1: voltagePlot.x(0), x2: voltagePlot.x(M.duration(parameters)), y1: voltagePlot.y(M.MIN_V), y2: voltagePlot.y(M.MIN_V), class: 'chart-limit' }));
    if (reference) append(voltagePlot.group, svg('path', { d: path(M.series(reference), voltagePlot, 'voltage'), class: 'chart-reference' }));
    voltagePlot.line = svg('path', { class: 'chart-voltage' });
    append(voltagePlot.group, voltagePlot.line, voltagePlot.cursor);
    currentPlot = plotBase('current-chart', 0, 180, [0, 80, 160], 138);
    currentPlot.supply = svg('path', { class: 'chart-supply' });
    currentPlot.load = svg('path', { class: 'chart-load' });
    append(currentPlot.group, currentPlot.supply, currentPlot.load, currentPlot.cursor);
  }
  function setReading(id, amount) {
    const target = $(id);
    target.replaceChildren(document.createTextNode(`${amount.toFixed(1)} `));
    const unit = document.createElement('small');
    unit.textContent = 'mA';
    target.appendChild(unit);
  }
  function phaseMessage(state) {
    if (!started) return ['准备中', '先预测，再开始。所有结果都由你选的参数计算，不是真实板子的测量。'];
    if (state.phase === 'steady') return ['平时供电', '芯片需要 40 mA，电源也提供 40 mA。电容两端已有电压，此时没有净充放电电流。'];
    if (state.phase === 'support') return ['电容补上差额', '芯片需求突然增加，电源正在跟上。缺的那部分由电容暂时补上，因此电容与芯片两端的电压一起下降。'];
    if (state.capacitorMa < .2) return ['接近初始状态', '电源已接近平时的 40 mA，电容也接近充回 3.3 V。这个理想模型会逐渐回到初始状态。'];
    return ['电源给电容回充', '芯片已经不忙了，电源电流还没立刻降下来。超过芯片需求的部分流入电容，电压逐渐回升。'];
  }
  function render() {
    const state = M.sample(parameters, elapsed);
    $('clock').textContent = `${elapsed.toFixed(0)} μs`;
    $('rail-voltage').textContent = `${state.voltage.toFixed(3)} V`;
    $('circuit-capacity').textContent = `电容 ${parameters.capacitanceUf} μF`;
    setReading('supply-value', state.supplyMa);
    setReading('load-value', state.loadMa);
    setReading('cap-value', Math.abs(state.capacitorMa));
    $('cap-label').textContent = Math.abs(state.capacitorMa) < .05 ? '电容近乎待命' : state.capacitorMa < 0 ? '电容补给' : '电容回充';
    const arrowVisible = Math.abs(state.capacitorMa) >= .2;
    for (const id of ['cap-arrow-top', 'cap-arrow-bottom']) $(id).setAttribute('visibility', arrowVisible ? 'visible' : 'hidden');
    $('cap-arrow-top').setAttribute('d', state.capacitorMa < 0 ? 'M180 109V84' : 'M180 84V109');
    $('cap-arrow-bottom').setAttribute('d', state.capacitorMa < 0 ? 'M180 176V151' : 'M180 151V176');
    const [phase, message] = phaseMessage(state);
    $('phase-tag').textContent = phase;
    if (lastPhase !== phase) { $('phase-note').textContent = message; lastPhase = phase; }
    $('timeline').value = Math.round(elapsed / M.duration(parameters) * 1000);
    $('timeline').setAttribute('aria-valuetext', `${elapsed.toFixed(0)} 微秒，电压 ${state.voltage.toFixed(3)} 伏，${phase}`);
    const points = M.series(parameters, elapsed);
    voltagePlot.line.setAttribute('d', path(points, voltagePlot, 'voltage'));
    currentPlot.supply.setAttribute('d', path(points, currentPlot, 'supplyMa'));
    currentPlot.load.setAttribute('d', path(points, currentPlot, 'loadMa'));
    for (const plot of [voltagePlot, currentPlot]) {
      plot.cursor.setAttribute('x1', plot.x(elapsed)); plot.cursor.setAttribute('x2', plot.x(elapsed));
    }
    $('run').textContent = playing ? '暂停观察' : completed && elapsed >= M.duration(parameters) ? '重播这次实验' : started ? '继续接力' : '开始接力';
  }
  function stop() {
    playing = false;
    previousTime = null;
    if (frame !== null) window.cancelAnimationFrame(frame);
    frame = null;
  }
  function finish() {
    stop();
    started = true;
    completed = true;
    elapsed = M.duration(parameters);
    $('timeline').disabled = false;
    $('compare').disabled = false;
    const min = M.minimum(parameters), drop = M.SUPPLY_V - min;
    const text = min < M.MIN_V
      ? '低于本例的 3.0 V 下限。电容并没有“完全没电”，但本例已不能保证芯片的正常供电要求。'
      : '没有低于本例的 3.0 V 下限。这只表示此简化模型下满足设定，不等于真实电路已经通过验证。';
    const result = $('result');
    result.hidden = false;
    result.classList.toggle('warning', min < M.MIN_V);
    const headline = document.createElement('strong');
    headline.textContent = `最低 ${min.toFixed(3)} V · 下降 ${(drop * 1000).toFixed(0)} mV`;
    result.replaceChildren(headline, document.createTextNode(text));
    $('voltage-description').textContent = `本次电容 ${parameters.capacitanceUf} 微法，额外负载 ${parameters.extraMa} 毫安、持续 ${parameters.pulseUs} 微秒。电压最低 ${min.toFixed(3)} 伏，随后回充并接近 3.3 伏。${text}`;
    $('prediction-feedback').textContent = prediction === 'less'
      ? '你的猜想与模型一致：同样电流缺口下，容量更大，电压下降更少。现在保留这次曲线，只改容量再验证一次。'
      : '模型给出的线索：同样电流缺口下，容量更大，电压下降更少。可以保留这次曲线，再换一个容量验证。';
    render();
  }
  function tick(time) {
    if (!playing) return;
    if (previousTime !== null) elapsed += Math.min(time - previousTime, 100) / 9000 * M.duration(parameters);
    previousTime = time;
    if (elapsed >= M.duration(parameters)) { finish(); return; }
    render();
    frame = window.requestAnimationFrame(tick);
  }
  function reset() {
    stop();
    parameters = M.parameters(controls());
    if (reference && (reference.extraMa !== parameters.extraMa || reference.pulseUs !== parameters.pulseUs)) {
      reference = null;
      $('comparison').textContent = '负载条件变了，已清除旧对照。要比较容量，请保持额外电流与持续时间相同。';
    }
    elapsed = 0; started = false; completed = false; lastPhase = '';
    $('result').hidden = true;
    $('compare').disabled = true;
    $('timeline').disabled = true;
    $('run-hint').textContent = prediction ? '准备好后开始；动画会把几百微秒放慢到 9 秒。' : '需先选一个猜想。动画会把几百微秒放慢到 9 秒。';
    $('voltage-description').textContent = '尚未运行新条件。开始后显示曲线与数值结论。';
    buildPlots(); render();
  }

  $('prediction-choices').querySelectorAll('button').forEach(node => node.addEventListener('click', () => {
    prediction = node.dataset.answer;
    chosen($('prediction-choices'), prediction);
    $('prediction-feedback').textContent = '猜想已留在本页。现在运行实验，留意电源追上需求之前的那段电压变化。';
    $('run').disabled = false;
    $('finish').disabled = false;
    $('run-hint').textContent = reducedMotion.matches ? '已遵循减少动态效果设置；点击开始会直接展示完整结果，也可拖动时间拨盘。' : '准备好后开始；动画会把几百微秒放慢到 9 秒。';
  }));
  $('run').addEventListener('click', () => {
    if (!prediction) return;
    if (playing) { stop(); render(); return; }
    if (reducedMotion.matches) { finish(); return; }
    if (elapsed >= M.duration(parameters)) elapsed = 0;
    started = true; playing = true;
    $('timeline').disabled = false;
    previousTime = null;
    render();
    frame = window.requestAnimationFrame(tick);
  });
  $('finish').addEventListener('click', () => { if (prediction) finish(); });
  $('timeline').addEventListener('input', () => {
    stop();
    elapsed = Number($('timeline').value) / 1000 * M.duration(parameters);
    if (elapsed >= M.duration(parameters)) finish(); else render();
  });
  ['capacity', 'extra', 'pulse'].forEach(id => $(id).addEventListener('change', reset));
  $('compare').addEventListener('click', () => {
    reference = { ...parameters };
    $('comparison').textContent = `灰色点线为对照：${reference.capacitanceUf} μF，最低 ${M.minimum(reference).toFixed(3)} V。保持负载相同，只改“电容大小”，再开始一次。`;
    reset();
    $('capacity').focus();
  });
  $('transfer-choices').querySelectorAll('button').forEach(node => node.addEventListener('click', () => {
    chosen($('transfer-choices'), node.dataset.answer);
    $('transfer-feedback').textContent = (node.dataset.answer === 'no' ? '判断正确。' : '还差一个边界：') + '只要长期有 20 mA 缺口，电容电压就持续下降。更大容量只延缓下降，不能补足持续功率；要从电源能力或负载需求解决。达到允许电压下限之前，就需要处理，不能等“放完电”。';
  }));
  document.addEventListener('visibilitychange', () => { if (document.hidden) { stop(); render(); } });
  window.addEventListener('pagehide', stop);
  buildPlots(); render();
})();
