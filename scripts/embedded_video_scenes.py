"""Original animated circuit diagrams, used only by the offline video author.

Blue minus-marked dots in the first four capacitor scenes represent electrons
in metal; they make finite, one-way trips. Fixed directional arrows elsewhere
represent conventional current. Field shading is never a particle path.
All motion and waveforms are idealized teaching models, not real speed or counts.
The helper functions are supplied by generate_course_videos, avoiding a second
renderer or any runtime dependencies in the Android course package.
The original Star Lantern Workshop skin belongs only to these subject films;
decorative lights stay outside the circuit panel and never imply current flow.
"""
import math


# Shared by the drawing and the physical-boundary regression check. Plates
# occupy y=208..232 and 304..328; the entire moving symbol stays out of this gap.
CAP_DIELECTRIC = (460, 244, 660, 292)
ELECTRON_RADIUS = 7
CHARGE_OUT = ((520, 208), (520, 177), (180, 177), (180, 231))
CHARGE_IN = ((180, 312), (180, 366), (520, 366), (520, 328))
DISCHARGE = ((620, 328), (800, 328), (800, 208), (620, 208))


def path_point(points, fraction):
    """Position on a finite path, including both ends; never wraps around."""
    lengths = [math.dist(a, b) for a, b in zip(points, points[1:])]
    distance = max(0, min(1, fraction)) * sum(lengths)
    for a, b, length in zip(points, points[1:], lengths):
        if distance <= length and length:
            ratio = distance / length
            return (a[0] + (b[0]-a[0])*ratio, a[1] + (b[1]-a[1])*ratio)
        distance -= length
    return points[-1]


def electron_positions(points, progress, count=6):
    """Each identity is emitted once, arrives once, then leaves the scene.

    No modulo: resetting an open path can imply that an electron crosses an
    insulator between the path's end and start. Counts/speed are schematic.
    """
    positions = []
    for identity in range(count):
        fraction = (progress - (.08 + identity*.085)) / .32
        if 0 <= fraction <= 1:
            positions.append((identity, *path_point(points, fraction)))
    return positions


