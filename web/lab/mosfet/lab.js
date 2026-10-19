(function () {
  'use strict';
  const M = window.MosfetLabModel;
  const $ = id => document.getElementById(id);
  const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const NS = 'http://www.w3.org/2000/svg';
  let p = M.parameters(), prediction = null, started = false, playing = false, elapsed = 0;
  let frame = null, previous = null, lastPhase = '';
  let plot;

  function svg(tag, attrs, value) {
    const node = document.createElementNS(NS, tag);
    Object.entries(attrs || {}).forEach(([name, text]) => node.setAttribute(name, String(text)));
    if (value !== undefined) node.textContent = value;
    return node;
  }
  function add(parent, ...nodes) { nodes.forEach(node => parent.appendChild(node)); }
  function chosen(container, answer) { container.querySelectorAll('button').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.answer === answer))); }
  function waveform(high, low) {
    const x = time => 70 + time / p.periodUs * 272;
    const onEnd = p.duty * p.periodUs;
    if (p.duty === 0) return `M70 ${low}H${x(elapsed)}`;
    if (p.duty === 1 || elapsed < onEnd) return `M70 ${high}H${x(elapsed)}`;
    return `M70 ${high}H${x(onEnd)}V${low}H${x(elapsed)}` + (elapsed === p.periodUs ? `V${high}` : '');
  }
  function createPlot() {
    $('timing').querySelectorAll('g').forEach(node => node.remove());
    const group = svg('g');
    add(group, svg('rect', { x: 70, y: 23, width: 272, height: 118, rx: 6, fill: '#f0eee7' }));
    for (const [y, label] of [[32, '3.3 V'], [66, '0 V'], [106, '电流高'], [140, '0 A']]) add(group, svg('text', { x: 58, y, 'text-anchor': 'end', class: 'axis' }, label));
    for (const [x, label] of [[70, '0'], [206, '500'], [342, '1000 μs']]) add(group, svg('line', { x1: x, x2: x, y1: 20, y2: 145, stroke: '#ded7c6', 'stroke-width': 1 }), svg('text', { x, y: 165, 'text-anchor': x === 342 ? 'end' : 'middle', class: 'axis' }, label));
    const gate = svg('path', { class: 'wave-gate' }), current = svg('path', { class: 'wave-current' });
    const cursor = svg('line', { x1: 70, x2: 70, y1: 20, y2: 145, stroke: '#8a642e', 'stroke-width': 1, 'stroke-dasharray': '2 3' });
    add(group, gate, current, cursor); $('timing').appendChild(group);
    plot = { gate, current, cursor };
  }
  function render() {
    const state = started ? M.sample(p, elapsed) : { on: false, gateV: 0, currentA: 0 };
    const a = M.averages(p);
    $('phase').textContent = !started ? '等待启动' : state.on ? '开：负载回路连通' : '关：负载回路断开';
    $('time').textContent = `${Math.round(elapsed)} μs`;
    $('gate-value').textContent = started ? `${state.gateV.toFixed(1)} V` : '尚未启动';
    $('switch-line').setAttribute('d', state.on ? 'M282 190V236' : 'M282 236L303 200');
    $('load-body').classList.toggle('on', state.on);
    $('current-arrows').setAttribute('visibility', state.on ? 'visible' : 'hidden');
    $('instant').textContent = started ? `${state.currentA.toFixed(3)} A` : '—';
    $('on-current').textContent = started ? `${a.onCurrentA.toFixed(3)} A` : '—';
    $('average').textContent = started ? `${a.loadAverageW.toFixed(3)} W` : '—';
    $('timeline').value = Math.round(elapsed);
    $('timeline').setAttribute('aria-valuetext', `${Math.round(elapsed)} 微秒，${state.on ? '导通' : '关断'}，电流 ${state.currentA.toFixed(3)} 安培`);
    const phase = started ? String(state.on) : 'waiting';
    if (phase !== lastPhase) {
      $('observation').textContent = !started ? 'G 发控制信号；外部 5 V 电源给负载供能。' : state.on
        ? 'G 相对 S 为 3.3 V；按本例假设开关充分导通。负载电流由外部电源提供，经负载、D、S 回到电源。'
        : 'G 被拉到 0 V；MOS 回路断开。在这个理想纯电阻模型里，负载电流为 0。紫色控制线没有替负载供电。';
      lastPhase = phase;
    }
    $('run').textContent = playing ? '暂停观察' : elapsed >= p.periodUs ? '重播这一轮' : started ? '继续节拍' : '启动节拍';
    if (started) {
      plot.gate.setAttribute('d', waveform(28, 62));
      plot.current.setAttribute('d', waveform(102, 136));
    } else { plot.gate.removeAttribute('d'); plot.current.removeAttribute('d'); }
    const cursorX = 70 + elapsed / p.periodUs * 272;
    plot.cursor.setAttribute('x1', cursorX); plot.cursor.setAttribute('x2', cursorX);
    $('timing-text').textContent = started
      ? `紫线是 G 栅压；绿线是负载电流，高电平时为 ${a.onCurrentA.toFixed(3)} A。这轮开 ${Math.round(a.onTimeUs)} μs，关 ${Math.round(a.offTimeUs)} μs。右边界也是下一轮起点。`
      : '先启动，再看控制信号与电流如何对应。灰底表示尚未观察的时段。';
  }
  function stop() { playing = false; previous = null; if (frame !== null) window.cancelAnimationFrame(frame); frame = null; }
  function finish() {
    stop(); started = true; elapsed = p.periodUs;
    $('timeline').disabled = false;
    const a = M.averages(p), result = $('result');
    result.hidden = false;
    const title = document.createElement('strong');
    title.textContent = `${Math.round(p.duty * 100)}% · 平均负载功率 ${a.loadAverageW.toFixed(3)} W`;
    result.replaceChildren(title, document.createTextNode(`假定导通时电流始终为 ${a.onCurrentA.toFixed(3)} A。占空比改变的是开着的时间，所以平均功率随之变化。换成25%或50%再观察，并记下你自己的比较。`));
    $('prediction-feedback').textContent = (prediction === 'time' ? '你的预测与模型一致。' : '本实验揭示的区别是：') + '导通期间电流由电源和电阻决定；在其他条件相同时，25%变50%是开着的时间加倍，纯电阻的平均负载功率也加倍。';
    $('timing-description').textContent = `占空比 ${Math.round(p.duty * 100)}%，每轮 ${p.periodUs} 微秒，导通 ${Math.round(a.onTimeUs)} 微秒，关闭 ${Math.round(a.offTimeUs)} 微秒。导通时电流 ${a.onCurrentA.toFixed(3)} 安培，负载平均功率 ${a.loadAverageW.toFixed(3)} 瓦。`;
    render();
  }
  function tick(time) {
    if (!playing) return;
    if (previous !== null) elapsed += Math.min(time - previous, 100) / 6000 * p.periodUs;
    previous = time;
    if (elapsed >= p.periodUs) { finish(); return; }
    render(); frame = window.requestAnimationFrame(tick);
  }
  $('prediction').querySelectorAll('button').forEach(button => button.addEventListener('click', () => {
    prediction = button.dataset.answer; chosen($('prediction'), prediction);
    $('prediction-feedback').textContent = '猜想已留在本页。先用25%运行，再试50%，留意瞬时电流与平均功率的区别。';
    $('run').disabled = false; $('finish').disabled = false;
    $('run-hint').textContent = motion.matches ? '已遵循减少动态效果设置；启动后直接看结果，再用时间拨盘观察。' : '准备好了就启动。1毫秒的一轮会放慢到6秒。';
  }));
  $('duty').addEventListener('input', () => {
    stop(); p = M.parameters({ duty: Number($('duty').value) / 100 }); elapsed = 0; started = false; lastPhase = '';
    $('duty-value').textContent = `${Math.round(p.duty * 100)}%`;
    $('duty').setAttribute('aria-valuetext', `${Math.round(p.duty * 100)}%，每轮开${Math.round(p.duty * 1000)}微秒`);
    $('result').hidden = true; $('timeline').disabled = true;
    $('timing-description').textContent = '新占空比尚未运行，启动后可观察这一轮。';
    createPlot(); render();
  });
  $('run').addEventListener('click', () => {
    if (!prediction) return;
    if (playing) { stop(); render(); return; }
    if (motion.matches) { finish(); return; }
    if (elapsed >= p.periodUs) elapsed = 0;
    playing = true; started = true; previous = null; $('timeline').disabled = false;
    render(); frame = window.requestAnimationFrame(tick);
  });
  $('finish').addEventListener('click', () => { if (prediction) finish(); });
  $('timeline').addEventListener('input', () => { stop(); elapsed = Number($('timeline').value); if (elapsed >= p.periodUs) finish(); else render(); });
  $('transfer').querySelectorAll('button').forEach(button => button.addEventListener('click', () => {
    chosen($('transfer'), button.dataset.answer);
    $('transfer-feedback').textContent = (button.dataset.answer === 'no' ? '判断正确。' : '这里不能照搬：') + '电机还有电感、反电动势和机械负载，转速不一定跟占空比成正比。要核对工作条件和实际表现；线圈关断时还要有合适续流或钳位。';
  }));
  document.addEventListener('visibilitychange', () => { if (document.hidden) { stop(); render(); } });
  window.addEventListener('pagehide', stop);
  createPlot(); render();
})();
