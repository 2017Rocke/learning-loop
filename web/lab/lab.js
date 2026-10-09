'use strict';

// Keep the standalone lab useful while removing duplicate navigation in a lesson.
const embedded = new URLSearchParams(location.search).get('embedded') === '1' && window.parent !== window;
if (embedded) {
  document.body.classList.add('embedded');
  document.querySelector('.record h2').textContent = '留下一条观察，再在下方记录实验。';
  document.querySelector('.record-description').textContent = '模板会带上此刻的真实参数与误差。补充预测、原因和反例，再填入课程的实验记录。';
}

// A screen-space teaching model only: no 3D camera, reconstruction or training.
const WIDTH = 144;
const HEIGHT = 100;
const BACKGROUND = [0.95, 0.96, 0.99];
const RED = [0.95, 0.21, 0.16];
const BLUE = [0.12, 0.40, 0.95];
const TARGET = Object.freeze({ x: 0.43, scale: 1, opacity: 0.82, reverse: false });
const INITIAL = Object.freeze({ x: 0.65, scale: 1.2, opacity: 0.6, reverse: false });
const controls = {
  x: document.getElementById('position'),
  scale: document.getElementById('scale'),
  opacity: document.getElementById('opacity'),
  order: document.getElementById('order')
};
let state = { ...INITIAL };
let currentError = 0;
let userChanges = 0;
let hintCount = 0;
let renderPending = false;

function gaussian(x, y, cx, cy, sx, sy, opacity) {
  return opacity * Math.exp(-0.5 * (((x - cx) / sx) ** 2 + ((y - cy) / sy) ** 2));
}

function render(parameters) {
  const output = new Float64Array(WIDTH * HEIGHT * 3);
  for (let y = 0; y < HEIGHT; y++) {
    for (let x = 0; x < WIDTH; x++) {
      const px = (x + 0.5) / WIDTH;
      const py = (y + 0.5) / HEIGHT;
      const redAlpha = gaussian(px, py, parameters.x, 0.49,
        0.15 * parameters.scale, 0.20 * parameters.scale, parameters.opacity);
      const blueAlpha = gaussian(px, py, 0.57, 0.51, 0.17, 0.19, 0.82);
      const frontColor = parameters.reverse ? BLUE : RED;
      const backColor = parameters.reverse ? RED : BLUE;
      const frontAlpha = parameters.reverse ? blueAlpha : redAlpha;
      const backAlpha = parameters.reverse ? redAlpha : blueAlpha;
      const remaining = (1 - frontAlpha) * (1 - backAlpha);
      const offset = (y * WIDTH + x) * 3;
      for (let channel = 0; channel < 3; channel++) {
        output[offset + channel] = frontAlpha * frontColor[channel]
          + (1 - frontAlpha) * backAlpha * backColor[channel]
          + remaining * BACKGROUND[channel];
      }
    }
  }
  return output;
}

function mse(a, b) {
  let sum = 0;
  for (let index = 0; index < a.length; index++) sum += (a[index] - b[index]) ** 2;
  return sum / a.length;
}

function paint(canvas, pixels) {
  const buffer = document.createElement('canvas');
  buffer.width = WIDTH;
  buffer.height = HEIGHT;
  const context = buffer.getContext('2d');
  const image = context.createImageData(WIDTH, HEIGHT);
  for (let i = 0; i < WIDTH * HEIGHT; i++) {
    for (let channel = 0; channel < 3; channel++) {
      image.data[i * 4 + channel] = Math.round(255 * pixels[i * 3 + channel]);
    }
    image.data[i * 4 + 3] = 255;
  }
  context.putImageData(image, 0, 0);
  const display = canvas.getContext('2d');
  display.imageSmoothingEnabled = true;
  display.drawImage(buffer, 0, 0, canvas.width, canvas.height);
}

const targetPixels = render(TARGET);
const initialError = mse(render(INITIAL), targetPixels);

function observationTemplate() {
  const order = state.reverse ? '蓝色在前，红色在后' : '红色在前，蓝色在后';
  return [
    '高斯小实验 · 我的观察记录',
    '范围：二维高斯有序 alpha 合成，不是完整 3DGS 重建。',
    '',
    `当前参数：红色水平位置=${state.x.toFixed(2)}；尺度=${state.scale.toFixed(2)}；不透明度=${state.opacity.toFixed(2)}；${order}。`,
    `当前 RGB 均方误差=${currentError.toFixed(10)}；初始误差=${initialError.toFixed(10)}。`,
    '',
    '1. 调整前，我预测：［自己填写］',
    '2. 我单独改变了哪个参数，实际观察到什么：［自己填写］',
    '3. 我的数值证据，以及误差变化的原因：［自己填写］',
    '4. 为什么交换前后顺序会改变重叠颜色？什么情况下变化很小：［自己填写］',
    '5. 这个实验还缺哪些真实三维重建环节：［自己填写］',
    '6. 下一步我会怎样拍摄杯子或摆件来验证：［自己填写］',
    '',
    '我的一句话总结：［自己填写］'
  ].join('\n');
}