class EmbeddedScenes:
    def __init__(self, text, box, arrow, mascot, ease, mix, colors):
        self._text, self._box, self._arrow = text, box, arrow
        self.ease, self.mix = ease, mix
        # Copy, never mutate the other courses' palette. Scientific roles keep
        # their established colors, with darker strokes on warm pale panels.
        self.c = dict(colors, night='#17233F', nightsoft='#233251',
                      brass='#C5A367', brasslight='#E8CB8E', parchment='#FFF4DB',
                      paper='#FFFAED', ink='#24324C', muted='#5A6374',
                      purple='#7352A0', purplesoft='#EEE5F3',
                      blue='#2775A6', bluesoft='#E5F0F3',
                      green='#287858', mint='#C7EAD8',
                      red='#BF514A', redsoft='#F8E4D8')

    def text(self, d, pos, value, size=30, fill=None, anchor='mm'):
        self._text(d,pos,value,size,fill or self.c['ink'],anchor)

    def box(self, d, bounds, fill='white', outline=None, radius=22, width=2):
        x1,y1,x2,y2=bounds
        panel=x2-x1>100 and y2-y1>55
        if panel and outline is None:
            outline=self.c['brass']
            width=1
        self._box(d,bounds,self.c.get(fill,fill),self.c.get(outline,outline),min(radius,14),width)

    def arrow(self, d, a, b, color='purple', width=5):
        self._arrow(d,a,b,self.c.get(color,color),width)

    def mascot(self, d, x, y, t, scale=.8):
        """An original mint crystal lantern with a floating brass ring."""
        c=self.c; y+=math.sin(t*1.9)*3; s=scale
        # Back and front ring arcs establish depth without any borrowed crest.
        ring=(x-33*s,y+1*s,x+33*s,y+17*s)
        d.arc(ring,180,360,fill=c['brass'],width=max(1,round(3*s)))
        crystal=[(x,y-31*s),(x+21*s,y-5*s),(x+15*s,y+22*s),
                 (x,y+34*s),(x-15*s,y+22*s),(x-21*s,y-5*s)]
        d.polygon(crystal,fill='#A5DCC4',outline='#456F69')
        d.polygon([(x,y-31*s),(x,y+34*s),(x-15*s,y+22*s),(x-21*s,y-5*s)],fill='#CFF4DD')
        d.line([(x,y-31*s),(x+2*s,y-5*s),(x,y+34*s)],fill='#EAFCE8',width=max(1,round(2*s)))
        d.line([(x-21*s,y-5*s),(x+2*s,y-5*s),(x+21*s,y-5*s)],fill='#7ABBA4',width=max(1,round(s)))
        for dx in (-7,7):
            d.ellipse((x+(dx-1.7)*s,y+1*s,x+(dx+1.7)*s,y+5*s),fill=c['ink'])
        d.arc((x-5*s,y+5*s,x+5*s,y+13*s),0,180,fill=c['ink'],width=max(1,round(2*s)))
        d.arc(ring,0,180,fill=c['brasslight'],width=max(1,round(3*s)))

    def frame(self, d, header, title, scene, total, p, t, lines):
        """A star-lit study around an unobstructed, high-contrast work surface."""
        c=self.c
        d.rounded_rectangle((12,12,948,528),19,outline=c['brass'],width=1)
        d.rounded_rectangle((19,19,941,521),15,outline='#384561',width=1)
        # Small deterministic glints are confined to the frame, never circuits.
        for n,(x,y) in enumerate([(30,38),(643,29),(814,85),(931,44),(24,188),
                                   (938,276),(24,353),(935,463),(35,510),(925,510)]):
            r=1.2+1.0*(.5+.5*math.sin(t*1.3+n*1.7))
            color=c['brasslight'] if n%3 else '#B6DDD1'
            d.line((x-r,y,x+r,y),fill=color,width=1)
            d.line((x,y-r,x,y+r),fill=color,width=1)
        # A round-arched alcove and modest bookshelf suggest a study, without
        # school insignia, a franchise character, or replacing physical labels.
        d.rounded_rectangle((841,21,920,120),39,fill=c['nightsoft'],outline=c['brass'],width=1)
        d.line((847,118,914,118),fill=c['brass'],width=2)
        self.mascot(d,880,67,t,.92)
        for n,(height,color) in enumerate([(28,'#405F71'),(36,'#71634F'),(31,'#47746D'),
                                           (38,'#625A80'),(29,'#806352')]):
            x=701+n*19
            d.rounded_rectangle((x,59-height,x+14,59),2,fill=color)
            d.line((x+4,63-height,x+10,63-height),fill=c['brasslight'],width=1)
        d.line((692,62,802,62),fill=c['brass'],width=2)
        self.text(d,(44,29),header,28,c['brasslight'],anchor='la')
        self.text(d,(44,76),title,34,c['parchment'],anchor='la')
        for i in range(total):
            x=730+i*24
            d.ellipse((x,111,x+10,121),fill=c['brasslight'] if i<=scene else '#4E5770')
        d.rounded_rectangle((30,132,930,402),18,fill=c['parchment'],outline=c['brass'],width=2)
        d.rounded_rectangle((35,137,925,397),14,outline='#E7D4AE',width=1)
        # A separate dark caption strip preserves the 23-character line budget.
        d.rounded_rectangle((45,419,915,508),15,fill='#111C33',outline='#48506A',width=1)
        for i,value in enumerate(lines):
            self.text(d,(480,438+i*42),value,34,c['parchment'])
        d.rounded_rectangle((44,526,916,532),3,fill='#3E4861')
        d.rounded_rectangle((44,526,44+872*p,532),3,fill=c['brasslight'])

    def wire(self, d, points, color='blue', width=5):
        d.line(points, fill=self.c[color], width=width, joint='curve')

    def electrons(self, d, points, progress):
        for _, x, y in electron_positions(points, progress):
            self.electron(d, x, y)

    def electron(self, d, x, y):
        r = ELECTRON_RADIUS
        d.ellipse((x-r, y-r, x+r, y+r), fill=self.c['blue'])
        d.line((x-4, y, x+4, y), fill=self.c['white'], width=2)

    def current(self, d, points, t, color='green', count=5, strength=1):
        """Fixed, gently pulsing arrows: direction symbols, never particles."""
        shade = self.mix(.45, .95, strength)*(.92+.08*math.sin(t*2))
        # Arrow size changes with current strength, not the direction/location.
        half = 6 + 7*shade
        for i in range(count):
            fraction = (i+.5)/count
            a = path_point(points, max(0, fraction-.018))
            b = path_point(points, min(1, fraction+.018))
            x, y = path_point(points, fraction)
            angle = math.atan2(b[1]-a[1], b[0]-a[0])
            self.arrow(d, (x-half*math.cos(angle), y-half*math.sin(angle)),
                       (x+half*math.cos(angle), y+half*math.sin(angle)), color, 4)

    def plates(self, d, charge=0, field=False):
        c = self.c
        d.rectangle((460,208,660,232), fill=c['purple'])
        d.rectangle((460,304,660,328), fill=c['blue'])
        d.rectangle(CAP_DIELECTRIC, fill=c['purplesoft'], outline='#BAA6CB', width=2)
        self.text(d, (560,267), '绝缘层', 29, c['purple'])
        # Field is a stationary violet background cue. Never animate particles
        # or solid current arrows between the plates.
        if field:
            for x in (475,645):
                for y in range(237,299,10):
                    d.line((x,y,x,y+4),fill='#AB8EBB',width=2)
        for i in range(round(charge*5)):
            x = 480+40*i
            self.text(d, (x,219), '+', 22, c['white'])
            self.electron(d, x,316)

    def battery(self, d):
        self.box(d,(125,231,235,312),'bluesoft')
        self.text(d,(180,267),'电源',29)
        self.text(d,(212,219),'+',28,self.c['purple'])
        self.text(d,(212,326),'−',28,self.c['blue'])

    def capacitor(self, d, scene, u, t):
        text, box, c = self.text, self.box, self.c
        if scene == 0:
            self.plates(d, charge=0)
            # Both plates contain electrons even before charging; the total
            # positive lattice charge is omitted from this structural picture.
            for x in (485,535,585,635):
                self.electron(d,x,220); self.electron(d,x,316)
            text(d,(240,178),'先认三层',34)
            text(d,(256,220),'上面：金属板',29)
            text(d,(256,267),'中间：绝缘材料',29,c['purple'])
            text(d,(256,316),'下面：金属板',29)
            text(d,(775,220),'蓝点带 −',27,c['blue'])
            text(d,(775,259),'表示电子',27,c['blue'])
            text(d,(775,313),'不能穿过绝缘层',25,c['red'])
            text(d,(480,374),'只画部分电子；未充电时，两板整体不带电',24,c['muted'])
        elif scene == 1:
            self.wire(d,CHARGE_OUT,'blue',4); self.wire(d,CHARGE_IN,'blue',4)
            self.battery(d)
            self.plates(d,charge=.6*self.ease(u/.85),field=True)
            self.electrons(d,CHARGE_OUT,u); self.electrons(d,CHARGE_IN,u)
            text(d,(342,153),'从上板取走电子',26,c['blue'])
            text(d,(760,218),'上板：电子少',28,c['purple'])
            text(d,(760,255),'带正电 +',27,c['purple'])
            text(d,(760,315),'下板：电子多 −',27,c['blue'])
            text(d,(480,389),'两条外线同时移动；中间始终绝缘',27)
        elif scene == 2:
            q = .6+.4*(1-math.exp(-5*u))
            self.wire(d,CHARGE_OUT,'blue',3); self.wire(d,CHARGE_IN,'blue',3)
            self.battery(d); self.plates(d,charge=q,field=True)
            # The bars illustrate approaching voltages, not a timed switch.
            text(d,(784,165),'电压对比（示意）',24)
            text(d,(784,203),'电源：保持不变',23)
            box(d,(694,224,884,241),'purple',radius=3)
            text(d,(784,272),'电容：逐渐接近',23)
            box(d,(694,293,884,310),'purplesoft',radius=3)
            box(d,(694,293,694+190*q,310),'blue',radius=3)
            text(d,(784,345),'推动充电的差值 ↓',23,c['red'])
            text(d,(480,389),'理想直流稳态：充电流趋近 0，电荷仍保留',25)
        elif scene == 3:
            self.plates(d,charge=1-self.ease(u),field=u<.95)
            # Supply is visibly separate; only the external load closes the
            # path between plates. Electrons go lower -> load -> upper.
            box(d,(79,220,293,316),'bluesoft')
            text(d,(186,248),'电源已断开',29)
            text(d,(186,289),'不再接在板上',23,c['muted'])
            self.wire(d,DISCHARGE,'blue',4)
            box(d,(747,247,853,291),'redsoft',radius=7)
            text(d,(800,268),'负载',27)
            self.electrons(d,DISCHARGE,u)
            text(d,(560,172),'少电子的一板',27,c['purple'])
            text(d,(560,357),'多电子的一板',27,c['blue'])
            text(d,(480,389),'电子沿外线经负载返回；电场逐渐减弱',27)
        else:
            # This scene explicitly switches representations. Conventional
            # current uses fixed green arrows, with no dot respawning at plates.
            rail_top, rail_bottom = 208,344
            self.wire(d,[(155,rail_top),(802,rail_top),(802,rail_bottom),(155,rail_bottom)],'blue',3)
            box(d,(77,245,230,309),'bluesoft');text(d,(154,277),'电源',30)
            self.wire(d,[(155,rail_top),(155,245)],'blue',3)
            self.wire(d,[(155,309),(155,rail_bottom)],'blue',3)
            self.wire(d,[(480,rail_top),(480,238)],'purple',4)
            self.wire(d,[(480,306),(480,rail_bottom)],'purple',4)
            d.line((442,238,518,238),fill=c['purple'],width=8)
            d.line((442,306,518,306),fill=c['blue'],width=8)
            text(d,(362,271),'近端电容',27,c['purple'])
            text(d,(480,272),'绝缘',20,c['muted'])
            box(d,(727,244,878,310),'redsoft');text(d,(802,277),'芯片',32)
            phase = u < .76
            if phase:
                path=[(480,232),(480,rail_top),(802,rail_top),(802,rail_bottom),(480,rail_bottom),(480,312)]
                self.current(d,path,t,'green',7)
                text(d,(480,167),'需求突增：近端电容暂时补给',30)
            else:
                self.current(d,[(155,rail_top),(480,rail_top),(480,232)],t,'green',3)
                self.current(d,[(480,312),(480,rail_bottom),(155,rail_bottom),(155,309)],t,'green',3)
                text(d,(480,167),'随后：电源补回电容的能量',30)
            text(d,(480,383),'绿色箭头＝约定电流；与金属电子方向相反',25,c['green'])

    def mos_circuit(self,d,t,on=True,freewheel=False,phase=0):
        text, box, c = self.text,self.box,self.c
        self.wire(d,[(360,178),(610,178),(610,206)],'blue')
        box(d,(536,206,684,265),'bluesoft');text(d,(610,235),'线圈负载',25)
        self.wire(d,[(610,265),(610,303)],'blue')
        self.wire(d,[(610,348),(610,370),(195,370)],'blue')
        text(d,(427,157),'电源 +',27,c['blue']);text(d,(646,286),'D',25)
        box(d,(568,303,650,348),'mint' if on else 'purplesoft')
        text(d,(609,326),'通' if on else '断',28)
        text(d,(654,358),'S',25)
        box(d,(66,241,276,311),'purplesoft');text(d,(171,263),'控制器',29)
        text(d,(171,292),'小引脚发令',23)
        self.wire(d,[(276,276),(493,276),(493,326),(548,326)],'purple',4)
        d.line((552,306,552,346),fill=c['purple'],width=5)
        text(d,(523,347),'G',24,c['purple'])
        self.wire(d,[(195,311),(195,370),(78,370)],'blue',3)
        text(d,(141,346),'电源负极',21,c['blue'])
        d.ellipse((72,364,84,376),fill=c['blue'])
        text(d,(390,389),'共地 · 箭头为约定电流',23,c['muted'])
        if on:
            self.current(d,[(360,178),(610,178),(610,303),(610,348),(610,370),(78,370)],t,'blue',7)
        if freewheel:
            self.wire(d,[(610,281),(813,281),(813,178),(610,178)],'red',4)
            d.polygon([(801,242),(825,242),(813,218)],fill=c['red'])
            d.line((796,214,830,214),fill=c['red'],width=4)
            text(d,(862,202),'K',25,c['red']);text(d,(862,263),'A',25,c['red'])
            if not on:
                self.current(d,[(610,269),(610,281),(813,281),(813,178),(610,178),(610,269)],t,'red',6,strength=1-.8*phase)

    def mosfet(self,d,scene,u,t):
        text,box,arrow,c=self.text,self.box,self.arrow,self.c
        if scene==0:
            self.mos_circuit(d,t,on=u>.27)
            text(d,(781,322),'G 管控制',28,c['purple'])
            text(d,(781,362),'D / S 过负载电流',23,c['blue'])
        elif scene==1:
            # Gate charge is indicated on the external metal, never across its
            # insulating layer. Channel response is a separate labelled panel.
            text(d,(260,171),'G：先充电，再放电',29)
            self.wire(d,[(86,265),(333,265)],'purple',4)
            d.rectangle((333,213,349,320),fill=c['purple'])
            d.rectangle((366,213,418,320),fill=c['purplesoft'],outline='#BAA6CB',width=2)
            text(d,(391,242),'绝',23,c['purple']);text(d,(391,278),'缘',23,c['purple'])
            charging=u<.55
            arrow(d,(126,265) if charging else (293,265),(293,265) if charging else (126,265),'purple',5)
            text(d,(210,313),'箭头：约定电流',25,c['purple'])
            text(d,(260,359),'电荷不穿过绝缘层',25)
            box(d,(474,184,900,341),'mint')
            text(d,(688,220),'控制量：G 与 S 的电压差',27)
            text(d,(688,268),'名字叫「栅源电压」',29)
            text(d,(688,313),'变化后，通道随之变化',25)
            text(d,(480,386),'刚到门槛 ≠ 能带好负载；还需查驱动条件',24,c['muted'])
        elif scene==2:
            text(d,(480,165),'一轮中，打开的时间占多少？',30)
            x0,yhigh,ylow,period=110,242,318,230
            duty=.30 if u<.5 else .65
            # Change only duty between the two examples; period stays fixed.
            pts=[(x0,ylow)]
            for i in range(3):
                x=x0+i*period
                pts.extend([(x,ylow),(x,yhigh),(x+period*duty,yhigh),(x+period*duty,ylow),(x+period,ylow)])
            d.line(pts,fill=c['purple'],width=5)
            text(d,(74,yhigh),'开',27,c['green']);text(d,(74,ylow),'关',27)
            for i in range(3):
                x=x0+i*period
                d.line((x,343,x+period,343),fill=c['blue'],width=2)
                for xx in (x,x+period): d.line((xx,337,xx,349),fill=c['blue'],width=2)
            text(d,(225,366),'一轮（周期）',24,c['blue'])
            text(d,(682,210),'打开时间较短' if u<.5 else '把打开时间加长',27,c['purple'])
            text(d,(640,374),'占空比 ≠ 转速百分比',27,c['muted'])
        else:
            self.mos_circuit(d,t,on=u<.16,freewheel=True,phase=max(0,(u-.16)/.84))
            text(d,(370,205),'开通' if u<.16 else '关断 → 续流',26,c['red'] if u>=.16 else c['blue'])
            text(d,(380,233),'电流同向减小' if u>=.16 else '二极管不导通',23,c['muted'])
            text(d,(812,335),'不走 MOS 断口',24,c['red'])
            text(d,(812,369),'沿外部回路返回',23,c['red'])
