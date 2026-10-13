'use strict';

// The playlist only stores listening convenience state. It never submits learning evidence.
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.LessonListen = api;
})(typeof window === 'object' ? window : null, () => {
  const chapters = ['logic', 'case', 'code', 'experiment', 'application', 'summary'];
  const chapterNames = { logic: '看懂原理', case: '跟着案例', code: '拆解代码', experiment: '动手实验', application: '用到实际', summary: '回想总结' };
  const checkpoints = {
    experiment: '接下来是动手实验。先准备一个预测，再亲手观察变化。准备好后继续听本节说明。',
    application: '接下来要用到实际。先选一个自己的问题，准备好后继续听本节说明。',
    summary: '接下来是回想总结。先不看资料，用自己的话想一遍，再继续听本节提示。',
  };
  const timeLabel = seconds => `${Math.floor(Math.max(0, seconds) / 60)}:${String(Math.floor(Math.max(0, seconds) % 60)).padStart(2, '0')}`;
  const fingerprint = clips => JSON.stringify(clips.map(clip => [clip.chapter, clip.src, clip.duration_seconds, clip.transcript]));

  function mainClips(lesson, resolveMedia) {
    return chapters.map(chapter => (lesson.audio_lesson?.clips || []).find(clip => clip.chapter === chapter && !clip.walkthrough_id))
      .filter(clip => clip && Number.isFinite(clip.duration_seconds) && clip.duration_seconds > 0)
      .map(clip => ({ ...clip, url: resolveMedia(clip.src) })).filter(clip => clip.url);
  }

  // The same controller runs in the DOM and in isolated media-event regression tests.
  function createController({ clips, courseID, scope, player, storage = null, onChange = () => {}, isHidden = () => false, now = () => Date.now() }) {
    if (!clips.length) throw new Error('没有可播放的章节');
    const key = `zhixing.listen.v1:${scope}:${encodeURIComponent(courseID)}`;
    const signature = fingerprint(clips);
    let index = 0, position = 0, pending = null, phase = 'paused', message = '点播放开始听课。';
    let disposed = false, switching = false, token = 0, seekOnMetadata = null, lastSaved = 0, rate = 1;
    let hasResume = false, loading = false, metadataReady = false;
    const remove = () => { try { storage?.removeItem(key); } catch { /* Optional convenience storage. */ } };
    try {
      const raw = JSON.parse(storage?.getItem(key) || 'null');
      if (raw && raw.signature === signature && chapters.includes(raw.chapter) && Number.isFinite(raw.time) && raw.time >= 0) {
        const found = clips.findIndex(clip => clip.chapter === raw.chapter);
        const next = clips.findIndex(clip => clip.chapter === raw.pending);
        if (found >= 0 && raw.time <= clips[found].duration_seconds + 1 && (raw.pending == null || next === found + 1)) {
          index = found; position = raw.time; pending = next >= 0 ? next : null;
          hasResume = index > 0 || position > 0 || pending !== null;
          if ([0.8, 1, 1.25, 1.5].includes(raw.rate)) rate = raw.rate;
          phase = pending !== null ? 'checkpoint' : 'paused';
          message = pending !== null ? checkpoints[clips[pending].chapter] || '上次在章节间暂停，点继续听下一章。' : `上次听到第 ${index + 1} 章 ${timeLabel(position)}，点继续播放。`;
        } else remove();
      } else if (raw) remove();
    } catch { /* Unavailable or malformed storage cannot block a course. */ }

    const total = () => clips.reduce((sum, clip) => sum + clip.duration_seconds, 0);
    function state() {
      return { index, position, pending, phase, message, rate, hasResume, loading, clips,
        chapterDuration: clips[index].duration_seconds,
        coursePosition: clips.slice(0, index).reduce((sum, clip) => sum + clip.duration_seconds, 0) + Math.min(position, clips[index].duration_seconds),
        courseDuration: total() };
    }
    const notify = () => { if (!disposed) onChange(state()); };
    function persist(force = false) {
      if (disposed || switching) return;
      if (phase === 'ended' || (index === 0 && position <= 0 && pending === null)) { remove(); return; }
      const clock = now();
      if (!force && clock - lastSaved < 1500) return;
      lastSaved = clock;
      try { storage?.setItem(key, JSON.stringify({ signature, chapter: clips[index].chapter, time: Math.round(position * 10) / 10, pending: pending === null ? null : clips[pending].chapter, rate })); }
      catch { /* Continue playing when quota is exceeded or persistence is blocked. */ }
    }
    function currentPosition() {
      if (!metadataReady || loading || switching || pending !== null || phase === 'ended') return;
      if (Number.isFinite(player.currentTime)) position = Math.max(0, Math.min(player.currentTime, clips[index].duration_seconds));
    }
    function seek(time) {
      if (disposed) return;
      if (pending !== null || phase === 'ended') { pending = null; phase = player.paused ? 'paused' : 'playing'; message = ''; }
      position = Math.max(0, Math.min(time, Math.max(0, clips[index].duration_seconds - .1)));
      if (metadataReady) { try { player.currentTime = position; } catch { seekOnMetadata = position; } }
      else seekOnMetadata = position;
      hasResume = false;
      persist(true); notify();
    }
    async function play() {
      if (disposed) return;
      if (isHidden()) { message = '已暂停。回到课程后点播放继续。'; notify(); return; }
      if (pending !== null) { const next = pending; pending = null; load(next, 0, true); return; }
      if (phase === 'ended') { load(0, 0, true); return; }
      if (phase === 'error') { load(index, position, true); return; }
      const attempt = token;
      hasResume = false;
      message = loading ? '正在准备这段语音…' : '';
      notify();
      try { await player.play(); }
      catch {
        if (!disposed && attempt === token && phase !== 'error') {
          phase = 'paused'; message = '播放已暂停，请再点一次播放继续。'; notify();
        }
      }
    }
    function pause(reason = '') {
      if (disposed) return;
      currentPosition();
      player.pause();
      if (!['checkpoint', 'ended', 'error'].includes(phase)) phase = 'paused';
      if (reason) message = reason;
      persist(true); notify();
    }
    function load(next, time = 0, autoPlay = false) {
      if (disposed) return;
      switching = true; token++; player.pause();
      index = next; position = time; loading = true; metadataReady = false;
      seekOnMetadata = time;
      phase = pending !== null ? 'checkpoint' : 'paused';
      player.src = clips[index].url;
      player.playbackRate = rate;
      player.load();
      switching = false;
      persist(true); notify();
      if (autoPlay) play();
    }
    function select(next) {
      if (!Number.isInteger(next) || next < 0 || next >= clips.length || disposed) return;
      pending = null; hasResume = false;
      message = `已选择${chapterNames[clips[next].chapter]}，点播放开始。`;
      load(next, 0);
    }
    function setRate(value) {
      if (![0.8, 1, 1.25, 1.5].includes(Number(value)) || disposed) return;
      rate = Number(value); player.playbackRate = rate; persist(true); notify();
    }
    const events = {
      loadedmetadata() {
        if (disposed || switching || player.readyState < 1 || (player.currentSrc && player.currentSrc !== clips[index].url)) return;
        loading = false; metadataReady = true; player.playbackRate = rate;
        if (seekOnMetadata !== null) {
          try { player.currentTime = Math.min(seekOnMetadata, Math.max(0, (Number.isFinite(player.duration) ? player.duration : clips[index].duration_seconds) - .1)); seekOnMetadata = null; }
          catch { message = '语音已准备，可以点播放；当前位置暂时无法恢复。'; }
        }
        notify();
      },
      playing() {
        if (disposed || switching || !metadataReady || player.paused) return;
        if (pending !== null) { pause(checkpoints[clips[pending].chapter] || '章节间已暂停，请点“准备好了，继续下一章”。'); return; }
        if (isHidden()) { pause('已暂停。回到课程后点继续。'); return; }
        phase = 'playing'; message = ''; hasResume = false; notify();
      },
      pause() {
        if (disposed || switching || !player.paused) return;
        currentPosition();
        if (phase === 'playing') phase = 'paused';
        persist(true); notify();
      },
      timeupdate() { if (!disposed && !switching) { currentPosition(); persist(); notify(); } },
      seeked() {
        if (disposed || switching || !metadataReady) return;
        if (phase === 'ended' && player.currentTime < clips[index].duration_seconds - .1) { phase = player.paused ? 'paused' : 'playing'; message = '已定位，可以重听这一段。'; }
        currentPosition(); persist(true); notify();
      },
      ended() {
        // Queued events from an old source may arrive after src/load has changed.
        // Check the live media state, not merely the name of the queued event.
        if (disposed || switching || !metadataReady || !player.ended || pending !== null || phase === 'error') return;
        position = clips[index].duration_seconds;
        if (index === clips.length - 1) {
          phase = 'ended'; hasResume = false; message = '本课主讲已播完。试着用自己的话解释，再到练习区留下真实记录。'; remove(); notify(); return;
        }
        const next = index + 1;
        if (checkpoints[clips[next].chapter] || isHidden()) {
          pending = next; phase = 'checkpoint'; player.pause();
          message = isHidden() ? '已暂停。回到课程后点继续听下一章。' : checkpoints[clips[next].chapter];
          persist(true); notify();
        } else { message = ''; load(next, 0, true); }
      },
      error() {
        if (disposed || switching || !player.error) return;
        currentPosition();
        phase = 'error'; loading = false; player.pause();
        const code = player.error?.code;
        message = `这段语音暂时无法播放${code ? `（音频 ${code}）` : ''}，点重新加载会从当前位置重试。文字稿仍可阅读。`;
        persist(true); notify();
      },
    };
    Object.entries(events).forEach(([name, handler]) => player.addEventListener(name, handler));
    load(index, position);
    return { state, play, pause, select, seek, setRate,
      rewind: () => { currentPosition(); if (pending !== null || phase === 'ended') { pending = null; phase = 'paused'; message = '已后退，可以重听这一段。'; } seek(position - 10); },
      background: () => pause('已暂停。回到课程后点播放继续。'),
      dispose() {
        if (disposed) return;
        currentPosition(); persist(true); disposed = true; token++;
        Object.entries(events).forEach(([name, handler]) => player.removeEventListener(name, handler));
        player.pause(); player.removeAttribute('src'); player.load();
      },
    };
  }

  function create({ el, button, onCleanup, courseID, lesson, assetBase, onOpenChapter = null }) {
    const base = new URL('.', assetBase || document.baseURI);
    const resolveMedia = value => {
      if (typeof value !== 'string' || !value.startsWith('/media/')) return null;
      try { const url = new URL(value.slice(1), base); return url.origin === base.origin && url.pathname.startsWith(`${base.pathname}media/`) ? url.href : null; } catch { return null; }
    };
    const clips = mainClips(lesson, resolveMedia);
    if (!clips.length) return document.createDocumentFragment();
    const audio = el('audio', { class: 'listen-audio', controls: true, preload: 'metadata', 'aria-label': '整课听讲播放器' });
    const title = el('strong', {}, '整课听讲');
    const chapterProgress = el('p', { class: 'listen-progress' });
    const courseProgress = el('progress', { class: 'listen-course-progress', max: clips.reduce((sum, clip) => sum + clip.duration_seconds, 0), value: 0, 'aria-label': '整课播放位置（不代表掌握进度）' });
    const coursePosition = el('p', { class: 'listen-position' });
    const status = el('p', { class: 'listen-status', role: 'status' });
    let controller;
    const primary = button('播放', () => { const state = controller.state(); if (state.phase === 'playing') controller.pause(); else controller.play(); }, 'primary', null, false);
    const rewind = button('↶ 后退 10 秒', () => controller.rewind(), 'outline', null, false);
    const openChapter = onOpenChapter ? button('打开这一节', () => { const state = controller.state(); controller.pause(); onOpenChapter(clips[state.pending ?? state.index].chapter); }, 'ghost', null, false) : null;
    const speed = el('select', { class: 'narration-speed', 'aria-label': '整课听讲语速', on: { change: event => controller.setRate(event.target.value) } }, [0.8, 1, 1.25, 1.5].map(rate => el('option', { value: rate }, `${rate} ×`)));
    const transcript = el('p', { class: 'narration-transcript' });
    const items = clips.map((clip, index) => button(`${String(index + 1).padStart(2, '0')} · ${chapterNames[clip.chapter]} · ${timeLabel(clip.duration_seconds)}`, () => controller.select(index), 'listen-chapter', null, false));
    const panel = el('details', { class: 'listen-panel' }, el('summary', {}, el('span', {}, '◖♪◗ 整课听讲'), el('span', {}, `${clips.length} 章 · ${timeLabel(clips.reduce((sum, clip) => sum + clip.duration_seconds, 0))}`)),
      el('div', { class: 'listen-body' }, el('p', { class: 'listen-intro' }, '主讲按章节连续播放；进入实验、应用和总结前会停下来，等你准备好。源码逐行精讲可在代码章节单独听。'), title, chapterProgress, audio,
        el('div', { class: 'listen-controls' }, primary, rewind, el('label', { class: 'narration-speed-label' }, '语速', speed), openChapter),
        courseProgress, coursePosition, status,
        el('nav', { class: 'listen-chapters', 'aria-label': '本课主讲播放列表' }, items),
        el('details', { class: 'lesson-fold' }, el('summary', {}, '展开当前章节文字稿'), transcript),
        el('p', { class: 'listen-note' }, '播放位置仅保存在此设备，不计入学习成果。离开本页或切到后台会暂停，返回后点播放继续。')));
    let store = null; try { store = window.localStorage; } catch { /* Optional storage. */ }
    controller = createController({ clips, courseID, scope: base.pathname, player: audio, storage: store, isHidden: () => document.hidden,
      onChange(state) {
        title.textContent = `${state.index + 1} / ${clips.length} · ${clips[state.index].title || chapterNames[clips[state.index].chapter]}`;
        chapterProgress.textContent = `本章 ${timeLabel(state.position)} / ${timeLabel(state.chapterDuration)}`;
        courseProgress.value = state.coursePosition;
        coursePosition.textContent = `整课位置 ${timeLabel(state.coursePosition)} / ${timeLabel(state.courseDuration)}`;
        const label = state.phase === 'playing' ? '暂停' : state.phase === 'checkpoint' ? '准备好了，继续下一章' : state.phase === 'ended' ? '从第一章重听' : state.phase === 'error' ? '重新加载并续播' : state.hasResume ? '继续上次播放' : '播放';
        if (primary.textContent !== label) primary.textContent = label;
        if (status.textContent !== state.message) status.textContent = state.message;
        if (transcript.textContent !== clips[state.index].transcript) transcript.textContent = clips[state.index].transcript || '';
        audio.controls = state.pending === null;
        speed.value = String(state.rate);
        items.forEach((item, index) => { item.classList.toggle('active', index === state.index); item.setAttribute('aria-current', index === state.index ? 'step' : 'false'); });
        panel.classList.toggle('at-checkpoint', state.phase === 'checkpoint');
        if (openChapter) openChapter.textContent = state.pending !== null ? `打开${chapterNames[clips[state.pending].chapter]}` : '打开这一节';
      },
    });
    const exclusive = () => { for (const other of document.querySelectorAll('audio, video')) if (other !== audio) other.pause(); };
    const background = () => { if (document.hidden) controller.background(); };
    const pagehide = () => controller.background();
    const close = () => { if (!panel.open) controller.pause(); };
    audio.addEventListener('play', exclusive);
    document.addEventListener('visibilitychange', background);
    window.addEventListener('pagehide', pagehide);
    panel.addEventListener('toggle', close);
    onCleanup(() => { audio.removeEventListener('play', exclusive); document.removeEventListener('visibilitychange', background); window.removeEventListener('pagehide', pagehide); panel.removeEventListener('toggle', close); controller.dispose(); });
    return panel;
  }
  return { create, createController, mainClips, fingerprint };
});
