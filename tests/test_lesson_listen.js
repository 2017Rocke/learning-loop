'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const Listen = require('../web/lesson-listen.js');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

class Media extends EventTarget {
  constructor() { super(); this.currentTime = 0; this.duration = NaN; this.paused = true; this.playCalls = 0; this.loadCalls = 0; this.src = ''; this.error = null; this.readyState = 0; }
  emit(type) { this.dispatchEvent(new Event(type)); }
  play() { this.playCalls++; this.paused = false; this.emit('play'); if (this.readyState > 0) this.emit('playing'); return Promise.resolve(); }
  pause() { if (!this.paused) { this.paused = true; this.emit('pause'); } }
  load() { this.loadCalls++; this.currentSrc = this.src; this.currentTime = 0; this.duration = NaN; this.readyState = 0; this.error = null; this.paused = true; }
  removeAttribute(name) { if (name === 'src') this.src = ''; }
  metadata(duration) { this.duration = duration; this.readyState = 1; this.emit('loadedmetadata'); if (!this.paused) this.emit('playing'); }
  get ended() { return Number.isFinite(this.duration) && this.currentTime >= this.duration; }
  finish() { this.currentTime = this.duration; this.paused = true; this.emit('ended'); }
}
function memory() {
  const values = new Map([['private-learner-record', '{"evidence":["real answer"]}']]);
  return { values, getItem: key => values.get(key) || null, setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key) };
}
const fixture = () => ['logic', 'case', 'experiment', 'application', 'summary'].map((chapter, i) => ({ chapter, src: `/media/demo/${chapter}.mp3`, url: `https://app.test/media/demo/${chapter}.mp3`, duration_seconds: 20 + i * 10, transcript: `${chapter} 的讲解原稿` }));
function setup({ clips = fixture(), courseID = 'a', storage = memory(), hidden = false } = {}) {
  const player = new Media(); const changes = []; let hiddenState = hidden;
  const controller = Listen.createController({ clips, courseID, scope: '/site/', player, storage, isHidden: () => hiddenState, onChange: state => changes.push(state), now: () => 5000 });
  return { player, controller, storage, changes, setHidden: value => { hiddenState = value; } };
}
const key = id => `zhixing.listen.v1:/site/:${encodeURIComponent(id)}`;
const saved = app => JSON.parse(app.storage.getItem(key('a')));

test('main playlist orders only main narration and excludes optional source walkthroughs', () => {
  const lesson = { audio_lesson: { clips: [...fixture().reverse(), { ...fixture()[0], chapter: 'code', walkthrough_id: 'source-line' }, { ...fixture()[0], chapter: 'other' }] } };
  assert.deepEqual(Listen.mainClips(lesson, path => path).map(clip => clip.chapter), ['logic', 'case', 'experiment', 'application', 'summary']);
  assert.equal(Listen.mainClips(lesson, () => null).length, 0);
});

test('initial playlist never autoplays; leaving saves before media reset and exact position resumes', async () => {
  const app = setup(); assert.equal(app.player.playCalls, 0);
  app.player.metadata(20); await app.controller.play(); app.player.currentTime = 13.2; app.player.emit('timeupdate');
  app.controller.dispose(); assert.equal(app.player.currentTime, 0); assert.equal(saved(app).time, 13.2);
  const again = setup({ storage: app.storage }); assert.equal(again.player.playCalls, 0); assert.equal(again.controller.state().hasResume, true);
  again.player.metadata(20); assert.equal(again.player.currentTime, 13.2);
  await again.controller.play(); assert.equal(again.controller.state().phase, 'playing');
  assert.equal(app.storage.getItem('private-learner-record'), '{"evidence":["real answer"]}');
});

test('same URLs in separate courses and deployment paths cannot share a resume position', () => {
  const app = setup(); app.player.metadata(20); app.controller.seek(8);
  const other = setup({ storage: app.storage, courseID: 'b' }); assert.equal(other.controller.state().position, 0);
  const player = new Media(); const scoped = Listen.createController({ clips: fixture(), courseID: 'a', scope: '/different/', player, storage: app.storage });
  assert.equal(scoped.state().position, 0); assert.equal(saved(app).time, 8);
});

