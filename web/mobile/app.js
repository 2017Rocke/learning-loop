'use strict';

(() => {
  const STORE_KEY = `zhixing.mobile.learning.v1:${new URL('.', document.baseURI).pathname}`;
  const L = window.LearningState;
  const root = document.getElementById('app');
  const toastNode = document.getElementById('toast');
  const chapters = [['logic', '看懂原理'], ['case', '跟着案例'], ['code', '拆解代码'], ['experiment', '动手实验'], ['application', '用到实际'], ['summary', '回想总结']];
  const navItems = [['today', '今日', '◷'], ['courses', '课程', '▤'], ['review', '复习', '↻'], ['settings', '我的', '☷']];
  let courses = [];
  let state;
  let storageError = '';
  let storedRaw = null;
  let cleanup = [];
  let courseFilter = '全部';
  let query = '';
  let selectedReview = null;
  let pendingImport = null;
  let installPrompt = null;
  let offlineReady = false;
  let workerRegistration = null;
  let updateReady = false;
  let hadController = Boolean(navigator.serviceWorker?.controller);
  let reloadAfterUpdate = false;
  let toastTimer;
  const drafts = new Map();
  const revealed = new Set();
  const visuals = window.LessonVisuals.create({ el, button, link, onCleanup: fn => cleanup.push(fn), assetBase: document.baseURI });

  function el(tag, props = {}, ...children) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(props)) {
      if (value === null || value === undefined || value === false) continue;
      if (key === 'class') node.className = value;
      else if (key === 'text') node.textContent = value;
      else if (key === 'on') for (const [event, handler] of Object.entries(value)) node.addEventListener(event, handler);
      else if (['disabled', 'checked', 'value'].includes(key)) node[key] = value;
      else node.setAttribute(key, value === true ? '' : String(value));
    }
    for (const child of children.flat(Infinity)) if (child !== null && child !== undefined && child !== false) node.append(child instanceof Node ? child : document.createTextNode(String(child)));
    return node;
  }
  function button(label, callback, style = '', _icon = null, disabled = false) { return el('button', { type: 'button', class: `button ${style}`, disabled, on: { click: callback } }, label); }
  function link(label, value, cls = '') { try { const url = new URL(value); if (['https:', 'http:'].includes(url.protocol)) return el('a', { href: url.href, class: cls, target: '_blank', rel: 'noopener noreferrer' }, label); } catch { /* No link when no valid source was provided. */ } return el('span', { class: cls }, label); }
  function route() { const parts = location.hash.slice(1).split('/'); if (parts[0] === 'course') { try { return { view: 'course', id: decodeURIComponent(parts[1] || ''), chapter: parts[2] || 'logic' }; } catch { return { view: 'courses' }; } } return { view: navItems.some(([key]) => key === parts[0]) ? parts[0] : 'today' }; }
  function navigate(hash) { if (location.hash === `#${hash}`) render(); else location.hash = hash; window.scrollTo({ top: 0, behavior: 'auto' }); }
  function courseRoute(course, chapter = 'logic') { navigate(`course/${encodeURIComponent(course.id)}/${chapter}`); }
  function toast(message, error = false) { clearTimeout(toastTimer); toastNode.textContent = message; toastNode.className = `visible${error ? ' error' : ''}`; toastTimer = setTimeout(() => { toastNode.className = ''; }, error ? 8000 : 4000); }
  function date(value) { return new Intl.DateTimeFormat('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date(value)); }
  function dayKey(value) { const d = new Date(value); return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`; }
  function uid(prefix) { return `${prefix}-${crypto.randomUUID()}`; }
  function courseByID(id) { return courses.find(course => course.id === id); }
  function panel(title, ...children) { return el('section', { class: 'panel' }, title ? el('h2', {}, title) : null, ...children); }
  function commit(next, message, allowRecovery = false) {
    try {
      if (storageError && !allowRecovery) throw new Error('原学习记录尚未恢复。请先在“我的”导出备份并导入有效记录。');
      const checked = L.validateState(next, courses);
      // One atomic localStorage write: keep the previous state on validation/quota errors.
      localStorage.setItem(STORE_KEY, JSON.stringify(checked));
      state = checked; storedRaw = JSON.stringify(checked); storageError = ''; if (message) toast(message); render(); return true;
    } catch (error) { toast(error.message || '记录未保存，请导出备份后重试。', true); return false; }
  }
  function safeAction(action) { try { action(); } catch (error) { toast(error.message || '操作没有完成。', true); } }
  function empty(title, text, action = null) { return el('div', { class: 'empty' }, el('div', { class: 'empty-sign', 'aria-hidden': 'true' }, '◌'), el('h2', {}, title), el('p', {}, text), action); }
  function stopMedia() { for (const fn of cleanup.splice(0)) fn(); }

  function render() {
    if (!state) return;
    stopMedia(); root.setAttribute('aria-busy', 'false');
    const current = route();
    const header = el('header', { class: 'app-header' }, el('button', { class: 'brand', type: 'button', on: { click: () => navigate('today') } }, el('span', { class: 'brand-mark', 'aria-hidden': 'true' }, '↻'), el('span', {}, el('strong', {}, '知行'), el('small', {}, '随身学习'))), el('div', { class: 'connection-pill', id: 'connection-state', role: 'status' }, connectionText()));
    const page = el('main', { id: 'main-content', class: current.view === 'course' ? 'main course-main' : 'main' });
    if (storageError) page.append(el('div', { class: 'warning' }, storageError, ' 原记录未被覆盖。请在“我的”恢复。'));
    const renderers = { today: renderToday, courses: renderCourses, review: renderReview, settings: renderSettings, course: renderCourse };
    page.append(renderers[current.view](current));
    const bottom = el('nav', { class: 'bottom-nav', 'aria-label': '主导航' }, navItems.map(([key, label, glyph]) => el('button', { type: 'button', class: current.view === key || current.view === 'course' && key === 'courses' ? 'active' : '', 'aria-current': current.view === key ? 'page' : null, on: { click: () => navigate(key) } }, el('span', { class: 'nav-glyph', 'aria-hidden': 'true' }, glyph), el('span', {}, label), key === 'review' && L.due(state).length ? el('b', {}, L.due(state).length) : null)));
    root.replaceChildren(header, el('div', { id: 'update-notice' }), page, bottom); showUpdateNotice();
  }
  function connectionText() { return navigator.onLine ? offlineReady ? '已保存离线课程' : '联网可学习' : offlineReady ? '离线学习中' : '当前离线'; }
  function updateConnection() { const label = document.getElementById('connection-state'); if (label) label.textContent = connectionText(); }
  function showUpdateNotice() {
    const node = document.getElementById('update-notice');
    if (!node) return;
    node.replaceChildren(...(updateReady ? [el('div', { class: 'update-banner', role: 'status' }, el('span', {}, '新课程已下载，保存当前输入后刷新使用。'), button('刷新课程', applyUpdate, 'small outline'))] : []));
  }
  function applyUpdate() {
    const waiting = workerRegistration?.waiting;
    if (!waiting) { location.reload(); return; }
    reloadAfterUpdate = true;
    waiting.postMessage({ type: 'SKIP_WAITING' });
  }
  function observeWorker(registration) {
    const noticeWaiting = () => { if (registration.waiting && navigator.serviceWorker.controller) { updateReady = true; showUpdateNotice(); } };
    const watchInstalling = () => {
      const worker = registration.installing;
      if (!worker) return;
      worker.addEventListener('statechange', () => { if (worker.state === 'installed') noticeWaiting(); });
    };
    registration.addEventListener('updatefound', watchInstalling); watchInstalling(); noticeWaiting();
  }
  async function checkUpdates() {
    if (!navigator.onLine) { toast('请联网后检查课程更新。', true); return; }
    if (!workerRegistration) { toast('离线应用尚在准备，请稍后再试。'); return; }
    try { await workerRegistration.update(); if (workerRegistration.waiting) { updateReady = true; showUpdateNotice(); } toast(updateReady ? '新版本已就绪，点击顶部“刷新课程”即可使用。' : '已检查更新；发现新版本后会完整下载，再提示刷新。'); } catch { toast('暂时无法检查更新，请稍后重试。', true); }
  }

  function renderToday() {
    const due = L.due(state);
    const selected = state.enrollments.map(item => courseByID(item.course_id)).filter(Boolean);
    const today = dayKey(Date.now());
    const evidenceToday = state.evidence.filter(item => dayKey(item.created_at) === today).length;
    const reviewsToday = state.review_history.filter(item => dayKey(item.answered_at) === today).length;
    const preferred = selected.find(course => { const p = L.progress(state, course.id); return !p.experiment || !p.application || !p.summary; }) || selected[0] || courses[0];
    const progress = preferred ? L.progress(state, preferred.id) : null;
    const nextChapter = progress ? !progress.experiment ? 'experiment' : !progress.application ? 'application' : !progress.summary ? 'summary' : 'logic' : 'logic';
    const page = el('div', {}, el('div', { class: 'page-heading' }, el('div', { class: 'eyebrow' }, '每天一个小进步'), el('h1', {}, '把好奇，变成自己的能力。'), el('p', {}, `今天留 ${state.settings.daily_minutes} 分钟学习，再用 ${state.settings.review_minutes} 分钟找回旧知识。`)));
    page.append(el('div', { class: 'today-stats' }, [['等待回忆', due.length, '题'], ['今日已复习', reviewsToday, '次'], ['今日成果', evidenceToday, '份']].map(([label, number, unit]) => el('div', {}, el('span', {}, label), el('strong', {}, number, el('small', {}, unit))))));
    if (due.length) page.append(el('section', { class: 'daily-callout' }, el('div', { class: 'eyebrow' }, '先花几分钟，接住旧知识'), el('h2', {}, `${due.length} 道核心问题到期了`), el('p', {}, '不看资料解释一次，再对照答案。今天完成几题就有价值。'), button('开始主动回忆 →', () => navigate('review'), 'primary')));
    if (preferred) {
      const enrolled = selected.some(course => course.id === preferred.id);
      page.append(el('section', { class: 'course-hero' }, el('span', { class: 'subject-label' }, preferred.subject || '跨学科学习'), el('h2', {}, preferred.title), el('p', {}, preferred.lesson.visual_lesson?.hook || preferred.lesson.summary), el('div', { class: 'learning-path' }, ['看懂', '动手', '应用', '回想'].map((label, i) => el('span', { class: i > 0 && progress[['experiment', 'application', 'summary'][i - 1]] ? 'done' : '' }, label))), button(enrolled ? `继续 · ${chapters.find(([key]) => key === nextChapter)[1]} →` : '开始今天的学习 →', () => { if (!enrolled) commit(L.enroll(state, preferred), '已加入你的学习计划。'); courseRoute(preferred, enrolled ? nextChapter : 'logic'); }, 'primary')));
    }
    page.append(panel('今天怎样算有收获', el('ol', { class: 'steps' }, el('li', {}, '先解释一个原理，再用图解核对。'), el('li', {}, '改变一个条件，观察结果是否符合预测。'), el('li', {}, '留下自己的判断或成果，明天再主动回忆。'))));
    page.append(el('p', { class: 'helper' }, '观看和播放不会自动算作掌握。今日督学会在打开应用时更新；关闭后不会发送推送。'));
    return page;
  }

  function renderCourses() {
    const page = el('div', {}, el('div', { class: 'page-heading' }, el('div', { class: 'eyebrow' }, '沿着问题，连接学科'), el('h1', {}, '今天想理解什么？'), el('p', {}, '选择一个可以解释、可以验证、可以用起来的问题。')));
    const subjects = ['全部', ...new Set(courses.map(course => course.subject || '其他'))];
    if (!subjects.includes(courseFilter)) courseFilter = '全部';
    page.append(el('div', { class: 'subject-filters', role: 'group', 'aria-label': '按学科筛选' }, subjects.map(subject => button(subject, () => { courseFilter = subject; render(); }, courseFilter === subject ? 'chip active' : 'chip'))));
    const grid = el('div', { class: 'course-grid' });
    function update() { const visible = courses.filter(course => (courseFilter === '全部' || (course.subject || '其他') === courseFilter) && (!query || `${course.title} ${course.subject} ${course.topic_id}`.toLowerCase().includes(query.toLowerCase()))); grid.replaceChildren(...(visible.length ? visible.map(courseCard) : [empty('没有匹配的课程', '试试其他学科或更短的关键词。')])); }
    page.append(el('input', { class: 'search', type: 'search', placeholder: '搜索课程、学科或问题', 'aria-label': '搜索课程', value: query, on: { input: event => { query = event.target.value; update(); } } }), grid);
    update();
    page.append(el('p', { class: 'helper' }, '这里展示已准备并发布的课程。新选题由电脑端学习助手研究后加入，手机会在联网刷新时读取更新。'));
    return page;
  }
  function courseCard(course) {
    const started = state.enrollments.some(item => item.course_id === course.id); const progress = L.progress(state, course.id);
    const poster = course.lesson.visual_lesson?.steps?.[0];
    return el('article', { class: 'course-card' }, poster ? visuals.imageCard(poster) : el('div', { class: 'course-placeholder', 'aria-hidden': 'true' }, course.kind === 'project' ? '⌘' : '◉'), el('div', { class: 'course-card-copy' }, el('div', { class: 'course-card-meta' }, el('span', {}, course.subject || '综合学习'), el('span', {}, started ? '已加入学习' : '可开始')), el('h2', {}, course.title), el('p', {}, course.lesson.visual_lesson?.hook || course.lesson.summary), el('div', { class: 'course-card-bottom' }, el('span', {}, `${progress.count} 份实践记录`), button(started ? '继续学习 →' : '进入课程 →', () => courseRoute(course), 'small primary'))));
  }

  function evidenceForm(course, kind, title) {
    const key = `evidence:${course.id}:${kind}`;
    const input = el('textarea', { class: 'textarea', id: `record-${kind}`, placeholder: '我做了什么？原先怎样预测？实际观察到了什么？结果有什么限制？', maxlength: '20000', value: drafts.get(key) || '', on: { input: event => drafts.set(key, event.target.value) } });
    const form = el('div', { class: 'evidence-form' }, el('label', { class: 'field-label', for: `record-${kind}` }, title), input, button('保存这次记录', () => safeAction(() => { const value = String(drafts.get(key) || '').trim(); if (!value) { input.focus(); throw new Error('先留下自己的过程、观察或判断。'); } const next = L.addEvidence(state, course, kind, value, uid('evidence')); if (commit(next, '已保存到这台设备，首次记录后核心问题会进入复习计划。')) { drafts.delete(key); render(); } }), 'primary'), el('p', { class: 'helper' }, '保存在这台设备的浏览器中。提交自己的观察；不替你执行代码，也不自动认定掌握。'));
    const entries = state.evidence.filter(item => item.course_id === course.id && item.kind === kind).slice().reverse();
    if (entries.length) form.append(visuals.fold(`查看 ${entries.length} 条已有记录`, entries.map(item => el('article', { class: 'saved-record' }, el('time', {}, date(item.created_at)), el('p', {}, item.text)))));
    return form;
  }
  function steps(items) { return el('ol', { class: 'steps' }, (items || []).map(item => el('li', {}, item))); }
  function acceptance(items) { return items?.length ? el('div', { class: 'acceptance' }, el('h4', {}, '用这些标准检查成果'), el('ul', {}, items.map(item => el('li', {}, item)))) : null; }
  function renderCourse(current) {
    const course = courseByID(current.id);
    if (!course) return empty('这条课程还没有发布', '返回课程列表选择当前可用的课程。', button('浏览课程', () => navigate('courses'), 'primary'));
    const lesson = course.lesson; const visual = lesson.visual_lesson || {};
    const available = chapters.filter(([key]) => key !== 'code' || lesson.code_insight !== null && typeof lesson.code_insight === 'object');
    const chapter = available.some(([key]) => key === current.chapter) ? current.chapter : 'logic';
    const selected = state.enrollments.some(item => item.course_id === course.id);
    const page = el('div', { class: 'learn-page' }, el('div', { class: 'course-topline' }, button('← 全部课程', () => navigate('courses'), 'ghost'), el('span', { class: 'subject-label' }, course.subject || '综合学习')), el('div', { class: 'course-title' }, el('h1', {}, course.title), !selected ? button('加入学习', () => commit(L.enroll(state, course), '已加入学习，记录成果后再安排复习。'), 'small outline') : el('span', { class: 'tag' }, '已加入学习')));
    const nav = el('nav', { class: 'lesson-nav', 'aria-label': '学习章节' }, available.map(([key, title]) => el('button', { type: 'button', class: `lesson-tab${key === chapter ? ' active' : ''}`, 'aria-current': key === chapter ? 'step' : null, on: { click: () => courseRoute(course, key) } }, title)));
    const content = el('section', { class: 'lesson-content panel' });
    const audio = visuals.audioNarration(lesson, chapter);
    if (chapter === 'logic') {
      content.append(el('div', { class: 'lesson-hook' }, el('h2', {}, visual.hook || lesson.summary || course.title)), audio, visuals.videoLesson(visual), visuals.stepLesson(visual, lesson.core_ideas), visuals.gaussianViewer(visual.interactive), visuals.fold('展开完整原理讲解', el('p', { class: 'prose' }, lesson.mental_model || lesson.summary), (lesson.core_ideas || []).map(idea => el('div', { class: 'idea' }, el('h3', {}, idea.title), el('p', {}, idea.explanation)))));
    } else if (chapter === 'case') {
      content.append(el('h2', {}, lesson.case_study?.title || '跟着一个案例理解'), audio, visuals.caseWalkthrough(lesson), visuals.fold('案例背景与完整步骤', el('p', { class: 'prose' }, lesson.case_study?.scenario), steps(lesson.case_study?.steps)));
    } else if (chapter === 'code') {
      content.append(el('h2', {}, lesson.code_insight.title || '拆解代码'), audio, visuals.codeWalkthrough(lesson));
    } else if (chapter === 'experiment') {
      content.append(el('h2', {}, lesson.experiment?.title || '动手验证一次'), audio);
      if (visual.interactive?.kind === 'gaussian-viewer') content.append(visuals.experimentEmbed());
      content.append(steps(lesson.experiment?.steps), acceptance(lesson.experiment?.acceptance), evidenceForm(course, 'experiment', '记录你的实验'));
    } else if (chapter === 'application') {
      content.append(el('h2', {}, '把知识用到自己的问题'), audio, el('p', { class: 'prose' }, lesson.application?.prompt), acceptance(lesson.application?.acceptance), evidenceForm(course, 'application', '记录一次实际使用'));
    } else {
      content.append(el('h2', {}, '留下自己的解释'), audio, visuals.takeaways(lesson), visuals.fold('查看总结提示', steps(lesson.recap_prompts)), evidenceForm(course, 'summary', '用自己的话做总结'), el('h3', {}, '自测问题'));
      content.append(...(lesson.questions || []).map((q, i) => el('div', { class: 'question-item' }, el('p', {}, `${i + 1}. ${q.prompt}`), visuals.fold('想过以后，看参考答案', el('p', { class: 'prose' }, q.answer)))));
    }
    if (lesson.source_refs?.length) content.append(visuals.fold('资料来源', el('div', { class: 'lesson-sources' }, lesson.source_refs.map(ref => link(`${ref.title} ↗`, ref.url)))));
    const index = available.findIndex(([key]) => key === chapter);
    content.append(el('div', { class: 'lesson-pager' }, index > 0 ? button('← 上一节', () => courseRoute(course, available[index - 1][0]), 'ghost') : el('span', {}, '先理解，再动手'), el('span', {}, `${index + 1} / ${available.length}`), index < available.length - 1 ? button(`${available[index + 1][1]} →`, () => courseRoute(course, available[index + 1][0]), 'outline') : button('回忆复习 →', () => navigate('review'), 'outline')));
    page.append(nav, content); return page;
  }

  function renderReview() {
    const due = L.due(state); const sorted = state.reviews.slice().sort((a, b) => Date.parse(a.due_at) - Date.parse(b.due_at));
    const page = el('div', {}, el('div', { class: 'page-heading' }, el('div', { class: 'eyebrow' }, '先回忆，再对照'), el('h1', {}, '把答案，从脑海里找回来。'), el('p', {}, `${due.length} 题到期 · 建议今天用 ${state.settings.review_minutes} 分钟完成几题。`)));
    let review = sorted.find(item => item.id === selectedReview) || due[0];
    if (!review) {
      page.append(empty(sorted.length ? '这一刻，没有到期的复习' : '先留下第一次实践记录', sorted.length ? `下一次：${date(sorted[0].due_at)}。提前练习不会延长原来的计划。` : '完成一次实验、应用或总结后，这门课的核心问题会在次日进入复习。', sorted.length ? button('提前练习一题', () => { selectedReview = sorted[0].id; render(); }, 'outline') : button('去选课程', () => navigate('courses'), 'primary'))); return page;
    }
    selectedReview = review.id;
    const course = courseByID(review.course_id); const question = course.lesson.questions.find(q => q.id === review.question_id);
    const key = `review:${review.id}`; const isDue = Date.parse(review.due_at) <= Date.now();
    const response = el('textarea', { class: 'textarea', id: 'review-answer', maxlength: '20000', placeholder: '用自己的话解释。暂时想不起来，也可以诚实写下卡住的地方。', value: drafts.get(key) || '', on: { input: event => drafts.set(key, event.target.value) } });
    const card = panel(null, el('div', { class: 'review-meta' }, el('span', { class: 'subject-label' }, course.title), el('span', { class: 'tag' }, isDue ? '已到期' : '提前练习')), el('h2', { class: 'review-question' }, question.prompt), el('label', { class: 'field-label', for: 'review-answer' }, '先写你的回答'), response);
    if (!revealed.has(review.id)) card.append(button('我答过了，查看参考答案', () => { if (!String(drafts.get(key) || '').trim()) { response.focus(); toast('先写下自己的回答，再看参考答案。', true); return; } revealed.add(review.id); render(); }, 'primary'));
    else card.append(el('div', { class: 'answer-box' }, el('h3', {}, '参考答案'), el('p', {}, question.answer)), el('p', { class: 'helper' }, isDue ? '根据自己的独立回忆评分，决定下次何时再练。' : '本次提前练习不会延长原计划；忘记则 10 分钟后再练。'), el('div', { class: 'rating-grid' }, [['again', '还没想起', '10 分钟后'], ['hard', '有点吃力', '再近一点'], ['good', '基本想起', '正常间隔'], ['easy', '轻松解释', '适当延长']].map(([rating, title, hint]) => el('button', { type: 'button', class: `rating ${rating}`, on: { click: () => safeAction(() => { const next = L.answerReview(state, review.id, String(drafts.get(key) || ''), rating, uid('review')); if (commit(next, '已保存回答，并更新下次复习时间。')) { selectedReview = null; revealed.delete(review.id); drafts.delete(key); render(); } }) } }, title, el('small', {}, hint)))));
    card.append(el('p', { class: 'helper' }, `原计划 ${date(review.due_at)} · 已成功回忆 ${review.repetitions} 次`)); page.append(card);
    if (sorted.length > 1) page.append(visuals.fold('查看复习队列', sorted.slice(0, 20).map(item => el('div', { class: 'queue-item' }, el('span', {}, courseByID(item.course_id).lesson.questions.find(q => q.id === item.question_id).prompt), button(item.id === review.id ? '当前' : '换这题', () => { selectedReview = item.id; render(); }, 'small outline', null, item.id === review.id)))));
    return page;
  }

  function downloadText(text, filename) { const url = URL.createObjectURL(new Blob([text], { type: 'application/json;charset=utf-8' })); const anchor = el('a', { href: url, download: filename }); document.body.append(anchor); anchor.click(); anchor.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000); }
  function exportState() { downloadText(JSON.stringify(state, null, 2), `zhixing-mobile-${new Date().toISOString().slice(0, 10)}.json`); toast('备份已交给浏览器下载，请妥善保存。'); }
  async function importFile(file) {
    if (!file) return;
    try { if (file.size > 10000000) throw new Error('请选择 10 MB 以内的备份。'); pendingImport = L.importBackup(await file.text(), courses); render(); }
    catch (error) { pendingImport = null; toast(error.message, true); }
  }
  async function installApp() { if (!installPrompt) return; const prompt = installPrompt; installPrompt = null; await prompt.prompt(); await prompt.userChoice; render(); }
  function renderSettings() {
    const page = el('div', {}, el('div', { class: 'page-heading' }, el('div', { class: 'eyebrow' }, '你的节奏，你的记录'), el('h1', {}, '把学习放进口袋。')));
    const daily = el('input', { type: 'number', min: '5', max: '180', value: state.settings.daily_minutes, required: true, id: 'daily-minutes' });
    const review = el('input', { type: 'number', min: '1', max: '60', value: state.settings.review_minutes, required: true, id: 'review-minutes' });
    page.append(el('form', { class: 'panel', on: { submit: event => { event.preventDefault(); const next = JSON.parse(JSON.stringify(state)); next.settings = { daily_minutes: Number(daily.value), review_minutes: Number(review.value) }; next.updated_at = new Date().toISOString(); commit(next, '学习节奏已保存。'); } } }, el('h2', {}, '每天留几分钟'), el('div', { class: 'settings-fields' }, el('label', { for: 'daily-minutes' }, '学习 / 分钟', daily), el('label', { for: 'review-minutes' }, '复习 / 分钟', review)), el('button', { class: 'button primary', type: 'submit' }, '保存节奏')));
    const fileInput = el('input', { type: 'file', accept: 'application/json,.json', id: 'import-file', on: { change: event => importFile(event.target.files?.[0]) } });
    page.append(panel('备份与换设备', el('p', { class: 'prose' }, '记录只保存在当前浏览器，电脑端与其他手机不会自动同步。清除浏览器数据会失去本机记录，请定期导出。'), el('div', { class: 'action-row' }, button('导出学习记录', exportState, 'outline'), storageError && storedRaw ? button('导出原始记录', () => downloadText(storedRaw, 'zhixing-recovery-original.json'), 'outline') : null), el('label', { class: 'file-import', for: 'import-file' }, '选择知行手机端 JSON 备份', fileInput), el('p', { class: 'helper' }, '导入会先检查格式、课程、问题与记录关联；确认后一次性替换本机记录。不会合并或上传。')));
    if (pendingImport) page.append(el('section', { class: 'panel import-confirm' }, el('h2', {}, '备份有效，确认后替换'), el('p', { class: 'prose' }, `将恢复 ${pendingImport.enrollments.length} 门课程、${pendingImport.evidence.length} 条实践记录和 ${pendingImport.review_history.length} 次复习回答。原记录不会与它合并。`), el('div', { class: 'action-row' }, button('先导出当前记录', exportState, 'outline'), button('确认替换本机记录', () => { const candidate = pendingImport; if (commit(candidate, '已完整恢复备份。', true)) { pendingImport = null; selectedReview = null; revealed.clear(); drafts.clear(); render(); } }, 'primary'), button('取消', () => { pendingImport = null; render(); }, 'ghost'))));
    page.append(panel('手机日历提醒', el('p', { class: 'prose' }, '导出每天 20:00 的复习日历，再由你导入手机日历。日历是否提醒取决于手机设置。'), button('导出每日复习提醒', () => safeAction(() => { if (!window.LearningCalendar) throw new Error('日历功能暂未加载，请联网刷新。'); window.LearningCalendar.download({ time: '20:00', minutes: state.settings.review_minutes }); }), 'outline'), el('p', { class: 'helper' }, '这会下载日历文件；导入后才能提醒，并非浏览器后台推送。')));
    page.append(panel('安装与离线', el('p', { class: 'prose' }, offlineReady ? '课程已保存在此设备，可以离线查看图解、音频与练习。新课程需要联网更新。' : '第一次联网打开时会准备离线课程。完成前请保持页面打开，准备好后顶部会显示“已保存离线课程”。'), installPrompt ? button('安装知行到主屏幕', installApp, 'primary') : el('p', { class: 'helper' }, 'iPhone：Safari 的分享菜单 → 添加到主屏幕。Android：浏览器菜单 → 安装应用 / 添加到主屏幕。'), el('p', { class: 'helper' }, '语音需你点播放；浏览器或系统可能在后台暂停媒体。复习提醒在打开应用时显示，关闭网页后不提供推送。'), button('检查课程更新', checkUpdates, 'outline')));
    page.append(el('p', { class: 'privacy-note' }, el('a', { href: './credits.html' }, '项目许可与素材来源')));
    page.append(el('p', { class: 'privacy-note' }, '不设账户 · 学习记录不上传 · 无云端同步'));
    return page;
  }

  async function init() {
    try {
      const response = await fetch(new URL('courses.json', document.baseURI), { cache: 'no-cache' });
      if (!response.ok) throw new Error('课程包暂时无法读取。请联网重新打开。');
      const catalog = await response.json();
      if (catalog.schema_version !== 1 || !Array.isArray(catalog.courses) || catalog.courses.length > 2000 || !catalog.courses.every(course => course && typeof course.id === 'string' && typeof course.title === 'string' && course.lesson && Array.isArray(course.lesson.questions)) || new Set(catalog.courses.map(course => course.id)).size !== catalog.courses.length) throw new Error('课程包格式不正确，请更新应用。');
      courses = catalog.courses;
      try { storedRaw = localStorage.getItem(STORE_KEY); state = storedRaw ? L.importBackup(storedRaw, courses) : L.fresh(); } catch (error) { storageError = error.message || '浏览器暂时无法读取本机记录。'; state = L.fresh(); }
      render();
      if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register(new URL('sw.js', document.baseURI), { scope: new URL('.', document.baseURI).pathname }).then(async registration => {
          workerRegistration = registration; observeWorker(registration); await navigator.serviceWorker.ready; offlineReady = Boolean(registration.active); updateConnection();
        }).catch(() => { offlineReady = false; updateConnection(); });
      }
    } catch (error) { root.setAttribute('aria-busy', 'false'); root.replaceChildren(el('main', { class: 'main' }, empty('学习空间还没准备好', error.message, button('重新连接', init, 'primary')))); }
  }
  window.addEventListener('hashchange', render);
  window.addEventListener('online', updateConnection); window.addEventListener('offline', updateConnection);
  window.addEventListener('beforeinstallprompt', event => { event.preventDefault(); installPrompt = event; if (route().view === 'settings') render(); });
  window.addEventListener('pagehide', stopMedia);
  if ('serviceWorker' in navigator) navigator.serviceWorker.addEventListener('controllerchange', () => {
    offlineReady = true; updateConnection();
    if (reloadAfterUpdate) { location.reload(); return; }
    if (hadController) { updateReady = true; showUpdateNotice(); }
    hadController = true;
  });
  init();
})();
