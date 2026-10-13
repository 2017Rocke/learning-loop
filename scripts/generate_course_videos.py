#!/usr/bin/env python3
"""Render two original narrated mechanism films from maintained public scripts.

Optional authoring dependencies: Pillow and an existing FFmpeg executable.
Prepare narration with generate_neural_audio.py first. This command does not use
network services, install anything, or touch learner data. Font and FFmpeg are
explicit arguments so no author's machine paths enter this public generator.
The numbered voice files are decoded and measured, then joined with one second
of breathing room. Frames, scene boundaries, VTT and lesson metadata all use
those measured durations. Animated shapes are teaching models, not real outputs.
"""
from __future__ import annotations
import argparse
import array
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import wave
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
W, H, FPS, RATE = 960, 540, 15, 24000
C = dict(bg='#FFF9EF', ink='#27364D', muted='#63738B', white='#FFFFFF',
         red='#EF7771', redsoft='#FFE0D7', blue='#73B6EB', bluesoft='#E2F0FF',
         mint='#A8E5C7', green='#228764', purple='#9C83E9', purplesoft='#EDE5FF',
         yellow='#FFDB78', pink='#FFB6D0')
FONT = None
FONTS = {}

def font(size):
    if size not in FONTS: FONTS[size] = ImageFont.truetype(FONT, size)
    return FONTS[size]

def text(d, pos, value, size=30, fill=None, anchor='mm'):
    d.text(pos, str(value), font=font(size), fill=fill or C['ink'], anchor=anchor)

def box(d, bounds, fill='white', outline=None, radius=22, width=2):
    d.rounded_rectangle(bounds, radius, fill=C.get(fill, fill), outline=C.get(outline, outline), width=width)

def ease(x):
    x = max(0, min(1, x)); return x*x*(3-2*x)

def mix(a,b,p): return a+(b-a)*p

def arrow(d,a,b,color='purple',width=5):
    c=C.get(color,color); d.line([a,b],fill=c,width=width)
    theta=math.atan2(b[1]-a[1],b[0]-a[0]); r=13
    d.polygon([b,(b[0]-r*math.cos(theta-.5),b[1]-r*math.sin(theta-.5)),(b[0]-r*math.cos(theta+.5),b[1]-r*math.sin(theta+.5))],fill=c)

def mascot(d,x,y,t,scale=.8):
    y += math.sin(t*1.9)*3
    r=25*scale
    d.ellipse((x-r,y-r,x+r,y+r),fill=C['mint'],outline=C['white'],width=3)
    for dx in [-9,9]: d.ellipse((x+dx*scale-2,y-4,x+dx*scale+2,y+2),fill=C['ink'])
    d.arc((x-9*scale,y-1,x+9*scale,y+11*scale),0,180,fill=C['ink'],width=2)
    d.polygon([(x-r*.65,y-r*.75),(x-r*.45,y-r*1.4),(x-r*.05,y-r*.95)],fill=C['mint'])
    d.polygon([(x+r*.65,y-r*.75),(x+r*.45,y-r*1.4),(x+r*.05,y-r*.95)],fill=C['mint'])

def point(d,x,y,c,r=3,mark=False):
    d.ellipse((x-r,y-r,x+r,y+r),fill=C[c])
    if mark:
        # Shape/mark cues accompany the color for the enlarged, conceptual dots.
        if c=='red':
            d.line((x-r/2,y-r/2,x+r/2,y+r/2),fill=C['white'],width=2)
            d.line((x-r/2,y+r/2,x+r/2,y-r/2),fill=C['white'],width=2)
        else: d.line((x-r/2,y,x-r/8,y+r/3,x+r/2,y-r/3),fill=C['white'],width=2)

def wrap(value,limit=23):
    # Balance two lines and keep Chinese punctuation attached to its phrase.
    if len(value)<=limit: return [value]
    middle=(len(value)+1)//2
    candidates=[i for i,c in enumerate(value,1) if c in '，；。？！' and 8<=i<=limit]
    split=min(candidates,key=lambda i:abs(i-middle)) if candidates else min(limit,middle)
    while split<len(value) and value[split] in '，；。？！': split+=1
    return [value[:split],value[split:]]

