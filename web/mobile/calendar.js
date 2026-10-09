/* A user-imported calendar reminder also works when this web app is closed. */
(function (root) {
  'use strict';
  function escapeText(value) {
    return String(value).replace(/\\/g, '\\\\').replace(/\r?\n/g, '\\n').replace(/,/g, '\\,').replace(/;/g, '\\;');
  }
  function formatLocal(date) {
    const pad = value => String(value).padStart(2, '0');
    return `${date.getFullYear()}${pad(date.getMonth()+1)}${pad(date.getDate())}T${pad(date.getHours())}${pad(date.getMinutes())}00`;
  }
  function fold(line) {
    const encoder = new TextEncoder();
    let output = '', length = 0;
    for (const character of line) {
      const bytes = encoder.encode(character).length;
      if (length + bytes > 75) { output += '\r\n '; length = 1; }
      output += character;
      length += bytes;
    }
    return output;
  }
  function create({time = '20:00', minutes = 5, url = '', now = new Date()} = {}) {
    if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(time)) throw new Error('提醒时间应为 HH:MM');
    if (!Number.isInteger(minutes) || minutes < 1 || minutes > 120) throw new Error('复习时长需要在1到120分钟');
    const start = new Date(now);
    const [hours, mins] = time.split(':').map(Number);
    start.setHours(hours, mins, 0, 0);
    if (start <= now) start.setDate(start.getDate()+1);
    const stamp = now.toISOString().replace(/[-:]/g, '').replace(/\.\d{3}Z$/, 'Z');
    const description = '打开学习循环，先回忆再看答案。今天是否有到期复习以 App 为准。' + (url ? '\n' + url : '');
    return [
      'BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Learning Loop//Review Reminder//ZH',
      'CALSCALE:GREGORIAN', 'METHOD:PUBLISH', 'BEGIN:VEVENT',
      // Stable UID helps calendar applications recognize a repeated import.
      'UID:daily-review@learning-loop.local', `DTSTAMP:${stamp}`,
      `DTSTART:${formatLocal(start)}`, `DURATION:PT${minutes}M`,
      'RRULE:FREQ=DAILY', 'SUMMARY:学习循环 · 回忆复习',
      `DESCRIPTION:${escapeText(description)}`, 'BEGIN:VALARM', 'TRIGGER:PT0M',
      'ACTION:DISPLAY', 'DESCRIPTION:花几分钟回忆之前学过的核心思路',
      'END:VALARM', 'END:VEVENT', 'END:VCALENDAR', ''
    ].map(fold).join('\r\n');
  }
  function download(options = {}) {
    const current = new URL(root.location.href);
    current.hash = 'review';
    const text = create({...options, url: current.href});
    const objectUrl = URL.createObjectURL(new Blob([text], {type:'text/calendar;charset=utf-8'}));
    const anchor = document.createElement('a');
    anchor.href = objectUrl;
    anchor.download = 'learning-loop-review.ics';
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
  }
  const api = {create, download};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.LearningCalendar = api;
})(typeof window !== 'undefined' ? window : globalThis);
