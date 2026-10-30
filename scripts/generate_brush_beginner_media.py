#!/usr/bin/env python3
"""Make original beginner Brush diagrams and an optional narrated film.

Uses existing Pillow/FFmpeg only; never installs tools, contacts a service,
executes upstream code, or changes learner records. The cup is synthetic.
Its simple pinhole projection and depth-sorted alpha blending illustrate the
idea; they are not Brush's anisotropic, differentiable renderer. The fitting
scene computes image MSE and finite-difference steps for ONE handle position.
It is explicitly a synthetic example, not a measured reconstruction result.
"""
from __future__ import annotations

import argparse
import array
from functools import lru_cache
from html import escape
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import wave

from PIL import Image, ImageDraw, ImageFont, ImageChops, ImageStat

ROOT = Path(__file__).resolve().parents[1]
W, H, FPS, RATE = 960, 540, 15, 24000
BG, PANEL, INK = '#231d38', '#30283f', '#f5f1ff'
CYAN, PURPLE, GOLD = '#89e2df', '#c7aff3', '#efd194'
FONT = 'PingFang SC,Noto Sans CJK SC,Microsoft YaHei,sans-serif'
NAMES = ['capture', 'representation', 'projection', 'fitting', 'novel-view']
TITLES = ['先拍证据：手机换位置，杯子不动', '怎样表示？用一群三维软色斑',
          '从一个位置看，画成屏幕图像', '对照同角度照片，再调整', '换个方向看，还要检查证据']
FOOTERS = ['不同位置，提供不同方向的观察', '不是实体材料，也不是把照片贴上去',
           '相机位置决定它们在屏幕上怎样叠', '画 → 比较 → 调整 → 再画',
           '可转动展示 ≠ 精确网格 / 可直接打印']


def cup_points():
    points = []
    for row in range(7):
        y = -.7 + row*.2
        radius = .43 + .11*(y+.7)/1.2
        for col in range(24):
            a = col*2*math.pi/24
            rgb = (123+row*10, 202+row*4, 211+row*3)
            if col % 6 == 0:
                rgb = (190, 166, 232)
            points.append((radius*math.cos(a), y, radius*math.sin(a), rgb, False))
    for col in range(36):
        a=col*2*math.pi/36
        points.append((.55*math.cos(a), .62, .55*math.sin(a), (225,207,248), False))
    for k in range(23):
        a=-math.pi/2 + k*math.pi/22
        points.append((.51+.45*math.cos(a), -.03+.43*math.sin(a), 0, (239,209,148), True))
    return points


POINTS = cup_points()


def project(angle=0, handle_offset=0, width=300, height=240):
    """Pinhole camera around a fixed synthetic cup; far-to-near drawing order."""
    result=[]
    for x,y,z,color,handle in POINTS:
        if handle:x+=handle_offset
        xx=x*math.cos(angle)+z*math.sin(angle)
        zz=-x*math.sin(angle)+z*math.cos(angle)
        # Small downward camera tilt reveals the rim without moving the cup.
        yy=y*math.cos(.22)-zz*math.sin(.22)
        zz=y*math.sin(.22)+zz*math.cos(.22)
        distance=3.5-zz
        scale=min(width,height)*1.62/distance
        result.append((distance, width*.43+xx*scale, height*.47-yy*scale,
                       scale*.12, scale*.105, color))
    return sorted(result, reverse=True)


@lru_cache(maxsize=256)
def stamp(rx, ry, color):
    # Gaussian opacity, not a hard filled disk or a pasted photograph.
    img=Image.new('RGBA',(2*rx+1,2*ry+1),(0,0,0,0)); p=img.load()
    for yy in range(-ry,ry+1):
        for xx in range(-rx,rx+1):
            q=(xx/max(rx,1))**2+(yy/max(ry,1))**2
            p[xx+rx,yy+ry]=(*color,round(225*math.exp(-3*q)))
    return img


def render_cup(angle=0, handle_offset=0, size=(300,240), fraction=1):
    img=Image.new('RGBA',size,PANEL)
    values=project(angle,handle_offset,*size)
    for _,x,y,rx,ry,color in values[:round(len(values)*fraction)]:
        rx=max(2,round(rx*1.2));ry=max(2,round(ry*1.2))
        img.alpha_composite(stamp(rx,ry,color),(round(x-rx),round(y-ry)))
    return img.convert('RGB')


