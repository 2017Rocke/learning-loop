'use strict';

// Course data stays plain text. Only verified, same-origin media paths enter DOM attributes.
window.LessonVisuals = (() => {
  const mediaURL = value => {
    if (typeof value !== 'string' || !value) return null;
    try { const u = new URL(value, location.origin); return u.origin === location.origin && /^\/media\//.test(u.pathname) ? u.href : null; } catch { return null; }
  };
  const timeLabel = seconds => `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`;

  function create({ el, button, link, onCleanup, assetBase = null }) {
    const resolveMedia = value => {
      if (!assetBase) return mediaURL(value);
      if (typeof value !== 'string' || !value.startsWith('/media/')) return null;
      try {
        const base = new URL('.', assetBase);
        const result = new URL(value.slice(1), base);
        return result.origin === base.origin && result.pathname.startsWith(`${base.pathname}media/`) ? result.href : null;
      } catch { return null; }
    };
    const localAsset = path => assetBase ? new URL(path, new URL('.', assetBase)).href : `/${path}`;
    let preferredAudioRate = 1;
    const audioDisposers = new WeakMap();
    function fold(label, ...content) { return el('details', { class: 'lesson-fold' }, el('summary', {}, label), el('div', { class: 'fold-body' }, content)); }

    function exclusivePlayback(player) {
      const stopOthers = () => { for (const other of document.querySelectorAll('audio, video')) if (other !== player) other.pause(); };
      player.addEventListener('play', stopOthers);
      return () => player.removeEventListener('play', stopOthers);
    }

    function audioNarration(lesson, chapter, walkthroughID = null) {
      const audioLesson = lesson.audio_lesson;
      const clip = audioLesson?.clips?.find(item => item.chapter === chapter && (item.walkthrough_id ?? null) === walkthroughID);
      const sourceURL = resolveMedia(clip?.src);
      if (!clip || !sourceURL) return document.createDocumentFragment();
      const extension = new URL(sourceURL).pathname.split('.').pop().toLowerCase();
      const source = el('source', { src: sourceURL, type: ({ wav: 'audio/wav', m4a: 'audio/mp4', mp3: 'audio/mpeg' })[extension] || 'audio/mpeg' });
      const player = el('audio', { class: 'narration-audio', controls: true, preload: 'metadata', 'aria-label': clip.title || '中文课程语音' }, source, '浏览器暂不支持播放音频，可展开下方旁白全文。');
      player.playbackRate = preferredAudioRate;
      const duration = el('span', { class: 'narration-duration' }, Number.isFinite(clip.duration_seconds) && clip.duration_seconds > 0 ? timeLabel(clip.duration_seconds) : '中文讲解');
      const speed = el('select', { class: 'narration-speed', 'aria-label': '语音播放速度', on: { change: event => { preferredAudioRate = Number(event.target.value); player.playbackRate = preferredAudioRate; } } }, [0.8, 1, 1.25, 1.5].map(rate => el('option', { value: rate }, `${rate} ×`))); speed.value = String(preferredAudioRate);
      const status = el('p', { class: 'narration-status', role: 'status' });
      let retryAt = null;
      const retry = button('重新加载这段语音', () => {
        if (disposed) return;
        retryAt = Number.isFinite(player.currentTime) ? player.currentTime : 0;
        status.textContent = '正在重新读取语音…'; retry.hidden = true;
        player.load();
        const attempt = player.play();
        attempt?.catch(() => { if (!disposed && !player.error) { status.textContent = '语音已重新加载，请点击播放继续。'; retry.hidden = false; } });
      }, 'small outline narration-retry');
      retry.hidden = true;
      const transcript = clip.transcript ? fold('展开旁白全文', el('p', { class: 'narration-transcript' }, clip.transcript)) : null;
      const card = el('section', { class: `narration-card${walkthroughID === null ? '' : ' snippet-narration'}`, 'aria-label': walkthroughID === null ? '听这一节的中文讲解' : '听这个代码片段的逐行讲解' },
        el('div', { class: 'narration-heading' }, el('div', { class: 'narration-title-group' }, el('span', { class: 'narration-icon', 'aria-hidden': 'true' }, '◖♪◗'), el('strong', {}, clip.title || '听一遍中文讲解')), duration),
        el('div', { class: 'narration-controls' }, player, el('label', { class: 'narration-speed-label' }, '语速', speed)),
        el('p', { class: 'narration-note' }, audioLesson.voice || '本机合成中文语音', ' · 点击播放，可以暂时移开视线'), status, retry, transcript);
      const stopExclusive = exclusivePlayback(player);
      let disposed = false;
      const failed = () => {
        if (disposed) return;
        player.pause();
        const code = player.error?.code || 0;
        const reason = ({ 1: '语音播放被中断', 2: '语音读取中断', 3: '语音解码失败', 4: '当前设备无法读取这段语音' })[code] || '语音暂时无法播放';
        status.textContent = `${reason}，可以重新加载；仍失败时请把此提示截图反馈（音频 ${code || '未知'}）。旁白全文仍可阅读。`;
        retry.hidden = false;
        if (transcript) transcript.open = true;
      };
      const metadata = () => {
        if (Number.isFinite(player.duration) && player.duration > 0) duration.textContent = timeLabel(player.duration);
        player.playbackRate = Number(speed.value);
        if (retryAt !== null) { player.currentTime = Math.min(retryAt, Math.max(0, (player.duration || 0) - .1)); retryAt = null; }
      };
      const playing = () => { status.textContent = ''; retry.hidden = true; };
      player.addEventListener('error', failed); source.addEventListener('error', failed); player.addEventListener('loadedmetadata', metadata); player.addEventListener('playing', playing);
      const dispose = () => {
        if (disposed) return;
        disposed = true; stopExclusive(); player.removeEventListener('error', failed); source.removeEventListener('error', failed); player.removeEventListener('loadedmetadata', metadata); player.removeEventListener('playing', playing); player.pause(); source.removeAttribute('src'); player.removeAttribute('src'); player.load();
      };
      audioDisposers.set(card, dispose); onCleanup(dispose);
      return card;
    }

    function imageCard(step, className = '') {
      const imageURL = resolveMedia(step?.image);
      const figure = el('figure', { class: `lesson-figure ${className}` });
      const fallback = () => figure.replaceChildren(el('div', { class: 'figure-fallback' }, el('span', { class: 'figure-symbol', 'aria-hidden': 'true' }, '↔'), el('strong', {}, step?.title || '观察输入与输出'), el('p', {}, step?.caption || '先预测变化，再通过实验检查。')));
      if (imageURL) figure.append(el('img', { src: imageURL, alt: step.alt || step.title || '课程原理图', loading: 'lazy', decoding: 'async', on: { error: fallback } }));
      else fallback();
      return figure;
    }

    function videoLesson(visual) {
      const source = resolveMedia(visual?.video?.src);
      if (!source) return document.createDocumentFragment();
      const item = visual.video;
      const status = el('p', { class: 'video-status', role: 'status' });
      const captionURL = resolveMedia(item.captions);
      const player = el('video', { class: 'lesson-video', controls: true, playsinline: true, preload: 'metadata', poster: resolveMedia(item.poster), 'aria-label': item.title || '课程原理短片' }, el('source', { src: source, type: new URL(source).pathname.endsWith('.webm') ? 'video/webm' : 'video/mp4' }), captionURL ? el('track', { kind: 'captions', src: captionURL, srclang: 'zh', label: '中文字幕', default: true }) : null, '浏览器暂不支持视频，可继续使用下方图解。');
      const stopExclusive = exclusivePlayback(player);
      const shell = el('div', { class: 'lesson-player' }, player);
      const fallback = () => {
        if (shell.dataset.failed) return;
        shell.dataset.failed = 'true';
        player.pause();
        shell.replaceChildren(imageCard(visual.steps?.[0] || { title: '继续看分步图解' }));
        status.textContent = '短片暂时无法播放。下方图解包含同样的核心过程，可以继续学习。';
      };
      player.addEventListener('error', fallback);
      player.querySelector('source').addEventListener('error', fallback);
      onCleanup(() => { stopExclusive(); player.removeEventListener('error', fallback); player.querySelector('source')?.removeEventListener('error', fallback); player.pause(); player.removeAttribute('src'); player.querySelector('source')?.removeAttribute('src'); player.load(); });
      const chapters = (item.transcript || []).filter(part => Number.isFinite(part.time) && part.time >= 0 && typeof part.text === 'string');
      const transcript = chapters.length ? fold('查看分镜讲解 · 点击时间跳转', el('ol', { class: 'video-transcript' }, chapters.map(part => el('li', {}, el('button', { type: 'button', class: 'timecode', 'aria-label': `跳到 ${timeLabel(part.time)}：${part.text}`, on: { click: () => {
        if (shell.dataset.failed) { status.textContent = '视频不可用，请阅读讲解或下方图解。'; return; }
        const seek = () => { player.currentTime = Number.isFinite(player.duration) ? Math.min(part.time, Math.max(0, player.duration - .05)) : part.time; player.focus(); };
        if (player.readyState >= 1) seek(); else { player.addEventListener('loadedmetadata', seek, { once: true }); player.load(); }
      } } }, timeLabel(part.time)), el('span', {}, part.text))))) : null;
      return el('section', { class: 'video-lesson', 'aria-label': '先看一段原理短片' },
        el('div', { class: 'visual-heading' }, el('span', { class: 'visual-eyebrow' }, '01 · 先看见，再理解'), el('span', { class: 'visual-duration' }, `${timeLabel(Number(item.duration_seconds) || 0)} 原理短片 · 可暂停`)),
        shell, el('div', { class: 'video-caption' }, el('strong', {}, item.title || '看一遍核心过程'), el('span', {}, '点播放开始，按你的节奏观看')),
        status, transcript, item.attribution ? el('p', { class: 'media-attribution' }, item.attribution) : null);
    }

    function stepLesson(visual, legacyIdeas = []) {
      const steps = visual?.steps?.length ? visual.steps : legacyIdeas.map((idea, i) => ({ id: String(i), title: idea.title, caption: idea.explanation }));
      if (!steps.length) return document.createDocumentFragment();
      let selected = 0;
      const answers = new Map();
      const stage = el('div');
      const tabs = el('div', { class: 'visual-step-tabs', role: 'tablist', 'aria-label': '原理图解步骤' });
      const view = el('section', { class: 'step-lesson' }, el('div', { class: 'visual-heading' }, el('span', { class: 'visual-eyebrow' }, '逐步拆开 · 每次理解一个变化'), el('span', { class: 'visual-duration' }, `${steps.length} 幅图解`)), tabs, stage);
      function show(index, focusTab = false) {
        selected = Math.max(0, Math.min(steps.length - 1, index));
        tabs.replaceChildren(...steps.map((step, i) => el('button', { type: 'button', class: `visual-step-tab${i === selected ? ' active' : ''}`, role: 'tab', 'aria-selected': String(i === selected), 'aria-controls': 'visual-step-panel', id: `visual-tab-${i}`, tabindex: i === selected ? '0' : '-1', on: { click: () => show(i), keydown: event => {
          let next;
          if (event.key === 'ArrowRight') next = (i + 1) % steps.length;
          if (event.key === 'ArrowLeft') next = (i - 1 + steps.length) % steps.length;
          if (event.key === 'Home') next = 0;
          if (event.key === 'End') next = steps.length - 1;
          if (next !== undefined) { event.preventDefault(); show(next, true); }
        } } }, el('span', {}, String(i + 1).padStart(2, '0')), el('strong', {}, String(step.title).replace(/^\d+\s*[·.、]\s*/, '')))));
        const step = steps[selected];
        const panel = el('div', { class: 'visual-step-panel', role: 'tabpanel', id: 'visual-step-panel', 'aria-labelledby': `visual-tab-${selected}` }, imageCard(step), el('div', { class: 'visual-step-copy' }, el('h3', {}, step.title), el('p', {}, step.caption)));
        const q = step.question;
        if (q?.prompt && q.options?.length) {
          const feedback = el('div', { class: 'prediction-feedback', role: 'status', 'aria-live': 'polite' });
          const options = el('div', { class: 'prediction-options' });
          function reveal(choice) {
            answers.set(selected, choice);
            [...options.children].forEach((option, i) => { option.className = `prediction-option${i === choice ? ' selected' : ''}${i === q.correct_index ? ' correct' : ''}`; option.setAttribute('aria-pressed', String(i === choice)); });
            const correct = choice === q.correct_index;
            feedback.className = `prediction-feedback ${correct ? 'correct' : 'retry'}`;
            feedback.replaceChildren(el('strong', {}, correct ? '预测吻合' : '这里值得再观察'), el('span', {}, q.explanation || `参考选择：${q.options[q.correct_index] || '请继续观察图解。'}`));
          }
          options.append(...q.options.map((option, i) => el('button', { type: 'button', class: 'prediction-option', 'aria-pressed': 'false', on: { click: () => reveal(i) } }, el('span', { class: 'option-marker' }, String.fromCharCode(65 + i)), option)));
          if (answers.has(selected)) reveal(answers.get(selected));
          panel.append(el('div', { class: 'prediction' }, el('div', { class: 'prediction-kicker' }, '停一下，先预测'), el('p', { class: 'prediction-prompt' }, q.prompt), options, feedback));
        }
        panel.append(el('div', { class: 'visual-step-controls' }, button('← 上一幅', () => show(selected - 1), 'ghost', null, selected === 0), el('span', {}, `${selected + 1} / ${steps.length}`), button('下一幅 →', () => show(selected + 1), 'outline', null, selected === steps.length - 1)));
        stage.replaceChildren(panel);
        if (focusTab) tabs.children[selected].focus();
      }
      show(0);
      return view;
    }

    function gaussianViewer(config) {
      if (config?.kind !== 'gaussian-viewer') return document.createDocumentFragment();
      const canvas = el('canvas', { class: 'gaussian-canvas', role: 'img', 'aria-label': '合成三维杯子。改变相机角度，观察高斯位置如何投影到画面。' });
      let theta = 24;
      let mode = 'splat';
      let size = 1;
      let playing = false;
      let alive = true;
      let frame = null;
      let lastTime = 0;
      const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
      const context = canvas.getContext('2d');
      const points = [];
      // A cylindrical shell, rim, bottom and handle. These are synthetic 3D points,
      // not a reconstruction; each screen-space Gaussian is drawn by alpha blending.
      for (let row = 0; row < 24; row++) for (let col = 0; col < 64; col++) {
        const angle = col / 64 * Math.PI * 2;
        const y = row / 23 * 1.75 - .8;
        const radius = .63 + row / 23 * .055;
        const stripe = col % 12 < 5;
        points.push({ x: Math.cos(angle) * radius, y, z: Math.sin(angle) * radius, color: stripe ? [217, 137, 100] : [239, 184, 141], radius: .040, flat: .92 });
      }
      for (let row = 0; row < 4; row++) for (let col = 0; col < 100; col++) {
        const angle = col / 100 * Math.PI * 2; const radius = .58 + row * .035;
        points.push({ x: Math.cos(angle) * radius, y: .95, z: Math.sin(angle) * radius, color: [250, 216, 168], radius: .038, flat: .48 });
      }
      for (let row = 0; row < 48; row++) for (let col = 0; col < 7; col++) {
        const angle = -Math.PI / 2 + row / 47 * Math.PI; const ring = col / 7 * Math.PI * 2;
        points.push({ x: .60 + Math.cos(angle) * (.52 + .07 * Math.cos(ring)), y: .05 + Math.sin(angle) * (.66 + .07 * Math.cos(ring)), z: .07 * Math.sin(ring), color: [224, 155, 111], radius: .035, flat: 1 });
      }
      const angleValue = el('output', { for: 'gaussian-angle' }, `${theta}°`);
      const sizeValue = el('output', { for: 'gaussian-size' }, '1.0 ×');
      const info = el('p', { class: 'viewer-observation', 'aria-live': 'polite' }, '先拖动视角，再切换“只看中心点”：杯子的空间位置没有改变，改变的是投影。');
      const angleInput = el('input', { id: 'gaussian-angle', type: 'range', min: '0', max: '360', step: '1', value: theta, 'aria-label': '相机环绕角度', on: { input: event => { theta = Number(event.target.value); angleValue.textContent = `${theta}°`; draw(); } } });
      const sizeInput = el('input', { id: 'gaussian-size', type: 'range', min: '0.35', max: '1.7', step: '0.05', value: 1, 'aria-label': '高斯覆盖大小', on: { input: event => { size = Number(event.target.value); sizeValue.textContent = `${size.toFixed(2)} ×`; info.textContent = size < .7 ? '小高斯之间开始出现缝隙。覆盖范围会影响画面的连续性。' : size > 1.3 ? '覆盖范围变大，轮廓更柔和，细节也更容易糊在一起。' : '位置不变，只调整覆盖范围：观察轮廓和相邻高斯之间的缝隙。'; draw(); } } });
      const modeButtons = el('div', { class: 'viewer-modes', role: 'group', 'aria-label': '显示模式' });
      [['splat', '软边高斯叠加'], ['points', '只看中心点']].forEach(([value, title]) => modeButtons.append(el('button', { type: 'button', class: `viewer-mode${mode === value ? ' active' : ''}`, 'aria-pressed': String(mode === value), on: { click: () => { mode = value; [...modeButtons.children].forEach((b, i) => { b.classList.toggle('active', i === (value === 'splat' ? 0 : 1)); b.setAttribute('aria-pressed', String(i === (value === 'splat' ? 0 : 1))); }); info.textContent = mode === 'points' ? '每个点是一个三维高斯的中心。仅有中心点时，表面之间的空隙很明显。' : '每个中心扩展成软边分布，再按前后关系叠加，形成连续外观。'; draw(); } } }, title)));
      const play = button(reducedMotion.matches ? '转动 30°' : '播放环绕', () => {
        if (reducedMotion.matches) { theta = (theta + 30) % 360; angleInput.value = String(Math.round(theta)); angleValue.textContent = `${Math.round(theta)}°`; draw(); return; }
        playing = !playing; play.textContent = playing ? '暂停环绕' : '播放环绕'; play.setAttribute('aria-pressed', String(playing)); if (playing) { lastTime = 0; frame = requestAnimationFrame(tick); } else { cancelAnimationFrame(frame); frame = null; }
      }, 'outline', null, false);
      play.setAttribute('aria-pressed', 'false');
      const stage = el('div', { class: 'gaussian-stage' }, canvas, el('div', { class: 'viewer-stage-label' }, el('span', { class: 'viewer-live-dot' }), '合成原理示意 · 非照片重建'), el('div', { class: 'viewer-stage-bottom' }, el('span', {}, `${points.length.toLocaleString()} 个高斯中心`), el('span', {}, '相机在动，场景不动')));
      const card = el('section', { class: 'viewer-card' }, el('div', { class: 'visual-heading' }, el('span', { class: 'visual-eyebrow' }, '亲手转一转 · 空间如何变成画面'), el('span', { class: 'visual-duration' }, '1 分钟交互')), el('h3', {}, config.title || '一个杯子，两种看法'), el('p', { class: 'viewer-prompt' }, config.prompt || '转动视角，比较中心点与软边高斯。'), stage,
        el('div', { class: 'viewer-toolbar' }, modeButtons, play),
        el('div', { class: 'viewer-sliders' }, el('label', { for: 'gaussian-angle' }, el('span', {}, '相机角度', angleValue), angleInput), el('label', { for: 'gaussian-size' }, el('span', {}, '高斯覆盖', sizeValue), sizeInput)), info);
      function draw() {
        if (!alive || !context || !canvas.isConnected) return;
        const rect = canvas.getBoundingClientRect(); if (!rect.width || !rect.height) return;
        const ratio = Math.min(devicePixelRatio || 1, 2);
        const w = rect.width; const h = rect.height;
        const bw = Math.round(w * ratio); const bh = Math.round(h * ratio);
        if (canvas.width !== bw || canvas.height !== bh) { canvas.width = bw; canvas.height = bh; }
        context.setTransform(ratio, 0, 0, ratio, 0, 0); context.clearRect(0, 0, w, h);
        const gradient = context.createRadialGradient(w * .5, h * .42, 0, w * .5, h * .45, w * .65);
        gradient.addColorStop(0, '#2a493f'); gradient.addColorStop(1, '#172d28'); context.fillStyle = gradient; context.fillRect(0, 0, w, h);
        context.fillStyle = '#11241b45'; context.beginPath(); context.ellipse(w * .49, h * .80, Math.min(w * .28, 125), h * .065, 0, 0, Math.PI * 2); context.fill();
        const yaw = theta / 180 * Math.PI; const cp = Math.cos(.24); const sp = Math.sin(.24);
        const projection = points.map(point => { const rx = point.x * Math.cos(yaw) + point.z * Math.sin(yaw); const rz = -point.x * Math.sin(yaw) + point.z * Math.cos(yaw); const ry = point.y * cp - rz * sp; const depth = point.y * sp + rz * cp; const factor = Math.min(w * .37, h * .49) / (3.3 - depth); return { point, depth, x: w * .47 + rx * factor * 2.15, y: h * .51 - ry * factor * 2.15, r: point.radius * factor * 2.15 }; }).sort((a, b) => a.depth - b.depth);
        for (const p of projection) {
          const color = p.point.color; const light = .77 + (p.depth + 1) * .105;
          const rgb = color.map(v => Math.min(255, Math.round(v * light))).join(',');
          if (mode === 'points') { context.fillStyle = `rgba(${rgb},.86)`; context.beginPath(); context.arc(p.x, p.y, Math.max(.75, p.r * .18), 0, Math.PI * 2); context.fill(); }
          else { const radius = p.r * size * 2.5; const fog = context.createRadialGradient(p.x, p.y, 0, p.x, p.y, radius); fog.addColorStop(0, `rgba(${rgb},.70)`); fog.addColorStop(.40, `rgba(${rgb},.40)`); fog.addColorStop(1, `rgba(${rgb},0)`); context.fillStyle = fog; context.beginPath(); context.ellipse(p.x, p.y, radius, radius * p.point.flat, 0, 0, Math.PI * 2); context.fill(); }
        }
      }
      function tick(now) { if (!playing || !alive) return; const delta = lastTime ? Math.min(now - lastTime, 50) : 0; lastTime = now; theta = (theta + delta * .012) % 360; angleInput.value = String(Math.round(theta)); angleValue.textContent = `${Math.round(theta)}°`; draw(); frame = requestAnimationFrame(tick); }
      const observer = new ResizeObserver(() => draw()); observer.observe(canvas);
      const visibility = () => { if (document.hidden && playing) { playing = false; cancelAnimationFrame(frame); frame = null; play.textContent = '播放环绕'; play.setAttribute('aria-pressed', 'false'); } };
      const motionPreference = () => { playing = false; cancelAnimationFrame(frame); frame = null; play.textContent = reducedMotion.matches ? '转动 30°' : '播放环绕'; play.setAttribute('aria-pressed', 'false'); };
      document.addEventListener('visibilitychange', visibility);
      reducedMotion.addEventListener('change', motionPreference);
      onCleanup(() => { alive = false; playing = false; cancelAnimationFrame(frame); observer.disconnect(); document.removeEventListener('visibilitychange', visibility); reducedMotion.removeEventListener('change', motionPreference); });
      queueMicrotask(draw);
      return card;
    }

    function caseWalkthrough(lesson) {
      const item = lesson.case_study || {};
      const steps = item.steps || [];
      let current = 0;
      const visualSteps = lesson.visual_lesson?.steps || [];
      const panel = el('div', { class: 'case-walkthrough' });
      function update() {
        const step = visualSteps.find(s => s.id === 'capture') || visualSteps[0];
        panel.replaceChildren(step ? imageCard(step, 'case-figure') : document.createDocumentFragment(), el('div', { class: 'case-progress' }, steps.map((_, i) => el('button', { type: 'button', class: i === current ? 'active' : '', 'aria-label': `案例第 ${i + 1} 步`, 'aria-current': i === current ? 'step' : null, on: { click: () => { current = i; update(); } } }, String(i + 1)))), el('div', { class: 'case-current-step' }, el('span', {}, `现在只做这一步 · ${current + 1} / ${steps.length || 1}`), el('p', {}, steps[current] || item.scenario || '选择一个真实问题，准备一份可以检查的结果。')), el('div', { class: 'visual-step-controls' }, button('← 上一步', () => { current--; update(); }, 'ghost', null, current === 0), button('下一步 →', () => { current++; update(); }, 'outline', null, current >= steps.length - 1)));
      }
      update(); return panel;
    }

    function codeWalkthrough(lesson) {
      const item = lesson.code_insight || {};
      const lines = String(item.snippet || '').split('\n').filter(line => line.trim() && !line.trim().startsWith('#') && !line.trim().startsWith('//'));
      const isGaussian = lesson.visual_lesson?.interactive?.kind === 'gaussian-viewer';
      const steps = isGaussian ? [
        { title: '取一个视角', match: 'choose_training', caption: '拿到相机位置与真实照片，确定这一次要对齐的目标。' },
        { title: '画出预测', match: 'prediction =', caption: '用当前高斯参数，从同一相机位置生成一张画面。' },
        { title: '找出差距', match: 'loss =', caption: '比较预测画面与真实照片，用误差描述差了多少。' },
        { title: '调整参数', match: 'optimizer_update', caption: '根据梯度小步更新位置、尺度、颜色等参数，然后再看一次。' },
      ] : (lesson.core_ideas || []).slice(0, 4).map((idea, i) => ({ title: String(idea.title).replace(/^\d+[.、]\s*/, ''), caption: idea.explanation }));
      let current = 0;
      const buttons = el('div', { class: 'code-flow' }); const focus = el('div', { class: 'code-focus', 'aria-live': 'polite' });
      function update() { buttons.replaceChildren(...steps.map((step, i) => el('button', { type: 'button', class: `code-flow-step${i === current ? ' active' : ''}`, 'aria-pressed': String(i === current), on: { click: () => { current = i; update(); } } }, el('span', {}, String(i + 1).padStart(2, '0')), step.title))); const step = steps[current]; if (step) focus.replaceChildren(el('span', { class: 'code-focus-label' }, isGaussian ? '看这一行在做什么' : '理解这个环节负责什么'), el('pre', {}, el('code', {}, lines.find(line => step.match && line.includes(step.match)) || step.line || step.title)), el('p', {}, step.caption)); }
      update();
      const walkthroughs = Array.isArray(item.walkthroughs) ? item.walkthroughs.filter(part => part && typeof part.snippet === 'string') : [];
      const guide = walkthroughs.length ? annotatedCode(walkthroughs, lesson) : document.createDocumentFragment();
      return el('div', {}, buttons, focus, guide, fold(walkthroughs.length ? '展开整体说明与完整代码' : '展开完整代码与逐项说明', el('p', { class: 'prose' }, item.explanation), item.snippet ? el('div', { class: 'code-wrap' }, el('div', { class: 'code-label' }, item.language || '代码片段'), el('pre', {}, el('code', {}, item.snippet))) : null, item.source_url ? link('查看源码上下文 ↗', item.source_url, 'text-link') : null));
    }

    function annotatedCode(walkthroughs, lesson) {
      let current = 0;
      let currentNarration = null;
      const tabs = el('div', { class: 'walkthrough-tabs', role: 'tablist', 'aria-label': '选择逐行讲解片段' });
      const stage = el('div', { class: 'walkthrough-stage' });
      const section = el('section', { class: 'annotated-code', 'aria-label': '代码逐行中文讲解' }, el('div', { class: 'annotated-code-heading' }, el('h3', {}, '逐行看懂：做什么，为什么'), el('span', {}, `${walkthroughs.length} 个短片段`)), tabs, stage);
      function sourceLineURL(part, number) {
        if (!part.source_url) return null;
        try { const url = new URL(part.source_url); url.hash = `L${number}`; return url.href; } catch { return null; }
      }
      function show(index, focusTab = false) {
        if (currentNarration) audioDisposers.get(currentNarration)?.();
        current = Math.max(0, Math.min(walkthroughs.length - 1, index));
        tabs.replaceChildren(...walkthroughs.map((part, i) => el('button', { type: 'button', id: `walkthrough-tab-${i}`, role: 'tab', class: `walkthrough-tab${i === current ? ' active' : ''}`, 'aria-selected': String(i === current), 'aria-controls': 'walkthrough-panel', tabindex: i === current ? '0' : '-1', on: { click: () => show(i), keydown: event => {
          let next;
          if (event.key === 'ArrowRight') next = (i + 1) % walkthroughs.length;
          if (event.key === 'ArrowLeft') next = (i - 1 + walkthroughs.length) % walkthroughs.length;
          if (event.key === 'Home') next = 0;
          if (event.key === 'End') next = walkthroughs.length - 1;
          if (next !== undefined) { event.preventDefault(); show(next, true); }
        } } }, el('span', {}, String(i + 1).padStart(2, '0')), part.title || `片段 ${i + 1}`)));
        const part = walkthroughs[current];
        currentNarration = audioNarration(lesson, 'code', part.id);
        const isSource = part.kind === 'source';
        const snippetLines = part.snippet.split('\n');
        const notes = new Map((part.notes || []).map(note => [Number(note.line), note]));
        const start = isSource && Number.isInteger(part.source_start_line) && part.source_start_line > 0 ? part.source_start_line : 1;
        const rawLanguage = String(part.language || '代码');
        const language = ({ rust: 'Rust', python: 'Python', javascript: 'JavaScript', typescript: 'TypeScript', json: 'JSON' })[rawLanguage.toLowerCase()] || rawLanguage;
        const sourceTitle = part.source_path ? part.source_path.split('/').pop() : '查看原文件';
        const sourceMeta = isSource ? el('div', { class: 'walkthrough-source' }, part.source_url ? link(`${sourceTitle} · 从第 ${start} 行查看 ↗`, sourceLineURL(part, start), 'source-file-link') : null, part.source_commit ? el('span', {}, `固定版本 ${String(part.source_commit).slice(0, 10)}`) : null) : null;
        const rows = snippetLines.map((line, index) => {
          const number = start + index;
          const note = notes.get(index + 1);
          const lineNumber = isSource && part.source_url ? link(String(number), sourceLineURL(part, number), 'annotated-line-number') : el('span', { class: 'annotated-line-number', 'aria-label': `片段第 ${number} 行` }, String(number));
          const sourceCell = el('div', { class: 'annotated-source-cell' }, lineNumber, el('pre', { tabindex: line.length > 48 ? '0' : null, 'aria-label': `${isSource ? '源码' : '伪代码'}第 ${number} 行` }, el('code', {}, line)));
          const noteCell = el('div', { class: 'annotated-note-cell' }, note ? [el('p', { class: 'line-comment' }, note.comment), note.why ? el('p', { class: 'line-reason' }, el('span', {}, '为什么'), note.why) : null] : line.trim() ? el('p', { class: 'line-comment' }, '这行的中文说明尚未提供。') : null);
          return el('li', { class: `annotated-row${line.trim() ? '' : ' blank-line'}` }, sourceCell, noteCell);
        });
        const panel = el('div', { id: 'walkthrough-panel', class: 'walkthrough-panel', role: 'tabpanel', 'aria-labelledby': `walkthrough-tab-${current}` }, el('div', { class: 'walkthrough-meta' }, el('span', { class: `walkthrough-kind${isSource ? ' source' : ' pseudo'}` }, isSource ? `真实源码 · ${language}` : '教学伪代码 · 非可运行 API'), sourceMeta), el('p', { class: 'annotation-provenance' }, isSource ? '中文讲解由本课编写；原代码保持原样，讲解不是上游源码的原始注释。' : '这段伪代码由本课编写，用于解释流程；名称不代表真实 API，不能直接作为项目代码运行。'), currentNarration, el('div', { class: 'annotated-columns', 'aria-hidden': 'true' }, el('span', {}, isSource ? '原文件行号 / 原始代码' : '片段行号 / 教学伪代码'), el('span', {}, '中文解释 / 设计原因')), el('ol', { class: 'annotated-rows' }, rows));
        stage.replaceChildren(panel);
        if (focusTab) tabs.children[current].focus();
      }
      show(0);
      return section;
    }

    function takeaways(lesson) {
      const items = lesson.visual_lesson?.takeaways || (lesson.core_ideas || []).slice(0, 3).map(idea => idea.title);
      return items.length ? el('div', { class: 'takeaway-grid' }, items.slice(0, 3).map((item, i) => el('article', { class: 'takeaway-card' }, el('div', { class: `takeaway-mark mark-${i}`, 'aria-hidden': 'true' }, ['◉', '↻', '↗'][i]), el('span', {}, ['记住表示', '记住过程', '记住边界'][i]), el('p', {}, item)))) : document.createDocumentFragment();
    }

    function experimentEmbed() {
      const iframe = el('iframe', { src: localAsset('lab/index.html?embedded=1'), class: 'experiment-frame', title: '二维高斯交互实验：改变参数、比较误差与拟合位置', loading: 'lazy', sandbox: 'allow-scripts allow-same-origin', referrerpolicy: 'same-origin' });
      const resize = event => { if (event.origin !== location.origin || event.source !== iframe.contentWindow || event.data?.type !== 'learning-loop:lab-height') return; const height = Number(event.data.height); if (Number.isFinite(height) && height >= 300 && height <= 4000) iframe.style.height = `${Math.ceil(height)}px`; };
      window.addEventListener('message', resize); onCleanup(() => window.removeEventListener('message', resize));
      // Existing labs need no messaging support: measure their same-origin document after load.
      let observer;
      iframe.addEventListener('load', () => { try { const doc = iframe.contentDocument; if (!doc?.body) return; const measure = () => { const height = Math.ceil(doc.body.getBoundingClientRect().height); if (height >= 300 && height <= 5000 && Math.abs(iframe.getBoundingClientRect().height - height) > 2) iframe.style.height = `${height}px`; }; observer = new ResizeObserver(measure); observer.observe(doc.body); measure(); } catch { /* The standalone link remains available. */ } });
      onCleanup(() => observer?.disconnect());
      return el('div', { class: 'experiment-embed' }, el('div', { class: 'embed-heading' }, el('span', {}, '直接在这里动手，记录在下方'), el('a', { href: localAsset('lab/index.html'), target: '_blank', rel: 'noopener', class: 'text-link' }, '独立窗口 ↗')), iframe);
    }

    return { videoLesson, audioNarration, stepLesson, gaussianViewer, caseWalkthrough, codeWalkthrough, takeaways, experimentEmbed, fold, imageCard };
  }
  return { create };
})();
