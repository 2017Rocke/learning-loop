#!/usr/bin/env python3
"""Original static MOSFET beginner diagrams, using only Python's standard library.

These are functional teaching illustrations, not package pinout drawings. The
circuits use an enhancement-mode N-channel MOSFET as a low-side switch with a
non-inductive, suitably rated 5 V lamp module. Gate voltage is referenced to S.
The faucet is an explicitly marked analogy, not a physical device cross-section.
"""
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "web/media/mosfet-beginner"
INK = "#243c38"
CURRENT = "#08765e"
CONTROL = "#8051a0"
BRASS = "#925e22"
CORAL = "#ad463d"
PAPER = "#fff9e9"
FONT = "PingFang SC,Noto Sans CJK SC,Microsoft YaHei,sans-serif"


def text(x, y, value, size=38, color=INK, anchor="middle", weight=650):
    return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" '
            f'text-anchor="{anchor}" font-weight="{weight}">{escape(value)}</text>')


def rect(x, y, w, h, fill=PAPER, stroke=BRASS, radius=20, width=3):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>'


def path(d, color=BRASS, width=7, extra=""):
    return f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round" {extra}/>'


def arrow(x1, y1, x2, y2, color=BRASS, width=7):
    import math
    a = math.atan2(y2-y1, x2-x1)
    bx, by = x2-16*math.cos(a), y2-16*math.sin(a)
    return path(f'M{x1} {y1}L{x2} {y2}', color, width) + path(
        f'M{bx-8*math.sin(a)} {by+8*math.cos(a)}L{x2} {y2}L{bx+8*math.sin(a)} {by-8*math.cos(a)}', color, width)


def circle(x, y, r, fill, stroke="none", width=3):
    return f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>'


def base(title):
    b = '<rect width="960" height="540" rx="24" fill="#efe4cc"/>'
    b += rect(18, 86, 924, 356, PAPER, "#c7ad7d", 20, 2)
    b += path('M27 38H42M35 30V46M922 38H936M929 31V45', BRASS, 3)
    b += text(480, 57, title, 42)
    return b


def footer(value):
    return text(480, 500, value, 35, BRASS)


def save(name, title, description, body):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f'{name}.svg').write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540" '
        f'viewBox="0 0 960 540" role="img" aria-labelledby="title desc">'
        f'<title id="title">{escape(title)}</title><desc id="desc">{escape(description)}</desc>'
        f'<g font-family="{FONT}">{body}</g></svg>\n', encoding="utf-8")


def identity():
    b = base('MOS 管长什么样？')
    b += text(264, 140, '三脚封装', 39) + text(707, 140, '小型贴片', 39)
    # Generic TO-220-like outline. Deliberately do not label physical pins G/D/S.
    b += rect(192, 163, 144, 134, '#52615d', '#243c38', 12, 4)
    b += rect(218, 158, 92, 62, '#bdc8bd', '#243c38', 8, 3)
    b += circle(264, 185, 12, PAPER, '#69766e', 3)
    b += rect(192, 219, 144, 88, '#2b423d', 'none', 8)
    for x in (219, 264, 309):
        b += path(f'M{x} 308V365', '#758680', 13)
    b += text(264, 412, '引脚可伸出外壳', 34)
    # Generic leadless surface-mount outline, shown obliquely to reveal pads.
    b += '<path d="M600 206L741 174L821 220L679 254Z" fill="#344e46" stroke="#233c35" stroke-width="4"/>'
    b += '<path d="M600 206V287L679 338V254ZM679 254L821 220V299L679 338Z" fill="#263f37" stroke="#233c35" stroke-width="4"/>'
    for x, y in ((616, 286), (642, 302), (668, 318), (703, 322), (745, 310), (787, 299)):
        b += '<path d="M%d %dL%d %dV%dL%d %dZ" fill="#d8bf86" stroke="#927340" stroke-width="2"/>' % (x, y, x+17, y-5, y+12, x, y+17)
    b += text(707, 412, '焊盘也可能在底部', 34)
    b += footer('认型号、查手册；不能只看外形')
    save('identity', '先认 MOS 管的外形',
         '左侧为类似 TO-220 的三脚封装，右侧为小型贴片封装的功能外观示意。图中没有指定 G、D、S 的物理引脚顺序。相似外形也可能是其他器件，必须根据型号查数据手册确认。', b)