def mse(a,b):
    stat=ImageStat.Stat(ImageChops.difference(a,b))
    return sum(v*v for v in stat.rms)/(3*255*255)


def fit_handle():
    """Backtracking makes the finite-difference teaching example inspectable."""
    target=render_cup(size=(240,200));offset=.27
    records=[]
    for iteration in range(11):
        image=render_cup(handle_offset=offset,size=(240,200))
        loss=mse(image,target)
        records.append(dict(iteration=iteration,offset=offset,mse=loss))
        if iteration==10:break
        h=.012
        gradient=(mse(render_cup(handle_offset=offset+h,size=(240,200)),target)-
                  mse(render_cup(handle_offset=offset-h,size=(240,200)),target))/(2*h)
        rate=4.0
        candidate=offset
        for _ in range(16):
            probe=offset-rate*gradient
            if mse(render_cup(handle_offset=probe,size=(240,200)),target)<loss:
                candidate=probe;break
            rate*=.5
        offset=candidate
    assert records[-1]['mse']<records[0]['mse']
    assert all(b['mse']<=a['mse'] for a,b in zip(records,records[1:]))
    return records


def st(x,y,value,size=37,color=INK,anchor='middle'):
    return (f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" '
            f'fill="{color}" text-anchor="{anchor}" font-weight="600">{escape(value)}</text>')


def sp(d,color=CYAN,width=5,extra=''):
    return f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round" {extra}/>'


def sa(x1,y1,x2,y2,color=CYAN):
    a=math.atan2(y2-y1,x2-x1);bx=x2-15*math.cos(a);by=y2-15*math.sin(a)
    return sp(f'M{x1} {y1}L{x2} {y2}',color)+sp(
        f'M{bx-8*math.sin(a)} {by+8*math.cos(a)}L{x2} {y2}L{bx+8*math.sin(a)} {by-8*math.cos(a)}',color)


def svg_cup(cx,cy,scale=1):
    return (f'<g transform="translate({cx} {cy}) scale({scale})">'
            '<path d="M-59-67H59L48 64Q0 88-48 64Z" fill="#aadbd4" stroke="#def6ed" stroke-width="4"/>'
            '<ellipse cy="-67" rx="59" ry="15" fill="#403254" stroke="#def6ed" stroke-width="4"/>'
            '<path d="M59-48C123-57 125 45 50 44" fill="none" stroke="#efd194" stroke-width="15"/>'
            '<path d="M-29-43V41M2-40V49M31-43V41" stroke="#c4adea" stroke-width="8" opacity=".65"/>'
            '</g>')


def svg_camera(cx,cy,scale=1):
    return (f'<g transform="translate({cx} {cy}) scale({scale})">'
            '<rect x="-36" y="-25" width="72" height="52" rx="9" fill="#a48acb" stroke="#e3d2ff" stroke-width="3"/>'
            '<path d="M-21-25L-13-35H14L21-25" fill="#bca7dd"/>'
            '<circle r="17" fill="#29354c" stroke="#8de4df" stroke-width="5"/>'
            '<circle cx="-5" cy="-5" r="5" fill="#defaf5"/></g>')


def svg_splats(x,y,width=300,height=240,angle=0,offset=0):
    body=''
    for _,xx,yy,rx,ry,color in project(angle,offset,width,height):
        kind='gold' if color==(239,209,148) else 'violet' if color[1]<190 else 'cyan'
        body+=f'<ellipse cx="{x+xx:.2f}" cy="{y+yy:.2f}" rx="{rx*1.2:.2f}" ry="{ry*1.2:.2f}" fill="url(#{kind})"/>'
    return body


