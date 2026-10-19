#!/usr/bin/env python3
"""Generate original, static electronics teaching diagrams with no dependencies."""
from pathlib import Path
from html import escape

ROOT = Path(__file__).resolve().parents[1]
FONT = 'PingFang SC,Noto Sans CJK SC,Microsoft YaHei,sans-serif'


def text(x, y, value, size=29, fill='#263b4e', anchor='middle', weight=650):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" text-anchor="{anchor}" font-weight="{weight}">{escape(value)}</text>'


def rect(x, y, w, h, fill, stroke='none', radius=12, sw=2):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'


def line(d, color='#317eb2', width=5, arrow=False, dash=None):
    name = {'#317eb2': 'blue', '#9260ac': 'purple', '#dc775d': 'coral', '#62d4ba': 'mint'}[color] if arrow else ''
    return f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"' + (f' marker-end="url(#{name})"' if arrow else '') + (f' stroke-dasharray="{dash}"' if dash else '') + '/>'


def circle(x, y, radius, fill, stroke='none', sw=2):
    return f'<circle cx="{x}" cy="{y}" r="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'


def electron(x, y):
    return circle(x, y, 12, '#317eb2') + text(x, y+6, '−', 21, '#fff')


def markers():
    return '<defs>' + ''.join(f'<marker id="{name}" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="3.5" markerHeight="3.5" orient="auto"><path d="M0 0L10 5L0 10Z" fill="{color}"/></marker>' for name, color in [('blue','#317eb2'), ('purple','#9260ac'), ('coral','#dc775d'), ('mint','#62d4ba')]) + '</defs>'


def frame(title, body, footer, theme, description):
    cap = theme == 'capacitor'
    bg, paper, edge, ink = ('#182a42', '#f7f2de', '#bc9c5c', '#fff6dc') if cap else ('#efe4cc', '#fff9e9', '#ad8148', '#503920')
    mascot = ''
    if cap:
        mascot = '<path d="M29 25L42 17L55 25V47L42 55L29 47Z" fill="#62d4ba" stroke="#d4b676" stroke-width="2"/>' + line('M34 36H50', '#38505e', 2) + circle(38,33,2,'#23394a') + circle(47,33,2,'#23394a')
    else:
        mascot = rect(25,20,34,30,'#d6aa61','#7d5a31',6) + circle(35,33,3,'#3b4d50') + circle(49,33,3,'#3b4d50') + line('M36 43H48','#7d5a31',2)
        for x in [22,62]:
            mascot += line(f'M{x} 30V40','#7d5a31',4)
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="720" height="405" viewBox="0 0 720 405" role="img" aria-label="{escape(title)}">{markers()}<desc>{escape(description)}</desc><g font-family="{FONT}">{rect(0,0,720,405,bg,radius=20)}{rect(16,66,688,286,paper,edge,18)}{mascot}{text(76,45,title,30,ink,"start")}{body}{text(360,385,footer,27,ink)}</g></svg>'


def write(theme, name, title, body, footer, description):
    directory = ROOT / 'web' / 'media' / f'{theme}-academy'
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f'{name}.svg').write_text(frame(title, body, footer, theme, description), encoding='utf-8')


