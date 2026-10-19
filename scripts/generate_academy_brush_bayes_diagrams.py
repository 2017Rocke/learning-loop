#!/usr/bin/env python3
"""Generate original, static teaching diagrams with no external dependencies.

Brush: prism/light atelier. Bayes: evidence observatory.
The artwork is explanatory illustration, not a reconstruction or measured data.
Bayes counts are the lesson's explicitly synthetic product example.
"""
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FONT = 'system-ui, -apple-system, sans-serif'
INK = '#f2f1ff'
GOLD = '#e9c778'
ORANGE = '#ff9f77'
BLUE = '#8bcaff'


def text(x, y, value, size=28, fill=INK, anchor='middle', weight=600):
    return f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-family="{FONT}" font-size="{size}" font-weight="{weight}" fill="{fill}">{escape(str(value))}</text>'


def path(d, stroke, width=3, fill='none', extra=''):
    return f'<path d="{d}" stroke="{stroke}" stroke-width="{width}" fill="{fill}" stroke-linecap="round" stroke-linejoin="round" {extra}/>'


def star(x, y, size=5, color=GOLD):
    return path(f'M{x-size} {y}H{x+size}M{x} {y-size}V{y+size}',color,1.5)


def arrow(x1,y1,x2,y2,color='#a4dfef'):
    import math
    theta=math.atan2(y2-y1,x2-x1)
    bx=x2-10*math.cos(theta);by=y2-10*math.sin(theta)
    return path(f'M{x1} {y1}L{x2} {y2}',color,3)+path(f'M{bx-5*math.sin(theta)} {by+5*math.cos(theta)}L{x2} {y2}L{bx+5*math.sin(theta)} {by-5*math.cos(theta)}',color,3)


def lantern(x,y,scale=.6):
    return f'''<g transform="translate({x} {y}) scale({scale})">
{path('M-7-25V-33Q0-42 7-33V-25',GOLD,3)}
<path d="M-18-20L0-28L18-20L23 10L10 26H-10L-23 10Z" fill="#78cfbd" stroke="#c9efe3" stroke-width="2"/>
<path d="M-14-15L0-20L14-15L16 9L0 17L-16 9Z" fill="#d3f4c7"/>
{path('M-6-5V-2M7-5V-2','#375960',3)}{path('M-3 5Q1 9 5 5','#375960',2)}
<path d="M-8 27H8L6 32H-6Z" fill="{GOLD}"/>
</g>'''


def cup(x,y,s=1,color='#b8e5f3'):
    return f'''<g transform="translate({x} {y}) scale({s})"><path d="M-26-24H26L22 29Q0 41-22 29Z" fill="{color}" stroke="#e7f4ff" stroke-width="2"/>
<ellipse cy="-24" rx="26" ry="8" fill="#655382" stroke="#e0edf9" stroke-width="2"/>
{path('M27-17C57-23 59 22 25 19','#e4e4ff',6)}
<path d="M-16-10V19" stroke="#f7f7ff" stroke-opacity=".55" stroke-width="4" stroke-linecap="round"/>
</g>'''


def camera(x,y,s=1):
    return f'''<g transform="translate({x} {y}) scale({s})"><rect x="-23" y="-16" width="46" height="33" rx="6" fill="#967ace" stroke="#d5c4f8" stroke-width="2"/>
<path d="M-12-16L-7-23H9L13-16" fill="#af98dc"/><circle r="10" fill="#243250" stroke="#8ee2ee" stroke-width="3"/><circle cx="-3" cy="-3" r="3" fill="#dbf3ff"/></g>'''


def base(title,theme='brush'):
    midnight=theme=='bayes'
    bg='#142641' if midnight else '#28243f'
    edge='#35516b' if midnight else '#53466d'
    accents=GOLD if midnight else '#b4a1ed'
    body=f'<rect width="640" height="360" rx="24" fill="{bg}"/>'
    body+=f'<path d="M18 72H622M18 316H622" fill="none" stroke="{edge}" stroke-width="1.5"/>'
    body+=f'<path d="M18 40V18H40M600 18H622V40M622 320V342H600M40 342H18V320" fill="none" stroke="{accents}" stroke-opacity=".6" stroke-width="1.5"/>'
    # The guide is decorative and never a counting unit.
    body+=lantern(598,48,.42)
    body+=text(305,46,title,29,INK)
    for x,y,s in [(44,94,3),(592,287,3),(566,89,2)]:body+=star(x,y,s,accents)
    return body


