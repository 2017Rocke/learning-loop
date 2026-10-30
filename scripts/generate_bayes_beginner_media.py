#!/usr/bin/env python3
"""Original Bayes beginner diagrams and a counted-lamp mechanism film.

Uses installed Pillow and, for video, existing FFmpeg plus prepared narration.
Every point represents exactly one teaching lamp. Orange means faulty and
blue means normal; purple outlines indicate alarms and never change true class.
No external model, service request, or installation is run. Captions are length-weighted
within measured speech segments, not word-aligned transcripts.
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
C=dict(bg='#142B48',ink='#243C56',rose='#CDA960',teal='#73539E',paper='#FFF9E9',mint='#E4DAF0',pink='#F3DDC1',blue='#DBE9F2',line='#B7A7C4',muted='#586A7A',red='#AF552D',soft='#E9E8E2',fault='#BD5E26',normal='#286D9B',alarm='#7B4AA4')
TITLES=['报警是线索，不等于故障','先看原本这一百盏灯','报警有两个来源','已知报警，就在报警队伍里数','只减少误报，先猜结果']
NAMES=['recognize','prior','branches','posterior','transfer']
LAMPS=tuple(range(100))
FAULTY=frozenset(range(10))
ALARMS=frozenset(list(range(8))+list(range(10,19)))
NEW_ALARMS=frozenset(list(range(8))+list(range(10,13)))
assert len(LAMPS)==100 and len(FAULTY)==10 and len(ALARMS)==17 and len(NEW_ALARMS)==11
assert len(ALARMS&FAULTY)==8 and len(ALARMS-FAULTY)==9
assert len(NEW_ALARMS&FAULTY)==8 and len(NEW_ALARMS-FAULTY)==3
FONT_PATH=None
FONTS={}

def font(n):
    if n not in FONTS:FONTS[n]=ImageFont.truetype(FONT_PATH,n)
    return FONTS[n]

def text(d,xy,s,size=35,color='ink',anchor='mm',limit=None):
    if limit is not None and d.textlength(s,font=font(size))>limit:
        raise ValueError(f'Text exceeds layout: {s}')
    d.text(xy,s,font=font(size),fill=C.get(color,color),anchor=anchor)

def box(d,xy,fill='paper',outline='line',radius=20,width=3):
    d.rounded_rectangle(xy,radius,fill=C.get(fill,fill),outline=C.get(outline,outline),width=width)

def arrow(d,a,b,color='teal',width=6):
    color=C.get(color,color);d.line((a,b),fill=color,width=width)
    angle=math.atan2(b[1]-a[1],b[0]-a[0]);d.polygon([b,(b[0]-16*math.cos(angle-.5),b[1]-16*math.sin(angle-.5)),(b[0]-16*math.cos(angle+.5),b[1]-16*math.sin(angle+.5))],fill=color)

def clamp(x):return max(0,min(1,x))
def ease(x):x=clamp(x);return x*x*(3-2*x)

def source_xy(lamp):
    return 78+30*(lamp%10),163+24*(lamp//10)

def destination_xy(lamp):
    if lamp in FAULTY:return 531+43*lamp,229
    return 531+40*(lamp-10),317

def lamp(d,xy,lamp_id,alarm=False,r=9,fade=1,seen=None):
    if seen is not None:
        if lamp_id in seen:raise AssertionError('Lamp drawn twice in a single view')
        seen.add(lamp_id)
    x,y=xy
    color=C['fault']if lamp_id in FAULTY else C['normal']
    if fade<1:
        bg=C['paper'];a=tuple(int(color[i:i+2],16)for i in (1,3,5));b=tuple(int(bg[i:i+2],16)for i in (1,3,5))
        color=tuple(round(v*fade+w*(1-fade))for v,w in zip(a,b))
    d.ellipse((x-r,y-r,x+r,y+r),fill=color)
    if fade>.3:
        if lamp_id in FAULTY:
            d.line((x-r*.38,y-r*.38,x+r*.38,y+r*.38),fill=C['paper'],width=max(1,round(r/4)))
            d.line((x-r*.38,y+r*.38,x+r*.38,y-r*.38),fill=C['paper'],width=max(1,round(r/4)))
        else:
            d.line((x-r*.45,y,x-r*.1,y+r*.32,x+r*.45,y-r*.37),fill=C['paper'],width=max(1,round(r/4)))
    if alarm:d.ellipse((x-r-4,y-r-4,x+r+4,y+r+4),outline=C['alarm'],width=3)

def star(d,x,y,r=10):
    d.line((x-r,y,x+r,y),fill=C['rose'],width=2);d.line((x,y-r,x,y+r),fill=C['rose'],width=2)

def base(index,video):
    im=Image.new('RGB',(W,H),C['bg']);d=ImageDraw.Draw(im)
    d.arc((760,-100,1080,220),0,360,fill='#354D65',width=18)
    star(d,886,40);star(d,923,71,6)
    text(d,(32,25),'证据观星台 · 贝叶斯入门',26,'rose','la')
    text(d,(35,66),TITLES[index],39,'paper','la',885)
    box(d,(23,119,937,427),'paper',None,23,0)
    return im,d

def draw_scene(index,u=1,video=False,subtitle='',progress=0,calculate=True):
    im,d=base(index,video)
    if index==0:
        # Two hypothetical explanations are not two newly classified lamps.
        box(d,(67,187,319,348),'mint','alarm',22)
        text(d,(193,225),'听到报警',39,'alarm')
        d.ellipse((162,252,224,314),fill='#D9DCE0',outline=C['alarm'],width=5)
        text(d,(193,283),'?',42,'ink')
        arrow(d,(331,267),(491,202),'teal');arrow(d,(331,267),(491,343),'teal')
        lamp(d,(560,202),0,False,23);text(d,(734,202),'可能故障',39,'ink')
        lamp(d,(560,343),10,False,23);text(d,(734,343),'也可能正常',39,'ink')
        if video:
            radius=39+int(5*math.sin(u*math.pi*7))
            d.arc((193-radius,283-radius,193+radius,283+radius),195,345,fill=C['alarm'],width=3)
        text(d,(480,397),'两种可能，不是把正常变故障',32,'muted')
    elif index in (1,2):
        seen=set()
        for lamp_id in LAMPS:
            selected=index==2 and lamp_id in ALARMS
            if video and index==2:
                selected=selected and ((lamp_id in FAULTY and u>.12)or(lamp_id not in FAULTY and u>.45))
            lamp(d,source_xy(lamp_id),lamp_id,selected,8,seen=seen)
        assert seen==set(LAMPS)
        if index==1:
            text(d,(641,175),'100 盏灯',44)
            box(d,(434,215,885,277),'pink',None,14,0);text(d,(678,246),'10 盏故障',39)
            box(d,(434,295,885,357),'blue',None,14,0);text(d,(678,326),'90 盏正常',39)
            text(d,(640,399),'原本故障比例 10%',35,'ink')
        else:
            text(d,(656,161),'紫圈 = 报警',34,'alarm')
            box(d,(427,200,900,274),'pink',None,15,0)
            text(d,(540,235),'故障 10',36,'red');arrow(d,(641,236),(696,236));text(d,(801,235),'报警 8',36,'alarm')
            box(d,(427,293,900,367),'blue',None,15,0)
            text(d,(540,328),'正常 90',36,'normal');arrow(d,(641,328),(696,328));text(d,(801,328),'误报 9',36,'alarm')
            text(d,(650,403),'两条路都要数',34,'ink')
    elif index==3:
        box(d,(460,142,909,365),'mint','alarm',22,4)
        text(d,(684,176),'报警队伍',37,'alarm')
        seen=set();in_pool=[]
        motion=ease(u)
        for lamp_id in LAMPS:
            if lamp_id in ALARMS:
                a=source_xy(lamp_id);b=destination_xy(lamp_id)
                xy=(a[0]+(b[0]-a[0])*motion,a[1]+(b[1]-a[1])*motion)
                lamp(d,xy,lamp_id,True,10 if motion==1 else 8+2*motion,seen=seen)
                if motion==1:in_pool.append(lamp_id)
            elif motion<1:
                lamp(d,source_xy(lamp_id),lamp_id,False,8,fade=1-motion,seen=seen)
        assert ALARMS.issubset(seen) and len(seen)==len(set(seen))
        if motion==1:
            assert set(in_pool)==ALARMS and len(in_pool)==17 and sum(i in FAULTY for i in in_pool)==8
            text(d,(247,211),'只保留',40,'teal');text(d,(247,270),'17 盏报警灯',37,'teal')
        else:text(d,(230,405),'同一批灯，按报警筛选',27,'muted')
        if calculate and motion==1:
            text(d,(685,399),'8 / 17 ≈ 47%',40,'alarm')
        else:text(d,(685,399),'先组好队，再数比例',33,'alarm')
    else:
        for side,x0,label in [(0,42,'之前：误报 9'),(1,496,'之后：误报 3')]:
            box(d,(x0,140,x0+422,410),'paper','line',20,3)
            text(d,(x0+211,171),label,35,'ink')
            text(d,(x0+211,209),'真故障报警 8',30,'red')
            seen=set()
            for i in range(8):lamp(d,(x0+72+39*i,248),i,r=12,seen=seen)
            if side==0:
                for j in range(9):lamp(d,(x0+53+39*j,321),10+j,r=12,seen=seen)
                assert len(seen)==17
            else:
                motion=ease(u)
                for j in range(9):
                    if j<3:lamp(d,(x0+53+39*j,321),10+j,r=12,seen=seen)
                    elif video and motion<1:
                        lamp(d,(x0+53+39*j,321+75*motion),10+j,r=12,fade=1-motion,seen=seen)
                if not video or motion==1:assert len(seen)==11
            text(d,(x0+211,376),'橙色仍为 8；蓝色是误报',25,'muted')
        # Intentionally no new denominator, percentage or direction: prediction.
    if video:
        box(d,(20,439,940,521),'ink',None,15,0)
        lines=split_caption(subtitle)
        for j,line in enumerate(lines):text(d,(480,467+34*j if len(lines)==2 else 482),line,33,'paper')
        d.rounded_rectangle((30,529,30+900*clamp(progress),535),3,fill=C['rose'])
    else:
        footers=['线索不等于真相','每个点 = 一盏灯；数字是教学假设','每个点 = 一盏灯；颜色不改变','17 个点 = 17 盏灯；其中 8 盏故障','每个点 = 一盏灯；先预测，不看答案']
        text(d,(480,486),footers[index],34,'paper')
    return im

def split_caption(s):
    if len(s)<=25:return [s]
    if len(s)>50:raise ValueError('Caption is too long: '+s)
    midpoint=(len(s)+1)//2
    points=[i for i,c in enumerate(s,1) if c in '，；。？！' and len(s)-25<=i<=25]
    n=min(points,key=lambda i:abs(i-midpoint))if points else midpoint
    return [s[:n],s[n:]]

def run(command):return subprocess.run(command,check=True,capture_output=True,timeout=180)
def tc(s):
    ms=round(s*1000);return f'{ms//3600000:02d}:{ms//60000%60:02d}:{ms//1000%60:02d}.{ms%1000:03d}'

def diagrams(args):
    args.output_dir.mkdir(parents=True,exist_ok=True);args.review_output.mkdir(parents=True,exist_ok=True)
    sheet=Image.new('RGB',(894,336),C['bg'])
    for i,name in enumerate(NAMES):
        im=draw_scene(i)
        im.save(args.output_dir/(name+'.png'),optimize=True)
        thumb=im.resize((298,168),Image.Resampling.LANCZOS)
        thumb.save(args.review_output/(name+'-298.png'))
        sheet.paste(thumb,((i%3)*298,(i//3)*168))
    sheet.save(args.review_output/'diagrams-298px.png')
    print('Generated 5 original counted-lamp diagrams.')

def film(args):
    ffmpeg=shutil.which(args.ffmpeg)
    if not ffmpeg:raise ValueError('An existing FFmpeg executable is required')
    clips=json.loads(args.input.read_text())['clips']
    if len(clips)!=5:raise ValueError('Five scene clips are required')
    video_dir=args.output_dir/'video';video_dir.mkdir(parents=True,exist_ok=True)
    args.review_output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='bayes-beginner-')as folder:
        tmp=Path(folder);joined=bytearray();scenes=[];captions=[]
        for i,c in enumerate(clips):
            pcm=tmp/f'{i}.pcm'
            run([ffmpeg,'-y','-v','error','-xerror','-i',str(args.audio_dir/c['filename']),'-ac','1','-ar',str(RATE),'-f','s16le',str(pcm)])
            data=pcm.read_bytes();spoken=len(data)/(2*RATE)
            if not 1<spoken<50:raise ValueError('Unexpected scene duration')
            start=len(joined)/(2*RATE);joined.extend(data);joined.extend(bytes(2*RATE));end=len(joined)/(2*RATE)
            scenes.append(dict(start=start,end=end,spoken_seconds=spoken,title=c['title'],text=c['text']))
            sentences=[s.strip()for s in re.split(r'(?<=[。？！；])',c['text'])if s.strip()]
            total=sum(map(len,sentences));cursor=start
            for sentence in sentences:
                split_caption(sentence);stop=cursor+spoken*len(sentence)/total
                captions.append((cursor,stop,sentence));cursor=stop
        exact=len(joined)/(2*RATE);count=math.ceil(exact*FPS);duration=count/FPS
        joined.extend(bytes(round((duration-exact)*RATE)*2))
        with wave.open(str(tmp/'audio.wav'),'wb')as f:
            f.setnchannels(1);f.setsampwidth(2);f.setframerate(RATE);f.writeframes(joined)
        command=[ffmpeg,'-y','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-','-i',str(tmp/'audio.wav'),'-c:v','libx264','-preset','fast','-crf','21','-pix_fmt','yuv420p','-c:a','aac','-b:a','96k','-movflags','+faststart','-t',str(duration),str(tmp/'principle.mp4')]
        process=subprocess.Popen(command,stdin=subprocess.PIPE,stderr=subprocess.PIPE);snaps=[]
        try:
            for n in range(count):
                t=n/FPS;index=next((i for i,s in enumerate(scenes)if t<s['end']),4);scene=scenes[index]
                u=clamp((t-scene['start'])/scene['spoken_seconds'])
                caption=next((s for a,b,s in captions if a<=t<b),'')
                # Re-group the same seventeen IDs before revealing the fraction.
                calculate=True
                if index==3:
                    calc_cue=next(a for a,b,s in captions if scene['start']<=a<scene['end'] and '故障比例是' in s)
                    u=clamp((t-scene['start'])/max(.1,calc_cue-scene['start']))
                    calculate=t>=calc_cue
                if index==4:
                    removal=next((a,b)for a,b,s in captions if scene['start']<=a<scene['end'] and '正常灯误报从九盏减少到三盏' in s)
                    u=clamp((t-removal[0])/max(.1,removal[1]-removal[0]))
                frame=draw_scene(index,u,True,caption,t/duration,calculate)
                process.stdin.write(frame.tobytes())
                if index==0 and abs(u-.6)<.5/FPS/scene['spoken_seconds']:frame.save(tmp/'poster.jpg',quality=95)
                for checkpoint in (.1,.5,.9):
                    if abs(t-(scene['start']+checkpoint*scene['spoken_seconds']))<.5/FPS:snaps.append((index,checkpoint,frame.copy()))
            process.stdin.close();error=process.stderr.read().decode();ret=process.wait()
            if ret:raise RuntimeError(error)
        except Exception:
            process.kill();process.wait();raise
        run([ffmpeg,'-v','error','-xerror','-i',str(tmp/'principle.mp4'),'-f','null','-'])
        run([ffmpeg,'-y','-v','error','-i',str(tmp/'principle.mp4'),'-map','0:a:0','-ar',str(RATE),'-ac','1','-f','s16le',str(tmp/'verified.pcm')])
        samples=array.array('h',(tmp/'verified.pcm').read_bytes());rms=math.sqrt(sum(x*x for x in samples)/len(samples))
        if rms<100:raise ValueError('Video soundtrack is silent')
        (tmp/'zh.vtt').write_text('WEBVTT\n\n'+'\n\n'.join(f'{i+1}\n{tc(a)} --> {tc(b)}\n{s}'for i,(a,b,s)in enumerate(captions))+'\n')
        for a,b,s in captions:assert 0<=a<b<=duration
        for name in ['principle.mp4','poster.jpg','zh.vtt']:shutil.copyfile(tmp/name,video_dir/name)
        sheet=Image.new('RGB',(894,168*5),C['bg'])
        for j,(index,q,im)in enumerate(snaps):
            im.save(args.review_output/f'scene-{index+1}-{int(q*100)}.jpg',quality=95)
            sheet.paste(im.resize((298,168),Image.Resampling.LANCZOS),((j%3)*298,(j//3)*168))
        sheet.save(args.review_output/'video-298px.jpg',quality=95)
        metadata=dict(src='/media/bayes-beginner/video/principle.mp4',poster='/media/bayes-beginner/video/poster.jpg',captions='/media/bayes-beginner/video/zh.vtt',title='100盏灯：报警以后重新组队',duration_seconds=round(duration,3),attribution='本项目原创计数动画；晓晓合成中文女声（Microsoft Edge Neural）。数字为教学假设，每点始终代表一盏灯；橙叉表示真实故障、蓝对号表示真实正常、紫圈表示报警。前后对照为同组不同条件，不相加计数。',transcript=[dict(time=round(s['start'],3),text=s['text'])for s in scenes])
        (args.review_output/'video-metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n')
        report=dict(duration_seconds=duration,frame_count=count,scenes=scenes,cues=len(captions),audio_rms=round(rms,2),decode_passed=True,count_invariant_frames=count-math.ceil(scenes[0]['end']*FPS),unit='one lamp per point',counting_scope='Scenes 2–5; scene 1 shows two possible explanations, not a counted population',original_counts=dict(total=100,faulty=10,normal=90),alarm_counts=dict(total=17,faulty=8,normal=9),transfer_counts=dict(faulty=8,normal=3),limitations='Synthetic functional diagrams; scene timing is measured but captions are length-weighted, not word alignment. Every dot remains one lamp; true class never changes. Playback requires separate browser/device checks.')
        (args.review_output/'video-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({'duration_seconds':duration,'frames':count,'audio_rms':round(rms,2)},ensure_ascii=False))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--font',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,default=ROOT/'web/media/bayes-beginner')
    p.add_argument('--review-output',type=Path,required=True)
    p.add_argument('--input',type=Path)
    p.add_argument('--audio-dir',type=Path)
    p.add_argument('--ffmpeg',default='ffmpeg')
    args=p.parse_args()
    global FONT_PATH
    FONT_PATH=str(args.font)
    diagrams(args)
    if args.input:
        if not args.audio_dir:p.error('--audio-dir is required with --input')
        film(args)

if __name__=='__main__':main()
