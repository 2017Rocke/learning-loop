#!/usr/bin/env python3
"""Render a short, original MOS electronic-switch film from prepared speech.

This optional author tool needs existing Pillow, FFmpeg and a Chinese font.
It does not contact a model/service, install packages, change lesson JSON or
touch learning records. Input clips use the generate_neural_audio.py schema.
The public output is media plus a metadata fragment for the course author.
All circuit motion is a teaching schematic, not a device simulation or wiring
guide. Arrows mean conventional current. No electrons are drawn and no arrow
crosses the gate insulator. The lamp module is represented as a resistive load;
the chosen logic-level N-channel device is assumed suitable for 3.3 V drive.
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
C = dict(night='#172D30', paper='#FFF5DC', brass='#C59A53', light='#F2D89E',
         ink='#253D3C', muted='#586B65', control='#79549C', controlsoft='#EEE3F4',
         current='#247F69', currentsoft='#D6EDDD', wire='#477B79', pale='#C8D7C7')
TITLES = ['为什么要用 MOS 管？', '先借水龙头，认清三个角色',
          '给 G 合适的电压，开关打开', '灯的电流，来自电源',
          '把 G 主动拉低，开关关闭']
# The whole conventional-current route is an external closed circuit.
LOAD_ROUTE = [(150, 215), (150, 180), (735, 180), (735, 382), (150, 382), (150, 315), (150, 215)]
INSULATOR = (682, 260, 697, 342)
FONT_CACHE = {}
FONT_PATH = None


def font(size):
    if size not in FONT_CACHE:
        FONT_CACHE[size] = ImageFont.truetype(FONT_PATH, size)
    return FONT_CACHE[size]


def text(d, xy, value, size=30, fill=None, anchor='mm'):
    d.text(xy, str(value), font=font(size), fill=fill or C['ink'], anchor=anchor)


def box(d, xy, fill, outline=None, radius=12, width=2):
    d.rounded_rectangle(xy, radius=radius, fill=C.get(fill, fill),
                        outline=C.get(outline, outline), width=width)


def clamp(x):
    return max(0, min(1, x))


def ease(x):
    x = clamp(x)
    return x*x*(3-2*x)


def arrow(d, a, b, color, width=5):
    d.line([a, b], fill=color, width=width)
    theta = math.atan2(b[1]-a[1], b[0]-a[0])
    d.polygon([b, (b[0]-11*math.cos(theta-.55), b[1]-11*math.sin(theta-.55)),
               (b[0]-11*math.cos(theta+.55), b[1]-11*math.sin(theta+.55))], fill=color)


def arrow_bounds(a, b, width=5):
    theta=math.atan2(b[1]-a[1],b[0]-a[0])
    points=[a,b,(b[0]-11*math.cos(theta-.55),b[1]-11*math.sin(theta-.55)),
            (b[0]-11*math.cos(theta+.55),b[1]-11*math.sin(theta+.55))]
    return (min(p[0] for p in points)-width/2,min(p[1] for p in points)-width/2,
            max(p[0] for p in points)+width/2,max(p[1] for p in points)+width/2)


def route_point(fraction):
    length = sum(math.dist(a, b) for a, b in zip(LOAD_ROUTE, LOAD_ROUTE[1:]))
    distance = clamp(fraction)*length
    for a, b in zip(LOAD_ROUTE, LOAD_ROUTE[1:]):
        segment = math.dist(a, b)
        if distance <= segment:
            q = distance/segment
            return a[0]+(b[0]-a[0])*q, a[1]+(b[1]-a[1])*q
        distance -= segment
    return LOAD_ROUTE[-1]


def current_arrows(d, t, trace=1):
    """A growing set of fixed arrow symbols traces the route, not electrons."""
    for i in range(16):
        q = (i+.3)/16
        if q <= trace:
            a, b = route_point(q-.008), route_point(q+.008)
            # Source is a power block; the wire arrows stop at its terminals.
            if 110 < a[0] < 200 and 215 < a[1] < 315:
                continue
            bounds=arrow_bounds(a,b)
            assert (bounds[2] < INSULATOR[0] or bounds[0] > INSULATOR[2]
                    or bounds[3] < INSULATOR[1] or bounds[1] > INSULATOR[3]), 'Current symbol intersects gate insulation'
            arrow(d, a, b, C['current'], 4 + int(math.sin(t*2)>0))


def split_caption(value, limit=23):
    if len(value) <= limit:
        return [value]
    if len(value) > limit*2:
        raise ValueError('Subtitle sentence is too long; shorten the source narration')
    midpoint = (len(value)+1)//2
    candidates = [i for i, c in enumerate(value, 1) if c in '，；。？！' and len(value)-limit <= i <= limit]
    split = min(candidates, key=lambda i: abs(i-midpoint)) if candidates else min(limit, midpoint)
    return [value[:split], value[split:]]


def frame(scene, u, t, progress, caption):
    im = Image.new('RGB', (W, H), C['night'])
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((13, 13, 947, 525), 20, outline=C['brass'], width=2)
    text(d, (42, 30), '机械工坊 · MOS 管入门', 27, C['light'], 'la')
    text(d, (42, 79), TITLES[scene], 37, C['paper'], 'la')
    # Original mint crystal companion; decorative, outside the circuit panel.
    x, y = 888, 63+math.sin(t*1.5)*3
    d.polygon([(x,y-24),(x+19,y),(x+12,y+23),(x,y+30),(x-15,y+18),(x-19,y)], fill='#BCEACF')
    d.line([(x,y-24),(x+3,y),(x,y+30)], fill='#E1F9DC', width=3)
    for dx in (-6,6):
        d.ellipse((x+dx-2,y,x+dx+2,y+4),fill=C['ink'])
    d.arc((x-29,y+5,x+29,y+24),0,180,fill=C['light'],width=3)
    for i in range(5):
        d.ellipse((726+i*24,108,736+i*24,118),fill=C['light'] if i<=scene else '#51645A')
    box(d, (30,132,930,402), 'paper', 'brass', 18)
    box(d, (36,416,924,510), '#102327', '#52706A', 15)
    for i, line in enumerate(split_caption(caption)):
        text(d, (480,442+i*40),line,38,C['paper'])
    d.rounded_rectangle((43,523,917,529),3,fill='#4B635A')
    d.rounded_rectangle((43,523,43+874*progress,529),3,fill=C['light'])
    if scene == 0:
        intro(d, u, t)
    elif scene == 1:
        analogy(d, u, t)
    else:
        circuit(d, scene, u, t)
    return im


def lamp(d, cx, cy, on):
    if on:
        d.ellipse((cx-48,cy-48,cx+48,cy+48),fill='#F4DB86')
        for angle in (0,.7,1.6,2.3,3.1,3.9,4.7,5.4):
            d.line((cx+53*math.cos(angle),cy+53*math.sin(angle),cx+62*math.cos(angle),cy+62*math.sin(angle)),fill=C['brass'],width=3)
    d.ellipse((cx-28,cy-28,cx+28,cy+28),fill='#FFE699' if on else '#E0E2CF',outline=C['brass'],width=4)
    d.line((cx-17,cy-17,cx+17,cy+17),fill=C['ink'],width=3)
    d.line((cx+17,cy-17,cx-17,cy+17),fill=C['ink'],width=3)


def intro(d, u, t):
    box(d, (76,204,290,316), 'controlsoft', 'control')
    text(d,(183,235),'单片机',35)
    text(d,(183,283),'发出开灯信号',26,C['control'])
    lamp(d, 750,251,False)
    text(d,(750,160),'5 V 小灯模块',30)
    for x in range(309,634,21):
        d.line((x,251,x+10,251),fill=C['control'],width=4)
    text(d,(475,216),'仅靠信号脚',29,C['control'])
    text(d,(475,288),'供电能力不够',29,C['ink'])
    if u > .42:
        box(d,(319,331,631,382),'currentsoft','current')
        text(d,(475,357),'加一个电子开关',31,C['current'])
    text(d,(750,333),'需要电源来出力',27)


def analogy(d, u, t):
    """The familiar object and electrical roles stay separate and labelled."""
    text(d,(264,161),'水龙头：先看角色',28,C['muted'])
    # Original side-view faucet: handle is separate from the water passage.
    d.rounded_rectangle((139,274,369,318),12,fill='#C9E7D7',outline=C['brass'],width=4)
    d.rounded_rectangle((332,279,375,343),8,fill='#C9E7D7',outline=C['brass'],width=4)
    d.line((257,226,257,274),fill=C['brass'],width=12)
    d.rounded_rectangle((207,214,307,233),8,fill=C['control'])
    text(d,(257,191),'手柄',31,C['control'])
    text(d,(142,345),'进水',28,C['current'])
    text(d,(392,351),'出水',28,C['current'])
    d.line((469,158,469,369),fill='#D5C8A3',width=2)
    text(d,(702,161),'MOS：对应三个角色',28,C['muted'])
    box(d,(527,199,877,252),'controlsoft','control')
    text(d,(702,227),'G 栅极 → 控制',34,C['control'])
    box(d,(527,275,877,334),'currentsoft','current')
    text(d,(702,305),'D 漏极 · S 源极',31,C['current'])
    text(d,(702,359),'负载电流通路的两端',27)
    text(d,(264,382),'只是类比：器件内没有手柄',23,C['muted'])


def scene_state(scene, u):
    # Stage changes are deliberately slow, visible actions. Gate charge and
    # resistance are not numerically simulated; values identify control states.
    if scene == 1:
        return 0.0, False
    if scene == 2:
        q = ease((u-.18)/.30)
        return q, u >= .55
    if scene == 3:
        return 1.0, True
    q = 1-ease((u-.24)/.25)
    return q, u < .52


def circuit(d, scene, u, t):
    gate, on = scene_state(scene, u)
    # Stable spatial arrangement throughout: supply left; load above MOS right;
    # controller in the middle, G branch purple, shared source reference below.
    d.line([(150,215),(150,180),(735,180),(735,185)],fill=C['wire'],width=5)
    d.line([(735,241),(735,275)],fill=C['wire'],width=5)
    d.line([(735,338),(735,382),(150,382),(150,315)],fill=C['wire'],width=5)
    box(d,(100,215,200,315),'currentsoft','current')
    text(d,(150,244),'电源',30)
    text(d,(150,286),'5 V',29)
    text(d,(119,194),'+',27,C['current'])
    text(d,(119,337),'−',30,C['current'])
    text(d,(435,153),'小灯模块（按电阻负载理解）',25,C['muted'])
    lamp(d,735,213,on)
    text(d,(838,213),'亮' if on else '灭',38,C['current'] if on else C['muted'])
    box(d,(334,239,525,322),'controlsoft','control')
    text(d,(429,266),'单片机',32)
    text(d,(429,302),'发令，不供灯电流',21,C['control'])
    d.line([(350,322),(350,333),(300,333),(300,382)],fill=C['wire'],width=3)
    d.line([(525,285),(665,285)],fill=C['control'],width=5)
    d.line((665,260,665,342),fill=C['control'],width=7)
    d.rectangle(INSULATOR,fill='#D3CFDD',outline='#9E91AB',width=2)
    text(d,(683,359),'绝缘',21,C['control'])
    # The gap is actual whitespace: the control wire never joins the channel.
    if gate > 0:
        for yy in range(267,339,13):
            d.line((673,yy,679,yy),fill='#9D85BA',width=2)
    text(d,(611,259),'G',33,C['control'])
    text(d,(592,322),'控制',26,C['control'])
    d.line((735,275,735,294),fill=C['wire'],width=5)
    d.line((735,322,735,338),fill=C['wire'],width=5)
    if on:
        d.line((735,294,735,322),fill=C['current'],width=7)
    else:
        d.line((735,322,713,296),fill=C['wire'],width=5)
    for yy in (294,322):
        d.ellipse((731,yy-4,739,yy+4),fill=C['wire'])
    text(d,(778,261),'D',29)
    text(d,(778,350),'S',29)
    text(d,(844,298),'MOS',31)
    text(d,(837,333),'导通' if on else '关断',26,C['current'] if on else C['muted'])
    text(d,(429,351),'G 对 S：'+('3.3 V' if gate >= .99 else ('0 V' if gate <= .01 else '变化中')),27,C['control'])
    # A short bar shows gate control-state change without drawing charge across
    # insulation or implying that an arbitrary Vgs threshold fully turns it on.
    box(d,(334,367,525,373),'#D2C1DE',radius=2)
    if gate > .01:
        box(d,(334,367,334+191*gate,373),'control',radius=2)
    if on:
        current_arrows(d,t,ease(u/.65) if scene==3 else 1)
    if scene == 1:
        text(d,(260,390),'共同参考：电源负端',21,C['muted'])
    elif scene == 2:
        text(d,(260,390),'假设：MOS 已按 3.3 V 驱动选好',21,C['muted'])
    elif scene == 3:
        text(d,(260,390),'绿色箭头＝约定电流方向',21,C['current'])
    else:
        text(d,(260,390),'主动拉低 ≠ 把控制线悬空',21,C['control'])


def tc(seconds):
    ms = round(seconds*1000)
    return f'{ms//3600000:02d}:{ms//60000%60:02d}:{ms//1000%60:02d}.{ms%1000:03d}'


def cue_containing(cues, phrase):
    """Resolve a meaning-bearing cue; added intro sentences cannot shift it."""
    matches=[cue for cue in cues if phrase in cue[2]]
    if len(matches)!=1:
        raise ValueError(f'Expected exactly one narration cue containing {phrase!r}')
    return matches[0]


def action_for(index, t, u, cues):
    if index==0:
        start,end,_=cue_containing(cues,'请外部电源供能')
        return .43 if t>=start else 0
    if index==2:
        start,end,_=cue_containing(cues,'控制器把G相对S的电压升到合适值')
        return clamp((t-start)/(end-start))
    if index==3:
        start,end,_=cue_containing(cues,'电源正端，经过小灯')
        return clamp((t-start)/(end-start))
    if index==4:
        start,end,_=cue_containing(cues,'把G主动拉回S的电位')
        return clamp((t-start)/(end-start))
    return u


def run(command):
    return subprocess.run(command,check=True,capture_output=True,timeout=180)


def build(args, ffmpeg):
    source = json.loads(args.input.read_text())
    clips = source['clips']
    if len(clips) != 5:
        raise ValueError('The beginner film needs five narration clips')
    args.output_dir.mkdir(parents=True,exist_ok=True)
    args.review_output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='mos-beginner-') as folder:
        tmp = Path(folder)
        joined = bytearray(); scenes = []; captions = []; scene_cues=[]
        for i, clip in enumerate(clips):
            audio = args.audio_dir/clip['filename']
            pcm = tmp/f'{i}.pcm'
            run([ffmpeg,'-y','-v','error','-xerror','-i',str(audio),'-ac','1','-ar',str(RATE),'-f','s16le',str(pcm)])
            data = pcm.read_bytes(); spoken = len(data)/(2*RATE)
            if not 1 < spoken < 45:
                raise ValueError('Unexpected narration duration')
            start = len(joined)/(2*RATE)
            joined.extend(data); joined.extend(bytes(2*RATE))
            end = len(joined)/(2*RATE)
            scenes.append(dict(start=start,end=end,spoken_seconds=spoken,title=clip['title'],text=clip['text']))
            sentences = [s.strip() for s in re.split(r'(?<=[。？！；])',clip['text']) if s.strip()]
            cursor = start; total = sum(len(s) for s in sentences)
            local_cues=[]
            for sentence in sentences:
                split_caption(sentence)
                stop = cursor+spoken*len(sentence)/total
                captions.append((cursor,stop,sentence)); cursor = stop
                local_cues.append(captions[-1])
            scene_cues.append(local_cues)
        exact = len(joined)/(2*RATE); nframes = math.ceil(exact*FPS); duration = nframes/FPS
        joined.extend(bytes(round((duration-exact)*RATE)*2))
        with wave.open(str(tmp/'narration.wav'),'wb') as stream:
            stream.setnchannels(1); stream.setsampwidth(2); stream.setframerate(RATE); stream.writeframes(joined)
        movie = tmp/'principle.mp4'
        command = [ffmpeg,'-y','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-',
                   '-i',str(tmp/'narration.wav'),'-c:v','libx264','-preset','fast','-crf','21','-profile:v','high','-pix_fmt','yuv420p',
                   '-c:a','aac','-b:a','96k','-movflags','+faststart','-t',str(duration),str(movie)]
        process = subprocess.Popen(command,stdin=subprocess.PIPE,stderr=subprocess.PIPE)
        snapshots=[]; boundary_frames=0
        try:
            for n in range(nframes):
                t=n/FPS
                index=next((i for i,s in enumerate(scenes) if t<s['end']),len(scenes)-1)
                scene=scenes[index]; u=(t-scene['start'])/(scene['end']-scene['start'])
                caption=next((c for a,b,c in captions if a<=t<b),'')
                # Cause/state transitions follow the appropriate spoken
                # sentence window, not an arbitrary midpoint of the whole
                # scene. Sentence windows are length-weighted within measured
                # speech; this is intentionally not claimed as word alignment.
                action=action_for(index,t,u,scene_cues[index])
                im=frame(index,action,t,t/duration,caption)
                process.stdin.write(im.tobytes())
                # current_arrows checks every rendered symbol, including its
                # head and stroke width, against the gate insulator. Off frames
                # render no current symbols at all. Count circuit frames only.
                if index>=2:
                    boundary_frames += 1
                if index==0 and abs(u-.72)<.5/FPS/(scene['end']-scene['start']):
                    im.save(tmp/'poster.jpg',quality=94,optimize=True)
                for checkpoint in (.10,.48,.72):
                    if abs(t-(scene['start']+checkpoint*(scene['end']-scene['start'])))<.5/FPS:
                        snapshots.append((index,checkpoint,im.copy()))
            process.stdin.close(); error=process.stderr.read().decode(); code=process.wait()
            if code:
                raise RuntimeError(error)
        except Exception:
            process.kill();process.wait();raise
        run([ffmpeg,'-v','error','-xerror','-i',str(movie),'-f','null','-'])
        run([ffmpeg,'-y','-v','error','-i',str(movie),'-map','0:a:0','-ar',str(RATE),'-ac','1','-f','s16le',str(tmp/'verified.pcm')])
        samples=array.array('h',(tmp/'verified.pcm').read_bytes())
        rms=math.sqrt(sum(x*x for x in samples)/len(samples))
        if rms<100:
            raise ValueError('Silent video soundtrack')
        vtt='WEBVTT\n\n'+'\n\n'.join(f'{i+1}\n{tc(a)} --> {tc(b)}\n{c}' for i,(a,b,c) in enumerate(captions))+'\n'
        (tmp/'zh.vtt').write_text(vtt)
        for a,b,c in captions:
            assert 0<=a<b<=duration
        for filename in ('principle.mp4','poster.jpg','zh.vtt'):
            shutil.copyfile(tmp/filename,args.output_dir/filename)
        sheet=Image.new('RGB',(960,270*math.ceil(len(snapshots)/2)),C['paper'])
        narrow=Image.new('RGB',(298*3,168*5),C['paper'])
        for i,(index,checkpoint,im) in enumerate(snapshots):
            im.save(args.review_output/f'scene-{index+1}-{round(checkpoint*100)}.jpg',quality=95)
            sheet.paste(im.resize((480,270)),((i%2)*480,(i//2)*270))
            narrow.paste(im.resize((298,168)),((i%3)*298,(i//3)*168))
        sheet.save(args.review_output/'mos-beginner-frames.jpg',quality=95)
        narrow.save(args.review_output/'mos-beginner-298px.jpg',quality=95)
        metadata=dict(src=args.media_prefix+'/principle.mp4',poster=args.media_prefix+'/poster.jpg',
                      captions=args.media_prefix+'/zh.vtt',title='用小信号控制小灯：MOS 电子开关',
                      duration_seconds=round(duration,3),
                      attribution='本项目原创原理动画；晓晓合成中文女声（Microsoft Edge Neural）。N 沟道低端开关示意；小灯模块按电阻负载理解，器件假设适合 3.3 V 驱动。绿色箭头为约定电流，紫色为控制；不是实物接线或测量。',
                      transcript=[dict(time=round(s['start'],3),text=s['text']) for s in scenes])
        (args.review_output/'video-metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n')
        report=dict(duration_seconds=duration,audio_decoded_seconds=len(samples)/RATE,voice_rms=round(rms,2),
                    width=W,height=H,fps=FPS,scenes=scenes,cues=len(captions),frame_count=nframes,
                    insulator_boundary_frames_checked=boundary_frames,
                    limitations='Teaching states, not semiconductor simulation; subtitles use measured scene time, not word alignment. Browser and device playback require separate checks.')
        (args.review_output/'video-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(report,ensure_ascii=False))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--audio-dir',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,default=ROOT/'web/media/mosfet-beginner/video')
    parser.add_argument('--media-prefix',default='/media/mosfet-beginner/video')
    parser.add_argument('--review-output',type=Path,required=True)
    parser.add_argument('--font',type=Path,required=True)
    parser.add_argument('--ffmpeg',default='ffmpeg')
    args=parser.parse_args()
    ffmpeg=shutil.which(args.ffmpeg)
    if not ffmpeg or not args.font.is_file():
        parser.error('An existing FFmpeg executable and Chinese font are required')
    global FONT_PATH
    FONT_PATH=str(args.font)
    build(args,ffmpeg)


if __name__=='__main__':
    main()