def finish(name,filename,title,body):
    definitions='''<defs>
<radialGradient id="cloud-cyan"><stop stop-color="#8fe8ee" stop-opacity=".95"/><stop offset=".6" stop-color="#63c6d8" stop-opacity=".48"/><stop offset="1" stop-color="#63c6d8" stop-opacity="0"/></radialGradient>
<radialGradient id="cloud-violet"><stop stop-color="#c8adff" stop-opacity=".95"/><stop offset=".6" stop-color="#a27de2" stop-opacity=".5"/><stop offset="1" stop-color="#a27de2" stop-opacity="0"/></radialGradient>
<radialGradient id="cloud-red"><stop stop-color="#ffa39f" stop-opacity=".96"/><stop offset=".6" stop-color="#ec7d92" stop-opacity=".54"/><stop offset="1" stop-color="#ec7d92" stop-opacity="0"/></radialGradient>
<radialGradient id="cloud-blue"><stop stop-color="#7fcaff" stop-opacity=".95"/><stop offset=".6" stop-color="#579ff0" stop-opacity=".5"/><stop offset="1" stop-color="#579ff0" stop-opacity="0"/></radialGradient>
</defs>'''
    output=ROOT/'web'/'media'/f'{name}-academy'/filename
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 360" role="img" aria-labelledby="title"><title id="title">{escape(title)}</title>{definitions}{body}</svg>\n',encoding='utf-8')


def brush_capture():
    b=base('换个位置，收集新的观察线索')
    b+='<ellipse cx="159" cy="231" rx="100" ry="27" fill="#3c3456" stroke="#655681" stroke-dasharray="5 7"/>'
    b+=cup(159,165,.75)
    b+=path('M90 228L159 162L230 228','#779eb8',2,extra='stroke-dasharray="5 5"')
    b+=camera(82,234,.8)+camera(236,234,.8)
    b+=text(82,288,'位置 A',27,'#c2b0ed')+text(236,288,'位置 B',27,'#a0e5ed')
    b+=text(159,112,'杯子不动',27)
    b+=arrow(280,195,326,195)
    for x,label,dx,col in [(400,'照片 A',-19,'#c6afe9'),(548,'照片 B',19,'#9ddde4')]:
        b+=f'<rect x="{x-61}" y="116" width="122" height="143" rx="13" fill="#35334e" stroke="{col}" stroke-width="2"/>'
        b+=path(f'M{x} 131V240','#7884a9',8)
        b+=cup(x+dx,201,.6)
        b+=text(x,288,label,27,col)
    b+=text(320,344,'近物相对远景的位置发生变化',27)
    finish('brush','capture.svg','不同相机位置观察同一静止杯子：照片中的杯子相对远处标志发生位移，这是视差的示意；不是实际重建结果。',b)


def brush_projection():
    b=base('三维小云团，投成屏幕软光斑')
    b+='<ellipse cx="130" cy="178" rx="83" ry="56" fill="url(#cloud-cyan)" transform="rotate(-24 130 178)"/>'
    b+='<ellipse cx="127" cy="182" rx="65" ry="23" fill="none" stroke="#8de4e7" stroke-width="2" transform="rotate(-24 127 182)"/>'
    b+='<ellipse cx="127" cy="182" rx="30" ry="57" fill="none" stroke="#c1c0ee" stroke-width="2" transform="rotate(-24 127 182)"/>'
    b+=path('M69 135L299 179L62 224','#6a89aa',2,extra='stroke-dasharray="6 5"')
    b+=camera(299,179,1.1)
    b+=arrow(336,179,394,179)
    b+='<path d="M416 117L594 104V245L416 259Z" fill="#383551" stroke="#a194cc" stroke-width="2"/>'
    b+='<ellipse cx="529" cy="169" rx="58" ry="39" fill="url(#cloud-blue)" transform="rotate(-19 529 169)"/>'
    b+='<ellipse cx="482" cy="202" rx="56" ry="39" fill="url(#cloud-red)" transform="rotate(-19 482 202)"/>'
    b+=text(127,288,'三维高斯',27,'#a4e9ec')+text(299,288,'相机',27)+text(508,288,'屏幕合成',27,'#d1b6f4')
    b+=text(320,344,'软边 · 颜色 · 透明度 · 前后顺序',27)
    finish('brush','projection.svg','三维椭球形高斯通过相机投影成屏幕软边椭圆；红蓝光斑按前后与透明度合成。线条是投影关系，不是物理发光路径。',b)


