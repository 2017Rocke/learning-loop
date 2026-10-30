#!/usr/bin/env python3
"""Original VoiceStudio beginner diagrams and mechanism film.

Uses installed Pillow and, for video, existing FFmpeg plus prepared narration.
No VoiceStudio code, model inference, service request or installation is run.
All cards and waveforms are functional illustrations, not software screenshots
or recordings of the three example sentences. Captions are length-weighted
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
C=dict(bg='#F3E5ED',ink='#263F4A',rose='#A8446A',teal='#14756F',paper='#FFFDF5',mint='#D3EDE0',pink='#F8D9E4',blue='#DDEDF6',line='#B8829C',muted='#53656D',red='#9C3F4F',soft='#EADFE5')
TITLES=['语音工作台，不是声音模型','先把三句提醒写清楚','文字和声音，保持对应','连接已有声音，不会补句','对照原稿，完整听到结尾']
NAMES=['roles','script','pairs','join','listen']
SENTENCES=['先合上课本。','用自己的话解释一个概念。','想不起来，就回去看对应的一段。']
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

def guide(d,x,y):
    # Original little garden helper with petal ears and a headset.
    d.ellipse((x-36,y-41,x-5,y-5),fill=C['pink'],outline=C['rose'],width=2)
    d.ellipse((x+5,y-41,x+36,y-5),fill=C['pink'],outline=C['rose'],width=2)
    d.ellipse((x-29,y-22,x+29,y+33),fill=C['paper'],outline=C['rose'],width=3)
    d.arc((x-34,y-30,x+34,y+35),180,360,fill=C['teal'],width=5)
    d.ellipse((x-14,y+3,x-7,y+11),fill=C['ink']);d.ellipse((x+7,y+3,x+14,y+11),fill=C['ink'])
    d.arc((x-9,y+10,x+9,y+23),0,180,fill=C['rose'],width=3)

def wavelet(d,x,y,w=120,h=32,phase=0,color='teal'):
    # Deliberately synthetic, non-semantic waveform, never labelled measured.
    for i in range(18):
        q=i/17; amp=(.25+.75*abs(math.sin(i*1.23+.3)))*h
        d.line((x+q*w,y-amp/2,x+q*w,y+amp/2),fill=C[color],width=5)

def checked(d,x,y,on):
    box(d,(x-17,y-17,x+17,y+17),'mint' if on else 'paper','teal',7,3)
    if on:d.line((x-9,y,x-2,y+8,x+11,y-9),fill=C['teal'],width=4)

def base(index,video):
    im=Image.new('RGB',(W,H),C['bg']);d=ImageDraw.Draw(im)
    d.arc((-80,-145,190,140),0,360,fill='#D0E4D5',width=20)
    d.arc((820,390,1080,660),0,360,fill='#E9C0CF',width=20)
    text(d,(32,28),'回声花园 · VoiceStudio 入门',25,'rose','la')
    text(d,(40,66),TITLES[index],40,'ink','la',880)
    box(d,(23,112,937,427),'paper',None,23,0)
    guide(d,887,45)
    return im,d

def draw_scene(index,u=1,video=False,subtitle='',progress=0):
    im,d=base(index,video)
    if index==0:
        labels=['文字','工作台','模型','声音'];xs=[36,270,504,738]
        for i,(x,label) in enumerate(zip(xs,labels)):
            box(d,(x,203,x+186,317),['pink','blue','mint','pink'][i],'rose' if i in (0,3) else 'teal',18)
            text(d,(x+93,242),label,39)
            if i==0:text(d,(x+93,286),'说什么',30,'rose')
            elif i==1:text(d,(x+93,286),'组织制作',30,'teal')
            elif i==2:text(d,(x+93,286),'产生语音',30,'teal')
            else:wavelet(d,x+35,285,116,24)
            if i<3:arrow(d,(x+193,260),(x+225,260))
        if video:
            stage=min(2,int(u*3)); p=(u*3)%1 if u<1 else 1
            x=xs[stage]+194+p*29
            d.ellipse((x-7,252,x+7,266),fill=C['rose'])
        text(d,(480,375),'先认分工，再做一小段',36,'teal')
    elif index==1:
        for i,s in enumerate(SENTENCES):
            y=166+i*94
            active=not video or u>i/3
            box(d,(60,y-30,899,y+40),'mint' if active else 'soft',None,15,0)
            d.ellipse((78,y-18,128,y+32),fill=C['teal'] if active else C['muted'])
            text(d,(103,y+9),str(i+1),32,'paper')
            text(d,(156,y+7),s,36,'ink','lm',725)
        # Not shown as a claim that automatic segmentation is one sentence/block.
    elif index==2:
        for i in range(3):
            y=174+i*88
            box(d,(67,y-32,331,y+34),'pink','rose',14)
            text(d,(199,y),f'文字 {i+1}',38,'rose')
            arrow(d,(348,y),(596,y),'teal')
            ready=(not video) or u>=(i+1)/3
            box(d,(619,y-32,890,y+34),'mint' if ready else 'soft','teal',14)
            text(d,(682,y),str(i+1),36,'teal')
            if ready:wavelet(d,718,y,138,33)
            if video and i/3<=u<(i+1)/3:
                p=ease((u-i/3)*3)
                d.ellipse((346+p*235-10,y-10,346+p*235+10,y+10),fill=C['rose'])
        text(d,(480,409),'一块不一定一句；编号用于找回原文',29,'muted')
    elif index==3:
        text(d,(129,157),'已有声音',31,'rose')
        xs=[251,456,661]
        for i,x in enumerate(xs):
            missing=i==1
            box(d,(x,135,x+166,215),'soft' if missing else 'mint','red' if missing else 'teal',16)
            text(d,(x+83,174),'2 为空' if missing else str(i+1),37,'red' if missing else 'teal')
        arrow(d,(460,231),(460,270),'teal')
        text(d,(129,319),'连接后',31,'rose')
        shift=50*(1-ease(u)) if video else 0
        for i,(label,x) in enumerate([('1',326-shift),('3',500+shift)]):
            box(d,(x,280,x+168,362),'mint','teal',15)
            text(d,(x+35,320),label,39,'teal');wavelet(d,x+70,320,72,24)
        if not video or u>.58:text(d,(480,402),'能播放，也可能缺了第二句',35,'red')
    else:
        text(d,(242,149),'原稿清单',35,'rose')
        for i in range(3):
            y=205+i*73
            on=(u>=(i+1)/3) if video else i==0
            box(d,(58,y-26,615,y+28),'mint' if on else 'paper','teal',12,2)
            text(d,(123,y),str(i+1),36,'teal')
            d.line((173,y-6,472,y-6),fill=C['line'],width=4)
            d.line((173,y+9,405,y+9),fill=C['line'],width=3)
            checked(d,557,y,on)
        box(d,(714,142,869,386),'blue','teal',23,4)
        box(d,(729,176,854,349),'paper',None,11,0)
        text(d,(791,204),'手机',31,'teal')
        wavelet(d,745,265,94,44)
        playx=745+94*clamp(u)
        d.line((playx,238,playx,292),fill=C['rose'],width=4)
        text(d,(791,324),'听到结尾',26,'rose')
        d.ellipse((783,357,799,373),fill=C['teal'])
    if video:
        box(d,(20,439,940,521),'ink',None,15,0)
        lines=split_caption(subtitle)
        for j,line in enumerate(lines):text(d,(480,467+34*j if len(lines)==2 else 482),line,33,'paper')
        d.rounded_rectangle((30,529,30+900*clamp(progress),535),3,fill=C['teal'])
    else:
        footers=['功能示意，不是软件截图','先写全内容；音色不能替你补稿','波形为示意，不是实测音频','拼接不等于重新生成','逐句核对，不只抽听开头']
        text(d,(480,488),footers[index],35,'teal')
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
    print('Generated 5 original diagrams.')

def film(args):
    ffmpeg=shutil.which(args.ffmpeg)
    if not ffmpeg:raise ValueError('An existing FFmpeg executable is required')
    clips=json.loads(args.input.read_text())['clips']
    if len(clips)!=5:raise ValueError('Five scene clips are required')
    video_dir=args.output_dir/'video';video_dir.mkdir(parents=True,exist_ok=True)
    args.review_output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='voicestudio-beginner-')as folder:
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
                frame=draw_scene(index,u,True,caption,t/duration)
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
        metadata=dict(src='/media/voicestudio-beginner/video/principle.mp4',poster='/media/voicestudio-beginner/video/poster.jpg',captions='/media/voicestudio-beginner/video/zh.vtt',title='三句中文怎样变成完整旁白',duration_seconds=round(duration,3),attribution='本项目原创流程动画；晓晓合成中文女声（Microsoft Edge Neural）。卡片和波形为教学示意，不是 VoiceStudio 界面、实测音频或模型演示；真实分块不一定一块一句。',transcript=[dict(time=round(s['start'],3),text=s['text'])for s in scenes])
        (args.review_output/'video-metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n')
        report=dict(duration_seconds=duration,frame_count=count,scenes=scenes,cues=len(captions),audio_rms=round(rms,2),decode_passed=True,limitations='Synthetic functional diagrams; scene timing is measured but captions are length-weighted, not word alignment. No VoiceStudio execution. Playback requires separate browser/device checks.')
        (args.review_output/'video-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({'duration_seconds':duration,'frames':count,'audio_rms':round(rms,2)},ensure_ascii=False))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--font',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,default=ROOT/'web/media/voicestudio-beginner')
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