def job():
    b = base('谁发信号，谁给小灯供电？')
    # Deliberately use simple functional blocks before the detailed route diagram.
    b += rect(61, 205, 230, 98, '#eee1f3', CONTROL, 18)
    b += text(176, 265, '控制器', 42, CONTROL)
    b += rect(424, 272, 203, 96, '#f5dfab', BRASS, 18)
    b += text(525, 331, 'MOS 开关', 37, BRASS)
    b += rect(424, 115, 203, 90, '#fff0ae', BRASS, 18)
    b += text(525, 170, '小灯模块', 37)
    b += rect(740, 174, 153, 135, '#e6ede4', BRASS, 18)
    b += text(816, 225, '5 V', 43) + text(816, 278, '电源', 38)
    b += path('M816 174V148H627M525 205V272M525 368V410H816V309', CURRENT)
    b += arrow(718, 148, 666, 148, CURRENT) + arrow(525, 214, 525, 259, CURRENT) + arrow(688, 410, 738, 410, CURRENT)
    b += text(854, 155, '+', 39, CURRENT) + text(854, 348, '−', 39, CURRENT)
    b += arrow(291, 254, 405, 309, CONTROL)
    b += text(338, 216, '控制', 36, CONTROL)
    b += text(370, 339, 'G', 38, CONTROL)
    b += path('M176 303V410H525', '#71867b', 4)
    b += text(275, 397, '共同地', 32, '#4e655a')
    b += text(661, 259, 'D', 35, CURRENT) + text(661, 375, 'S', 35, CURRENT)
    b += footer('控制器发信号；外部电源供能')
    save('job', '控制信号和供电是两件事',
         '教学假设：合适的增强型 N 沟道 MOS 低端开关，连接额定 5 V 的非感性小灯模块。绿色约定电流由电源正端经过小灯、MOS 的 D 和 S 回到负端。控制器通过紫色 G 线发信号，并与 S 共地；灯的工作电流不由控制器的 G 线提供。为突出功能省略驱动电阻和保护细节。', b)


def gate():
    b = base('栅极 G，像水阀的手柄')
    b += text(245, 136, '水阀类比', 37, CONTROL)
    # A mechanical water valve is explicitly separated from the circuit column.
    b += path('M92 283H368', '#a0c4b1', 58)
    b += path('M92 283H368', '#d5eee2', 39)
    b += rect(192, 233, 100, 103, '#d8b66f', BRASS, 15, 5)
    b += path('M242 233V195M188 189H296', CONTROL, 15)
    b += arrow(106, 283, 167, 283, CURRENT, 6)
    b += arrow(307, 283, 365, 283, CURRENT, 6)
    b += text(245, 388, '手柄控制水路', 35)
    b += path('M454 112V415', '#d5c7a8', 3, 'stroke-dasharray="9 10"')
    b += text(696, 136, '真实电路：看 G 对 S', 35, CONTROL)
    b += rect(492, 173, 400, 92, '#e8ede2', '#b0bba9', 16, 2)
    b += text(575, 228, '0 V', 39)
    b += arrow(641, 218, 704, 218, CONTROL, 6)
    b += text(800, 229, '关', 43)
    b += rect(492, 287, 400, 92, '#d3eee0', '#68a78b', 16, 2)
    b += text(583, 341, '合适栅压', 35)
    b += arrow(679, 332, 726, 332, CONTROL, 6)
    b += text(800, 343, '开', 43)
    b += text(696, 421, '本例 S 接共同地', 33)
    b += footer('类比不是内部结构；具体栅压查手册')
    save('gate', '先用水阀类比理解栅极控制',
         '左侧水阀手柄控制水路只是类比，不代表 MOS 内部有机械阀。右侧为增强型 N 沟道 MOS 低端开关：S 接共同地，控制取决于 G 相对 S 的电压。G 对 S 为零伏时关断；按器件手册和负载条件提供合适栅压才能充分导通。达到阈值不等于完全打开。', b)


