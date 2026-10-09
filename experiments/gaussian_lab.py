#!/usr/bin/env python3
"""Two 2D Gaussians: ordered alpha compositing and a one-parameter toy fit.

Standard library only; no downloads, GPU, image library or real 3D training.
The finite-difference fit is deliberately small and is NOT Brush's gradient
implementation. Running this script does not mark any learning task complete.
"""
import argparse
import base64
import html
import json
import math
from pathlib import Path
import struct
import zlib


BACKGROUND = (0.95, 0.96, 0.99)
RED = (0.95, 0.21, 0.16)
BLUE = (0.12, 0.40, 0.95)


def gaussian(x, y, cx, cy, sx, sy, opacity):
    """Screen-space opacity: peak opacity times an unnormalised Gaussian."""
    return opacity * math.exp(-0.5 * (((x - cx) / sx) ** 2 + ((y - cy) / sy) ** 2))


def pixel(x, y, red_x=0.43, scale=1.0, opacity=0.82, reverse=False):
    red_alpha = gaussian(x, y, red_x, 0.49, 0.15 * scale, 0.20 * scale, opacity)
    blue_alpha = gaussian(x, y, 0.57, 0.51, 0.17, 0.19, 0.82)
    layers = [(RED, red_alpha), (BLUE, blue_alpha)]
    if reverse:
        layers.reverse()
    transmittance = 1.0
    color = [0.0, 0.0, 0.0]
    for rgb, alpha in layers:  # front to back
        for channel in range(3):
            color[channel] += transmittance * alpha * rgb[channel]
        transmittance *= 1.0 - alpha
    return tuple(color[i] + transmittance * BACKGROUND[i] for i in range(3))


def render(width=80, height=56, **parameters):
    return [pixel((x + 0.5) / width, (y + 0.5) / height, **parameters)
            for y in range(height) for x in range(width)]


def mse(prediction, reference):
    return sum((a - b) ** 2 for p, q in zip(prediction, reference)
               for a, b in zip(p, q)) / (len(reference) * 3)


def fit_position(initial_x, steps, target):
    """Central finite differences + a bounded line search, fitting only x."""
    current = initial_x
    history = []
    epsilon = 0.0001
    for step in range(steps + 1):
        loss = mse(render(red_x=current), target)
        history.append({'step': step, 'red_x': current, 'mse': loss})
        if step == steps or loss < 1e-12:
            break
        plus = mse(render(red_x=current + epsilon), target)
        minus = mse(render(red_x=current - epsilon), target)
        gradient = (plus - minus) / (2.0 * epsilon)
        learning_rate = 4.0
        for _ in range(20):
            candidate = max(0.05, min(0.95, current - learning_rate * gradient))
            if mse(render(red_x=candidate), target) < loss:
                current = candidate
                break
            learning_rate *= 0.5
        else:
            break
    return current, history