def make_diagrams(output,fit):
    definitions='<defs>'
    for name,color in [('cyan',CYAN),('violet',PURPLE),('gold',GOLD)]:
        definitions+=(f'<radialGradient id="{name}"><stop stop-color="{color}" stop-opacity=".9"/>'
                      f'<stop offset=".55" stop-color="{color}" stop-opacity=".4"/>'
                      f'<stop offset="1" stop-color="{color}" stop-opacity="0"/></radialGradient>')
    definitions+='</defs>'
    descriptions=[
        '原创示意：杯子固定，相机在不同位置观察；相邻示意照片看到同一杯子的共同部分。不是实际采集结果。',
        '原创外观类比：左侧杯子轮廓，右侧相同形状由有空间位置的软色斑近似。色斑不是实体材料或贴到外壳上的照片。',
        '计算示意：从一个相机位置把同一组三维色斑投到二维屏幕并合成。线条表示映射关系，不是物质在相机中穿行。',
        '合成单参数拟合：同角度目标、初始预测和调整后预测对照。实际计算预测图与合成目标的像素MSE，只调整杯把横向位置；不代表真实照片重建或完整Brush优化。',
        '同一组合成三维色斑在两个相机方向的投影，杯把与杯身的相对关系改变。展示外观不保证未拍区域、尺度或可打印网格。']
    for i,name in enumerate(NAMES):
        body=f'<rect width="960" height="540" rx="25" fill="{BG}"/>'
        body+=f'<rect x="20" y="91" width="920" height="344" rx="22" fill="{PANEL}" stroke="#665479" stroke-width="2"/>'
        body+=st(480,57,TITLES[i],40)+st(480,496,FOOTERS[i],34,GOLD)
        body+=sp('M31 28H47M39 20V36M913 28H929M921 20V36',PURPLE,2)
        if i==0:
            body+='<ellipse cx="235" cy="306" rx="151" ry="70" fill="none" stroke="#8877a6" stroke-width="3" stroke-dasharray="9 9"/>'
            body+=svg_cup(230,236,.84)+svg_camera(95,332,.8)+svg_camera(370,332,.8)
            body+=st(235,140,'杯子不动',36)+st(235,408,'手机绕着走',35,CYAN)
            body+=sa(415,264,474,264)
            for xx,a,label in [(504,-.45,'照片 A'),(718,.65,'照片 B')]:
                body+=f'<rect x="{xx}" y="153" width="192" height="205" rx="12" fill="#3d354c" stroke="#9b8bb7" stroke-width="2"/>'
                body+=svg_splats(xx+10,182,170,145,a)
                body+=st(xx+96,403,label,35)
        elif i==1:
            body+=svg_cup(231,255,1.15)+st(235,402,'真实物件',36)
            body+=sa(389,258,492,258)
            body+=svg_splats(536,145,355,258)
            body+=st(718,402,'三维软色斑',36,CYAN)
        elif i==2:
            body+=svg_splats(38,139,321,262,.3)+st(194,407,'三维表示',35,CYAN)
            body+=sa(354,254,425,254)+svg_camera(477,254,.85)+st(477,407,'相机',35)
            body+=sa(535,254,595,254)
            body+=f'<rect x="610" y="128" width="302" height="249" rx="13" fill="{BG}" stroke="#b59bde" stroke-width="4"/>'
            body+=svg_splats(621,143,280,225,.3)+st(763,407,'屏幕画面',35,PURPLE)
        elif i==3:
            for xx,label,offset in [(39,'合成目标',0),(350,'初始预测',fit[0]['offset']),(661,'调整后',fit[-1]['offset'])]:
                body+=st(xx+130,147,label,35,CYAN if xx==39 else PURPLE)
                body+=svg_splats(xx,165,260,223,offset=offset)
            body+=st(480,414,'只调整一个位置 · 用图像误差反馈',31,GOLD)
        else:
            body+=svg_splats(75,127,330,264,0)+svg_splats(541,127,330,264,1.1)
            body+=sa(427,260,522,260)
            body+=st(240,404,'观察方向 A',36,CYAN)+st(706,404,'观察方向 B',36,PURPLE)
        svg=(f'<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540" viewBox="0 0 960 540" role="img" aria-labelledby="title desc">'
             f'<title id="title">{escape(TITLES[i])}</title><desc id="desc">{escape(descriptions[i])}</desc>{definitions}{body}</svg>\n')
        (output/(name+'.svg')).write_text(svg,encoding='utf-8')


FONT_PATH=None


@lru_cache(maxsize=32)
def font(size):
    return ImageFont.truetype(str(FONT_PATH),size)


def label(d,xy,value,size=34,color=INK,anchor='mm'):
    d.text(xy,value,font=font(size),fill=color,anchor=anchor)


def arrow(d,a,b,color=CYAN,width=5):
    d.line([a,b],fill=color,width=width)
    theta=math.atan2(b[1]-a[1],b[0]-a[0])
    d.polygon([b,(b[0]-14*math.cos(theta-.5),b[1]-14*math.sin(theta-.5)),
               (b[0]-14*math.cos(theta+.5),b[1]-14*math.sin(theta+.5))],fill=color)