def capacitor():
    body = line('M96 157V110H410V155','#6d8492',5) + line('M96 251V315H410V255','#6d8492',5)
    body += circle(96,204,47,'#e3ece8','#6d8492',3) + text(96,213,'电源',29)
    body += text(96,151,'+',28) + text(96,281,'−',28)
    body += rect(325,155,170,18,'#c7aa6f',radius=3) + rect(325,237,170,18,'#c7aa6f',radius=3)
    body += rect(325,180,170,50,'#dce7e3',radius=7) + text(410,213,'绝缘层',28)
    for x in (355,410,465):
        body += text(x,153,'+',23,'#966c42') + electron(x,246)
    body += line('M300 110H230','#317eb2',5,True) + line('M230 315H300','#317eb2',5,True)
    body += electron(270,110) + electron(270,315)
    body += text(240,91,'取走电子',26,'#317eb2') + text(240,343,'补入电子',26,'#317eb2')
    body += text(584,167,'少电子',29) + text(584,251,'多电子',29)
    write('capacitor','charge','星灯工坊 · 电子只走外线',body,'能量存于电场；中间绝缘不穿过','电源经上方外线取走上板电子，经下方外线补电子到下板。蓝色负号点表示电子，箭头位于外线，绝缘层中没有电子路径；数量不代表实测。')

    body = text(190,115,'电源电压',28) + rect(63,137,255,28,'#e5dabc',radius=8) + rect(63,137,255,28,'#7da9a0',radius=8)
    body += text(190,203,'3.3 V',38) + text(190,243,'电容电压',28) + rect(63,264,255,28,'#e5dabc',radius=8) + rect(63,264,255,28,'#d3b363',radius=8)
    body += text(190,331,'3.3 V',38) + line('M354 140V283','#bca986',3)
    body += text(526,149,'推动差 ≈ 0 V',31) + text(526,219,'充电电流 ≈ 0',32) + text(526,292,'电荷、电场还在',28,'#60737c')
    write('capacitor','steady','星灯工坊 · 为什么停下来了',body,'理想直流稳态：几乎不再充电','合成理想稳定状态：电源与电容都是3.3伏，二者电压差为零，充电电流为零，但电容仍有分开的电荷与电场。两个条长度仅对照本例相等电压。')

    body = line('M220 141V105H590V172','#6d8492',5) + line('M590 236V310H220V269','#6d8492',5)
    body += rect(145,141,150,18,'#c7aa6f',radius=3) + rect(145,251,150,18,'#c7aa6f',radius=3)
    body += rect(145,169,150,72,'#dce7e3',radius=7) + text(220,214,'绝缘层',28)
    for x in (175,220,265):
        body += text(x,139,'+',23,'#966c42') + electron(x,260)
    body += rect(540,172,100,64,'#edd29b','#9b7444',10) + text(590,213,'负载',29)
    body += line('M345 310H435','#317eb2',5,True) + line('M435 105H345','#317eb2',5,True) + line('M590 286V252','#317eb2',5,True)
    body += electron(390,310) + electron(390,105) + text(415,200,'电源已断开',29) + text(415,245,'电子绕外路',27,'#317eb2')
    write('capacitor','discharge','星灯工坊 · 绕外路释放能量',body,'电荷差变小，电场与电压一起减弱','断开电源后，电容接到外部负载。电子从下板经下外线、负载、上外线回上板。两板之间绝缘；箭头与负号点只在外线。')

    body = line('M88 150V109H609V163M88 252V311H609V241M360 109V178M360 236V311','#6d8492',5)
    body += circle(88,201,50,'#e3ece8','#6d8492',3) + text(88,211,'电源',29)
    body += rect(554,163,110,78,'#e5dff0','#957aa6',10) + text(609,211,'芯片',32)
    body += rect(318,178,84,15,'#c7aa6f',radius=2) + rect(318,222,84,15,'#c7aa6f',radius=2)
    body += text(360,213,'绝缘',23,'#647c7a') + text(360,286,'电容',29)
    body += line('M173 109H236','#317eb2',4,True) + line('M360 166V134','#62d4ba',6,True) + line('M360 297V255','#62d4ba',6,True)
    body += line('M422 109H493','#62d4ba',6,True) + line('M536 311H451','#62d4ba',6,True)
    body += text(208,156,'还没补齐',25,'#317eb2') + text(491,285,'暂补缺口',27,'#286e5c')
    write('capacitor','relay','星灯工坊 · 芯片突然忙起来',body,'绿色＝约定电流；之后由电源回充','芯片与电容跨接在同一供电和回流线之间。蓝箭头表示电源供给，绿箭头表示电容沿外路暂补的约定电流：上端流向芯片，经过芯片后回到下端，不穿过电容绝缘间隙。这是突忙时刻的定性示意，不按电流数值比例绘图。')