test('changed narration invalidates a resume even when source and duration are unchanged', () => {
  const app = setup(); app.player.metadata(20); app.controller.seek(9); app.controller.dispose();
  const changed = fixture(); changed[0].transcript = '讲解已经修改，不能沿用旧的听课位置';
  const afterUpdate = setup({ storage: app.storage, clips: changed });
  assert.equal(afterUpdate.controller.state().position, 0); assert.equal(afterUpdate.controller.state().hasResume, false);
  assert.equal(app.storage.getItem(key('a')), null);
});

test('one player advances ordinary chapters and waits for explicit continuation at every practice boundary', async () => {
  const app = setup(); app.player.metadata(20); await app.controller.play();
  app.player.currentTime = 20; app.player.emit('ended');
  assert.equal(app.controller.state().index, 1); assert.equal(app.player.src, fixture()[1].url); assert.equal(app.player.playCalls, 2);
  app.player.metadata(30); app.player.currentTime = 30; app.player.emit('ended');
  assert.equal(app.controller.state().phase, 'checkpoint'); assert.equal(app.controller.state().pending, 2); assert.equal(app.player.playCalls, 2);
  assert.equal(saved(app).pending, 'experiment');
  const resume = setup({ storage: app.storage }); resume.player.metadata(30);
  assert.equal(resume.controller.state().phase, 'checkpoint'); assert.equal(resume.player.playCalls, 0);
  for (const expected of [2, 3, 4]) {
    await resume.controller.play(); assert.equal(resume.controller.state().index, expected);
    resume.player.metadata(fixture()[expected].duration_seconds); resume.player.currentTime = fixture()[expected].duration_seconds; resume.player.emit('ended');
    assert.equal(resume.controller.state().phase, expected === 4 ? 'ended' : 'checkpoint');
  }
  assert.equal(resume.storage.getItem(key('a')), null);
  resume.controller.dispose(); assert.equal(resume.storage.getItem(key('a')), null, 'cleanup must not restore a completed playlist');
});

test('rewind, chapter selection, native seek and restart save the actual position', async () => {
  const app = setup(); app.player.metadata(20); app.controller.seek(14); app.controller.rewind();
  assert.equal(app.player.currentTime, 4); assert.equal(saved(app).time, 4);
  app.controller.rewind(); assert.equal(app.player.currentTime, 0); assert.equal(app.storage.getItem(key('a')), null);
  app.controller.select(3); assert.equal(app.player.playCalls, 0); assert.equal(saved(app).chapter, 'application'); assert.equal(saved(app).time, 0);
  app.player.metadata(50); app.player.currentTime = 23; app.player.emit('seeked'); assert.equal(saved(app).time, 23);
  app.controller.setRate(1.25); assert.equal(saved(app).rate, 1.25); assert.equal(app.player.playbackRate, 1.25);
  app.controller.select(4); app.player.metadata(60); app.player.finish(); await app.controller.play();
  assert.equal(app.controller.state().index, 0); assert.equal(app.player.playCalls, 1);
});

test('errors preserve position for retry; failed play promises and cleanup cannot advance chapters', async () => {
  const app = setup(); app.player.metadata(20); await app.controller.play(); app.player.currentTime = 7; app.player.emit('timeupdate');
  app.player.error = { code: 2 }; app.player.emit('error');
  assert.equal(app.controller.state().phase, 'error'); assert.equal(saved(app).time, 7); assert.match(app.controller.state().message, /音频 2/);
  app.player.error = null; await app.controller.play(); app.player.metadata(20); assert.equal(app.player.currentTime, 7);
  app.player.play = () => Promise.reject(new Error('Autoplay policy')); await app.controller.play();
  assert.equal(app.controller.state().phase, 'paused'); assert.equal(app.controller.state().index, 0);
  let rejectPlay; app.player.play = () => new Promise((resolve, reject) => { rejectPlay = reject; });
  const pending = app.controller.play(); app.controller.dispose(); const count = app.changes.length;
  rejectPlay(new Error('Disposed')); await pending; app.player.emit('ended'); app.player.emit('error');
  assert.equal(app.changes.length, count); assert.equal(app.player.src, '');
});

