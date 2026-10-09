'use strict';

(() => {
  const root = document.getElementById('app');
  const toastNode = document.getElementById('toast');
  const assistantPrompt = '请在当前 Learning Loop 项目中，先阅读 AGENTS.md 和 skill/learning-loop/SKILL.md，再读取真实状态，为用户已选择且待备课的主线准备课程。不要代替用户完成实验或复习。';
  const viewNames = { today: '今日', discover: '发现主线', learn: '学习工作台', review: '复习', settings: '设置' };
  const icons = {
    loop: ['M6 8a7 7 0 0 1 12-2l2 2', 'M20 3v5h-5', 'M18 16a7 7 0 0 1-12 2l-2-2', 'M4 21v-5h5'],
    today: ['M3 10l9-7 9 7', 'M5 9v11h14V9', 'M9 20v-7h6v7'],
    discover: ['M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18', 'M16 8l-3 5-5 3 3-5 5-3'],
    learn: ['M3 5c3-1 6-1 9 1v15c-3-2-6-2-9-1V5', 'M21 5c-3-1-6-1-9 1v15c3-2 6-2 9-1V5'],
    review: ['M4 10a8 8 0 1 1 1 7', 'M4 4v6h6', 'M12 7v5l3 2'],
    settings: ['M4 7h16', 'M4 17h16', 'M8 4v6', 'M16 14v6'],
    arrow: ['M5 12h14', 'M14 7l5 5-5 5'],
    external: ['M14 4h6v6', 'M20 4l-9 9', 'M10 4H4v16h16v-6'],
    clock: ['M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18', 'M12 7v5l3 2'],
    leaf: ['M19 4C8 2 3 8 6 15s15 4 13-11', 'M5 20l10-11'],
    check: ['M5 12l4 4L19 6'],
    code: ['M8 7l-5 5 5 5', 'M16 7l5 5-5 5', 'M14 4l-4 16'],
    star: ['M12 3l2.7 5.5 6.1.9-4.4 4.3 1 6.1-5.4-2.9-5.4 2.9 1-6.1L3.3 9.4l6.1-.9L12 3'],
    info: ['M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18', 'M12 11v6', 'M12 7v.2'],
    download: ['M12 3v12', 'M7 10l5 5 5-5', 'M4 15v6h16v-6'],
    user: ['M8 7a4 4 0 1 0 8 0 4 4 0 0 0-8 0', 'M4 21v-2a8 8 0 0 1 16 0v2'],
  };
  let state = null;
  let view = Object.hasOwn(viewNames, location.hash.slice(1)) ? location.hash.slice(1) : 'today';
  let selectedTrack = null;
  let selectedReview = null;
  let lessonTab = 'logic';
  let filter = 'software';
  let search = '';
  let busy = false;
  let toastTimer;
  const drafts = new Map();
  const revealedReviews = new Set();
  let viewCleanups = [];
  const visuals = window.LessonVisuals.create({ el, button, link, onCleanup: cleanup => viewCleanups.push(cleanup) });

  function el(tag, props = {}, ...children) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(props)) {
      if (value === null || value === undefined || value === false) continue;
      if (key === 'class') node.className = value;
      else if (key === 'text') node.textContent = value;
      else if (key === 'on') for (const [event, handler] of Object.entries(value)) node.addEventListener(event, handler);
      else if (key === 'disabled' || key === 'checked') node[key] = value;
      else if (key === 'value') node.value = value;
      else node.setAttribute(key, value === true ? '' : value);
    }
    for (const child of children.flat(Infinity)) {
      if (child === null || child === undefined || child === false) continue;
      node.append(child instanceof Node ? child : document.createTextNode(String(child)));
    }
    return node;
  }
  function icon(name, size = 18, cls = '') {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    for (const [key, value] of Object.entries({ width: size, height: size, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': 1.5, 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'aria-hidden': 'true', class: cls })) svg.setAttribute(key, String(value));
    for (const d of icons[name] || icons.info) { const path = document.createElementNS(svg.namespaceURI, 'path'); path.setAttribute('d', d); svg.append(path); }
    return svg;
  }
  function button(label, callback, type = '', iconName = null, disabled = busy) {
    return el('button', { type: 'button', class: `button ${type}`, disabled, on: { click: callback } }, iconName ? icon(iconName, 15) : null, label);
  }
  function safeURL(value) { try { const u = new URL(value); return ['http:', 'https:'].includes(u.protocol) ? u.href : null; } catch { return null; } }
  function link(label, url, cls = '') { const href = safeURL(url); return href ? el('a', { href, class: cls, target: '_blank', rel: 'noopener noreferrer' }, label) : el('span', { class: cls }, label); }
  function tag(text, type = '') { return el('span', { class: `tag ${type}` }, text); }
  function formatDate(value, withTime = false) {
    if (!value) return '尚无记录';
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return '日期未知';
    return new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', month: '2-digit', day: '2-digit', ...(withTime ? { hour: '2-digit', minute: '2-digit', hour12: false } : {}) }).format(d);
  }
  function stars(value) { return Number(value || 0).toLocaleString('en-US'); }
  function intervalText(value) { const days = Number(value || 0); return days > 0 && days < 1 ? `${Math.round(days * 1440)} 分钟` : `${Number(days.toFixed(1))} 天`; }
  function trackStatus(status) { return ({ exploring: '仅讨论过', learning: '正在理解', practicing: '正在实操', applied: '已记录应用', mastered: '已验收掌握', paused: '暂时搁置' })[status] || '状态待确认'; }
  function kindName(kind) { return ({ software: '软件项目', collection: '资源合集', 'learning-resource': '学习资源', unknown: '待分类', tutorial: '教程 / 课程', learning: '学习资料', resource: '资源 / 清单', documentation: '文档', framework: '框架 / 工具', course: '教程 / 课程' })[kind] || kind || '待分类'; }
  function dueReviews() { return (state.reviews || []).filter(r => new Date(r.due_at).getTime() <= Date.now()).sort((a, b) => new Date(a.due_at) - new Date(b.due_at)); }
  function activeTracks() { return (state.tracks || []).filter(t => ['learning', 'practicing', 'applied'].includes(t.status)); }
  function toast(message, error = false) { clearTimeout(toastTimer); toastNode.textContent = message; toastNode.className = `visible${error ? ' error' : ''}`; toastTimer = setTimeout(() => { toastNode.className = ''; }, error ? 7000 : 4200); }
  function navigate(next) { view = next; location.hash = next; render(); window.scrollTo({ top: 0, behavior: 'smooth' }); }
  async function api(path, data) {
    const response = await fetch(path, data === undefined ? { cache: 'no-store' } : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
    let result;
    try { result = await response.json(); } catch { throw new Error('服务返回了无法识别的内容，请检查本地服务是否正常运行。'); }
    if (!response.ok) throw new Error(result.error || result.message || `请求失败（${response.status}）`);
    return result;
  }
  async function mutate(path, data, message, callback) {
    if (busy) return;
    busy = true; render();
    try { const next = await api(path, data); state = next; if (callback) callback(next); if (message) toast(message); }
    catch (error) { toast(error.message || '操作失败，请稍后重试。', true); }
    finally { busy = false; render(); }
  }
  function heading(kicker, title, subtitle, actions = null) { return el('div', { class: 'page-heading' }, el('div', {}, el('div', { class: 'eyebrow' }, kicker), el('h1', {}, title), el('p', {}, subtitle)), actions ? el('div', { class: 'heading-actions' }, actions) : null); }
  function sectionHeading(title, sub, action) { return el('div', { class: 'section-heading' }, el('div', {}, el('h2', {}, title), sub ? el('p', {}, sub) : null), action); }
  function info(text, type = '') { return el('div', { class: `info-bar ${type}` }, icon('info', 16), el('span', {}, text)); }
  function empty(title, message, actions, name = 'leaf') { return el('div', { class: 'empty' }, icon(name, 30, 'empty-icon'), el('h3', {}, title), el('p', {}, message), actions ? el('div', { class: 'action-row' }, actions) : null); }
  function copyInstruction() {
    if (navigator.clipboard?.writeText) navigator.clipboard.writeText(assistantPrompt).then(() => toast('已复制，可粘贴到 Codex 中准备课程。')).catch(() => toast('复制受限。设置页中提供了可选中的完整指令。', true));
    else toast('当前浏览器不支持复制。设置页中提供了可选中的完整指令。', true);
  }

  function render() {
    if (!state) return;
    for (const cleanup of viewCleanups.splice(0)) cleanup();
    root.setAttribute('aria-busy', String(busy));
    const shell = el('div', { class: 'shell' });
    const nav = el('nav', { class: 'nav', 'aria-label': '主导航' });
    for (const [key, label] of Object.entries(viewNames)) nav.append(el('button', { class: `nav-button${view === key ? ' active' : ''}`, type: 'button', 'aria-current': view === key ? 'page' : null, on: { click: () => navigate(key) } }, icon(key), el('span', { class: 'nav-label' }, label), key === 'review' && dueReviews().length ? el('span', { class: 'nav-count' }, dueReviews().length) : null));
    shell.append(el('aside', { class: 'sidebar' }, el('div', { class: 'brand' }, el('div', { class: 'brand-mark' }, icon('loop', 25)), el('div', {}, el('div', { class: 'brand-name' }, '知行'), el('div', { class: 'brand-sub' }, 'LEARNING LOOP'))), nav, el('div', { class: 'sidebar-note' }, el('strong', {}, '把好奇心，变成能力。'), '每天一点理解，', el('br'), '每周一个真实成果。', el('div', { class: 'local-badge' }, el('span', { class: 'dot' }), '本地学习空间'))));
    const main = el('main', { class: 'main', id: 'main-content' });
    main.append(el('header', { class: 'topbar' }, el('div', { class: 'breadcrumb' }, '我的学习空间', el('span', {}, '/'), el('span', {}, viewNames[view])), el('div', { class: 'top-right' }, el('span', { class: 'desktop-date' }, new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', month: 'long', day: 'numeric', weekday: 'long' }).format(new Date())), el('span', { class: 'avatar', title: '学习者' }, icon('user', 15)))));
    const renderers = { today: renderToday, discover: renderDiscover, learn: renderLearn, review: renderReview, settings: renderSettings };
    main.append(renderers[view]());
    main.append(el('footer', { class: 'footer-note' }, '发现 → 理解 → 小实验 → 实际使用 → 回忆复习'));
    shell.append(main); root.replaceChildren(shell);
  }

  function renderToday() {
    const settings = state.settings || {};
    const due = dueReviews();
    const active = activeTracks();
    const track = active[0] || (state.tracks || []).find(t => t.status === 'exploring');
    const page = el('div', {}, heading('TODAY · 今天的学习', '让知识，真正派上用场。', `用 ${settings.daily_minutes || 30} 分钟推进一个问题，再留 ${settings.review_minutes || 5} 分钟，找回已经学过的思路。`));
    if (state.coach?.next_step) {
      const next = state.coach.next_step;
      page.append(el('section', { class: 'coach-card panel' }, el('div', { class: 'eyebrow' }, '今日督学 · 下一步只做一件事'), el('h2', {}, next.title || '继续今天的学习'), el('p', { class: 'prose' }, next.message || ''), el('div', { class: 'action-row' }, button(next.kind === 'review' ? '先回忆几题 →' : '开始这一步 →', () => {
        if (next.kind === 'review') navigate('review');
        else if (next.track_id) { selectedTrack = next.track_id; lessonTab = ['experiment','application','summary'].includes(next.kind) ? next.kind : 'logic'; navigate('learn'); }
        else navigate('discover');
      }, 'primary'), Number.isFinite(next.minutes) ? tag(`约 ${next.minutes} 分钟`) : null)));
    }
    const metrics = [ ['clock', String(settings.daily_minutes || 30), '分钟', '每日学习预算'], ['review', String(due.length), '题', '等待主动回忆'], ['leaf', String(state.stats?.mastered_tracks || 0), '条', '已验收掌握的主线'] ];
    page.append(el('div', { class: 'metrics' }, metrics.map(([name, value, unit, label]) => el('div', { class: 'metric' }, el('div', { class: 'metric-icon' }, icon(name)), el('div', {}, el('div', { class: 'metric-value' }, value, el('span', { class: 'metric-unit' }, unit)), el('div', { class: 'metric-label' }, label))))));
    const hero = el('section', { class: 'panel hero' }, el('div', { class: 'panel-kicker' }, icon('learn', 14), '今日只推进一条主线'));
    if (track) {
      hero.append(el('h2', {}, track.title), el('p', {}, track.lesson?.summary || '这条主线已经进入你的学习空间。把核心问题讲明白，再用一个小实验验证它。'), el('div', { class: 'hero-tags' }, tag(trackStatus(track.status)), tag(track.lesson_status === 'ready' ? '教学内容已准备' : '等待准备教学内容', track.lesson_status === 'ready' ? '' : 'amber')), el('div', { class: 'action-row' }, button(track.lesson_status === 'ready' ? '进入学习工作台' : '查看学习任务', () => { selectedTrack = track.id; navigate('learn'); }, 'primary', 'arrow')));
    } else {
      hero.append(el('h2', {}, '从一个值得动手的问题开始'), el('p', {}, '从 GitHub 高关注项目中选一个方向。先理解它解决什么问题，再留下自己的实验成果。'), el('div', { class: 'hero-tags' }, tag('一次专注一条'), tag('以真实成果验收')), el('div', { class: 'action-row' }, button('发现下一条主线', () => navigate('discover'), 'primary', 'arrow')));
    }
    const review = el('section', { class: 'panel review-teaser' }, el('div', { class: 'panel-kicker' }, icon('review', 14), '给旧知识几分钟'), el('h2', {}, due.length ? '先回忆，再看答案。' : '让理解经得起时间。'), el('div', { class: 'review-illustration' }, el('span', { class: 'review-number' }, String(due.length).padStart(2, '0')), el('span', { class: 'prose' }, '道到期复习题')), el('p', {}, due.length ? '尝试解释原理、预测结果或排查一个反例。答完后，再决定下次见面的时间。' : '完成一条主线的学习与练习后，用复习问题持续检验核心思路。'), el('div', { class: 'action-row' }, button(due.length ? '开始 3–5 分钟复习' : '查看复习计划', () => navigate('review'), 'outline', 'review')));
    page.append(el('div', { class: 'today-grid' }, hero, review));
    page.append(el('div', { class: 'loop-strip' }, [['01', '发现', '选值得解决的问题'], ['02', '理解', '建立自己的解释'], ['03', '小实验', '验证一个关键判断'], ['04', '实际使用', '留下可检查的成果'], ['05', '回忆复习', '隔一段时间再调用']].map(([num, title, description]) => el('div', { class: 'loop-step' }, el('small', {}, num), el('strong', {}, title), el('span', {}, description)))));
    const candidates = state.discovery?.candidates || [];
    page.append(sectionHeading('下一次好奇，从这里开始', '按累计 Star 排序的候选方向，选择前先判断与你的关系。', button('查看全部候选', () => navigate('discover'), 'ghost', 'arrow')));
    if (candidates.length) page.append(el('div', { class: 'candidate-grid' }, candidates.slice(0, 3).map((repo, i) => candidateCard(repo, i))));
    else page.append(empty('还没有候选主线', '联网刷新后，会展示满足门槛且未被排除的开源项目。', button('获取候选项目', refreshDiscovery, 'outline', 'loop'), 'discover'));
    if ((state.notifications || []).length) page.append(el('div', { class: 'notice-list' }, state.notifications.slice(0, 3).map(n => el('div', { class: 'notice' }, el('time', {}, formatDate(n.created_at)), el('span', {}, n.text)))));
    return page;
  }

  function candidateCard(repo, index) {
    const already = (state.tracks || []).find(t => t.repo_full_name === repo.full_name);
    const nameParts = String(repo.full_name || '').split('/');
    const card = el('article', { class: 'candidate' }, el('div', { class: 'candidate-top' }, el('span', { class: 'repo-glyph' }, icon('code', 17)), el('span', { class: 'rank' }, `#${String(index + 1).padStart(2, '0')}`)), el('h3', {}, nameParts.slice(1).join('/') || repo.full_name), el('div', { class: 'repo-owner' }, nameParts[0]), el('p', { class: 'candidate-description' }, repo.description || '该项目尚未提供简介，选择前请查看项目说明。'), el('div', { class: 'candidate-tags' }, tag(repo.topic_name || '待归类方向'), tag(kindName(repo.kind), repo.kind === 'software' ? 'blue' : 'grey'), repo.learned_core ? tag('核心基础已学习', 'amber') : null), el('div', { class: 'candidate-meta' }, el('span', {}, `☆ ${stars(repo.stars)} 累计 Star`), el('span', {}, repo.language || '语言未标注'), repo.license ? el('span', {}, String(repo.license)) : null));
    card.append(el('div', { class: 'candidate-actions' }, link('查看项目 ↗', repo.html_url, 'text-link'), already ? button('打开学习记录', () => { selectedTrack = already.id; navigate('learn'); }, 'small outline') : button('选择这条主线', () => selectRepo(repo), 'small')));
    card.append(el('div', { class: 'candidate-footer' }, el('button', { type: 'button', class: 'text-link', disabled: busy, on: { click: () => mutate('/api/topics/known', { topic_id: repo.topic_id, topic_name: repo.topic_name }, '已按你的自述记录已有基础，并移出该方向推荐。') } }, '已有基础，移出推荐'), repo.delta_7d !== null && repo.delta_7d !== undefined ? el('span', { class: 'helper' }, `7 日 ${Number(repo.delta_7d) >= 0 ? '+' : ''}${stars(repo.delta_7d)}`) : null));
    return card;
  }
  function selectRepo(repo) {
    mutate('/api/tracks', { repo_full_name: repo.full_name }, '已加入主线。教学内容准备状态会在工作台显示。', next => { selectedTrack = (next.tracks || []).find(t => t.repo_full_name === repo.full_name)?.id; lessonTab = 'logic'; view = 'learn'; location.hash = 'learn'; });
  }
  function refreshDiscovery() { mutate('/api/discovery/refresh', {}, '项目列表已更新。若联网失败，页面会标出缓存状态。'); }
  function renderTopicRequest() {
    const get = (name, fallback = '') => drafts.get(`request:${name}`) ?? fallback;
    const field = (label, name, props = {}) => el('label', { class: 'request-field' }, label, el('input', { type: 'text', maxlength: '200', value: get(name), ...props, on: { input: event => drafts.set(`request:${name}`, event.target.value) } }));
    const kind = el('select', { class: 'select', 'aria-label': '选题类型', value: get('kind', 'subject'), on: { change: event => drafts.set('request:kind', event.target.value) } }, el('option', { value: 'subject' }, '学科知识 / 具体问题'), el('option', { value: 'project' }, '开源项目 / 技术工具')); kind.value = get('kind', 'subject');
    return el('form', { class: 'panel topic-request', on: { submit: event => {
      event.preventDefault();
      const title = String(get('title')).trim(); const subject = String(get('subject')).trim(); const repoURL = String(get('repo_url')).trim();
      if (!title || !subject) { toast('先填写想学的主题和所属学科。', true); return; }
      if (repoURL) { try { if (new URL(repoURL).protocol !== 'https:') throw new Error(); } catch { toast('项目链接请使用完整的 HTTPS 地址。', true); return; } }
      mutate('/api/tracks/request', { title, topic_id: title.normalize('NFKC').toLowerCase(), subject, kind: get('kind', 'subject'), repo_url: repoURL }, '已加入选题，学习助手会研究资料并准备图文课程。', next => { ['title','subject','kind','repo_url'].forEach(name => drafts.delete(`request:${name}`)); selectedTrack = next.requested_track_id; lessonTab = 'logic'; view = 'learn'; location.hash = 'learn'; });
    } } }, el('div', { class: 'eyebrow' }, '不局限于技术，也可以从一个问题开始'), el('h2', {}, '告诉我，你想理解什么'), el('p', { class: 'helper' }, '例如“用贝叶斯思维更新判断”“摄影里的光圈”或一个 GitHub 项目。选题后准备课程，不会把排队显示成已经学会。'), el('div', { class: 'request-grid' }, field('想学的主题', 'title', { required: true, placeholder: '例如：贝叶斯推断如何帮助判断' }), field('所属学科', 'subject', { required: true, maxlength: '100', placeholder: '例如：统计学、心理学、计算机' })), el('div', { class: 'request-grid' }, el('label', { class: 'request-field' }, '选题类型', kind), field('项目或资料链接（可选）', 'repo_url', { type: 'url', maxlength: '1000', placeholder: 'https://…' })), el('div', { class: 'action-row' }, el('button', { type: 'submit', class: 'button primary', disabled: busy }, '加入这条学习主线')));
  }
  function renderDiscover() {
    const discovery = state.discovery || {};
    const page = el('div', {}, heading('DISCOVER · 发现主线', '从一个想弄懂的问题开始。', '学科知识、实际问题和开源项目都可以成为主线。下方继续保留 GitHub 十万 Star 项目雷达。', button(busy ? '正在处理…' : '刷新候选', refreshDiscovery, 'outline', 'loop')));
    page.append(renderTopicRequest());
    page.append(info('默认展示已识别常见开源许可证的软件，按累计 Star 排序，同一主线合并。可切换到包含学习资源的候选；已有基础的方向会从推荐中排除。'));
    if (discovery.warning) page.append(info(discovery.warning, 'warning'));
    if (!state.settings?.automation_enabled) page.append(el('p', { class: 'helper' }, '当前可手动刷新；定时发现是否运行，以设置中的自动化状态为准。'));
    const candidates = (filter === 'software' ? discovery.candidates : discovery.broader_candidates) || [];
    const controls = el('div', { class: 'filters' }, el('span', { class: 'filter-label' }, '项目类型'), ['software', 'all'].map(key => el('button', { type: 'button', class: `chip${filter === key ? ' active' : ''}`, 'aria-pressed': String(filter === key), on: { click: () => { filter = key; render(); } } }, key === 'all' ? '含学习资源' : '开源软件')));
    const searchInput = el('input', { class: 'search', type: 'search', placeholder: '搜索项目或主线…', 'aria-label': '搜索候选项目', value: search, on: { input: event => { search = event.target.value; updateGrid(); } } });
    controls.append(searchInput); page.append(controls);
    const results = el('div');
    function updateGrid() {
      const visible = candidates.map((repo, i) => ({ repo, i })).filter(({ repo }) => !search || `${repo.full_name} ${repo.description} ${repo.topic_name}`.toLowerCase().includes(search.toLowerCase()));
      results.replaceChildren(visible.length ? el('div', { class: 'candidate-grid' }, visible.map(({ repo, i }) => candidateCard(repo, i))) : empty(candidates.length ? '没有匹配的候选' : '等待第一次发现', candidates.length ? '试试更短的关键词，或查看全部类型。' : '刷新后将读取 GitHub 的实际项目数据。网络不可用时，不会用虚构榜单代替。', !candidates.length ? button('获取候选项目', refreshDiscovery, 'outline', 'loop') : null, 'discover'));
    }
    updateGrid(); page.append(results);
    const hasGrowth = candidates.some(repo => repo.delta_7d !== null && repo.delta_7d !== undefined);
    page.append(el('p', { class: 'source-note' }, `来源：GitHub · 更新时间：${formatDate(discovery.fetched_at, true)}（北京时间） · 当前候选 ${candidates.length} 个 · 已排除 ${Number(discovery.excluded_count || 0)} 个。`, el('br'), hasGrowth ? '近 7 日增长基于已保存的实际快照。' : '近 7 日增长：尚无可比较的历史基线。', ' Star 数随抓取时间变化；已识别许可证不代替商用许可核查。'));
    return page;
  }

  const lessonTabs = [ ['logic', '看懂原理'], ['case', '跟着案例'], ['code', '拆解代码'], ['experiment', '动手实验'], ['application', '用到实际'], ['summary', '回想总结'] ];
  function renderLearn() {
    const tracks = state.tracks || [];
    const page = el('div', { class: 'learn-page' });
    if (!tracks.length) { page.append(heading('WORKBENCH · 学习工作台', '看懂一个原理，再亲手验证。', '从一个有用的问题开始。'), empty('还没有学习主线', '先挑一个项目，学习助手会为它准备核心逻辑、问题和实践任务。', button('去发现主线', () => navigate('discover'), 'primary', 'arrow'))); return page; }
    const track = tracks.find(t => t.id === selectedTrack) || activeTracks()[0] || tracks[0]; selectedTrack = track.id;
    const select = el('select', { class: 'select', 'aria-label': '选择学习主线', on: { change: event => { selectedTrack = event.target.value; lessonTab = 'logic'; render(); } } }, tracks.map(t => el('option', { value: t.id }, t.title))); select.value = track.id;
    const status = visuals.fold('查看学习进度', el('div', { class: 'track-status' }, tag(trackStatus(track.status)), tag(track.lesson_status === 'ready' ? '课程已准备' : '教学内容待准备', track.lesson_status === 'ready' ? '' : 'amber')), el('p', { class: 'helper' }, track.status === 'exploring' ? '此前讨论不等于已经掌握；从下面的实验开始验证。' : track.progress_note || '进度根据你的记录推进，掌握状态需要实操、应用和总结证据。')); status.classList.add('track-detail-fold');
    page.append(el('div', { class: 'workbench-top' }, select, status, link('项目 ↗', track.repo_url, 'button outline')));
    if (track.lesson_status !== 'ready' || !track.lesson) {
      page.append(el('div', { class: 'panel pending-card' }, el('div', { class: 'pending-icon' }, icon('clock', 21)), el('div', {}, el('h3', {}, '学习任务已加入，内容仍待准备。'), el('p', {}, '学习助手会核实官方资料或权威教材，再准备图解、语音、案例和练习。先写下你最想解决的问题，便于选择合适的例子。'), el('div', { class: 'action-row' }, button('复制学习助手指令', copyInstruction, 'primary'), button('检查准备状态', reloadState, 'outline', 'loop')), el('div', { class: 'assistant-instruction' }, assistantPrompt))));
      return page;
    }
    const lesson = track.lesson;
    const visual = lesson.visual_lesson || {};
    const availableTabs = lessonTabs.filter(([key]) => key !== 'code' || lesson.code_insight !== null && typeof lesson.code_insight === 'object');
    if (!availableTabs.some(([key]) => key === lessonTab)) lessonTab = 'logic';
    const tabNav = el('nav', { class: 'lesson-nav', 'aria-label': '学习章节' }, availableTabs.map(([key, label], i) => el('button', { type: 'button', class: `lesson-tab${lessonTab === key ? ' active' : ''}`, 'aria-current': lessonTab === key ? 'step' : null, on: { click: () => { lessonTab = key; render(); } } }, el('span', { class: 'lesson-index' }, String(i + 1).padStart(2, '0')), label, ['experiment', 'application', 'summary'].includes(key) && (track.evidence || []).some(e => e.kind === key) ? el('span', { class: 'check', title: '已有记录' }, '·') : null)));
    const content = el('section', { class: 'panel lesson-content' });
    if (lessonTab === 'logic') {
      content.append(el('div', { class: 'lesson-hook' }, el('h2', {}, visual.hook || track.title), visual.duration_minutes ? tag(`约 ${visual.duration_minutes} 分钟 · 看 + 做`) : null), visuals.videoLesson(visual), visuals.stepLesson(visual, lesson.core_ideas), visuals.gaussianViewer(visual.interactive));
      const explanation = el('div');
      if (lesson.summary) explanation.append(el('p', { class: 'prose' }, lesson.summary));
      if (lesson.mental_model) explanation.append(el('div', { class: 'mental-model' }, el('div', { class: 'label' }, '用自己的话再讲一遍'), el('p', {}, lesson.mental_model)));
      explanation.append(...(lesson.core_ideas || []).map((idea, i) => el('div', { class: 'idea' }, el('h3', {}, `${String(i + 1).padStart(2, '0')}  ${String(idea.title).replace(/^\d+[.、]\s*/, '')}`), el('p', {}, idea.explanation))));
      content.append(visuals.fold('需要更深入？展开完整原理讲解', explanation));
      if (visual.watch_more?.length) content.append(visuals.fold('延伸观看 · 官方演示与原始资料', el('div', { class: 'watch-more' }, visual.watch_more.map(item => el('div', {}, link(`${item.title} ↗`, item.url), el('p', {}, item.description))))));
    } else if (lessonTab === 'case') {
      const item = lesson.case_study || {};
      content.append(el('div', { class: 'eyebrow' }, '跟着案例 · 一步一个判断'), el('h2', {}, item.title || '学习案例'), visuals.caseWalkthrough(lesson), visuals.fold('展开案例背景与完整步骤', el('p', { class: 'prose' }, item.scenario || '案例内容尚未提供。'), stepList(item.steps)));
    } else if (lessonTab === 'code') {
      const item = lesson.code_insight || {};
      content.append(el('div', { class: 'eyebrow' }, '拆解代码 · 先看数据怎样流动'), el('h2', {}, item.title || '代码核心思想'), el('p', { class: 'helper' }, item.walkthroughs?.length ? '先看整体流程，再选一个短片段。逐行对照原代码、中文解释和设计原因。' : visual.interactive?.kind === 'gaussian-viewer' ? '点击一个环节，只看对应的一行与它的作用。' : '点击一个环节，理解它的职责；完整代码可以在下方展开。'), visuals.codeWalkthrough(lesson));
    } else if (lessonTab === 'experiment') {
      const item = lesson.experiment || {};
      content.append(el('div', { class: 'eyebrow' }, '动手实验 · 预测 → 改参数 → 看结果'), el('h2', {}, item.title || '动手实验'));
      if (track.topic_id === 'gaussian-splatting') content.append(visuals.experimentEmbed());
      else if (visual.steps?.length) content.append(visuals.imageCard(visual.steps[0]));
      content.append(visuals.fold('展开实验步骤与本地操作方法', stepList(item.steps)), acceptance(item.acceptance), evidenceForm(track, 'experiment', '记录你的实验', '写下：我改了什么 → 预期会怎样 → 实际观察 → 结果或文件路径。'));
    } else if (lessonTab === 'application') {
      const item = lesson.application || {};
      content.append(el('div', { class: 'eyebrow' }, '用到实际 · 留下一个真实成果'), el('h2', {}, '把实验带进真实任务'), el('div', { class: 'app-hint-visual', 'aria-label': '应用过程' }, el('span', {}, '选一个', el('br'), '自己的问题'), el('i', {}, '→'), el('span', {}, '用刚学的原理', el('br'), '做出结果'), el('i', {}, '→'), el('span', {}, '检查它是否', el('br'), '真的有效')), el('p', { class: 'prose' }, item.prompt || '实际应用任务尚未提供。'), acceptance(item.acceptance), evidenceForm(track, 'application', '记录实际使用', '写下：你解决的具体问题、交付物或文件路径、怎样检查它有效，以及剩余限制。'));
    } else {
      content.append(el('div', { class: 'eyebrow' }, '回想总结 · 先关掉资料，再自己解释'), el('h2', {}, '把核心思路，留在脑海里'), visuals.takeaways(lesson), visuals.fold('展开总结提示', stepList(lesson.recap_prompts)), evidenceForm(track, 'summary', '写一份可以复用的总结', '用自己的话解释：核心原理是什么？什么时候用？边界在哪里？下次我会怎样做？'), el('h3', {}, '自测问题'));
      content.append(...(lesson.questions || []).map((q, i) => el('div', { class: 'question-item' }, el('p', {}, `${i + 1}. ${q.prompt}`), el('details', {}, el('summary', {}, '思考后，再看参考答案'), el('p', {}, q.answer)))));
      content.append(el('h3', {}, '更新学习阶段'), el('p', { class: 'helper' }, '“已掌握”由服务检查实操、应用和总结记录；复习仍会继续。'), el('div', { class: 'status-actions' }, [['learning', '正在理解'], ['practicing', '正在实操'], ['applied', '已应用'], ['mastered', '验收为已掌握'], ['paused', '暂时搁置']].map(([status, text]) => button(text, () => mutate(`/api/tracks/${encodeURIComponent(track.id)}/status`, { status }, '学习阶段已更新。'), status === track.status ? 'small primary' : 'small outline', null, busy || status === track.status))));
    }
    const chapterAudio = visuals.audioNarration(lesson, lessonTab);
    const chapterHeading = lessonTab === 'logic' ? content.querySelector('.lesson-hook') : content.querySelector('h2');
    if (chapterHeading) chapterHeading.after(chapterAudio);
    const refs = lesson.source_refs || [];
    if (refs.length) content.append(visuals.fold('资料来源与核查依据', el('div', { class: 'lesson-sources' }, refs.map(ref => link(`${ref.title} ↗`, ref.url)))));
    const current = availableTabs.findIndex(([key]) => key === lessonTab);
    content.append(el('div', { class: 'lesson-pager' }, current ? button('上一节', () => { lessonTab = availableTabs[current - 1][0]; render(); }, 'ghost') : el('span', {}, '看懂之后，动手验证'), el('span', {}, `${current + 1} / ${availableTabs.length}`), current < availableTabs.length - 1 ? button(`下一节 · ${availableTabs[current + 1][1]}`, () => { lessonTab = availableTabs[current + 1][0]; render(); }, 'ghost', 'arrow') : button('去回忆复习', () => navigate('review'), 'ghost', 'review')));
    page.append(el('div', { class: 'learning-layout' }, tabNav, content));
    return page;
  }
  function stepList(items = []) { return el('ol', { class: 'steps' }, items.map(item => el('li', {}, item))); }
  function acceptance(items = []) { return items.length ? el('div', { class: 'acceptance' }, el('h4', {}, '完成前，用这些标准检查结果'), el('ul', {}, items.map(item => el('li', {}, item)))) : null; }
  function evidenceForm(track, kind, label, placeholder) {
    const key = `evidence:${track.id}:${kind}`;
    const input = el('textarea', { class: 'textarea', id: `evidence-${kind}`, placeholder, value: drafts.get(key) || '', on: { input: event => drafts.set(key, event.target.value) } });
    const form = el('div', {}, el('label', { class: 'field-label', for: `evidence-${kind}` }, label), input, button('保存这次记录', () => {
      const text = String(drafts.get(key) || '').trim();
      if (!text) { input.focus(); toast('先写下你实际做过什么和观察到的结果。', true); return; }
      mutate(`/api/tracks/${encodeURIComponent(track.id)}/evidence`, { kind, text }, '记录已保存。', () => drafts.delete(key));
    }, 'primary'), el('p', { class: 'helper' }, '保留真实过程和限制。记录会保存到本地，不会自动执行项目代码。'));
    const records = (track.evidence || []).filter(e => e.kind === kind);
    if (records.length) form.append(el('h3', {}, '已有记录'), ...records.map(e => el('div', { class: 'evidence-item' }, el('div', { class: 'evidence-date' }, formatDate(e.created_at, true)), e.text)));
    return form;
  }

  function renderReview() {
    const due = dueReviews();
    const reviews = (state.reviews || []).slice().sort((a, b) => new Date(a.due_at) - new Date(b.due_at));
    const page = el('div', {}, heading('RECALL · 回忆复习', '先从脑海里，把答案找回来。', '不翻资料，用自己的话解释。忘记是一条反馈：它告诉我们下一次该在哪儿多花一点时间。'));
    if (!reviews.length) { page.append(empty('复习队列还是空的', '先在工作台学习并记录实践，核心问题会随学习推进进入复习计划。', button('打开学习工作台', () => navigate('learn'), 'primary', 'learn'), 'review')); return page; }
    let review = reviews.find(r => r.id === selectedReview) || due[0];
    if (!review) {
      page.append(empty('现在没有到期的复习', `下一次复习：${formatDate(reviews[0].due_at, true)}（北京时间）。提前练习不延长原计划；忘记后 10 分钟再练。`, button('提前复习一题', () => { selectedReview = reviews[0].id; render(); }, 'outline', 'review'), 'check'));
      page.append(el('p', { class: 'source-note' }, `累计完成 ${state.stats?.completed_reviews || 0} 次复习。提前复习不是完成学习主线的必要条件。`));
      return page;
    }
    selectedReview = review.id;
    const isDue = new Date(review.due_at).getTime() <= Date.now();
    const key = `review:${review.id}`;
    const input = el('textarea', { class: 'textarea', id: 'review-response', placeholder: '先写下你的解释、推理过程或一个例子。记不清的地方也可以直接写下来。', value: drafts.get(key) || '', on: { input: event => drafts.set(key, event.target.value) } });
    const card = el('section', { class: 'panel review-card' }, el('div', { class: 'action-row' }, tag(review.track_title || '学习主线'), tag(isDue ? '已到复习时间' : '提前复习', isDue ? '' : 'amber')), el('h2', {}, review.question), el('label', { class: 'field-label', for: 'review-response' }, '你的回答'), input);
    const showAnswer = () => {
      if (!String(drafts.get(key) || '').trim()) { input.focus(); toast('先留下你的回答；“暂时想不起来”也是真实反馈。', true); return; }
      revealedReviews.add(review.id); render();
    };
    if (!revealedReviews.has(review.id)) card.append(button('写完了，查看参考答案', showAnswer, 'primary', 'arrow'), el('p', { class: 'helper' }, '这一步不会提交评分，也不会替你回答。'));
    else {
      card.append(el('div', { class: 'answer-box' }, el('h3', {}, '参考答案 · 对照核心逻辑，不必逐字一致'), el('p', {}, review.answer)), el('p', { class: 'helper' }, isDue ? '根据这次独立回忆的表现评分。回答和评分都会保存，下次复习时间由算法调整。' : '本次是提前练习：不会延长原来的复习计划；如果忘记，10 分钟后再练。'), el('div', { class: 'rating-grid' }, [['again', '还没想起', '尽快再练'], ['hard', '有些吃力', isDue ? '缩短间隔' : '保留原计划'], ['good', '基本掌握', isDue ? '正常间隔' : '保留原计划'], ['easy', '轻松解释', isDue ? '延长间隔' : '保留原计划']].map(([rating, label, hint]) => el('button', { type: 'button', class: `rating ${rating}`, disabled: busy, on: { click: () => {
        const response = String(drafts.get(key) || '').trim();
        if (!response) { toast('请先填写这次的回答。', true); return; }
        mutate(`/api/reviews/${encodeURIComponent(review.id)}/answer`, { rating, response }, '回答已保存，下次复习时间已更新。', () => { drafts.delete(key); revealedReviews.delete(review.id); selectedReview = null; });
      } } }, label, el('small', {}, hint)))));
    }
    card.append(el('p', { class: 'review-caption' }, `原计划：${formatDate(review.due_at, true)} · 已复习 ${review.repetitions || 0} 次 · 当前间隔 ${intervalText(review.interval_days)}`));
    const side = el('aside', { class: 'panel review-list' }, el('h3', {}, `复习队列 · ${due.length} 题到期`), reviews.slice(0, 7).map(r => el('div', { class: 'queue-item' }, el('strong', {}, r.track_title), el('span', {}, r.question.length > 52 ? `${r.question.slice(0, 52)}…` : r.question), el('div', { class: 'helper' }, `${formatDate(r.due_at, true)} · ${new Date(r.due_at).getTime() <= Date.now() ? '到期' : '待复习'}`), r.id !== review.id ? button('切换此题', () => { selectedReview = r.id; render(); }, 'small ghost') : tag('当前问题'))), el('p', { class: 'review-caption' }, '一次完成几题即可。优先回忆原理、判断依据和使用边界。'));
    page.append(el('div', { class: 'review-layout' }, card, side));
    return page;
  }

  function renderSettings() {
    const settings = state.settings || {};
    const page = el('div', {}, heading('SETTINGS · 学习节奏', '让机制适应你的生活。', '从能长期坚持的节奏开始。每日预算是安排依据，提醒是否运行会单独标明。'));
    const getDraft = (name, fallback) => drafts.has(`settings:${name}`) ? drafts.get(`settings:${name}`) : fallback;
    function field(label, name, type, value, hint, min, max) {
      return el('div', { class: 'field' }, el('label', { for: `setting-${name}` }, label), el('div', { class: 'unit-input' }, el('input', { id: `setting-${name}`, type, min, max, required: true, value: getDraft(name, value), on: { input: event => drafts.set(`settings:${name}`, event.target.value) } }), type === 'number' ? el('span', {}, '分钟 / 天') : null), el('div', { class: 'helper' }, hint));
    }
    const rhythm = el('form', { class: 'panel', on: { submit: event => {
      event.preventDefault();
      const daily = Number(getDraft('daily_minutes', settings.daily_minutes || 30));
      const review = Number(getDraft('review_minutes', settings.review_minutes || 5));
      const reminder = getDraft('reminder_time', settings.reminder_time || '20:00');
      if (!Number.isInteger(daily) || !Number.isInteger(review) || daily < 5 || daily > 180 || review < 1 || review > 60) { toast('请填写合理的每日时长：学习 5–180 分钟，复习 1–60 分钟。', true); return; }
      mutate('/api/settings', { daily_minutes: daily, review_minutes: review, reminder_time: reminder }, '本地学习偏好已保存。提醒运行状态请查看“自动化与提醒”。', () => ['daily_minutes', 'review_minutes', 'reminder_time'].forEach(name => drafts.delete(`settings:${name}`)));
    } } }, el('h2', {}, '每天留一点时间'), el('p', {}, '一条主线持续推进，比同时打开很多课程更容易产生成果。'), field('学习预算', 'daily_minutes', 'number', settings.daily_minutes || 30, '用于今日学习安排，不代表已投入或已完成的时间。', 5, 180), field('复习预算', 'review_minutes', 'number', settings.review_minutes || 5, '建议留 3–5 分钟，优先处理已经到期的问题。', 1, 60), field('偏好的提醒时间', 'reminder_time', 'time', settings.reminder_time || '20:00', '保存本地偏好；实际定时任务需要同步配置。'), el('div', { class: 'detail-row' }, el('span', {}, '时区'), el('strong', {}, settings.timezone || 'Asia/Shanghai')), el('div', { class: 'action-row' }, el('button', { type: 'submit', class: 'button primary', disabled: busy }, '保存学习偏好')));
    const operation = el('div', {}, el('section', { class: 'panel' }, el('h2', {}, '自动化与提醒'), el('p', {}, '网页关闭后，浏览器本身不会持续执行发现或发送提醒。'), el('div', { class: 'detail-row' }, el('span', {}, '定时自动化'), el('strong', {}, settings.automation_enabled ? '已配置 · 以调度器实际执行为准' : '尚未启用')), el('div', { class: 'detail-row' }, el('span', {}, '发现筛选门槛'), el('strong', {}, `至少 ${stars(settings.min_stars || 100000)} Star`)), el('div', { class: 'detail-row' }, el('span', {}, '候选项目上限'), el('strong', {}, `${settings.discovery_limit || 20} 个`)), el('div', { class: 'detail-row' }, el('span', {}, '同时推进主线'), el('strong', {}, `${settings.max_active_tracks || 1} 条`)), el('div', { class: 'action-row' }, button('复制学习助手指令', copyInstruction, 'outline')), el('div', { class: 'assistant-instruction' }, assistantPrompt), el('p', { class: 'helper' }, '教学内容准备需要学习助手执行。这里不会把排队任务显示为已完成课程。')), el('section', { class: 'panel', style: 'margin-top:20px' }, el('h2', {}, '你的学习记录'), el('p', {}, '导出包含偏好、主线、实践记录和复习数据的 JSON 文件，用于备份。'), el('div', { class: 'action-row' }, el('a', { href: '/api/export', class: 'button outline', download: 'learning-loop-backup.json' }, icon('download', 15), '导出全部记录'), button('重新读取状态', reloadState, 'ghost', 'loop'))));
    if (settings.schedule_sync_pending) operation.prepend(info('提醒偏好已改变：待学习助手同步定时任务。在同步完成前，调度仍可能使用原先的时间。', 'warning'));
    operation.append(el('section', { class: 'panel', style: 'margin-top:20px' }, el('h2', {}, '手机学习版'), el('p', {}, '独立的随身课堂，支持离线课程、实践记录和主动回忆。手机端记录留在它自己的浏览器中，不与本机数据库自动同步。'), el('div', { class: 'action-row' }, el('a', { href: '/mobile/', class: 'button outline', target: '_blank', rel: 'noopener' }, '打开手机学习版 ↗')), el('p', { class: 'helper' }, '此处是本机预览。公开部署为 HTTPS 站点后，手机才能通过远程网址访问；127.0.0.1 不是手机可用的公网地址。')));
    const knownTopics = state.known_topics || [];
    operation.append(el('section', { class: 'panel', style: 'margin-top:20px' }, el('h2', {}, '已有基础的方向'), el('p', {}, '这些记录来自你的自述，只影响推荐筛选，不计为验收掌握。可以随时撤销。'), knownTopics.length ? knownTopics.map(topic => el('div', { class: 'detail-row' }, el('span', {}, topic.topic_name || topic.topic_id), button('重新加入推荐', () => mutate('/api/topics/unknown', { topic_id: topic.topic_id }, '已撤销该方向的排除，符合条件的项目会重新出现在推荐中。'), 'small ghost'))) : el('p', { class: 'helper' }, '还没有主动排除的方向。')));
    page.append(el('div', { class: 'settings-grid' }, rhythm, operation));
    return page;
  }

  async function reloadState() {
    if (busy) return;
    busy = true; if (state) render();
    try { state = await api('/api/state'); toast('已读取最新学习状态。'); }
    catch (error) { toast(error.message, true); }
    finally { busy = false; if (state) render(); }
  }
  async function init() {
    try { state = await api('/api/state'); render(); }
    catch (error) { root.setAttribute('aria-busy', 'false'); root.replaceChildren(el('main', { class: 'main' }, heading('LEARNING LOOP · 知行', '学习空间暂时无法连接。', '请确认本地服务已经启动，再重新加载。'), info(error.message, 'error'), button('重新连接', init, 'primary', 'loop', false))); }
  }
  window.addEventListener('hashchange', () => { const next = location.hash.slice(1); if (Object.hasOwn(viewNames, next) && next !== view) { view = next; render(); } });
  init();
})();
