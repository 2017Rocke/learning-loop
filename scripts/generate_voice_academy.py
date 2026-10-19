#!/usr/bin/env python3
"""Generate original, non-measured VoiceStudio teaching SVGs with no dependencies.

Run from any directory; output is limited to web/media/voice-academy.
These are concept illustrations, not screenshots or model output.
"""

from html import escape
from pathlib import Path
import math

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "web" / "media" / "voice-academy"
INK = "#38384f"
BLUE = "#367b93"
ROSE = "#bc526c"
PURPLE = "#7864a4"
GREEN = "#3f7969"


def rect(x, y, w, h, fill, stroke=INK, radius=18, extra=""):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="3" {extra}/>'


def text(x, y, value, size=32, fill=INK, anchor="start", weight=600):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" text-anchor="{anchor}" font-weight="{weight}">{escape(value)}</text>'


def line(x1, y1, x2, y2, color=INK, width=4, extra=""):
    return f'<path d="M{x1} {y1} L{x2} {y2}" stroke="{color}" stroke-width="{width}" fill="none" stroke-linecap="round" {extra}/>'


def arrow(x1, y1, x2, y2, color=INK):
    return line(x1, y1, x2, y2, color, 4, 'marker-end="url(#arrow)"')


def wave(x, y, width, color, amplitude=20, envelope=None):
    points = []
    for i in range(121):
        t = i / 120
        scale = envelope(t) if envelope else 1
        dy = amplitude * scale * math.sin(t * math.pi * 16)
        points.append(f'{x+t*width:.1f},{y+dy:.1f}')
    return f'<polyline points="{" ".join(points)}" fill="none" stroke="{color}" stroke-width="4" stroke-linecap="round"/>'


def guide(x=866, y=58):
    # An original little lamp with headphones; it is a guide, not a data point.
    return (f'<g transform="translate({x} {y})">'
            '<path d="M-28 7v-12a28 28 0 0 1 56 0V7" fill="none" stroke="#7864a4" stroke-width="7"/>'
            '<path d="M-21 6Q-21-20 0-20Q21-20 21 6L13 25H-13Z" fill="#ffe7a9" stroke="#38384f" stroke-width="3"/>'
            '<path d="M-30 0v16M30 0v16" stroke="#bc526c" stroke-width="10" stroke-linecap="round"/>'
            '<circle cx="-7" cy="3" r="3" fill="#38384f"/><circle cx="7" cy="3" r="3" fill="#38384f"/>'
            '<path d="M-5 12q5 5 10 0M-10 29h20" fill="none" stroke="#38384f" stroke-width="3" stroke-linecap="round"/></g>')