def paint_camera(d,x,y):
    d.rounded_rectangle((x-28,y-20,x+28,y+21),7,fill='#a48acb',outline=PURPLE,width=3)
    d.ellipse((x-13,y-13,x+13,y+13),fill=BG,outline=CYAN,width=4)


def paint_solid_cup(d,cx,cy,scale=1):
    def pts(v):return [(cx+x*scale,cy+y*scale) for x,y in v]
    d.line(pts([(45,-37),(80,-37),(93,-10),(86,27),(43,31)]),fill=GOLD,width=round(14*scale))
    d.polygon(pts([(-50,-55),(50,-55),(40,55),(0,69),(-40,55)]),fill='#abdcd6')
    d.ellipse((cx-50*scale,cy-66*scale,cx+50*scale,cy-44*scale),fill='#423256',outline='#ddf3ee',width=3)
    for x in [-25,0,25]:d.line(pts([(x,-30),(x,35)]),fill=PURPLE,width=max(2,round(7*scale)))


def split_caption(value,limit=23):
    if len(value)<=limit:return [value]
    if len(value)>limit*2:raise ValueError('Shorten video narration sentence')
    mid=(len(value)+1)//2
    choices=[i for i,c in enumerate(value,1) if c in '，；。？！' and len(value)-limit<=i<=limit]
    split=min(choices,key=lambda i:abs(i-mid)) if choices else min(limit,mid)
    return [value[:split],value[split:]]


def frame(scene,u,t,progress,caption,fit):
    im=Image.new('RGB',(W,H),BG);d=ImageDraw.Draw(im)
    d.rounded_rectangle((13,13,947,525),20,outline='#786393',width=2)
    label(d,(38,34),'光影塔 · 高斯溅射入门',26,GOLD,'lm')
    label(d,(38,82),TITLES[scene],36,INK,'lm')
    d.rounded_rectangle((29,133,931,403),20,fill=PANEL,outline='#705b86',width=2)
    # A small original prism guide stays decorative, outside the teaching area.
    x,y=893,60
    d.polygon([(x,y-23),(x+18,y),(x+9,y+25),(x-13,y+18),(x-19,y)],fill=CYAN)
    d.line([(x,y-23),(x+3,y),(x+9,y+25)],fill='#e8ffec',width=3)
    for dx in [-6,6]:d.ellipse((x+dx-2,y-2,x+dx+2,y+2),fill=BG)
    if scene==0:
        d.ellipse((71,200,401,370),outline='#8876a2',width=3)
        paint_solid_cup(d,235,260,1)
        a=-.8+u*math.pi*1.8
        paint_camera(d,235+157*math.cos(a),285+82*math.sin(a))
        label(d,(236,166),'杯子不动',31)
        label(d,(236,385),'手机换位置',28,CYAN)
        arrow(d,(428,267),(482,267))
        count=min(3,1+int(u*3))
        for j in range(count):
            xx=505+j*128
            d.rounded_rectangle((xx,203,xx+120,340),8,outline=PURPLE,width=2)
            im.paste(render_cup(angle=-.4+j*.5,size=(114,125)),(xx+3,209))
        label(d,(701,166),'多角度照片（示意）',29,PURPLE)
        label(d,(701,379),'相邻画面有重叠',28)
    elif scene==1:
        paint_solid_cup(d,223,268,1.2)
        label(d,(225,375),'真实物件',31)
        arrow(d,(375,264),(469,264))
        im.paste(render_cup(angle=.35,size=(400,205),fraction=.15+.85*min(1,u*2)),(500,168))
        label(d,(710,377),'三维软色斑',31,CYAN)
        label(d,(710,151),'位置 · 大小 · 颜色 · 透明度',24,GOLD)
    elif scene==2:
        im.paste(render_cup(angle=.4,size=(292,238)),(42,151))
        label(d,(188,377),'三维表示',30,CYAN)
        arrow(d,(347,261),(404,261));paint_camera(d,462,261)
        arrow(d,(518,261),(580,261))
        label(d,(462,377),'固定一个相机',25)
        d.rounded_rectangle((603,158,904,371),10,outline=PURPLE,width=3)
        im.paste(render_cup(angle=.4,size=(293,205),fraction=min(1,.05+u*1.6)),(607,162))
        label(d,(754,387),'投影后合成',29,PURPLE)
    elif scene==3:
        idx=min(len(fit)-1,int(u*len(fit)))
        a=fit[idx]
        for xx,title,offset in [(86,'合成目标',0),(540,'当前预测',a['offset'])]:
            label(d,(xx+159,168),title,32,CYAN if xx==86 else PURPLE)
            im.paste(render_cup(handle_offset=offset,size=(318,204)),(xx,181))
        arrow(d,(429,264),(501,264),GOLD)
        label(d,(480,382),'只调杯把位置 · 图像差异逐步减小',25,GOLD)
        # The bar is based on computed image loss, never a fabricated score.
        d.rectangle((322,393,638,398),fill='#65516c')
        d.rectangle((322,393,322+316*a['mse']/fit[0]['mse'],398),fill='#edab98')
    else:
        angle=-.2+u*1.5
        im.paste(render_cup(angle=angle,size=(437,257)),(57,138))
        label(d,(276,381),'同一组色斑，换方向',29,CYAN)
        label(d,(718,194),'用预留照片检查',36,PURPLE)
        label(d,(718,263),'没拍到的背面？',34,GOLD)
        label(d,(718,326),'不能保证正确',34)
        label(d,(718,378),'外观 ≠ 精确网格',28,GOLD)
    d.rounded_rectangle((35,415,925,510),14,fill='#191525',outline='#655279',width=2)
    for i,line in enumerate(split_caption(caption)):
        label(d,(480,442+i*40),line,34)
    d.rounded_rectangle((45,522,915,528),3,fill='#4e3f62')
    d.rounded_rectangle((45,522,45+870*progress,528),3,fill=CYAN)
    return im