def png_bytes(pixels, width, height):
    """Write a tiny RGB PNG using only zlib/struct."""
    def chunk(kind, data):
        return (struct.pack('!I', len(data)) + kind + data
                + struct.pack('!I', zlib.crc32(kind + data) & 0xffffffff))
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        for rgb in pixels[y * width:(y + 1) * width]:
            rows.extend(round(255 * max(0.0, min(1.0, c))) for c in rgb)
    return (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', struct.pack('!2I5B', width, height, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(bytes(rows))) + chunk(b'IEND', b''))


def make_svg(panels, history, output):
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="1160" height="1030" viewBox="0 0 1160 1030">',
           '<rect width="1160" height="1030" fill="#101827"/>',
           '<style>text{font-family:system-ui,-apple-system,sans-serif;fill:#eef3fc}.muted{fill:#aebdd3}</style>',
           '<text x="40" y="52" font-size="29" font-weight="700">两枚高斯，六个可检验的结果</text>',
           '<text x="40" y="85" class="muted" font-size="16">教学简化：二维高斯 + 有序 alpha 合成 + 单参数拟合；不是完整 3DGS 重建</text>']
    for index, panel in enumerate(panels):
        x = 40 + (index % 3) * 365
        y = 117 + (index // 3) * 312
        png = png_bytes(render(width=240, height=168, **panel['parameters']), 240, 168)
        encoded = base64.b64encode(png).decode('ascii')
        svg.extend([
            f'<rect x="{x}" y="{y}" width="350" height="296" rx="16" fill="#1b283c"/>',
            f'<text x="{x+16}" y="{y+31}" font-size="19" font-weight="600">{html.escape(panel["title"])}</text>',
            f'<image x="{x+15}" y="{y+46}" width="320" height="224" href="data:image/png;base64,{encoded}"/>',
            f'<text x="{x+16}" y="{y+287}" class="muted" font-size="13">MSE = {panel["mse"]:.8f}</text>'
        ])
    graph_x, graph_y, graph_w, graph_h = 65, 797, 1040, 110
    max_loss = max(item['mse'] for item in history) or 1.0
    denom = max(1, len(history) - 1)
    points = ' '.join(f'{graph_x + i / denom * graph_w:.2f},{graph_y + graph_h - item["mse"] / max_loss * graph_h:.2f}'
                      for i, item in enumerate(history))
    svg.extend([
        '<text x="40" y="774" font-size="20" font-weight="600">只拟合红色高斯的水平位置</text>',
        f'<path d="M {graph_x} {graph_y} V {graph_y+graph_h} H {graph_x+graph_w}" stroke="#62738d" fill="none"/>',
        f'<polyline points="{points}" stroke="#64dcc9" stroke-width="3" fill="none"/>',
        f'<text x="65" y="930" class="muted" font-size="15">第 0 步 → 第 {history[-1]["step"]} 步；纵轴为 RGB 均方误差，越低越接近目标。</text>',
        '<text x="40" y="969" class="muted" font-size="15">观察：遮挡顺序会改变颜色；误差下降仅证明这个简化目标拟合改善。</text>',
        '<text x="40" y="997" class="muted" font-size="15">边界：没有相机定位、三维投影、多视角约束、球谐颜色或高斯增删。</text>',
        '</svg>'
    ])
    output.write_text('\n'.join(svg), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parent / 'output', help='输出目录')
    parser.add_argument('--offset', type=float, default=0.22, help='位置实验中红色高斯的水平偏移，范围 -0.35..0.45')
    parser.add_argument('--scale', type=float, default=1.5, help='尺度实验的红色高斯缩放，范围 0.1..3')
    parser.add_argument('--opacity', type=float, default=0.3, help='透明度实验中的峰值不透明度，范围 0..1')
    parser.add_argument('--steps', type=int, default=60, help='最多拟合步数，范围 1..300')
    args = parser.parse_args()
    for name, lower, upper in [('offset', -0.35, 0.45), ('scale', 0.1, 3.0), ('opacity', 0.0, 1.0)]:
        value = getattr(args, name)
        if not math.isfinite(value) or not lower <= value <= upper:
            parser.error(f'--{name} 必须在 {lower} 到 {upper} 之间')
    if not 1 <= args.steps <= 300:
        parser.error('--steps 必须在 1 到 300 之间')
    target = render()
    initial_x = 0.43 + args.offset
    fitted_x, history = fit_position(initial_x, args.steps, target)
    panels = [
        {'id': 'target', 'title': '01 目标：红色在前', 'parameters': {}},
        {'id': 'position', 'title': '02 只改变水平位置', 'parameters': {'red_x': initial_x}},
        {'id': 'scale', 'title': '03 只改变尺度', 'parameters': {'scale': args.scale}},
        {'id': 'opacity', 'title': '04 只改变不透明度', 'parameters': {'opacity': args.opacity}},
        {'id': 'order', 'title': '05 交换前后顺序', 'parameters': {'reverse': True}},
        {'id': 'fit', 'title': '06 从图 02 拟合位置', 'parameters': {'red_x': fitted_x}},
    ]
    for panel in panels:
        panel['mse'] = mse(render(**panel['parameters']), target)
    report = {
        'scope': '2D pedagogical alpha-compositing experiment; not real 3DGS reconstruction',
        'pixel_domain': '[0,1] RGB; MSE is averaged across all 80*56*3 values',
        'target_red_x': 0.43,
        'initial_red_x': initial_x,
        'fitted_red_x': fitted_x,
        'panels': panels,
        'center_pixel_red_front': pixel(0.5, 0.5),
        'center_pixel_blue_front': pixel(0.5, 0.5, reverse=True),
        'fit_history': history,
        'limitations': ['二维屏幕空间合成，没有三维投影或相机定位', '只拟合一个位置参数，使用有限差分；Brush 使用可微渲染及优化器',
                        '使用MSE教学，Brush默认RGB损失包含L1和SSIM', '没有多视角、球谐颜色、高斯增删或GPU加速'],
        'user_practice_status': 'not-assessed'
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'metrics.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    make_svg(panels, history, args.output / 'comparison.svg')
    print('教学实验已生成（不代表用户实操或知识掌握完成）：')
    print(args.output.resolve() / 'comparison.svg')
    print(args.output.resolve() / 'metrics.json')
    print(f'红色高斯 x: {initial_x:.6f} -> {fitted_x:.6f}，目标 0.430000')
    print(f'位置误差 MSE: {history[0]["mse"]:.10f} -> {history[-1]["mse"]:.10f}')
    print(f'交换前后顺序后的 MSE: {panels[4]["mse"]:.10f}')


if __name__ == '__main__':
    main()
