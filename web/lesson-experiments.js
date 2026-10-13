'use strict';

// Built-in teaching experiments never write learning records or call a model.
(function (target) {
  const count = value => new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 }).format(value);
  function bayesCounts(prior, detection, falseAlarm) {
    for (const n of [prior, detection, falseAlarm]) if (!Number.isFinite(n) || n < 0 || n > 100) throw new Error('比例应在 0 到 100 之间');
    const bad = 10000 * prior / 100, good = 10000 - bad;
    const hit = bad * detection / 100, missed = bad - hit, falseHit = good * falseAlarm / 100, correct = good - falseHit;
    const alarm = hit + falseHit;
    return { bad, good, cells: [hit, missed, falseHit, correct], alarm, posterior: alarm > 0 ? hit / alarm * 100 : null };
  }
  function gradeCells(raw, result) {
    const prompts = [
      `先从 ${count(result.bad)} 件坏件出发，乘坏件检出率。`,
      `这格和“坏件报警”加起来，应等于 ${count(result.bad)} 件坏件。`,
      `这一支从 ${count(result.good)} 件正常件出发，乘正常件误报率。别把误报率乘在坏件上。`,
      `这格和“正常件报警”加起来，应等于 ${count(result.good)} 件正常件。`,
    ];
    return result.cells.map((expected, i) => {
      const blank = raw[i] === undefined || raw[i] === null || String(raw[i]).trim() === '';
      const n = Number(raw[i]);
      if (blank || !Number.isFinite(n) || n < 0) return { ok: false, hint: `请填一个非负件数。${prompts[i]}` };
      if (Math.abs(n - expected) < 0.011) return { ok: true, hint: '这一格吻合。' };
      return { ok: false, hint: prompts[i] };
    });
  }
  function gradePosterior(rawDenominator, rawPercent, result) {
    if (String(rawDenominator).trim() === '') return { ok: false, hint: '先填分母：题目问的是所有报警件里的坏件比例。' };
    const n = Number(rawDenominator);
    if (!Number.isFinite(n) || Math.abs(n - result.alarm) > .011) {
      return { ok: false, hint: n === 10000 ? '一万件是原来的总体；看到报警以后，要缩小到所有报警件。' : n === result.bad ? '坏件总数回答的是另一方向的问题；这里要把两路报警相加。' : '把“坏件报警”和“正常件报警”相加，不包含未报警的两格。' };
    }
    if (result.posterior === null) return { ok: false, hint: '这个设定下没有报警件，分母为 0，不能定义报警后的比例。' };
    if (String(rawPercent).trim() === '' || !Number.isFinite(Number(rawPercent)) || Math.abs(Number(rawPercent) - result.posterior) > .11) return { ok: false, hint: '分母选对了。现在用坏件报警数 ÷ 所有报警数 × 100，百分数保留一位小数。' };
    return { ok: true, hint: `算得吻合：${count(result.cells[0])} ÷ ${count(result.alarm)} ≈ ${result.posterior.toFixed(1)}%。试着解释为什么分母包含正常件。` };
  }

  function create({ el, button, onCleanup, assetBase = null }) {
    const text = value => el('p', { class: 'practice-note' }, value);
    function bayes(config) {
      let prior = 1, detection = 90, falseAlarm = 5, result = bayesCounts(prior, detection, falseAlarm);
      const view = el('section', { class: 'practice-card', 'aria-label': config.title }, el('span', { class: 'practice-eyebrow' }, '手机小实验 · 约 3 分钟'), el('h3', {}, config.title), text(config.prompt), text('合成案例：每批 10,000 件，下面的比例是教学假设。先预测，再填四格；所有尝试只留在当前页面。'));
      const conditions = el('div', { class: 'practice-conditions' });
      const fields = [], hints = [];
      const totals = el('p', { class: 'practice-population' });
      const feedback = el('p', { class: 'practice-feedback', role: 'status' });
      const resultPanel = el('div', { class: 'practice-result', hidden: true });
      const denominator = el('input', { type: 'number', min: '0', step: 'any', inputmode: 'decimal', 'aria-label': '所有报警件数，分母', placeholder: '所有报警件数' });
      const percent = el('input', { type: 'number', min: '0', max: '100', step: 'any', inputmode: 'decimal', 'aria-label': '报警后坏件比例百分数', placeholder: '保留一位小数' });
      const finalFeedback = el('p', { class: 'practice-feedback', role: 'status' });
      function clearAnswers() {
        result = bayesCounts(prior, detection, falseAlarm);
        totals.textContent = `起点：坏件 ${count(result.bad)} 件；正常件 ${count(result.good)} 件。`;
        fields.forEach(field => { field.value = ''; field.removeAttribute('aria-invalid'); });
        hints.forEach(hint => { hint.textContent = ''; });
        denominator.value = ''; percent.value = ''; feedback.textContent = ''; finalFeedback.textContent = ''; resultPanel.hidden = true;
      }
      for (const [label, initial, min, max, change] of [
        ['坏件率', prior, 0, 100, n => { prior = n; }],
        ['坏件检出率', detection, 0, 100, n => { detection = n; }],
        ['正常件误报率', falseAlarm, 0, 100, n => { falseAlarm = n; }],
      ]) {
        const output = el('output', {}, `${initial}%`);
        const range = el('input', { type: 'range', min, max, step: '1', value: initial, 'aria-label': label, on: { input: event => { const n = Number(event.target.value); change(n); output.textContent = `${n}%`; clearAnswers(); } } });
        conditions.append(el('label', {}, el('span', {}, label, output), range));
      }
      view.append(conditions, text('改变参数会清空本页计算，方便重新预测；不会改动已保存的学习记录。'), el('label', { class: 'practice-prediction' }, '先猜：只提高坏件率，报警后坏件比例会怎样？', el('textarea', { rows: '2', maxlength: '500', placeholder: '先用自己的话说个方向；暂时不知道也可以。' })), totals);
      const table = el('table', { class: 'practice-counts' }, el('caption', {}, '第一步：把同一批产品分成四种情况'), el('thead', {}, el('tr', {}, el('th', { scope: 'col' }, '真实状态'), el('th', { scope: 'col' }, '报警'), el('th', { scope: 'col' }, '未报警'))));
      const tbody = el('tbody');
      ['坏件 ×', '正常件 ○'].forEach((rowLabel, row) => {
        const tr = el('tr', { class: row ? 'practice-good' : 'practice-bad' }, el('th', { scope: 'row' }, rowLabel));
        for (let col = 0; col < 2; col++) {
          const hintID = `bayes-cell-hint-${row}-${col}`;
          const field = el('input', { type: 'number', min: '0', step: 'any', inputmode: 'decimal', 'aria-label': `${rowLabel} · ${col ? '未报警' : '报警'}件数`, 'aria-describedby': hintID, placeholder: '件数' });
          const hint = el('span', { id: hintID, class: 'practice-cell-hint' });
          fields.push(field); hints.push(hint); tr.append(el('td', {}, field, hint));
        }
        tbody.append(tr);
      });
      table.append(tbody);
      function showResult() {
        const p = result.posterior;
        const bar = el('div', { class: 'practice-alarm-bar', role: 'img', 'aria-label': p === null ? '没有报警件，比例未定义' : `报警池共 ${count(result.alarm)} 件，坏件占 ${p.toFixed(1)}%，正常件占 ${(100-p).toFixed(1)}%` });
        if (p !== null) bar.append(el('span', { class: 'bad-share', style: `width:${p}%` }), el('span', { class: 'good-share', style: `width:${100-p}%` }));
        resultPanel.replaceChildren(el('h4', {}, '只把两路报警汇在一起'), bar, text(`× 坏件报警 ${count(result.cells[0])} 件 ＋ ○ 正常件报警 ${count(result.cells[2])} 件 ＝ ${count(result.alarm)} 件报警。`), text(p === null ? '没有报警，无法计算“报警后”的条件比例。' : `条形长度按件数比例绘制。坏件占报警池的 ${p.toFixed(1)}%；这与检出率 ${detection}% 回答的问题不同。`));
        resultPanel.hidden = false;
      }
      view.append(table, button('检查四格', () => {
        const grades = gradeCells(fields.map(field => field.value), result);
        grades.forEach((grade, i) => { hints[i].textContent = grade.hint; fields[i].setAttribute('aria-invalid', String(!grade.ok)); });
        feedback.textContent = grades.every(grade => grade.ok) ? '四格都吻合。接下来自己选分母。' : '先修正提示对应的那一格，再检查。';
      }, 'outline'), feedback);
      view.append(el('h4', {}, '第二步：我应该在谁里面数比例？'), el('div', { class: 'practice-ratio' }, el('label', {}, '分母：所有报警件数', denominator), el('label', {}, '坏件占这些报警的百分数', percent)), button('检查分母和比例', () => { const grade = gradePosterior(denominator.value, percent.value, result); finalFeedback.textContent = grade.hint; if (grade.ok || result.alarm === 0 && Number(denominator.value) === 0 && denominator.value !== '') showResult(); }, 'outline'), finalFeedback,
        button('看两条路径的推导', () => {
          feedback.textContent = `坏件：${count(result.bad)} × ${detection}% = ${count(result.cells[0])} 报警，剩下 ${count(result.cells[1])} 未报警；正常件：${count(result.good)} × ${falseAlarm}% = ${count(result.cells[2])} 报警，剩下 ${count(result.cells[3])} 未报警。`;
          showResult();
        }, 'ghost'), resultPanel, text('再试一轮：只把坏件率从 1% 改为 10%，其余不变。先猜方向，再核对。把自己的过程写到下方“记录你的实验”并保存；这里不会自动判定掌握。'));
      clearAnswers(); return view;
    }

    function voice(config) {
      const view = el('section', { class: 'practice-card', 'aria-label': config.title }, el('span', { class: 'practice-eyebrow' }, '手机听辨 · 约 3 分钟'), el('h3', {}, config.title), text(config.prompt), text('原创合成样例：同一晓晓女声、同一语速与字词，只改标点；不是 VoiceStudio 模型输出。'));
      const phrases = ['开头 / 中段 / 结尾', '没有漏句之后', '如果发现问题之后', '段落 / 重新生成'];
      const selected = new Set();
      const prediction = el('div', { class: 'practice-phrase-choices', role: 'group', 'aria-label': '选择你预测停顿会变化的位置' });
      for (const phrase of phrases) {
        const node = button(phrase, () => { if (selected.has(phrase)) selected.delete(phrase); else selected.add(phrase); node.setAttribute('aria-pressed', String(selected.has(phrase))); }, 'outline');
        node.setAttribute('aria-pressed', 'false'); prediction.append(node);
      }
      view.append(el('h4', {}, '先预测：哪里可能更容易听出停顿？'), prediction);
      const players = [];
      for (const sample of config.samples || []) {
        let src;
        try {
          if (!/^\/media\/[A-Za-z0-9_./-]+\.(mp3|m4a|wav)$/.test(sample.src) || sample.src.split('/').includes('..')) continue;
          const base = assetBase ? new URL('.', assetBase) : new URL('/', location.href);
          const url = new URL(sample.src.slice(1), base);
          if (url.origin !== location.origin || !url.pathname.startsWith(`${base.pathname}media/`)) continue;
          src = url.href;
        } catch { continue; }
        const audio = el('audio', { controls: true, preload: 'metadata', src, 'aria-label': sample.label });
        const status = el('p', { class: 'practice-feedback', role: 'status' });
        const stopOthers = () => { for (const other of document.querySelectorAll('audio,video')) if (other !== audio) other.pause(); };
        const failed = () => { status.textContent = '这一段暂时无法播放，请点重听重新加载。文字样例仍可阅读。'; };
        audio.addEventListener('play', stopOthers); audio.addEventListener('error', failed); players.push(audio);
        view.append(el('div', { class: 'practice-sample' }, el('h4', {}, sample.label), text(sample.transcript), audio,
          button('重听这一段', () => { status.textContent = ''; if (audio.error) audio.load(); try { audio.currentTime = 0; audio.play()?.catch(() => { status.textContent = '请点击音频的播放键。'; }); } catch { failed(); } }, 'small outline'), status));
        onCleanup(() => { audio.removeEventListener('play', stopOthers); audio.removeEventListener('error', failed); audio.pause(); audio.removeAttribute('src'); audio.load(); });
      }
      view.append(el('label', { class: 'practice-prediction' }, '听后对照：预测在哪里吻合，哪里没有听出差别？', el('textarea', { rows: '3', maxlength: '1000', placeholder: '可以写“没有听出明显差别”，不预设实验一定成功。' })),
        text('此处预测和观察只留在本页。把你实际听到的差别、建议的分句和不确定之处填到下方并保存。一次对照不能推出所有引擎都会同样变化。'));
      return view;
    }
    return { render: config => config?.kind === 'bayes-counts' ? bayes(config) : config?.kind === 'voice-ab' ? voice(config) : document.createDocumentFragment() };
  }
  const api = { bayesCounts, gradeCells, gradePosterior, create };
  if (typeof module === 'object' && module.exports) module.exports = api;
  else target.LessonExperiments = api;
})(typeof window === 'object' ? window : globalThis);