function updateTemplate() {
  document.getElementById('observation').value = observationTemplate();
}

function update() {
  const pixels = render(state);
  currentError = mse(pixels, targetPixels);
  paint(document.getElementById('current-canvas'), pixels);
  document.getElementById('position-value').value = state.x.toFixed(2);
  document.getElementById('scale-value').value = `${state.scale.toFixed(2)} ×`;
  document.getElementById('opacity-value').value = state.opacity.toFixed(2);
  document.getElementById('mse-value').textContent = currentError.toFixed(8);
  const note = document.getElementById('error-note');
  if (currentError < 1e-12) {
    note.textContent = '当前采样画面与目标一致。试着解释原因，再挑战一个反例。';
  } else if (currentError < 0.0001) {
    note.textContent = '画面已经很接近。还有哪些细节不同？';
  } else if (currentError < initialError) {
    note.textContent = '误差比初始值更低。保留证据，继续观察参数的影响。';
  } else {
    note.textContent = '越接近 0，画面越接近目标。一次只改一个参数更容易解释。';
  }
  document.getElementById('image-caption').textContent = state.reverse
    ? '现在蓝色在前。留意蓝色如何影响重叠区域。'
    : '现在红色在前。留意红色如何影响重叠区域。';
  updateTemplate();
}

function readControls() {
  state = {
    x: Number(controls.x.value), scale: Number(controls.scale.value),
    opacity: Number(controls.opacity.value), reverse: controls.order.value === 'blue-front'
  };
}

function scheduleUpdate() {
  readControls();
  userChanges += 1;
  document.getElementById('copy-status').textContent = '参数已变化。再次复制会带上最新数值。';
  if (renderPending) return;
  renderPending = true;
  requestAnimationFrame(() => { renderPending = false; update(); });
}

for (const name of ['x', 'scale', 'opacity']) controls[name].addEventListener('input', scheduleUpdate);
controls.order.addEventListener('change', scheduleUpdate);

document.getElementById('reset').addEventListener('click', () => {
  state = { ...INITIAL };
  controls.x.value = state.x;
  controls.scale.value = state.scale;
  controls.opacity.value = state.opacity;
  controls.order.value = 'red-front';
  document.getElementById('hint-text').textContent = '已恢复初始画面。先做一个预测，再单独改变一个参数。';
  document.getElementById('copy-status').textContent = '已恢复初始参数，可以重新尝试一个变化。';
  update();
});

document.getElementById('hint').addEventListener('click', () => {
  // Evaluate nearby candidates, but never apply them or reveal target values.
  readControls();
  update();
  const choices = [
    ['x', -0.03, '试着把红色高斯向左移一点，再观察误差。'],
    ['x', 0.03, '试着把红色高斯向右移一点，再观察误差。'],
    ['scale', -0.05, '试着让红色高斯的尺度小一点，观察边缘和误差。'],
    ['scale', 0.05, '试着让红色高斯的尺度大一点，观察边缘和误差。'],
    ['opacity', -0.04, '试着降低红色高斯的不透明度，观察重叠颜色。'],
    ['opacity', 0.04, '试着提高红色高斯的不透明度，观察重叠颜色。']
  ];
  const bounds = { x: [0.05, 0.95], scale: [0.3, 2], opacity: [0, 1] };
  let best = { error: currentError, message: '局部调整没有发现明显改善。先观察细小差异，或试着交换前后顺序再解释结果。' };
  for (const [key, delta, message] of choices) {
    const candidate = { ...state, [key]: Math.max(bounds[key][0], Math.min(bounds[key][1], state[key] + delta)) };
    const error = mse(render(candidate), targetPixels);
    if (error < best.error - 1e-12) best = { error, message };
  }
  const reversedError = mse(render({ ...state, reverse: !state.reverse }), targetPixels);
  if (reversedError < best.error - 1e-12) {
    best = { error: reversedError, message: '试着交换前后顺序，特别观察重叠区域的颜色。' };
  }
  if (currentError < 1e-12) best.message = '当前画面已一致。现在故意改一个参数，先预测误差方向，再验证你的理解。';
  hintCount += 1;
  document.getElementById('hint-text').textContent = best.message;
  updateTemplate();
});

document.getElementById('copy').addEventListener('click', async () => {
  readControls();
  update();
  const status = document.getElementById('copy-status');
  try {
    await navigator.clipboard.writeText(observationTemplate());
    status.textContent = '已复制当前参数与观察模板。补上自己的解释，再返回主应用记录。';
  } catch (_error) {
    document.getElementById('observation-details').open = true;
    const field = document.getElementById('observation');
    field.focus();
    field.select();
    status.textContent = '模板已展开并选中，可以手动复制。';
  }
});

paint(document.getElementById('target-canvas'), targetPixels);
document.getElementById('initial-mse').textContent = initialError.toFixed(8);
update();
