#!/usr/bin/env python3
"""Build original capacitor beginner pictures and a narrated causal film.

Offline authoring only: existing Pillow, FFmpeg and Chinese font are required.
Prepared public narration is measured, then pictures, captions, media and lesson
metadata are produced. No installation, network, device code or learner state.
Arrows are conventional current, not electrons. Open paths stop at the plates;
the complete arrow head/stroke stays outside the ideal dielectric gap.
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

ROOT=Path(__file__).resolve().parents[1]
W,H,FPS,RATE=960,540,15,24000
C=dict(night='#192840',paper='#FFF5DE',brass='#C39B59',light='#F2D498',ink='#25394E',
       muted='#5D6A78',blue='#2D78AD',green='#278363',purple='#8060A7',pale='#DCEAF3')
TITLES=['电容是什么，为什么芯片旁边有它？','像备用水杯；真实内部仍然绝缘',
        '芯片突然忙，电容暂时补缺口','电源接力，电容不负责长期供电','恢复空闲后，电源把能量补回']
LABELS=['先认元件，再认用途','比喻解释接力；电场负责储能','临时释放储能，电压会下降',
        '电源跟上，电容所补缺口缩小','储能恢复；稳定后不再持续净充电']
GAP=(443,254,557,289)
SUPPLY=[(150,228),(150,180),(785,180),(785,247)]
RETURN=[(785,320),(785,375),(150,375),(150,316)]
DISCHARGE=[(500,248),(500,180),(785,180),(785,247)]
DISCHARGE_RETURN=[(785,320),(785,375),(500,375),(500,295)]
CHARGE=[(150,228),(150,180),(500,180),(500,248)]
CHARGE_RETURN=[(500,295),(500,375),(150,375),(150,316)]
FONTS={}; FONT=None; GEOMETRY_CHECKS=0

def font(size):
    if size not in FONTS:FONTS[size]=ImageFont.truetype(FONT,size)
    return FONTS[size]
def text(d,xy,value,size=30,fill=None,anchor='mm'):
    d.text(xy,str(value),font=font(size),fill=fill or C['ink'],anchor=anchor)
def box(d,xy,fill,outline=None,r=12,width=2):
    d.rounded_rectangle(xy,r,fill=C.get(fill,fill),outline=C.get(outline,outline),width=width)
def clamp(x):return max(0,min(1,x))
def ease(x):x=clamp(x);return x*x*(3-2*x)
def point_on(path,q):
    lengths=[math.dist(a,b) for a,b in zip(path,path[1:])];remaining=clamp(q)*sum(lengths)
    for a,b,length in zip(path,path[1:],lengths):
        if remaining<=length:
            p=remaining/length;return (a[0]+(b[0]-a[0])*p,a[1]+(b[1]-a[1])*p)
        remaining-=length
    return path[-1]
def arrows(d,path,strength=1):
    global GEOMETRY_CHECKS
    if strength<=.03:return
    for i in range(5):
        q=(i+.45)/5;a=point_on(path,q-.012);b=point_on(path,q+.012)
        angle=math.atan2(b[1]-a[1],b[0]-a[0]);size=7+3*strength
        poly=[b,(b[0]-size*math.cos(angle-.6),b[1]-size*math.sin(angle-.6)),
              (b[0]-size*math.cos(angle+.6),b[1]-size*math.sin(angle+.6))]
        bounds=(min(p[0] for p in poly+[a])-3,min(p[1] for p in poly+[a])-3,
                max(p[0] for p in poly+[a])+3,max(p[1] for p in poly+[a])+3)
        assert bounds[2]<GAP[0] or bounds[0]>GAP[2] or bounds[3]<GAP[1] or bounds[1]>GAP[3], 'Current arrow reaches dielectric'
        GEOMETRY_CHECKS+=1
        d.line([a,b],fill=ACTIVE_COLOR,width=3+round(3*strength));d.polygon(poly,fill=ACTIVE_COLOR)
def wrap(value,limit=23):
    if len(value)<=limit:return [value]
    if len(value)>2*limit:raise ValueError('Narration sentence exceeds the two-line caption budget')
    positions=[i for i,c in enumerate(value,1) if c in '，；。？！' and len(value)-limit<=i<=limit]
    split=min(positions,key=lambda i:abs(i-len(value)/2)) if positions else (len(value)+1)//2
    return [value[:split],value[split:]]

def background(scene,t,progress,caption):
    im=Image.new('RGB',(W,H),C['night']);d=ImageDraw.Draw(im)
    d.rounded_rectangle((12,12,948,528),19,outline=C['brass'],width=2)
    text(d,(43,31),'星灯工坊 · 电容入门',27,C['light'],'la')
    text(d,(43,80),TITLES[scene],34,C['paper'],'la')
    x,y=888,62+math.sin(t*1.5)*3
    d.polygon([(x,y-25),(x+19,y),(x+12,y+25),(x,y+30),(x-16,y+19),(x-19,y)],fill='#AFE2C6')
    for dx in [-6,6]:d.ellipse((x+dx-2,y,x+dx+2,y+4),fill=C['ink'])
    d.arc((x-29,y+5,x+29,y+24),0,180,fill=C['light'],width=3)
    for i in range(5):d.ellipse((735+i*24,108,745+i*24,118),fill=C['light'] if i<=scene else '#4B5D73')
    box(d,(30,133,930,404),'paper','brass',18)
    box(d,(35,417,925,510),'#102034','#58667A',15)
    for i,line in enumerate(wrap(caption)):text(d,(480,441+i*41),line,37,C['paper'])
    d.rounded_rectangle((43,523,917,529),3,fill='#45546B')
    d.rounded_rectangle((43,523,43+874*progress,529),3,fill=C['light'])
    return im,d

def types(d):
    text(d,(265,171),'常见外形',31)
    box(d,(93,223,254,288),'#CBAA78','#997A4E',7)
    box(d,(90,223,119,288),'#B9C6CD',r=2);box(d,(228,223,257,288),'#B9C6CD',r=2)
    text(d,(174,329),'小长方块',28)
    box(d,(325,216,425,305),'#52677B',r=6)
    d.ellipse((325,205,425,233),fill='#BAC8D3',outline=C['ink'],width=2)
    d.line((356,305,356,329),fill=C['muted'],width=5);d.line((396,305,396,329),fill=C['muted'],width=5)
    text(d,(375,354),'圆柱小罐',27)
    d.line((481,158,481,377),fill='#D7C8A7',width=2)
    box(d,(545,194,887,338),'#DDEBD7','#689078')
    box(d,(683,229,818,305),'#355569','#E0D4A2')
    text(d,(751,269),'芯片',32,C['paper'])
    for i in range(5):
        y=235+i*15;d.line((671,y,683,y),fill=C['brass'],width=4);d.line((818,y,830,y),fill=C['brass'],width=4)
    box(d,(575,247,627,275),'#CBAA78','#997A4E',4)
    text(d,(602,303),'电容',27)
    text(d,(715,365),'在旁边短时帮忙',30,C['green'])
    text(d,(265,389),'认身份要对照原理图',24,C['muted'])

def analogy(d,q):
    text(d,(260,173),'像一小杯备用水',31)
    d.polygon([(163,211),(357,211),(332,340),(188,340)],fill='#E2F0F5',outline=C['blue'])
    d.polygon([(172,247),(348,247),(332,337),(188,337)],fill='#8DCDE0')
    d.line([(163,211),(188,340),(332,340),(357,211)],fill=C['blue'],width=5)
    text(d,(260,371),'只能临时顶一下',29,C['blue'])
    d.line((474,158,474,379),fill='#D7C8A7',width=2)
    text(d,(704,173),'真实电容',31)
    d.rectangle((582,225,830,243),fill=C['brass']);d.rectangle((582,313,830,331),fill=C['brass'])
    d.rectangle((592,253,820,302),fill='#E8DCEC',outline='#B098C3',width=2)
    text(d,(706,278),'绝缘层',30,C['purple'])
    for i in range(4):
        text(d,(612+i*62,235),'+',22,C['paper']);text(d,(612+i*62,322),'−',25,C['paper'])
    text(d,(704,370),'电场储能 · 电子不穿过',26,C['purple'])

def circuit(d,scene,q,t):
    global ACTIVE_COLOR
    if scene==2:
        busy=q>.01;source=.40;support=ease((q-.20)/.80);energy=1-.36*ease((q-.20)/.80);recharge=0
    elif scene==3:
        busy=True;source=.40+.60*ease(q);support=1-ease(q);energy=.64-.09*ease(q);recharge=0
    else:
        busy=False;source=.65-.25*ease(q);support=0;energy=.55+.45*ease(q);recharge=math.sin(math.pi*clamp(q))
    for path in (SUPPLY,RETURN,[(500,180),(500,248)],[(500,295),(500,375)]):d.line(path,fill='#7392A3',width=4)
    box(d,(101,228,199,316),'#DCEBF2','blue')
    text(d,(150,259),'电源',31);text(d,(150,296),'供能',24,C['blue'])
    text(d,(119,208),'+',27,C['blue']);text(d,(119,337),'−',29,C['blue'])
    box(d,(711,247,859,320),'#F3D98C' if busy else '#DFEBCF','#A68B4F')
    text(d,(785,268),'芯片',30);text(d,(785,305),'忙起来' if busy else '空闲',25)
    text(d,(785,213),'需要更多' if busy else ('平时需求' if scene==2 else '需求减少'),27,C['ink'])
    d.rectangle((440,239,560,253),fill=C['brass']);d.rectangle((440,290,560,304),fill=C['brass'])
    d.rectangle(GAP,fill='#E8DCEC',outline='#B098C3',width=1)
    text(d,(500,271),'绝缘',23,C['purple']);text(d,(610,271),'电容',31)
    text(d,(333,229),'储能示意',25,C['purple'])
    box(d,(312,249,354,333),'#E3D8ED','purple',5)
    if energy>0:box(d,(316,329-76*energy,350,329),'#A999CB',r=3)
    text(d,(500,389),'箭头＝约定电流；中间不走电子',24,C['muted'])
    source_label=('暂未跟上' if busy else '平时供电') if scene==2 else ('已接力' if q>=.99 else '逐渐跟上') if scene==3 else ('稳定供电' if q>=.99 else '供给与回充')
    text(d,(150,157),source_label,25,C['blue'])
    ACTIVE_COLOR=C['blue'];arrows(d,SUPPLY,source);arrows(d,RETURN,source)
    if support>.03:
        ACTIVE_COLOR=C['green'];arrows(d,DISCHARGE,support);arrows(d,DISCHARGE_RETURN,support)
        text(d,(614,343),'暂补',28,C['green'])
    elif scene==4 and recharge>.03:
        ACTIVE_COLOR=C['green'];arrows(d,CHARGE,recharge);arrows(d,CHARGE_RETURN,recharge)
        text(d,(614,343),'回充',28,C['green'])
    else:
        label='不再补给' if scene==3 else ('待回充' if scene==4 and q<.99 else '已稳定')
        text(d,(614,343),label,26,C['muted'])

def frame(scene,q,t,progress,caption):
    im,d=background(scene,t,progress,caption)
    if scene==0:types(d)
    elif scene==1:analogy(d,q)
    else:circuit(d,scene,q,t)
    return im

def tc(seconds):
    ms=round(seconds*1000);return f'{ms//3600000:02d}:{ms//60000%60:02d}:{ms//1000%60:02d}.{ms%1000:03d}'
def run(cmd):return subprocess.run(cmd,check=True,capture_output=True,timeout=180)
def cue(cues,phrase):
    matches=[item for item in cues if phrase in item[2]]
    if len(matches)!=1:raise ValueError('Narration mechanism cue not unique: '+phrase)
    return matches[0]
def phase(scene,t,u,cues):
    needles={2:'电源和连线没有立刻补齐时',3:'电源逐渐跟上',4:'电源又给电容补回能量'}
    if scene not in needles:return u
    a,b,_=cue(cues,needles[scene])
    if scene==2:
        busy_start,_,_=cue(cues,'芯片突然忙起来')
        if t<busy_start:return 0
        if t<a:return .15
        return .20+.80*clamp((t-a)/(b-a))
    return clamp((t-a)/(b-a))

def build(args,ffmpeg):
    media=ROOT/'web/media/capacitor-beginner';video=media/'video';video.mkdir(parents=True,exist_ok=True)
    review=args.review_output;review.mkdir(parents=True,exist_ok=True)
    for scene in range(5):frame(scene,.66 if scene!=3 else 1,1,1,LABELS[scene]).save(media/f'step-{scene+1}.png',optimize=True)
    narration=json.loads((ROOT/'content/capacitor-beginner-video-narration.json').read_text())
    with tempfile.TemporaryDirectory(prefix='capacitor-beginner-') as temporary:
        tmp=Path(temporary);joined=bytearray();scenes=[];captions=[];cues=[]
        for i,clip in enumerate(narration['clips']):
            decoded=tmp/f'{i}.pcm'
            run([ffmpeg,'-y','-v','error','-xerror','-i',str(video/'audio'/clip['filename']),'-ac','1','-ar',str(RATE),'-f','s16le',str(decoded)])
            data=decoded.read_bytes();spoken=len(data)/(2*RATE)
            if not 1<spoken<50:raise ValueError('Unexpected narration duration')
            start=len(joined)/(2*RATE);joined.extend(data);joined.extend(bytes(2*RATE));end=len(joined)/(2*RATE)
            scenes.append(dict(start=start,end=end,spoken_seconds=spoken,text=clip['text'],title=clip['title']))
            sentences=[s for s in re.split(r'(?<=[。？！；])',clip['text']) if s];total=sum(map(len,sentences));cursor=start;local=[]
            for sentence in sentences:
                wrap(sentence);stop=cursor+spoken*len(sentence)/total;local.append((cursor,stop,sentence));cursor=stop
            captions.extend(local);cues.append(local)
        exact=len(joined)/(2*RATE);count=math.ceil(exact*FPS);duration=count/FPS;joined.extend(bytes(round((duration-exact)*RATE)*2))
        with wave.open(str(tmp/'voice.wav'),'wb') as out:
            out.setnchannels(1);out.setsampwidth(2);out.setframerate(RATE);out.writeframes(joined)
        movie=tmp/'principle.mp4'
        process=subprocess.Popen([ffmpeg,'-y','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-',
          '-i',str(tmp/'voice.wav'),'-c:v','libx264','-preset','fast','-crf','21','-profile:v','high','-pix_fmt','yuv420p','-c:a','aac','-b:a','96k','-movflags','+faststart','-t',str(duration),str(movie)],stdin=subprocess.PIPE,stderr=subprocess.PIPE)
        samples=[];circuit_frames=0;mechanism_snapshots=set()
        try:
            for n in range(count):
                t=n/FPS;i=next((j for j,s in enumerate(scenes) if t<s['end']),4);s=scenes[i];u=(t-s['start'])/(s['end']-s['start'])
                caption=next((c for a,b,c in captions if a<=t<b),'');q=phase(i,t,u,cues[i]);im=frame(i,q,t,t/duration,caption);process.stdin.write(im.tobytes())
                if i>=2:circuit_frames+=1
                if i>=2 and q>=.5 and i not in mechanism_snapshots:
                    im.save(review/f'mechanism-{i+1}-half.jpg',quality=95);mechanism_snapshots.add(i)
                if i==0 and abs(u-.66)<.5/FPS/(s['end']-s['start']):im.save(tmp/'poster.jpg',quality=95)
                for marker in (.12,.48,.78):
                    if abs(t-(s['start']+marker*(s['end']-s['start'])))<.5/FPS:samples.append((i,marker,im.copy()))
            process.stdin.close();error=process.stderr.read().decode();code=process.wait()
            if code:raise RuntimeError(error)
        except Exception:process.kill();process.wait();raise
        run([ffmpeg,'-v','error','-xerror','-i',str(movie),'-f','null','-'])
        run([ffmpeg,'-y','-v','error','-i',str(movie),'-map','0:a:0','-ar',str(RATE),'-ac','1','-f','s16le',str(tmp/'verified.pcm')])
        sound=array.array('h',(tmp/'verified.pcm').read_bytes());rms=math.sqrt(sum(x*x for x in sound)/len(sound))
        if rms<100:raise ValueError('Silent soundtrack')
        (tmp/'zh.vtt').write_text('WEBVTT\n\n'+'\n\n'.join(f'{i+1}\n{tc(a)} --> {tc(b)}\n{c}' for i,(a,b,c) in enumerate(captions))+'\n')
        for a,b,c in captions:assert 0<=a<b<=duration
        for name in ('principle.mp4','poster.jpg','zh.vtt'):shutil.copyfile(tmp/name,video/name)
        narrow=Image.new('RGB',(894,840),C['paper'])
        for j,(i,marker,im) in enumerate(samples):
            im.save(review/f'scene-{i+1}-{round(marker*100)}.jpg',quality=95);narrow.paste(im.resize((298,168)),((j%3)*298,(j//3)*168))
        narrow.save(review/'video-298px.jpg',quality=95)
        stills=Image.new('RGB',(894,336),C['paper'])
        for i in range(5):stills.paste(Image.open(media/f'step-{i+1}.png').resize((298,168)),((i%3)*298,(i//3)*168))
        stills.save(review/'steps-298px.jpg',quality=95)
        metadata=dict(src='/media/capacitor-beginner/video/principle.mp4',poster='/media/capacitor-beginner/video/poster.jpg',captions='/media/capacitor-beginner/video/zh.vtt',title='芯片旁的电容：暂时帮忙，电源接力，再充回',duration_seconds=round(duration,3),
          attribution='原创星灯工坊机制动画；晓晓合成中文女声（Microsoft Edge Neural）。水杯只比喻短时缓冲；箭头为约定电流，不是电子。储能条、箭头粗细与时间为教学示意，不是实测或按比例的电路仿真；绝缘间隙没有电流箭头。',transcript=[dict(time=round(s['start'],3),text=s['text']) for s in scenes])
        (review/'video-metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n')
        report=dict(duration_seconds=duration,width=W,height=H,fps=FPS,frame_count=count,voice_rms=round(rms,2),audio_decoded_seconds=len(sound)/RATE,scenes=scenes,cues=len(captions),circuit_frames=circuit_frames,arrow_boundary_checks=GEOMETRY_CHECKS,electron_symbols=0,subtitle_timing='measured scene duration, weighted sentence windows; not word alignment',browser_device_playback='requires separate verification')
        (review/'video-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        lesson_file=ROOT/'content/capacitor.json';lesson=json.loads(lesson_file.read_text());lesson['visual_lesson']['video']=metadata
        audio_metadata=media/'audio/metadata.json'
        if audio_metadata.is_file():lesson['audio_lesson']=json.loads(audio_metadata.read_text())
        lesson_file.write_text(json.dumps(lesson,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(report,ensure_ascii=False))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--ffmpeg',default='ffmpeg');p.add_argument('--font',type=Path,required=True);p.add_argument('--review-output',type=Path,required=True);args=p.parse_args()
    ffmpeg=shutil.which(args.ffmpeg)
    if not ffmpeg or not args.font.is_file():p.error('Existing FFmpeg and Chinese font required')
    global FONT;FONT=str(args.font);build(args,ffmpeg)
if __name__=='__main__':main()