test('background transition pauses and never restarts on foreground or chains another chapter while hidden', async () => {
  const app = setup(); app.player.metadata(20); await app.controller.play(); app.player.currentTime = 8;
  app.setHidden(true); app.controller.background(); assert.equal(app.player.paused, true); assert.equal(saved(app).time, 8);
  await app.controller.play(); assert.equal(app.player.playCalls, 1);
  app.setHidden(false); assert.equal(app.player.playCalls, 1); await app.controller.play(); assert.equal(app.player.playCalls, 2);
  app.setHidden(true); app.player.currentTime = 20; app.player.emit('ended');
  assert.equal(app.controller.state().pending, 1); assert.equal(app.player.playCalls, 2);
  app.setHidden(false); assert.equal(app.player.playCalls, 2); await app.controller.play(); assert.equal(app.controller.state().index, 1);
});

test('queued media events from a previous source cannot skip or pause the newly selected chapter', async () => {
  const app = setup(); app.player.metadata(20); await app.controller.play();
  app.controller.select(1);
  app.player.emit('ended'); app.player.emit('loadedmetadata'); app.player.emit('playing'); app.player.emit('error');
  assert.equal(app.controller.state().index, 1); assert.equal(app.controller.state().loading, true); assert.equal(app.controller.state().phase, 'paused');
  app.player.metadata(30); await app.controller.play();
  app.player.emit('pause'); app.player.emit('ended'); app.player.emit('error');
  assert.equal(app.controller.state().index, 1); assert.equal(app.controller.state().phase, 'playing');
  app.player.currentTime = 7; app.player.emit('timeupdate'); assert.equal(app.controller.state().position, 7); app.controller.pause(); assert.equal(saved(app).time, 7);
});

test('native seeking after the final chapter reopens the current chapter for replay', () => {
  const app = setup(); app.controller.select(4); app.player.metadata(60); app.player.finish();
  assert.equal(app.controller.state().phase, 'ended');
  app.player.currentTime = 24; app.player.emit('seeked');
  assert.equal(app.controller.state().phase, 'paused'); assert.equal(app.controller.state().position, 24);
  assert.equal(saved(app).chapter, 'summary'); assert.equal(saved(app).time, 24);
});

test('checkpoint cannot be bypassed by a stray native play and retains its learning prompt', async () => {
  const app = setup(); app.controller.select(1); app.player.metadata(30); app.player.finish();
  await app.player.play();
  assert.equal(app.controller.state().phase, 'checkpoint'); assert.equal(app.controller.state().pending, 2);
  assert.equal(app.player.paused, true); assert.match(app.controller.state().message, /动手实验/);
});

test('broken or unavailable convenience storage never prevents playback or modifies learner data', async () => {
  const broken = { getItem() { throw new Error('Unavailable'); }, setItem() { throw new Error('Full'); }, removeItem() { throw new Error('Unavailable'); } };
  const app = setup({ storage: broken }); app.player.metadata(20); await app.controller.play(); app.controller.seek(6); app.controller.pause(); app.controller.dispose();
  const store = memory(); store.setItem(key('a'), '{broken json');
  const malformed = setup({ storage: store }); assert.equal(malformed.controller.state().position, 0); assert.equal(store.getItem('private-learner-record'), '{"evidence":["real answer"]}');
});