def run(command):
    return subprocess.run(command,check=True,capture_output=True,timeout=180)


def tc(seconds):
    ms=round(seconds*1000)
    return f'{ms//3600000:02d}:{ms//60000%60:02d}:{ms//1000%60:02d}.{ms%1000:03d}'


def make_video(args,fit,ffmpeg):
    clips=json.loads(args.input.read_text())['clips']
    if len(clips)!=5:raise ValueError('Need five scene narrations')
    destination=args.output_dir/'video';destination.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='brush-beginner-') as folder:
        tmp=Path(folder);joined=bytearray();scenes=[];captions=[]
        for i,clip in enumerate(clips):
            pcm=tmp/f'{i}.pcm'
            run([ffmpeg,'-y','-v','error','-xerror','-i',str(args.audio_dir/clip['filename']),
                 '-ac','1','-ar',str(RATE),'-f','s16le',str(pcm)])
            data=pcm.read_bytes();spoken=len(data)/(2*RATE)
            if not 1<spoken<60:raise ValueError('Unexpected scene speech duration')
            start=len(joined)/(2*RATE);joined.extend(data);joined.extend(bytes(2*RATE))
            end=len(joined)/(2*RATE)
            scenes.append(dict(start=start,end=end,spoken_seconds=spoken,title=clip['title'],text=clip['text']))
            sentences=[s for s in re.split(r'(?<=[。？！；])',clip['text']) if s.strip()]
            cursor=start;total=sum(len(s) for s in sentences)
            for sentence in sentences:
                split_caption(sentence)
                stop=cursor+spoken*len(sentence)/total
                captions.append((cursor,stop,sentence));cursor=stop
        exact=len(joined)/(2*RATE);nframes=math.ceil(exact*FPS);duration=nframes/FPS
        joined.extend(bytes(round((duration-exact)*RATE)*2))
        with wave.open(str(tmp/'narration.wav'),'wb') as stream:
            stream.setnchannels(1);stream.setsampwidth(2);stream.setframerate(RATE);stream.writeframes(joined)
        movie=tmp/'principle.mp4'
        process=subprocess.Popen([ffmpeg,'-y','-v','error','-f','rawvideo','-pix_fmt','rgb24',
            '-s',f'{W}x{H}','-r',str(FPS),'-i','-','-i',str(tmp/'narration.wav'),'-c:v','libx264',
            '-preset','fast','-crf','21','-profile:v','high','-pix_fmt','yuv420p','-c:a','aac',
            '-b:a','96k','-movflags','+faststart','-t',str(duration),str(movie)],stdin=subprocess.PIPE,stderr=subprocess.PIPE)
        snapshots=[]
        try:
            for n in range(nframes):
                t=n/FPS;idx=next((i for i,s in enumerate(scenes) if t<s['end']),4)
                scene=scenes[idx];u=(t-scene['start'])/(scene['end']-scene['start'])
                caption=next((c for a,b,c in captions if a<=t<b),'')
                im=frame(idx,u,t,t/duration,caption,fit);process.stdin.write(im.tobytes())
                if idx==0 and abs(u-.8)<.5/FPS/(scene['end']-scene['start']):im.save(tmp/'poster.jpg',quality=95)
                for at in (.1,.5,.9):
                    if abs(t-scene['start']-at*(scene['end']-scene['start']))<.5/FPS:
                        snapshots.append((idx,at,im.copy()))
            process.stdin.close();error=process.stderr.read().decode();code=process.wait()
            if code:raise RuntimeError(error)
        except Exception:
            process.kill();process.wait();raise
        run([ffmpeg,'-v','error','-xerror','-i',str(movie),'-f','null','-'])
        run([ffmpeg,'-y','-v','error','-i',str(movie),'-map','0:a:0','-ar',str(RATE),'-ac','1','-f','s16le',str(tmp/'verified.pcm')])
        samples=array.array('h',(tmp/'verified.pcm').read_bytes())
        rms=math.sqrt(sum(v*v for v in samples)/len(samples))
        assert rms>100
        (tmp/'zh.vtt').write_text('WEBVTT\n\n'+'\n\n'.join(
            f'{i+1}\n{tc(a)} --> {tc(b)}\n{c}' for i,(a,b,c) in enumerate(captions))+'\n')
        for name in ['principle.mp4','poster.jpg','zh.vtt']:shutil.copyfile(tmp/name,destination/name)
        sheet=Image.new('RGB',(894,168*5),BG)
        for j,(idx,at,im) in enumerate(snapshots):
            im.save(args.review_output/f'scene-{idx+1}-{round(at*100)}.jpg',quality=95)
            sheet.paste(im.resize((298,168)),((j%3)*298,(j//3)*168))
        sheet.save(args.review_output/'frames-298px.jpg',quality=95)
        prefix='/media/'+args.output_dir.relative_to(ROOT/'web/media').as_posix()+'/video'
        metadata=dict(src=prefix+'/principle.mp4',poster=prefix+'/poster.jpg',captions=prefix+'/zh.vtt',
            title='从照片到可转动的杯子：高斯溅射五步',duration_seconds=round(duration,3),
            attribution='本项目原创合成示意；晓晓合成中文女声（Microsoft Edge Neural）。杯子不是照片重建结果；单参数拟合用有限差分和像素MSE，非完整Brush训练。',
            transcript=[dict(time=round(s['start'],3),text=s['text']) for s in scenes])
        (args.review_output/'video-metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n')
        report=dict(duration_seconds=duration,frame_count=nframes,audio_decoded_seconds=len(samples)/RATE,
                    voice_rms=rms,scenes=scenes,cues=len(captions),fitting=fit,
                    limitations='Synthetic cup; simple projected splats; one finite-difference parameter, not Brush training; sentence timing is not word alignment.')
        (args.review_output/'video-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({'duration_seconds':duration,'frame_count':nframes,'audio_rms':rms,'fitting_start':fit[0],'fitting_end':fit[-1]}))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=ROOT/'web/media/brush-beginner')
    parser.add_argument('--review-output',type=Path,required=True)
    parser.add_argument('--video',action='store_true')
    parser.add_argument('--input',type=Path,default=ROOT/'content/brush-beginner-video-narration.json')
    parser.add_argument('--audio-dir',type=Path,default=ROOT/'web/media/brush-beginner/video/audio')
    parser.add_argument('--font',type=Path)
    parser.add_argument('--ffmpeg',default='ffmpeg')
    args=parser.parse_args();args.output_dir=args.output_dir.resolve()
    args.output_dir.mkdir(parents=True,exist_ok=True);args.review_output.mkdir(parents=True,exist_ok=True)
    fit=fit_handle();make_diagrams(args.output_dir,fit)
    (args.review_output/'fitting-evidence.json').write_text(json.dumps(fit,indent=2)+'\n')
    if args.video:
        global FONT_PATH
        FONT_PATH=args.font
        ffmpeg=shutil.which(args.ffmpeg)
        if not ffmpeg or not FONT_PATH or not FONT_PATH.is_file():parser.error('Existing font and FFmpeg required')
        make_video(args,fit,ffmpeg)
    else:print('Generated five static Brush beginner diagrams.')


if __name__=='__main__':main()