def base(name,title,scene,total,p,t,caption):
    im=Image.new('RGB',(W,H),C['bg'] if name=='bayes' else '#F6F1FF'); d=ImageDraw.Draw(im)
    text(d,(44,31),'贝叶斯小侦探' if name=='bayes' else 'VoiceStudio · 声音工坊',30,anchor='la')
    text(d,(44,76),title,35,anchor='la')
    mascot(d,899,49,t,.92)
    for i in range(total):
        x=720+i*24
        d.ellipse((x,100,x+12,112),fill=C['purple'] if i<=scene else '#DEDCE8')
    box(d,(30,132,930,402),'white',radius=25)
    d.rounded_rectangle((44,526,916,532),3,fill='#E1E5E9')
    d.rounded_rectangle((44,526,44+872*p,532),3,fill=C['purple'])
    # Captions are burnt in as well as supplied as switchable VTT.
    lines=wrap(caption)
    for i,s in enumerate(lines[:2]): text(d,(480,438+i*42),s,34)
    return im,d

BAYES_TITLES=['原本的队伍：1% 坏，99% 正常','两条来源：真报警 + 误报警','只把报警件移进同一个池子','条件变了，分母也跟着变']
VOICE_TITLES=['文字卡 → 已有模型 → 声音','编号不丢，缺句才能定位','找到空位，再局部重新生成','短重叠：前段退，后段进','读全 · 读对 · 连起来听']