def brush_training():
    b=base('训练：对照照片，反复修正')
    for x,y in [(45,90),(390,90),(390,218),(45,218)]:b+=f'<rect x="{x}" y="{y}" width="205" height="80" rx="15" fill="#35304e" stroke="#62527e" stroke-width="2"/>'
    b+='<ellipse cx="86" cy="126" rx="31" ry="20" fill="url(#cloud-cyan)"/><ellipse cx="104" cy="140" rx="25" ry="18" fill="url(#cloud-violet)"/>'
    b+=text(174,126,'高斯',27)+text(174,156,'参数',27)
    b+=cup(430,127,.55)+text(523,142,'渲染画面',27)
    b+='<rect x="406" y="231" width="53" height="52" rx="5" fill="#294458" stroke="#93c5df"/><rect x="466" y="231" width="53" height="52" rx="5" fill="#463951" stroke="#d7a5db"/>'
    b+=cup(430,254,.4)+cup(490,256,.36)
    b+=text(558,250,'比较',26)+text(558,280,'照片',26)
    for y,x in [(237,84),(255,112),(273,95)]:
        b+=path(f'M65 {y}H125','#8385ac',3)+f'<circle cx="{x}" cy="{y}" r="6" fill="#93e1e4"/>'
    b+=text(183,248,'按误差',26)+text(183,280,'修正',26)
    b+=arrow(268,131,374,131)+arrow(494,179,494,207)+arrow(375,259,269,259)+arrow(147,210,147,180)
    b+=text(320,203,'重复',27,'#c7b7ed')
    b+=text(320,344,'同一相机视角，才能对照',27)
    finish('brush','training.svg','闭环顺时针排列：高斯参数生成渲染画面，画面与同一视角照片比较，按误差修正参数，再重复。',b)


def brush_boundaries():
    b=base('逼真的画面，不等于实体模型')
    b+='<rect x="40" y="115" width="178" height="158" rx="17" fill="#373149" stroke="#8d79b1" stroke-width="2"/>'
    b+=cup(126,177,.85)
    # Small soft contributions identify the scene representation, not a watertight mesh.
    for x,y,rx in [(99,158,17),(147,187,20),(107,207,18),(141,151,15)]:b+=f'<ellipse cx="{x}" cy="{y}" rx="{rx}" ry="12" fill="url(#cloud-cyan)"/>'
    b+=text(129,255,'高斯场景',27)
    b+=path('M231 194H275V135H312M275 194V254H312','#a4dbe7',3)
    b+=arrow(300,135,317,135)+arrow(300,254,317,254)
    b+='<rect x="333" y="91" width="266" height="90" rx="14" fill="#28474f" stroke="#83cbc9" stroke-width="2"/>'
    b+='<rect x="351" y="108" width="55" height="44" rx="5" fill="#436a75" stroke="#b7edf1" stroke-width="2"/>'
    b+=cup(377,132,.35)+text(494,126,'展示 / 漫游',29)+text(494,160,'看外观',26,'#aedede')
    b+='<rect x="333" y="208" width="266" height="90" rx="14" fill="#40364f" stroke="#c6a3d9" stroke-width="2"/>'
    b+=path('M354 239L375 225L397 239V267L376 280L354 267ZM354 239L376 253L397 239M376 253V280','#c3a7ed',2)
    b+=text(497,243,'打印 / 测量',29)+text(497,279,'还需几何验证',26,'#e0c3e9')
    b+=text(320,344,'用途不同，验收证据也不同',27)
    finish('brush','boundaries.svg','高斯场景分成展示漫游与打印测量两条应用路径。展示主要检查外观；打印测量还需网格、尺度等几何验证。',b)