def mosfet():
    body = rect(45,152,166,70,'#eee1f2','#9260ac',12) + text(128,197,'小引脚',30,'#76508d')
    body += line('M483 130V98H629V148M629 244V326H483V289','#317eb2',5)
    body += circle(629,196,48,'#e5f1f2','#317eb2',3) + text(629,202,'电源',29) + text(629,151,'+',24) + text(629,258,'−',24)
    body += rect(432,130,102,58,'#d8e7f0','#317eb2',9) + text(483,169,'负载',29)
    body += line('M483 188V226','#317eb2',5,True) + rect(432,235,102,54,'#f2dbac','#a97e47',9) + text(483,272,'通道',28)
    body += line('M211 187H326V262H415','#9260ac',5,True) + text(387,240,'G',32,'#9260ac')
    body += text(529,226,'D',32,'#317eb2') + text(529,317,'S',32,'#317eb2')
    body += line('M128 222V326H483','#778381',3) + line('M521 326H575','#317eb2',5,True)
    body += text(154,280,'控制入口',26,'#9260ac') + text(279,323,'共地',25,'#687573')
    write('mosfet','paths','黄铜机巧室 · 发令与供能',body,'紫线发令；蓝线由外部电源供能','功能示意。紫色控制线连接G；蓝色约定电流从电源正端经过负载、D、S回到电源负端。小引脚与S共地。G不是负载供电入口，机械向导仅作装饰。')

    body = rect(35,85,315,250,'#eee9de','#c4b69b',13) + rect(370,85,315,250,'#e8efdc','#b2c094',13)
    body += text(193,122,'关断',31,'#71685e') + text(528,122,'充分导通',31,'#4e725e')
    for shift, on in [(0,False),(335,True)]:
        body += text(218+shift,163,'D',29,'#317eb2') + text(218+shift,318,'S',29,'#317eb2')
        body += line(f'M218 {173}V207M218 262V288','#317eb2',4) if not on else ''
        if on:
            body += line(f'M553 173V288','#317eb2',5) + line('M553 205V252','#317eb2',5,True)
        else:
            body += circle(218,207,5,'#fff','#317eb2',2) + circle(218,262,5,'#fff','#317eb2',2) + line('M218 262L246 220','#317eb2',4)
        body += line(f'M{88+shift} 228H{165+shift}M{165+shift} 203V253','#9260ac',4)
        body += rect(173+shift,200,12,57,'#d6c8d7',radius=3) + text(105+shift,203,'G',29,'#9260ac')
        body += text(108+shift,289,'0 V' if not on else '合适栅压',25,'#76508d')
    write('mosfet','gate','黄铜机巧室 · 同一开关两种状态',body,'门槛≠充分导通；要查实际驱动条件','N沟道增强型低端开关功能示意，S接地。左侧G为0伏，D/S断开；右侧假定栅压足够且满足器件条件，D/S通道导通。栅极旁灰条表示绝缘，不画穿越电子；非器件内部剖面。')

    body = line('M336 97H568V269H336M336 97V130M336 222V274M336 310V335','#aab3ae',4)
    body += line('M336 130C306 130 306 153 336 153C306 153 306 176 336 176C306 176 306 199 336 199C306 199 306 222 336 222','#865b37',5)
    body += line('M336 310L365 280','#566963',5) + circle(336,274,5,'#fff','#566963',2) + circle(336,310,5,'#fff','#566963',2)
    # Rectifier symbol: anode below, cathode bar above; current goes upwards.
    body += '<path d="M549 183H587L568 151Z" fill="#fff9e9" stroke="#dc775d" stroke-width="4"/>' + line('M546 147H590','#dc775d',4)
    body += text(615,153,'K',27,'#ae5444') + text(615,192,'A',27,'#ae5444')
    body += line('M373 269H492','#dc775d',5,True) + line('M568 244V205','#dc775d',5,True) + line('M516 97H388','#dc775d',5,True)
    body += line('M336 109V125','#dc775d',5,True)
    body += text(230,183,'线圈',32,'#865b37') + text(493,226,'外部二极管',24,'#ae5444')
    body += text(197,306,'MOS 断开',29) + text(134,117,'约定电流',24,'#ae5444')
    write('mosfet','flyback','黄铜机巧室 · 关门后还有路',body,'续流绕过断口，仍沿原方向过线圈','MOS开关在下方断开。珊瑚色约定电流从线圈下端经右侧外部二极管的A到K、回到线圈上端再通过线圈。二极管K在上，A在下。闭环没有穿过下方MOS断口，线圈电流逐渐减小。')

    body = ''
    for x,label,value,fill in [(43,'电流平方','(1 A)²','#e5edf2'),(269,'导通电阻','0.1 Ω','#f0e4ca'),(495,'导通损耗','0.1 W','#f8e2d2')]:
        body += rect(x,113,182,150,fill,'#c4a777',12) + text(x+91,157,label,27) + text(x+91,226,value,38)
    body += text(247,204,'×',30,'#8a7153') + text(473,204,'=',30,'#8a7153')
    body += text(360,309,'P = I² × R',33,'#79533a') + text(360,337,'左边电流先平方；瓦数不是温度',24,'#786d5c')
    write('mosfet','heat','黄铜机巧室 · 一张发热任务卡',body,'已知例子：若换成 2 A，先自己算','合成持续导通例子：电流1安培，导通电阻假定0.1欧姆不变，损耗0.1瓦。按P=I平方乘R计算，没有把功率当作温度。把电流改为2安培的答案没有出现在图中。')


if __name__ == '__main__':
    capacitor()
    mosfet()