def bayes(d,scene,u,t):
    if scene==0:
        box(d,(52,182,258,350),'redsoft'); box(d,(702,182,908,350),'bluesoft')
        text(d,(155,215),'坏件 ×',28,'#A94240'); text(d,(155,266),'100',52,'#A94240'); text(d,(155,320),'1%',32)
        text(d,(805,215),'正常件',28); text(d,(805,266),'9,900',48); text(d,(805,320),'99%',32)
        # Exactly 100 equally weighted points: one bad + 99 normal.
        for i in range(100):
            tx,ty=318+(i%10)*36,169+(i//10)*20
            q=ease((u-.05-i*.001)/.27)
            x=mix(480,tx,q); y=mix(268,ty,q)
            point(d,x,y,'red' if i==0 else 'blue',7,True)
        text(d,(480,377),'每点 100 件 · 共 10,000 件 · 教学假设',24,C['muted'])
    elif scene==1:
        for j,(label,count,rate,result,c) in enumerate([('坏件',100,'90%',90,'red'),('正常',9900,'5%',495,'blue')]):
            y=204+j*110
            box(d,(60,y-41,275,y+44),c+'soft')
            text(d,(167,y-10),f'{label} {count:,}',30)
            text(d,(167,y+26),'各自群体内计数',20,C['muted'])
            arrow(d,(290,y),(598,y),c)
            text(d,(444,y-26),'× '+rate,35,C[c])
            box(d,(620,y-42,900,y+44),c+'soft')
            text(d,(760,y),f'{result} '+('真报警' if j==0 else '误报警'),36,C[c] if j==0 else C['ink'])
            # Animated items travel through each conditional-probability branch.
            for k in range(6):
                q=((t*.21)+k/6)%1
                point(d,300+285*q,y,c,6,True)
        text(d,(480,381),'检测率和误报率的分母，是各自原群体',23,C['muted'])
    elif scene in [2,3]:
        box(d,(258,172,702,351),'purplesoft','purple',radius=20,width=3)
        text(d,(480,150),'已报警的共同队伍',27,C['purple'])
        progress=ease((u-.16)/.6) if scene==2 else 1
        arrived=[0,0]
        for i in range(585):
            bad=i<90; tx=282+(i%45)*9; ty=201+(i//45)*10
            if bad: sx=70+(i%10)*10; sy=185+(i//10)*15
            else:
                k=i-90; sx=761+(k%15)*8; sy=173+(k//15)*6
            q=ease((progress-(i%15)*.011)/.82)
            x=mix(sx,tx,q); y=mix(sy,ty,q)-math.sin(q*math.pi)*(45 if bad else -23)
            point(d,x,y,'red' if bad else 'blue',3)
            if q>=.999: arrived[0 if bad else 1]+=1
        text(d,(142,361),'90 真报警',28,C['red']); text(d,(810,377),'495 误报警',26)
        if scene==2:
            text(d,(480,371),'每点 1 件 · 颜色保留原来的类别',23,C['muted'])
        else:
            # A numerator/denominator frame makes the changed conditioning set explicit.
            text(d,(480,365),'90 ÷ (90 + 495) ≈ 15.4%',38,C['green'])
            d.rounded_rectangle((274,190,692,219),6,outline=C['red'],width=3)
            text(d,(149,260),'真坏',30,C['red']); text(d,(811,260),'全部报警',28,C['purple'])

def waveform(d,bounds,color,phase=0,weight=1):
    x1,y1,x2,y2=bounds; center=(y1+y2)/2; amp=(y2-y1)*.44
    pts=[]
    for x in range(int(x1),int(x2)+1,3):
        z=(x-x1)/(x2-x1)
        y=center+amp*weight*math.sin(z*math.pi*12+phase)*(0.5+0.5*math.sin(z*math.pi)**2)
        pts.append((x,y))
    d.line(pts,fill=C.get(color,color),width=3)

def audio_card(d,x,y,w,label,color,phase=0,missing=False):
    box(d,(x,y,x+w,y+72),'white',color,12,3)
    text(d,(x+21,y+17),label,22,C[color])
    if missing:
        text(d,(x+w/2,y+44),'空',29,C['red'])
        d.line((x+40,y+47,x+w-12,y+47),fill=C['red'],width=2)
    else: waveform(d,(x+42,y+25,x+w-10,y+61),color,phase)

def voice(d,scene,u,t):
    if scene==0:
        box(d,(350,178,605,343),'purplesoft','purple',22,3)
        text(d,(477,208),'引擎接入已有模型',26)
        mascot(d,478,267,t,1.4)
        text(d,(477,325),'通常是推理',24,C['muted'])
        box(d,(58,190,264,318),'mint')
        text(d,(160,222),'工作台组织',29); text(d,(160,267),'文字 + 声音条件',24)
        arrow(d,(270,255),(340,255),'purple'); arrow(d,(615,255),(679,255),'purple')
        audio_card(d,692,214,210,'①','blue',t*2)
        # Card and audio tokens follow the directional arrows, not a static slide.
        q=(u*2)%1; x=270+70*q; box(d,(x-10,235,x+10,257),'pink',radius=5)
        text(d,(480,378),'原创流程示意 · 不是模型实际运行画面',23,C['muted'])
    elif scene==1:
        for i in range(3):
            x=95+i*270
            box(d,(x,163,x+218,213),['mint','pink','yellow'][i]); text(d,(x+109,188),f'文字块 {i+1}',29)
            arrow(d,(x+109,222),(x+109,265),'purple')
            audio_card(d,x,285,218,str(i+1),'red' if i==1 else 'blue',t,missing=i==1 and u>.38)
            if i==1 and u>.38:
                text(d,(x+109,249),'缺失位置仍保留',21,C['red'])
            else:
                point(d,x+109,mix(225,270,(t*.35+i/3)%1),'blue',6)
        text(d,(480,382),'1 → 2 → 3：顺序和原文必须能对应',25,C['muted'])
    elif scene==2:
        box(d,(77,190,295,314),'pink'); text(d,(186,220),'文字块 2',29); text(d,(186,268),'定位 · 核对 · 重做',24)
        box(d,(367,188,594,314),'purplesoft'); text(d,(480,220),'同一模型 / 音色',25); mascot(d,480,268,t,1)
        arrow(d,(305,254),(355,254)); arrow(d,(605,254),(657,254))
        audio_card(d,670,217,212,'2','blue',t,missing=u<.55)
        q=ease((u-.2)/.45); x=mix(292,665,q); point(d,x,256,'red',8,True)
        if u>.55: text(d,(778,335),'重新核对这一句',24,C['green'])
        text(d,(480,378),'人工定位后的修复示意 · 不会自动补句',24,C['muted'])
    elif scene==3:
        # Existing sample strips physically overlap; the final overlap uses a
        # linear weight, matching the pedagogical mechanism (not a benchmark).
        q=ease(min(1,u/.5)); ax1,ax2=78,461; bx1,bx2=mix(575,423,q),mix(891,806,q)
        box(d,(ax1,169,ax2,224),'redsoft'); waveform(d,(ax1+8,173,ax2-8,219),'red')
        box(d,(bx1,249,bx2,304),'bluesoft'); waveform(d,(bx1+8,253,bx2-8,299),'blue',1)
        text(d,(193,150),'前段尾部',23,C['red']); text(d,(727,233),'后段头部',23)
        if q>.9:
            box(d,(423,160,461,312),'purplesoft','purple',7,2)
            # Enlarged overlap below shows one-to-zero and zero-to-one ramps.
            arrow(d,(429,313),(347,342),'purple',3); arrow(d,(458,313),(620,342),'purple',3)
            box(d,(286,334,673,391),'purplesoft')
            pts=[]
            for x in range(297,662,3):
                z=(x-297)/365
                a=math.sin(z*math.pi*12)*16; b=math.sin(z*math.pi*12+1)*16
                pts.append((x,361+(1-z)*a+z*b))
            d.line(pts,fill=C['purple'],width=3)
            d.line((300,339,660,388),fill=C['red'],width=2)
            d.line((300,388,660,339),fill=C['blue'],width=2)
        text(d,(150,373),'权重 1 → 0',23,C['red']); text(d,(796,373),'权重 0 → 1',23)
    else:
        labels=[('原稿','每句都在','mint'),('术语','读音核对','pink'),('连接处','试听接缝','bluesoft')]
        for i,(a,b,c) in enumerate(labels):
            x=76+i*285; box(d,(x,175,x+238,337),c)
            text(d,(x+119,207),a,31); text(d,(x+119,285),b,28)
            # Sweeping magnifier, without assigning a learner score or mastery.
            angle=t*1.3+i; cx=x+116+30*math.sin(angle); cy=247
            d.ellipse((cx-17,cy-17,cx+17,cy+17),outline=C['purple'],width=4)
            d.line((cx+13,cy+13,cx+26,cy+26),fill=C['purple'],width=5)
        text(d,(480,375),'每一项都需要检查，不预填“通过”',27,C['muted'])

def tc(seconds):
    ms=round(seconds*1000); return f'{ms//3600000:02d}:{ms//60000%60:02d}:{ms//1000%60:02d}.{ms%1000:03d}'

def run(cmd): return subprocess.run(cmd,check=True,capture_output=True,timeout=180)

def build(name,ffmpeg,output):
    src=json.loads((ROOT/f'content/{name}-video-narration.json').read_text())
    source_dir=ROOT/f'web/media/{name}/video-audio'; media=ROOT/f'web/media/{name}'
    with tempfile.TemporaryDirectory(prefix='learning-video-') as folder:
        tmp=Path(folder); pcm_all=bytearray(); scenes=[]; captions=[]
        for i,clip in enumerate(src['clips']):
            raw=tmp/f'{i}.pcm'
            run([ffmpeg,'-y','-v','error','-xerror','-i',str(source_dir/clip['filename']),'-ac','1','-ar',str(RATE),'-f','s16le',str(raw)])
            data=raw.read_bytes(); spoken=len(data)/(2*RATE)
            if not 1<spoken<40: raise ValueError('Unexpected scene voice duration')
            start=len(pcm_all)/(2*RATE); pcm_all.extend(data); pcm_all.extend(bytes(2*RATE))
            end=len(pcm_all)/(2*RATE)
            scenes.append(dict(start=start,end=end,spoken_seconds=spoken,title=clip['title'],text=clip['text']))
            sentences=[s for s in re.split(r'(?<=[。？！；])',clip['text']) if s]
            # Sentence cue windows derive from measured speech time. Detailed
            # word alignment is not claimed; each scene retains its full text.
            cursor=start; total=sum(len(s) for s in sentences)
            for s in sentences:
                stop=cursor+spoken*len(s)/total
                captions.append((cursor,stop,s)); cursor=stop
        exact=len(pcm_all)/(2*RATE); nframes=math.ceil(exact*FPS); duration=nframes/FPS
        pcm_all.extend(bytes(round((duration-exact)*RATE)*2))
        with wave.open(str(tmp/'narration.wav'),'wb') as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE); w.writeframes(pcm_all)
        cmd=[ffmpeg,'-y','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-',
             '-i',str(tmp/'narration.wav'),'-c:v','libx264','-preset','fast','-crf','21','-profile:v','high','-pix_fmt','yuv420p',
             '-c:a','aac','-b:a','96k','-movflags','+faststart','-t',str(duration),str(tmp/'principle.mp4')]
        process=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=subprocess.PIPE)
        frame_sheet=[]
        try:
            for n in range(nframes):
                t=n/FPS; ix=next((i for i,s in enumerate(scenes) if t<s['end']),len(scenes)-1); scene=scenes[ix]
                u=(t-scene['start'])/(scene['end']-scene['start']); cap=next((c for a,b,c in captions if a<=t<b),'')
                im,d=base(name,(BAYES_TITLES if name=='bayes' else VOICE_TITLES)[ix],ix,len(scenes),t/duration,t,cap)
                (bayes if name=='bayes' else voice)(d,ix,u,t)
                process.stdin.write(im.tobytes())
                if n==round(scenes[0]['end']*.72*FPS): im.save(tmp/'poster.jpg',quality=94,optimize=True)
                if any(abs(t-(s['start']+.72*(s['end']-s['start'])))<.5/FPS for s in scenes): frame_sheet.append(im.copy())
            process.stdin.close(); error=process.stderr.read().decode(); code=process.wait()
            if code: raise RuntimeError(error)
        except Exception:
            process.kill(); process.wait(); raise
        run([ffmpeg,'-v','error','-xerror','-i',str(tmp/'principle.mp4'),'-f','null','-'])
        # A non-silent decoded voice track is mandatory for these two films.
        run([ffmpeg,'-y','-v','error','-i',str(tmp/'principle.mp4'),'-map','0:a:0','-ar',str(RATE),'-ac','1','-f','s16le',str(tmp/'verified.pcm')])
        pcm=array.array('h',(tmp/'verified.pcm').read_bytes()); rms=math.sqrt(sum(x*x for x in pcm)/len(pcm))
        if rms<100: raise ValueError('Silent video soundtrack')
        vtt='WEBVTT\n\n'+'\n\n'.join(f'{i+1}\n{tc(a)} --> {tc(b)}\n{c}' for i,(a,b,c) in enumerate(captions))+'\n'
        (tmp/'zh.vtt').write_text(vtt)
        for a,b,c in captions:
            if not 0<=a<b<=duration: raise ValueError('Caption outside film')
        cols=2; rows=math.ceil(len(frame_sheet)/cols); sheet=Image.new('RGB',(960,270*rows),C['bg'])
        for i,im in enumerate(frame_sheet): sheet.paste(im.resize((480,270)),((i%cols)*480,(i//cols)*270))
        output.mkdir(parents=True,exist_ok=True); sheet.save(output/f'{name}-frames.jpg',quality=95)
        run([ffmpeg,'-y','-v','error','-i',str(tmp/'principle.mp4'),'-t','18','-vn','-c:a','libmp3lame','-q:a','3',str(output/f'{name}-voice-preview.mp3')])
        for filename in ['principle.mp4','poster.jpg','zh.vtt']: shutil.copyfile(tmp/filename,media/filename)
        lesson_file=ROOT/f'content/{name}.json'; lesson=json.loads(lesson_file.read_text())
        lesson['visual_lesson']['video']={
            'src':f'/media/{name}/principle.mp4','poster':f'/media/{name}/poster.jpg','captions':f'/media/{name}/zh.vtt',
            'title':'报警件重新组队：看见贝叶斯的分母' if name=='bayes' else '文字到声音：分块、查漏与交叉淡化',
            'duration_seconds':round(duration,3),
            'attribution':'原创机制动画；晓晓合成中文女声（Microsoft Edge Neural）。'+('数字为教学假设；点的计数单位在画面中标明。' if name=='bayes' else '模型、波形与局部修复均为教学示意，不是 VoiceStudio 实际运行或模型输出。'),
            'transcript':[dict(time=round(s['start'],3),text=s['text']) for s in scenes]}
        lesson_file.write_text(json.dumps(lesson,ensure_ascii=False,indent=2)+'\n')
        report=dict(course=name,duration_seconds=duration,audio_decoded_seconds=len(pcm)/RATE,voice_rms=round(rms,2),width=W,height=H,fps=FPS,scenes=scenes,cues=len(captions),frame_count=nframes)
        (output/f'{name}-video-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(report,ensure_ascii=False),flush=True)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ffmpeg',default='ffmpeg')
    parser.add_argument('--font',type=Path,required=True,help='Existing Chinese TrueType/OpenType font')
    parser.add_argument('--course',choices=['bayes','voicestudio','all'],default='all')
    parser.add_argument('--review-output',type=Path,required=True,help='Temporary, non-published QA artifacts directory')
    args=parser.parse_args(); ffmpeg=shutil.which(args.ffmpeg)
    if not ffmpeg or not args.font.is_file(): parser.error('FFmpeg and an existing Chinese font are required')
    global FONT
    FONT=str(args.font)
    for name in (['bayes','voicestudio'] if args.course=='all' else [args.course]): build(name,ffmpeg,args.review_output)

if __name__=='__main__': main()
