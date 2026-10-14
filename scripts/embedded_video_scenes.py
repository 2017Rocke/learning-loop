"""Original animated circuit diagrams, used only by the offline video author.

Moving markers indicate conventional current, not electron speed. Circuit
waveforms and numerical examples are explicitly idealized teaching models.
The helper functions are supplied by generate_course_videos, avoiding a second
renderer or any runtime dependencies in the Android course package.
"""
import math


class EmbeddedScenes:
    def __init__(self, text, box, arrow, mascot, ease, mix, colors):
        self.text, self.box, self.arrow = text, box, arrow
        self.mascot, self.ease, self.mix, self.c = mascot, ease, mix, colors

    def wire(self, d, points, color='blue', width=5):
        d.line(points, fill=self.c[color], width=width, joint='curve')

    def flow(self, d, points, t, color='blue', count=7, speed=.18, radius=6):
        lengths = [math.dist(a, b) for a, b in zip(points, points[1:])]
        total = sum(lengths)
        for n in range(count):
            distance = ((t * speed + n / count) % 1) * total
            for a, b, length in zip(points, points[1:], lengths):
                if distance <= length:
                    ratio = distance / length if length else 0
                    x, y = self.mix(a[0], b[0], ratio), self.mix(a[1], b[1], ratio)
                    d.ellipse((x-radius, y-radius, x+radius, y+radius), fill=self.c[color])
                    break
                distance -= length

    def capacitor(self, d, scene, u, t):
        text, box, arrow, c = self.text, self.box, self.arrow, self.c
        if scene == 0:
            box(d, (70,158,365,354), 'bluesoft')
            text(d, (217,186), '电容剖面 · 示意', 29)
            d.rectangle((156,220,172,310), fill=c['purple'])
            d.rectangle((266,220,282,310), fill=c['blue'])
            d.rectangle((182,220,256,310), fill=c['purplesoft'])
            for y in (238,263,288):
                text(d,(163,y),'+',23,c['white']); text(d,(274,y),'−',23,c['white'])
                arrow(d,(190,y),(246,y),'purple',3)
            text(d,(220,334),'绝缘层 · 电场储能',24)
            box(d,(515,184,872,327),'redsoft')
            self.mascot(d,580,247,t,1.15)
            text(d,(727,226),'芯片开始忙碌',31)
            text(d,(727,277),'电流需求突然增大',26)
            # A visibly growing demand bar represents a load step, not charge
            # crossing the capacitor's insulating dielectric.
            q=self.ease((u-.28)/.35)
            box(d,(535,343,850,363),'bluesoft',radius=7)
            box(d,(535,343,535+315*(.2+.8*q),363),'red',radius=7)
            text(d,(480,385),'电场储能示意；不是无限供电的电池',24,c['muted'])
        elif scene == 1:
            supply=[(130,210),(790,210),(790,337),(130,337)]
            self.wire(d,supply,'blue',4)
            box(d,(61,239,197,308),'bluesoft'); text(d,(129,273),'电源',31)
            self.wire(d,[(130,210),(130,239)],'blue');self.wire(d,[(130,308),(130,337)],'blue')
            box(d,(697,234,884,311),'redsoft');text(d,(790,270),'芯片',35)
            # Cap is connected across the same rails as the chip, not in series.
            self.wire(d,[(537,210),(537,257)],'purple')
            self.wire(d,[(537,287),(537,337)],'purple')
            d.line((510,257,564,257),fill=c['purple'],width=7)
            d.line((510,287,564,287),fill=c['purple'],width=7)
            text(d,(462,272),'近端 C',27,c['purple'])
            phase=u<.65
            if phase:
                self.flow(d,[(537,248),(537,210),(790,210),(790,337),(537,337),(537,295)],t,'green')
            else:
                self.flow(d,[(130,215),(537,215),(537,248)],t,'blue',4)
                self.flow(d,[(537,295),(537,332),(130,332),(130,310)],t,'blue',4)
            text(d,(480,172),'需求突增：近端短时补电' if phase else '负载回落：电源补回能量',31)
            text(d,(342,229),'走线也有电感',22,c['muted'])
            text(d,(480,380),'圆点表示常规电流方向；电容内部未画导电通路',22,c['muted'])
        elif scene == 2:
            box(d,(60,156,424,363),'bluesoft')
            for i,line in enumerate(['缺口电流 20 mA','持续 10 μs','有效电容 10 μF']):
                text(d,(242,194+56*i),line,32)
            q=self.ease((u-.14)/.68)
            self.wire(d,[(498,190),(498,326),(887,326)],'muted',3)
            text(d,(548,165),'电压 V',23);text(d,(859,350),'时间 t',23)
            d.line((511,204,860,204),fill='#D2D9E1',width=2)
            endx=520+325*q; endy=204+93*q
            d.line((520,204,endx,endy),fill=c['red'],width=5)
            d.ellipse((endx-7,endy-7,endx+7,endy+7),fill=c['red'])
            if q>.96: text(d,(711,248),'下降 20 mV',30,c['red'])
            text(d,(480,384),'ΔV = I × Δt / C · 忽略补给与 ESR / ESL',25,c['muted'])
        else:
            for i,(title,subtitle,color) in enumerate([
                ('有效容量','电压下实际有多少','bluesoft'),
                ('ESR / ESL','内部电阻与电感','purplesoft'),
                ('近端布局','缩短供电回路','mint')]):
                x=62+i*300;box(d,(x,162,x+270,286),color)
                text(d,(x+135,197),title,32);text(d,(x+135,247),subtitle,25)
            # Expanding time window poses the transfer question without drawing
            # the new voltage drop or disclosing its answer.
            q=self.ease(u/.7)
            self.wire(d,[(153,334),(153+650*q,334)],'purple',9)
            text(d,(480,314),'只把时间从 10 μs 改成 100 μs',29)
            text(d,(480,374),'先预测：电压下降会怎样变？',30,c['purple'])

    def mos_circuit(self,d,t,on=True,freewheel=False,phase=0):
        text, box, c = self.text,self.box,self.c
        # Conventional current: supply -> load -> D -> S -> return. The
        # flyback path instead traverses D -> diode A/K -> load top -> load.
        self.wire(d,[(360,178),(610,178),(610,206)],'blue')
        box(d,(536,206,684,265),'bluesoft');text(d,(610,235),'感性负载',25)
        self.wire(d,[(610,265),(610,303)],'blue')
        self.wire(d,[(610,348),(610,370),(195,370)],'blue')
        text(d,(427,157),'+5 V',27,c['blue']);text(d,(646,286),'D',25)
        box(d,(568,303,650,348),'mint' if on else 'purplesoft')
        text(d,(609,326),'通' if on else '断',28)
        text(d,(654,358),'S',25)
        box(d,(66,241,276,311),'purplesoft');text(d,(171,263),'单片机 GPIO',26)
        text(d,(171,292),'3.3 V 控制',23)
        self.wire(d,[(276,276),(493,276),(493,326),(548,326)],'purple',4)
        d.line((552,306,552,346),fill=c['purple'],width=5)
        text(d,(523,347),'G',24,c['purple'])
        self.wire(d,[(195,311),(195,370)],'blue',3)
        self.wire(d,[(195,370),(78,370)],'blue',3)
        text(d,(141,346),'电源负极',21,c['blue'])
        d.ellipse((72,364,84,376),fill=c['blue'])
        text(d,(441,389),'共同参考地 · 回到电源负极',21,c['muted'])
        if on:
            self.flow(d,[(360,178),(610,178),(610,303),(610,348),(610,370),(78,370)],t,'blue',7)
        if freewheel:
            self.wire(d,[(610,281),(813,281),(813,178),(610,178)],'red',4)
            # Vertical diode: triangle points to the cathode bar at the top.
            d.polygon([(801,242),(825,242),(813,218)],fill=c['red'])
            d.line((796,214,830,214),fill=c['red'],width=4)
            text(d,(862,202),'K 负极',23,c['red']);text(d,(862,263),'A 正极',23,c['red'])
            if not on:
                self.flow(d,[(610,269),(610,281),(813,281),(813,178),(610,178),(610,269)],t,'red',6,
                          speed=.16*(1-.7*phase),radius=max(2,6*(1-.65*phase)))

    def mosfet(self,d,scene,u,t):
        text,box,arrow,c=self.text,self.box,self.arrow,self.c
        if scene==0:
            self.mos_circuit(d,t,on=u>.27)
            text(d,(781,336),'控制 ≠ 供电',28,c['purple'])
        elif scene==1:
            box(d,(64,157,408,354),'purplesoft')
            text(d,(235,189),'栅极像小电容',31)
            q=.12+.88*self.ease((u-.1)/.7)
            box(d,(108,247,364,278),'white',radius=9)
            box(d,(108,247,108+256*q,278),'purple',radius=9)
            text(d,(236,225),'充电 → Vgs 上升',26)
            text(d,(236,318),'Vgs = 栅极电压 − 源极电压',22)
            arrow(d,(424,256),(489,256))
            box(d,(511,157,898,355),'mint')
            text(d,(704,188),'选型看哪一项？',30)
            text(d,(704,238),'阈值：刚开始微弱导通',27)
            text(d,(704,286),'Rds(on)：指定 Vgs 下的电阻',24)
            text(d,(704,326),'还要核对电流与温度条件',23)
            text(d,(480,382),'切换要充放电；3.3 V GPIO 不保证任意管子充分导通',23,c['muted'])
        elif scene==2:
            box(d,(58,155,521,369),'bluesoft');text(d,(290,181),'PWM：按时间开 / 关',29)
            pts=[(82,309)]
            for i in range(4):
                x=82+i*101;pts.extend([(x,309),(x,236),(x+50,236),(x+50,309),(x+101,309)])
            d.line(pts,fill=c['purple'],width=4)
            cx=82+(t*.28%1)*404
            d.line((cx,222,cx,323),fill=c['red'],width=3)
            text(d,(292,344),'占空比 ≠ 电机转速百分比',25)
            box(d,(550,156,903,367),'redsoft')
            text(d,(727,185),'另一项检查：发热',28)
            text(d,(727,235),'合成例：1 A，0.1 Ω',28)
            text(d,(727,282),'P = I²R = 0.1 W',31)
            text(d,(727,330),'仅导通损耗 · 忽略温升',23)
            text(d,(480,385),'波形是控制信号；不是电机实测电流或转速',24,c['muted'])
        else:
            self.mos_circuit(d,t,on=u<.22,freewheel=True,phase=max(0,(u-.22)/.78))
            text(d,(370,205),'开通' if u<.22 else '关断 · 续流',26,c['red'] if u>=.22 else c['blue'])
            text(d,(380,233),'电流同向衰减' if u>=.22 else '二极管反偏',23,c['muted'])
            text(d,(830,340),'方框是开关示意',19,c['muted'])
            text(d,(823,366),'续流走外部回路',21,c['red'])