def route_panel(origin, on):
    x = origin
    b = rect(x, 102, 430, 326, '#edf5e8' if on else '#f4ecdc', '#b1c5ab' if on else '#cbb995', 18, 2)
    b += text(x+215, 145, '开：回路接通' if on else '关：回路断开', 35, CURRENT if on else INK)
    # Supply on left, load and low-side MOS functional switch on right.
    b += path(f'M{x+72} 241V184H{x+300}V215M{x+300} 275V296M{x+300} 364V397H{x+72}V329', CURRENT, 6)
    b += rect(x+36, 241, 72, 88, '#e2e9df', CURRENT, 12, 3)
    b += text(x+72, 297, '5V', 29)
    b += text(x+34, 226, '+', 32) + text(x+34, 358, '−', 32)
    b += circle(x+300, 245, 30, '#ffdf76' if on else '#deded2', CURRENT, 4)
    b += path(f'M{x+284} 229L{x+316} 261M{x+316} 229L{x+284} 261', CURRENT, 3)
    b += text(x+359, 257, '灯', 34)
    b += circle(x+300, 300, 5, CURRENT) + circle(x+300, 360, 5, CURRENT)
    b += path(f'M{x+300} 360L{x+300 if on else x+267} {302 if on else 314}', CURRENT, 6)
    b += text(x+349, 310, 'D', 34, CURRENT) + text(x+349, 371, 'S', 34, CURRENT)
    b += arrow(x+157, 332, x+244, 332, CONTROL, 5)
    b += text(x+145, 318, 'G', 34, CONTROL)
    if on:
        b += arrow(x+161, 184, x+213, 184, CURRENT, 5)
        b += arrow(x+300, 278, x+300, 293, CURRENT, 4)
        b += arrow(x+220, 397, x+168, 397, CURRENT, 5)
    return b


def route():
    b = base('电流走 D → S；G 只控制')
    b += route_panel(38, False) + route_panel(492, True)
    b += footer('约定电流：电源＋ → 灯 → D → S → 电源−')
    save('route', '同一电路的关断和导通状态',
         '左右为同一个增强型 N 沟道 MOS 低端开关的功能示意，假设正确驱动且负载是额定 5 V 的非感性小灯模块。左侧关断时 D 到 S 的通路断开，无闭合负载电流；右侧导通时绿色约定电流从电源正端经灯、D、S 回负端。紫色 G 箭头表示控制关系，不是灯的工作电流。功能开关符号不是 MOS 实际内部结构；省略正常反向偏置的体二极管与驱动细节。', b)


def boundary_panel(x, floating):
    b = rect(x, 103, 430, 324, '#f6eade' if floating else '#e5f0e2', '#c9aa90' if floating else '#99b69b', 18, 2)
    b += text(x+215, 147, '悬空：状态不可靠' if floating else '拉到 0 V：关断', 34, CORAL if floating else CONTROL)
    b += text(x+260, 207, 'G', 37, CONTROL)
    # The gate's insulated control plate is on the LEFT of an explicit barrier.
    b += path(f'M{x+260} 218V321', CONTROL, 10)
    b += rect(x+288, 205, 22, 130, '#f1d092', BRASS, 3, 2)
    b += path(f'M{x+333} 218V321', '#778a77', 10)
    b += text(x+306, 381, '绝缘层', 31, BRASS)
    if floating:
        b += path(f'M{x+73} 271H{x+122}M{x+174} 271H{x+260}', CONTROL, 6)
        b += text(x+146, 252, '断线', 29, CORAL)
        b += text(x+238, 247, '+', 28, CONTROL) + text(x+238, 284, '+', 28, CONTROL)
        b += text(x+175, 406, '电荷可能留住', 31, CORAL)
    else:
        b += path(f'M{x+260} 271H{x+95}V343', CONTROL, 6)
        b += arrow(x+225, 271, x+165, 271, CONTROL, 5)
        b += arrow(x+95, 300, x+95, 339, CONTROL, 5)
        b += path(f'M{x+73} 347H{x+117}M{x+81} 359H{x+109}M{x+89} 371H{x+101}', CONTROL, 5)
        b += text(x+160, 243, '沿外线释放', 30, CONTROL)
        b += text(x+95, 406, '共同地', 29, CONTROL)
    return b


def boundary():
    b = base('关断要拉低，不能把 G 悬空')
    b += boundary_panel(38, False) + boundary_panel(492, True)
    b += footer('栅电荷走外部导线，不穿过绝缘层')
    save('boundary', '主动拉低和断开控制线不是一回事',
         '两侧均为栅极等效电容示意，不是真实内部剖面。紫色左极板表示 G，黄色竖条表示栅绝缘层。左侧把 G 主动连到共同地，经外部导线释放栅电荷，使 G 对 S 回到零伏而关断。右侧断开控制线后 G 悬空，栅电荷可能残留，因此不能把断线当作可靠关断。加号仅表示可能残留的净正电荷，不是运动的电子。紫色箭头只表示 G 端栅电荷沿外部控制线释放，未穿过绝缘层；不表示灯的负载电流。', b)


if __name__ == '__main__':
    for make in (identity, job, gate, route, boundary):
        make()
    print('Generated 5 static beginner MOSFET diagrams.')