def dot_grid(x,y,bad,pitch=17,r=5.8):
    b=''
    for i in range(100):
        cx=x+(i%10)*pitch;cy=y+(i//10)*pitch
        b+=f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{ORANGE if i<bad else BLUE}"/>'
        if i<bad:
            b+=path(f'M{cx-2} {cy-2}L{cx+2} {cy+2}M{cx+2} {cy-2}L{cx-2} {cy+2}','#55372c',1.3)
    return b


def bayes_prior():
    b=base('调查开始前，先数清两类产品','bayes')
    b+='<circle cx="170" cy="186" r="112" fill="#1b3553" stroke="#bda262" stroke-width="3"/>'
    b+=path('M242 270L267 298','#bda262',11)
    b+=dot_grid(94,110,1)
    b+=text(449,135,'× 坏件',28,ORANGE)+text(449,179,'100',43,ORANGE)
    b+=text(449,227,'✓ 正常件',28,BLUE)+text(449,272,'9,900',43,BLUE)
    b+=text(320,344,'每点 = 100 件；共 10,000 件',27,GOLD)
    finish('bayes','prior.svg','教学假设：一百颗计数点，每点代表一百件。一颗带叉橙点为100坏件，九十九颗蓝点为9900正常件。装饰向导不参与计数。',b)


def bayes_branches():
    b=base('沿两条线索，分别算出报警数','bayes')
    for y,c in [(100,ORANGE),(213,BLUE)]:
        b+=f'<rect x="33" y="{y}" width="174" height="79" rx="12" fill="#1e3550" stroke="{c}" stroke-width="2"/>'
        b+=f'<path d="M415 {y}H599V{y+79}H415L402 {y+40}Z" fill="#233b58" stroke="{c}" stroke-width="2"/>'
        b+=arrow(220,y+42,391,y+42,c)
    b+=text(120,133,'× 坏件',26,ORANGE)+text(120,168,'100',36,ORANGE)
    b+=text(306,124,'90% 报警',26,ORANGE)
    b+=text(507,135,'90',37,ORANGE)+text(507,169,'真报警',26,ORANGE)
    b+=text(120,245,'✓ 正常',26,BLUE)+text(120,280,'9,900',36,BLUE)
    b+=text(306,236,'5% 误报',26,BLUE)
    b+=text(507,248,'495',37,BLUE)+text(507,282,'误报警',26,BLUE)
    b+=text(320,344,'两类产品，都可能让铃铛响',27,GOLD)
    finish('bayes','branches.svg','教学假设下的两条计数路径：100坏件乘90%得到90真报警；9900正常件乘5%得到495误报警。框大小不表示数量比例。',b)


def bayes_posterior():
    b=base('听到报警，就换一组来数','bayes')
    b+=text(157,109,'× 真报警 90',27,ORANGE)+text(459,109,'✓ 误报警 495',27,BLUE)
    b+='<rect x="62" y="126" width="516" height="108" rx="20" fill="#213b59" stroke="#d6b66a" stroke-width="2"/>'
    # 90/585 = 2/13. Width 455 gives exactly 70 orange and 385 blue units.
    b+='<rect x="90" y="149" width="455" height="39" rx="0" fill="#8bcaff"/><rect x="90" y="149" width="70" height="39" fill="#ff9f77"/>'
    b+=path('M125 121V140',ORANGE,2)+path('M439 121V140',BLUE,2)
    b+=text(320,219,'全部报警：90 + 495 = 585',27,GOLD)
    b+=text(320,289,'90 ÷ 585 ≈ 15.4%',40)
    b+=text(320,344,'条形宽度按报警件数绘制',26,GOLD)
    finish('bayes','posterior.svg','仅在585个报警件中计算：90真报警加495误报警。条形宽度按90比495绘制，坏件比例90除以585约15.4%。',b)


def bayes_transfer():
    b=base('同一报警器，换一批产品','bayes')
    b+=text(320,107,'检出 90% · 误报 5% 不变',27,GOLD)
    for x in [171,469]:
        b+=f'<rect x="{x-105}" y="124" width="210" height="177" rx="18" fill="#203854" stroke="#7686a2" stroke-width="2"/>'
    b+=dot_grid(110,139,1,pitch=13.5,r=4.6)+dot_grid(408,139,10,pitch=13.5,r=4.6)
    b+=text(171,297,'坏件 1%',29,ORANGE)+text(469,297,'坏件 10%',29,ORANGE)
    b+=arrow(291,206,347,206,GOLD)
    b+=text(320,344,'报警后的比例：先猜，再算',27,GOLD)
    finish('bayes','transfer.svg','两组各100颗点，每点代表100件。左组1颗带叉橙点和99颗蓝点；右组10颗带叉橙点和90颗蓝点。坏件率由1%变10%，检出90%及误报5%不变，尚未展示后验结果。',b)


if __name__ == '__main__':
    for draw in [brush_capture,brush_projection,brush_training,brush_boundaries,bayes_prior,bayes_branches,bayes_posterior,bayes_transfer]:
        draw()
    print('Generated eight original Brush/Bayes academy teaching diagrams.')