function narrationHarness(storage = memory()) {
  const nodes = [], cleanups = [];
  function el(tag, props = {}, ...children) {
    const node = tag === 'audio' ? new Media() : new EventTarget();
    Object.assign(node, { tag, children: children.flat(Infinity).filter(child => child !== null), className: props.class || '', hidden: false, attributes: {}, textContent: children.filter(child => typeof child === 'string').join('') });
    node.setAttribute = (key, value) => { node.attributes[key] = value; };
    if (tag !== 'audio') node.removeAttribute = key => { delete node.attributes[key]; };
    node.append = (...items) => { node.children.push(...items); };
    for (const [key, value] of Object.entries(props)) {
      if (key === 'on') for (const [type, handler] of Object.entries(value)) node.addEventListener(type, handler);
      else node.attributes[key] = value;
    }
    nodes.push(node); return node;
  }
  const context = { window: { localStorage: storage }, location: { href: 'https://app.test/', origin: 'https://app.test' }, URL,
    document: { querySelectorAll: () => nodes.filter(node => ['audio', 'video'].includes(node.tag)), createDocumentFragment: () => el('fragment') } };
  vm.createContext(context); vm.runInContext(fs.readFileSync(path.join(__dirname, '../web/lesson-visuals.js'), 'utf8'), context);
  const visuals = context.window.LessonVisuals.create({ el, button: (label, action, style) => el('button', { class: style, on: { click: action } }, label), link: () => null, onCleanup: fn => cleanups.push(fn) });
  return { nodes, storage, cleanups, create(clip) { const from = nodes.length; visuals.audioNarration({ audio_lesson: { clips: [clip] } }, clip.chapter); return nodes.slice(from); } };
}

test('single-chapter controls restore and clear exact positions without writing learning records', () => {
  const app = narrationHarness(); const clip = fixture()[0];
  let nodes = app.create(clip); let audio = nodes.find(node => node.tag === 'audio'); audio.metadata(20); audio.currentTime = 12; audio.emit('timeupdate');
  app.cleanups.at(-1)();
  const progressKey = [...app.storage.values.keys()].find(item => item.startsWith('zhixing.audio-progress'));
  assert.equal(JSON.parse(app.storage.getItem(progressKey)).time, 12);
  nodes = app.create(clip); audio = nodes.find(node => node.tag === 'audio'); audio.metadata(20);
  const resume = nodes.find(node => node.tag === 'button' && node.textContent.startsWith('继续上次'));
  assert.equal(resume.hidden, false); resume.dispatchEvent(new Event('click')); assert.equal(audio.currentTime, 12); assert.equal(resume.hidden, true);
  const progress = nodes.find(node => node.className === 'narration-progress'); assert.equal(progress.attributes['aria-live'], undefined);
  audio.currentTime = 0; audio.emit('seeked'); assert.equal(app.storage.getItem(progressKey), null);
  audio.currentTime = 10; audio.emit('pause'); assert.equal(JSON.parse(app.storage.getItem(progressKey)).time, 10);
  audio.currentTime = 19; audio.emit('seeked'); assert.equal(app.storage.getItem(progressKey), null);
  assert.equal(app.storage.getItem('private-learner-record'), '{"evidence":["real answer"]}');
});

test('single-chapter resume ignores an old text even with an unchanged filename and duration', () => {
  const app = narrationHarness(); const clip = fixture()[0];
  const audio = app.create(clip).find(node => node.tag === 'audio'); audio.metadata(20); audio.currentTime = 8; audio.emit('seeked'); app.cleanups.at(-1)();
  const nodes = app.create({ ...clip, transcript: '全新的解说词' }); nodes.find(node => node.tag === 'audio').metadata(20);
  assert.equal(nodes.find(node => node.tag === 'button' && node.textContent === '继续上次').hidden, true);
});

test('merely opening and closing a chapter preserves its existing resume position', () => {
  const app = narrationHarness(); const clip = fixture()[0];
  let audio = app.create(clip).find(node => node.tag === 'audio'); audio.metadata(20); audio.currentTime = 11; audio.emit('seeked'); app.cleanups.at(-1)();
  audio = app.create(clip).find(node => node.tag === 'audio'); audio.metadata(20); audio.emit('pause'); app.cleanups.at(-1)();
  const nodes = app.create(clip); audio = nodes.find(node => node.tag === 'audio'); audio.metadata(20);
  const resume = nodes.find(node => node.tag === 'button' && node.textContent.startsWith('继续上次'));
  assert.equal(resume.hidden, false); resume.dispatchEvent(new Event('click')); assert.equal(audio.currentTime, 11);
});
