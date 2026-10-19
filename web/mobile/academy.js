'use strict';

// Presentation metadata only. Course/question identities and learner state stay
// in the existing catalog and LearningState. A new course gets a neutral cover.
(function (target) {
  const realms = {
    'gaussian-splatting': { name: '光影塔', art: 'brush', color: 'violet', x: 21, y: 42, title: '把照片里的世界，重新点亮', question: '一堆柔软的光斑，怎么变成可以转头看的场景？', action: '转一转高斯场景', outcome: '比较视角，解释光斑如何一起成像。' },
    'bayesian-reasoning': { name: '观星台', art: 'bayes', color: 'blue', x: 55, y: 37, title: '一条新线索，值得相信多少', question: '检测报警了，就一定有问题吗？', action: '改变比例，重新判断', outcome: '数清两路报警，找到正确的分母。' },
    'text-to-speech-workflows': { name: '回声花园', art: 'voice', color: 'rose', x: 82, y: 55, title: '让一句话，有自己的呼吸', question: '同一句话，只改标点，听起来会有什么不同？', action: '听一组声音对照', outcome: '比较停顿，记录实际听到的差别。' },
    'capacitor-decoupling': { name: '星灯工坊', art: 'capacitor', color: 'amber', x: 31, y: 85, title: '守住芯片身边的那盏灯', question: '芯片突然多要电流，电容能撑多久？', action: '启动供电接力实验', outcome: '调整电容量，观察电压下降与回充。' },
    'mosfet-switching': { name: '机关庭院', art: 'mosfet', color: 'mint', x: 65, y: 87, title: '用一个小信号，打开大机关', question: '小小的控制引脚，怎样让大负载工作？', action: '试一试开关与 PWM', outcome: '调整开关节拍，分清瞬时电流与平均功率。' },
  };
  function realm(course) {
    return Object.prototype.hasOwnProperty.call(realms, course.topic_id) ? realms[course.topic_id] : {
      name: '探索书库', art: 'guide', color: 'mint', title: course.title,
      question: course.lesson.visual_lesson?.hook || course.lesson.summary,
      action: '进入本课实验', outcome: '改变一个条件，留下自己的观察。',
    };
  }
  function nextChapter(progress) {
    return !progress.experiment ? 'experiment' : !progress.application ? 'application' : !progress.summary ? 'summary' : 'logic';
  }
  const api = { realm, nextChapter };
  if (typeof module === 'object' && module.exports) module.exports = api;
  else target.LearningAcademy = api;
})(typeof window === 'object' ? window : globalThis);