def page(filename, number, title, alt, drawing):
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540" viewBox="0 0 960 540" role="img" aria-labelledby="title desc">'
           f'<title id="title">{escape(title)}</title><desc id="desc">{escape(alt)}</desc>'
           '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto-start-reverse"><path d="M0 0L8 4L0 8" fill="#38384f"/></marker></defs>'
           '<g font-family="PingFang SC, Noto Sans CJK SC, Microsoft YaHei, sans-serif">'
           '<rect width="960" height="540" fill="#fff7ed"/>'
           + ''.join(line(x, 30, x, 510, '#ebdfde', 1) for x in range(48, 930, 24))
           + ''.join(line(30, y, 930, y, '#ebdfde', 1) for y in range(30, 520, 24))
           + '<rect x="14" y="14" width="932" height="512" rx="28" fill="none" stroke="#d1babf" stroke-width="3"/>'
           + text(43, 58, f'ECHO STUDIO / {number}', 18, PURPLE, weight=700)
           + text(43, 109, title, 39)
           + guide()
           + drawing
           + text(43, 506, '原创原理示意 · 非软件截图／非模型实测', 22, '#6c6574', weight=400)
           + '</g></svg>')
    (OUT / filename).write_text(svg + '\n', encoding='utf-8')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    d = rect(38, 142, 884, 320, '#f3e4e9', '#bca6ae', 26)
    d += text(64, 184, '工作台：组织稿子、设置与编辑', 29)
    d += rect(65, 215, 222, 170, '#edf5f3', BLUE)
    d += text(176, 257, '文字 + 音色', 31, BLUE, 'middle')
    for j, w in enumerate([138, 112, 142]):
        d += line(103, 287 + j * 24, 103 + w, 287 + j * 24, BLUE, 7)
    d += arrow(298, 300, 350, 300)
    d += rect(363, 215, 231, 170, '#e6def3', PURPLE)
    d += text(478, 257, '引擎接入', 31, PURPLE, 'middle')
    d += rect(391, 279, 175, 78, '#fff9f4', PURPLE, 38)
    d += text(478, 330, '已有模型', 31, PURPLE, 'middle')
    d += arrow(605, 300, 657, 300)
    d += rect(670, 215, 224, 170, '#fbe2df', ROSE)
    d += text(782, 257, '对应音频', 31, ROSE, 'middle')
    d += wave(692, 315, 180, ROSE)
    d += text(480, 432, '声音由模型产生，工作台安排流程', 31, INK, 'middle')
    page('studio-pipeline.svg', '01', '从稿子到声音，谁做什么？',
         '工作台内的文字和声音设置经过引擎接入已有模型，模型生成音频。工作台负责组织流程。所有图形为原理示意。', d)

    d = rect(40, 146, 880, 196, '#e7f1ef', '#a5c2ba', 24)
    d += text(66, 184, '这一轮，只在预算窗口内找边界', 31)
    chars = list('先检查。再导出。')
    for i, c in enumerate(chars):
        x = 78 + i * 101
        d += rect(x, 210, 84, 84, '#fffaf3' if i < 5 else '#ece8e2', BLUE if i < 5 else '#9f9a99', 12)
        d += text(x + 42, 267, c, 40, INK if i < 5 else '#807d7d', 'middle')
    d += '<circle cx="423" cy="251" r="43" fill="none" stroke="#bc526c" stroke-width="5"/>'
    d += line(569, 199, 569, 323, ROSE, 4, 'stroke-dasharray="8 8"')
    d += text(570, 324, '预算止于此', 25, ROSE, 'end')
    d += rect(40, 364, 880, 99, '#f5e8d6', '#bcaa90', 20)
    d += text(65, 407, '换一份稿：没有标点，也没有空格', 29)
    d += text(65, 444, '先别猜语义理解，预测会走哪条规则 → ?', 28, PURPLE)
    page('studio-budget.svg', '02', '分段：先看窗口，再找边界',
         '八个字符先检查。再导出。只有前五个在本轮示意窗口内。圈出窗口内的句号候选；预算线在再字之后。下方提出没有标点和空格时的预测问题，不显示回退结果。预算五字符仅为示意。', d)

    d = rect(41, 147, 878, 314, '#eae4f4', '#bcb1ce', 24)
    d += text(69, 187, '同一小段时间，把已有样本相加', 31)
    d += rect(318, 207, 386, 194, '#fff9f3', '#bca6ae', 14)
    d += text(71, 260, '前段尾部', 31, ROSE)
    d += wave(335, 251, 350, ROSE, 27, lambda t: 1-t)
    d += text(731, 260, '强 → 弱', 29, ROSE)
    d += text(71, 355, '后段头部', 31, BLUE)
    d += wave(335, 346, 350, BLUE, 27, lambda t: t)
    d += text(731, 355, '弱 → 强', 29, BLUE)
    d += text(510, 309, '+', 42, PURPLE, 'middle')
    d += text(480, 439, '重叠区 = 前段 × 权重 + 后段 × 权重', 29, INK, 'middle')
    page('studio-crossfade.svg', '03', '接缝：一边退出，一边进入',
         '同一重叠区内，前段尾部的权重逐渐减小，后段头部的权重逐渐增加；两段已有音频加权相加。示意波形不代表真实音频或声音质量实测。', d)

    d = ''
    for x, fill, color, label in [(42, '#e9f3f3', BLUE, '读全了吗'), (345, '#f8e5e8', ROSE, '读对了吗'), (648, '#e8efe7', GREEN, '连顺了吗')]:
        d += rect(x, 155, 270, 265, fill, color, 24)
        d += text(x + 135, 201, label, 34, color, 'middle')
    for i in range(3):
        y = 247 + i * 48
        d += text(63, y+8, str(i+1), 28, BLUE)
        d += line(93, y, 151, y, BLUE, 6)
        d += arrow(163, y, 191, y)
        d += wave(208, y, 76, BLUE, 12)
    d += rect(381, 236, 197, 68, '#fff9f4', ROSE, 12)
    d += text(479, 282, '术语 / 地名', 28, ROSE, 'middle')
    d += '<path d="M429 384v-11a50 50 0 0 1 100 0v11M429 373v22M529 373v22" fill="none" stroke="#bc526c" stroke-width="12" stroke-linecap="round"/>'
    d += wave(675, 281, 92, ROSE, 24)
    d += wave(787, 281, 92, BLUE, 24)
    d += line(778, 242, 778, 320, GREEN, 4, 'stroke-dasharray="7 7"')
    d += text(783, 374, '接缝 + 手机', 28, GREEN, 'middle')
    d += text(480, 462, '三份证据，分别对照；留空等自己听', 31, INK, 'middle')
    page('studio-listening.svg', '04', '试听台：把“能播放”拆开检查',
         '三张未预填结论的试听卡。左卡把一二三句文字分别对应音频；中卡检查术语和地名；右卡检查接缝及目标手机播放。各卡表示不同证据，不代表任何实际作品已通过验收。', d)
    print(f'Generated 4 original diagrams in {OUT.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
