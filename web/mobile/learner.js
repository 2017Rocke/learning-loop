'use strict';

// Pure learning state and scheduling rules, shared by the PWA and its Node checks.
(function (target) {
  const DAY = 86400000;
  const RATINGS = ['again', 'hard', 'good', 'easy'];
  const EVIDENCE_KINDS = ['experiment', 'application', 'summary'];
  const MAX_RECORDS = 10000;
  const INTERVALS = [1, 3, 7, 14, 30, 60];
  function fail(message) { throw new Error(message); }
  function isObject(value) { return value !== null && typeof value === 'object' && !Array.isArray(value) && Object.getPrototypeOf(value) === Object.prototype; }
  function shape(value, keys, label) {
    if (!isObject(value) || Object.keys(value).some(key => !keys.includes(key)) || keys.some(key => !Object.hasOwn(value, key))) fail(`${label}格式不正确。`);
  }
  function string(value, max, label, allowEmpty = false) { if (typeof value !== 'string' || value.length > max || (!allowEmpty && !value.trim()) || value.includes('\u0000')) fail(`${label}必须是有效文字。`); }
  function id(value, label = '标识') { string(value, 200, label); if (!/^[a-zA-Z0-9._:/-]+$/.test(value)) fail(`${label}格式不正确。`); }
  function stableID(value, label, max = 400) { string(value, max, label); if (/[\u0000-\u001f\u007f-\u009f]/.test(value)) fail(`${label}不能含控制字符。`); }
  function time(value, label) { if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}T/.test(value) || !Number.isFinite(Date.parse(value))) fail(`${label}日期不正确。`); }
  function integer(value, min, max, label) { if (!Number.isInteger(value) || value < min || value > max) fail(`${label}超出允许范围。`); }
  function finite(value, min, max, label) { if (!Number.isFinite(value) || value < min || value > max) fail(`${label}超出允许范围。`); }
  function iso(value) { return new Date(value).toISOString(); }
  function clone(value) { return JSON.parse(JSON.stringify(value)); }
  function unique(records, key, label) { const values = records.map(record => record[key]); if (new Set(values).size !== values.length) fail(`${label}含重复记录。`); }
  function questions(course) { return Array.isArray(course?.lesson?.questions) ? course.lesson.questions : []; }
  function reviewID(courseID, questionID) { return `${encodeURIComponent(courseID)}::${encodeURIComponent(questionID)}`; }
  function fresh(now = Date.now()) {
    return { schema_version: 1, settings: { daily_minutes: 20, review_minutes: 5 }, enrollments: [], evidence: [], reviews: [], review_history: [], updated_at: iso(now) };
  }
  function validateState(input, courses) {
    shape(input, ['schema_version', 'settings', 'enrollments', 'evidence', 'reviews', 'review_history', 'updated_at'], '学习备份');
    if (input.schema_version !== 1) fail('此备份版本暂不支持。');
    shape(input.settings, ['daily_minutes', 'review_minutes'], '学习偏好');
    integer(input.settings.daily_minutes, 5, 180, '学习分钟数'); integer(input.settings.review_minutes, 1, 60, '复习分钟数');
    time(input.updated_at, '更新时间');
    for (const key of ['enrollments', 'evidence', 'reviews', 'review_history']) if (!Array.isArray(input[key]) || input[key].length > MAX_RECORDS) fail(`${key}记录数量异常。`);
    const catalog = new Map(courses.map(course => [course.id, course]));
    const checkCourse = value => { stableID(value, '课程标识'); if (!catalog.has(value)) fail('备份中有当前课程包尚未收录的课程，请先更新课程包。'); return catalog.get(value); };
    const enrolled = new Set();
    for (const record of input.enrollments) {
      shape(record, ['course_id', 'started_at'], '已选课程'); checkCourse(record.course_id); time(record.started_at, '开始日期'); enrolled.add(record.course_id);
    }
    unique(input.enrollments, 'course_id', '已选课程');
    const isEnrolled = courseID => { if (!enrolled.has(courseID)) fail('学习记录缺少对应的已选课程。'); };
    for (const record of input.evidence) {
      shape(record, ['id', 'course_id', 'kind', 'text', 'created_at'], '实践记录'); id(record.id); checkCourse(record.course_id); isEnrolled(record.course_id);
      if (!EVIDENCE_KINDS.includes(record.kind)) fail('实践记录类型不正确。'); string(record.text, 20000, '实践记录'); time(record.created_at, '记录日期');
    }
    unique(input.evidence, 'id', '实践记录');
    const reviewMap = new Map();
    for (const record of input.reviews) {
      shape(record, ['id', 'course_id', 'question_id', 'due_at', 'interval_days', 'ease', 'repetitions', 'last_review_at'], '复习计划');
      stableID(record.id, '复习标识', 8000); stableID(record.question_id, '问题标识'); const course = checkCourse(record.course_id); isEnrolled(record.course_id);
      if (!questions(course).some(q => q.id === record.question_id) || record.id !== reviewID(record.course_id, record.question_id)) fail('复习题与当前课程不匹配。');
      time(record.due_at, '复习日期'); if (record.last_review_at !== null) time(record.last_review_at, '最近复习日期');
      finite(record.interval_days, 0, 3650, '复习间隔'); finite(record.ease, 1.3, 3, '复习系数'); integer(record.repetitions, 0, 100000, '复习次数');
      reviewMap.set(record.id, record);
    }
    unique(input.reviews, 'id', '复习计划');
    for (const record of input.review_history) {
      shape(record, ['id', 'review_id', 'course_id', 'response', 'rating', 'answered_at'], '复习回答');
      id(record.id); stableID(record.review_id, '复习标识', 8000); checkCourse(record.course_id); const plan = reviewMap.get(record.review_id);
      if (!plan || plan.course_id !== record.course_id) fail('复习回答缺少对应的问题。');
      string(record.response, 20000, '复习回答'); if (!RATINGS.includes(record.rating)) fail('复习评分不正确。'); time(record.answered_at, '回答日期');
    }
    unique(input.review_history, 'id', '复习回答');
    return clone(input);
  }
  function enroll(state, course, now = Date.now()) {
    const next = clone(state);
    if (!next.enrollments.some(item => item.course_id === course.id)) next.enrollments.push({ course_id: course.id, started_at: iso(now) });
    next.updated_at = iso(now); return next;
  }
  function addEvidence(state, course, kind, text, recordID, now = Date.now()) {
    if (!EVIDENCE_KINDS.includes(kind)) fail('记录类型不正确。'); string(text, 20000, '实践记录'); id(recordID);
    const next = enroll(state, course, now);
    if (next.evidence.some(item => item.id === recordID)) fail('记录标识重复。');
    if (next.evidence.length >= MAX_RECORDS) fail('记录已达上限，请先导出备份。');
    next.evidence.push({ id: recordID, course_id: course.id, kind, text: text.trim(), created_at: iso(now) });
    for (const q of questions(course)) if (!next.reviews.some(item => item.id === reviewID(course.id, q.id))) next.reviews.push({ id: reviewID(course.id, q.id), course_id: course.id, question_id: q.id, due_at: iso(now + DAY), interval_days: 1, ease: 2.5, repetitions: 0, last_review_at: null });
    return next;
  }
  function scheduleReview(previous, rating, now = Date.now()) {
    if (!RATINGS.includes(rating)) fail('复习评分不正确。');
    const next = clone(previous); const due = now >= Date.parse(previous.due_at);
    next.last_review_at = iso(now);
    if (rating === 'again') { next.interval_days = 10 / 1440; next.due_at = iso(now + 600000); next.repetitions = 0; return next; }
    // Practicing early does not repeatedly inflate the schedule or the ease factor.
    if (!due) return next;
    if (rating === 'hard') next.interval_days = Math.max(1, Math.min(previous.interval_days * 1.2, 3));
    else { next.repetitions = Math.min(previous.repetitions + (rating === 'easy' ? 2 : 1), INTERVALS.length - 1); next.interval_days = INTERVALS[next.repetitions]; }
    next.due_at = iso(now + next.interval_days * DAY); return next;
  }
  function answerReview(state, reviewIDValue, response, rating, recordID, now = Date.now()) {
    string(response, 20000, '你的回答'); id(recordID);
    const next = clone(state); const index = next.reviews.findIndex(item => item.id === reviewIDValue);
    if (index < 0) fail('这道复习题不存在。');
    if (next.review_history.some(item => item.id === recordID)) fail('回答标识重复。');
    const latest = next.review_history.filter(item => item.review_id === reviewIDValue).sort((a, b) => Date.parse(b.answered_at) - Date.parse(a.answered_at))[0];
    if (latest && now - Date.parse(latest.answered_at) < 60000) fail('这次回答已记录，请稍后再练，避免重复点击改变计划。');
    if (next.review_history.length >= MAX_RECORDS) fail('复习回答已达上限，请先导出备份。');
    next.reviews[index] = scheduleReview(next.reviews[index], rating, now);
    next.review_history.push({ id: recordID, review_id: reviewIDValue, course_id: next.reviews[index].course_id, response: response.trim(), rating, answered_at: iso(now) });
    next.updated_at = iso(now); return next;
  }
  function due(state, now = Date.now()) { return state.reviews.filter(item => Date.parse(item.due_at) <= now).sort((a, b) => Date.parse(a.due_at) - Date.parse(b.due_at)); }
  function progress(state, courseID) { const records = state.evidence.filter(item => item.course_id === courseID); return { experiment: records.some(item => item.kind === 'experiment'), application: records.some(item => item.kind === 'application'), summary: records.some(item => item.kind === 'summary'), count: records.length }; }
  function importBackup(text, courses) {
    if (typeof text !== 'string' || text.length > 10000000) fail('备份过大，请使用 10 MB 以内的知行手机端 JSON 备份。');
    let parsed; try { parsed = JSON.parse(text); } catch { fail('无法读取 JSON，请选择从知行手机端导出的备份。'); }
    return validateState(parsed, courses);
  }
  const api = { fresh, validateState, enroll, addEvidence, scheduleReview, answerReview, due, progress, importBackup, reviewID };
  if (typeof module === 'object' && module.exports) module.exports = api;
  else target.LearningState = api;
})(typeof window === 'object' ? window : globalThis);
