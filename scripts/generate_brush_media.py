#!/usr/bin/env python3
"""Generate original teaching diagrams and a silent H.264 Gaussian-splatting film.

Requires Pillow, numpy, and macOS Swift/AVFoundation; no downloaded media or codecs.
The scenes illustrate the mechanism; they are not outputs from a reconstruction.
Run with the bundled Python environment documented in the project README.
"""
from pathlib import Path
import argparse
import json
import math
import subprocess
import tempfile
import time

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "web/media/brush"
W, H, FPS, DURATION = 960, 540, 15, 48
BG, PANEL, INK, MUTED = "#102332", "#173344", "#F3F3E9", "#A8C1C7"
GREEN, GOLD, BLUE = "#8AE1B4", "#E5BE84", "#8FC8ED"
FONT = "/System/Library/Fonts/STHeiti Light.ttc"
fonts = {s: ImageFont.truetype(FONT, s) for s in [22, 28, 30, 36]}


def text(draw, xy, value, size=28, fill=INK, anchor=None):
    draw.text(xy, value, font=fonts[size], fill=fill, anchor=anchor)


def ease(x):
    x = min(1, max(0, x))
    return x * x * (3 - 2 * x)


def arrow(draw, a, b, color=GREEN, width=3):
    draw.line([a, b], fill=color, width=width)
    theta = math.atan2(b[1]-a[1], b[0]-a[0])
    tip = [(b[0]-13*math.cos(theta-.5), b[1]-13*math.sin(theta-.5)), b,
           (b[0]-13*math.cos(theta+.5), b[1]-13*math.sin(theta+.5))]
    draw.line(tip, fill=color, width=width)


def camera(draw, xy, color=GOLD, scale=1):
    x, y = xy
    draw.rounded_rectangle((x-20*scale, y-13*scale, x+15*scale, y+13*scale), radius=5, outline=color, width=3)
    draw.polygon([(x+15*scale,y-7*scale),(x+28*scale,y-14*scale),(x+28*scale,y+14*scale),(x+15*scale,y+7*scale)], fill=color)
    draw.ellipse((x-11*scale,y-7*scale,x+3*scale,y+7*scale), outline=color, width=2)


def cup_points():
    """An open cylindrical cup + a curved handle, each represented by 3-D samples."""
    rng = np.random.default_rng(20261009)
    points, colors = [], []
    for yy in np.linspace(-.85, .8, 25):
        for a in np.linspace(0, 2*math.pi, 50, endpoint=False):
            rr = .65 + .04 * (yy+.85)
            points.append([rr*math.cos(a), yy, rr*math.sin(a)])
            light = .73 + .25 * (math.cos(a+.9)+1)/2
            colors.append([138*light, 225*light, 180*light])
    for rr in np.linspace(.12, .67, 6):
        for a in np.linspace(0, 2*math.pi, 36, endpoint=False):
            points.append([rr*math.cos(a), -.85, rr*math.sin(a)])
            colors.append([75,143,121])
    for a in np.linspace(-math.pi/2, math.pi/2, 40):
        for b in np.linspace(0,2*math.pi,8,endpoint=False):
            points.append([.64+.58*math.cos(a)+.08*math.cos(b), .5*math.sin(a), .08*math.sin(b)])
            colors.append([183,229,194])
    return np.array(points), np.array(colors, dtype=np.uint8)


PTS, COLORS = cup_points()


def project(pts, angle, center=(480, 282), scale=128, tilt=.25):
    c, s = math.cos(angle), math.sin(angle)
    x = pts[:,0]*c + pts[:,2]*s
    z = -pts[:,0]*s + pts[:,2]*c
    y = pts[:,1]*math.cos(tilt)-z*math.sin(tilt)
    depth = pts[:,1]*math.sin(tilt)+z*math.cos(tilt)
    persp = 1/(1+depth*.08)
    return np.column_stack([center[0]+x*scale*persp, center[1]-y*scale*persp, depth])


def draw_cup(im, angle=0, center=(480,282), scale=128, style="splat", density=1, distortion=0, alpha=1):
    pts = PTS.copy()
    if distortion:
        pts[:,0] += distortion*np.sin(pts[:,1]*5 + pts[:,2]*3)
        pts[:,1] += distortion*.6*np.cos(pts[:,0]*7)
    xyz = project(pts,angle,center,scale)
    indices = np.arange(0,len(xyz),max(1,round(1/max(.04,density))))
    indices = indices[np.argsort(xyz[indices,2])[::-1]]
    # Nested translucent ellipses approximate each Gaussian's soft footprint.
    # They are illustrative and deliberately do not claim a training/render benchmark.
    layer = Image.new("RGBA",im.size)
    d = ImageDraw.Draw(layer,"RGBA")
    r = max(2, scale*.024)
    for i in indices:
        x,y,z = xyz[i]
        color = tuple(COLORS[i])
        if style == "points":
            d.ellipse((x-2,y-2,x+2,y+2),fill=(*color,int(240*alpha)))
        elif style == "ellipses":
            d.ellipse((x-r*2,y-r*.75,x+r*2,y+r*.75),outline=(*color,int(190*alpha)),width=1)
        else:
            for factor, opacity in [(2.0,24),(1.4,65),(.9,150),(.45,215)]:
                rr = r*factor
                d.ellipse((x-rr,y-rr*.85,x+rr,y+rr*.85),fill=(*color,int(opacity*alpha)))
    im.alpha_composite(layer)


def base(title, stage, progress):
    im = Image.new("RGBA",(W,H),BG)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((24,82,936,449),radius=24,fill=PANEL)
    text(d,(35,24),title,36)
    text(d,(917,35),f"0{stage+1} / 05",22,MUTED,"ra")
    for i in range(5):
        x=36+i*183
        d.rounded_rectangle((x,467,x+169,471),radius=2,fill="#304E5B")
        fill=1 if i<stage else progress if i==stage else 0
        if fill: d.rounded_rectangle((x,467,x+169*fill,471),radius=2,fill=GREEN)
    return im,d


TITLES = ["① 绕着拍，才有空间线索", "② 用许多软云团表示物体", "③ 把三维云团投到屏幕上", "④ 对照照片，一点点调准", "⑤ 换个角度，检查是否学会"]


def frame(t):
    starts, ends = [0, 12, 18, 24, 36], [12, 18, 24, 36, 48]
    stage = next((i for i, end in enumerate(ends) if t < end), 4)
    u = (t - starts[stage]) / (ends[stage] - starts[stage])
    im,d=base(TITLES[stage],stage,u)
    if stage==0:
        angle=u*2*math.pi
        d.ellipse((241,173,709,408),outline="#466573",width=2)
        for a in [0,2.09,4.19]:
            cx,cy=475+234*math.cos(a),291+117*math.sin(a)
            d.line((cx,cy,475,267),fill="#3D5D69",width=2)
            camera(d,(cx,cy),MUTED,.7)
        draw_cup(im,0,center=(480,273),scale=111)
        d=ImageDraw.Draw(im)
        cx,cy=475+234*math.cos(angle),291+117*math.sin(angle)
        d.line((cx,cy,475,267),fill=GOLD,width=3)
        camera(d,(cx,cy),GOLD,1.25)
        text(d,(57,109),"物体不动",28,GREEN)
        text(d,(705,109),"相机移动",28,GOLD)
        d.rounded_rectangle((728,260,905,411),radius=12,fill=BG,outline="#466573",width=2)
        draw_cup(im,angle,center=(815,337),scale=58)
    elif stage==1:
        style="points" if u<.3 else "ellipses" if u<.62 else "splat"
        density=.19 if u<.3 else .26 if u<.62 else 1
        draw_cup(im,.2+u*.55,center=(276,285),scale=137,style=style,density=density)
        d=ImageDraw.Draw(im)
        arrow(d,(432,262),(536,262),GOLD)
        for factor in np.linspace(1,.08,20):
            ratio=1-factor
            color=tuple(int(a+(b-a)*ratio) for a,b in zip((23,51,68),(138,225,180)))
            d.ellipse((699-113*factor,260-58*factor,699+113*factor,260+58*factor),fill=color)
        d.line((554,329,843,329),fill="#55747F",width=2)
        d.line((699,159,699,364),fill="#55747F",width=2)
        text(d,(558,115),"位置 · 形状 · 透明度",28,INK)
        text(d,(593,387),"中心浓，边缘淡",28,GREEN)
    elif stage==2:
        draw_cup(im,.7,center=(232,282),scale=107,style="ellipses",density=.3)
        d=ImageDraw.Draw(im)
        for yy in [193,264,338]: d.line((350,yy,564,yy+(-1 if yy<264 else 1)*27),fill="#4B7880",width=2)
        arrow(d,(373,264),(550,264),GOLD)
        d.rounded_rectangle((565,127,892,398),radius=12,fill=BG,outline=BLUE,width=3)
        d.line((635,418,822,418),fill=BLUE,width=4)
        density=.04+.96*ease(min(1,u*1.3))
        draw_cup(im,.7,center=(721,270),scale=124,style="splat",density=density)
        d=ImageDraw.Draw(im)
        text(d,(104,105),"三维高斯",28,GREEN)
        text(d,(636,90),"屏幕画面",28,BLUE)
    elif stage==3:
        d.rounded_rectangle((53,107,405,392),radius=18,fill=BG)
        d.rounded_rectangle((555,107,907,392),radius=18,fill=BG)
        err=.28*(1-ease(u))
        draw_cup(im,.45,center=(218,268),scale=125,distortion=err,density=.22+.78*ease(u))
        draw_cup(im,.45,center=(720,268),scale=125)
        d=ImageDraw.Draw(im)
        text(d,(132,112),"当前渲染",28,GREEN)
        text(d,(622,112),"目标图像",28,GOLD)
        arrow(d,(425,227),(535,227),BLUE)
        arrow(d,(535,286),(425,286),GREEN)
        text(d,(437,323),"调整",28,GREEN)
        text(d,(56,408),"误差",28,MUTED)
        d.rounded_rectangle((133,413,900,429),radius=8,fill="#304E5B")
        d.rounded_rectangle((133,413,133+735*(.07+.93*(1-ease(u))),429),radius=8,fill=GOLD)
    else:
        draw_cup(im,.1+u*2*math.pi,center=(392,282),scale=155)
        d=ImageDraw.Draw(im)
        d.arc((170,353,612,441),0,180,fill=GOLD,width=3)
        d.rounded_rectangle((652,139,899,364),radius=17,fill=BG)
        text(d,(680,174),"检查新视角",30,GREEN)
        text(d,(680,238),"有无缺口？",28,INK)
        text(d,(680,296),"边缘稳定？",28,INK)
    # Captions are delivered separately as VTT to keep the picture uncluttered.
    return im.convert("RGB")


def svg_shell(title,body):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540" viewBox="0 0 960 540" role="img" aria-label="{title}">
<defs><radialGradient id="cloud"><stop stop-color="#8AE1B4" stop-opacity=".95"/><stop offset="1" stop-color="#8AE1B4" stop-opacity="0"/></radialGradient><marker id="a" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0 0L6 3L0 6" fill="none" stroke="#E5BE84" stroke-width="1.5"/></marker></defs>
<rect width="960" height="540" rx="24" fill="#102332"/>
<g font-family="-apple-system,BlinkMacSystemFont,Helvetica,Arial,sans-serif" font-size="30" fill="#F3F3E9">{body}</g></svg>'''


def gaussian_diagram():
    body = '''<defs>
<radialGradient id="red"><stop stop-color="#F47C70" stop-opacity=".94"/><stop offset=".48" stop-color="#F47C70" stop-opacity=".72"/><stop offset="1" stop-color="#F47C70" stop-opacity="0"/></radialGradient>
<radialGradient id="blue"><stop stop-color="#77B9FC" stop-opacity=".94"/><stop offset=".48" stop-color="#77B9FC" stop-opacity=".72"/><stop offset="1" stop-color="#77B9FC" stop-opacity="0"/></radialGradient>
</defs>
<text x="45" y="57">三维高斯 → 屏幕上的软边椭圆</text>
<rect x="35" y="83" width="890" height="211" rx="20" fill="#173344"/>
<path d="M68 235H322 M174 264V110 M79 266L286 106" stroke="#416571" stroke-width="2"/>
<ellipse cx="185" cy="187" rx="116" ry="58" transform="rotate(-24 185 187)" fill="url(#cloud)"/>
<g transform="rotate(-24 185 187)" fill="none" stroke="#8AE1B4" stroke-width="2">
<ellipse cx="185" cy="187" rx="93" ry="44"/><ellipse cx="185" cy="187" rx="93" ry="17"/><ellipse cx="185" cy="187" rx="30" ry="44"/></g>
<path d="M321 187H377 M469 187H541" stroke="#E5BE84" stroke-width="3" marker-end="url(#a)"/>
<rect x="390" y="161" width="53" height="52" rx="9" fill="#102332" stroke="#E5BE84" stroke-width="3"/>
<circle cx="416" cy="187" r="14" fill="none" stroke="#E5BE84" stroke-width="3"/>
<path d="M443 174l22-10v46l-22-10z" fill="#E5BE84"/>
<rect x="571" y="104" width="306" height="162" rx="10" fill="#102332" stroke="#8FC8ED" stroke-width="3"/>
<ellipse cx="724" cy="185" rx="103" ry="49" fill="url(#cloud)"/>
<path d="M724 267v14 M684 281h80" stroke="#8FC8ED" stroke-width="3"/>
<rect x="35" y="312" width="434" height="205" rx="20" fill="#173344"/>
<rect x="491" y="312" width="434" height="205" rx="20" fill="#173344"/>
<text x="252" y="351" text-anchor="middle" fill="#F5C2B8">红在前</text>
<text x="708" y="351" text-anchor="middle" fill="#B8DAFF">蓝在前</text>
<!-- Same colors, centers and opacity in both panels. Only draw order changes. -->
<ellipse cx="279" cy="427" rx="82" ry="67" fill="url(#blue)"/>
<ellipse cx="225" cy="427" rx="82" ry="67" fill="url(#red)"/>
<ellipse cx="681" cy="427" rx="82" ry="67" fill="url(#red)"/>
<ellipse cx="735" cy="427" rx="82" ry="67" fill="url(#blue)"/>
<path d="M442 427H518" stroke="#E5BE84" stroke-width="3" marker-end="url(#a)"/>
'''
    (OUT/'gaussian.svg').write_text(svg_shell('三维高斯投影成软边椭圆；红蓝高斯交换前后顺序后重叠区域颜色改变',body))


def diagrams():
    cup='''<path d="M388 210 L403 371 Q478 402 553 371 L568 210" fill="#234D4B" stroke="#8AE1B4" stroke-width="5"/><ellipse cx="478" cy="210" rx="90" ry="26" fill="#142F3B" stroke="#8AE1B4" stroke-width="5"/><path d="M566 237 Q653 228 629 299 Q612 334 558 327" fill="none" stroke="#8AE1B4" stroke-width="17"/>'''
    body='<text x="48" y="62">多视角覆盖，提供空间线索</text><ellipse cx="480" cy="300" rx="336" ry="162" fill="none" stroke="#416571" stroke-width="3" stroke-dasharray="10 9"/>'+cup
    for x,y in [(180,251),(728,383),(578,122)]:
        body+=f'<path d="M{x} {y} L478 275" stroke="#73938E" stroke-width="2" stroke-dasharray="5 6"/><rect x="{x-31}" y="{y-21}" width="52" height="42" rx="8" fill="#173344" stroke="#E5BE84" stroke-width="4"/><path d="M{x+21} {y-10}l23 -10v40l-23 -10z" fill="#E5BE84"/>'
    body+='<text x="75" y="489" fill="#E5BE84">相机换位置</text><text x="661" y="489" fill="#8AE1B4">物体保持不动</text>'
    (OUT/'capture.svg').write_text(svg_shell('不同位置拍同一个静止物体',body))
    gaussian_diagram()
    body='''<text x="48" y="62">渲染 → 比较 → 调整，再来一次</text><rect x="74" y="131" width="300" height="239" rx="18" fill="#173344"/><rect x="585" y="131" width="300" height="239" rx="18" fill="#173344"/>'''
    for x,shift in [(110,13),(620,0)]:
        body+=f'<g transform="translate({x} 103) scale(.43)"><path d="M148 197L{160+shift} 464Q335 526 510 464L{525+shift} 197Z" fill="#547D67" stroke="#8AE1B4" stroke-width="8"/><ellipse cx="336" cy="197" rx="188" ry="57" fill="#173344" stroke="#8AE1B4" stroke-width="8"/><path d="M526 247Q680 227 654 380Q614 449 511 432" fill="none" stroke="#8AE1B4" stroke-width="27"/></g>'
    body+='''<path d="M400 231H554" stroke="#E5BE84" stroke-width="4" marker-end="url(#a)"/><path d="M733 428V458H223V428" fill="none" stroke="#E5BE84" stroke-width="4" marker-end="url(#a)"/><text x="127" y="409" fill="#8AE1B4">当前渲染</text><text x="634" y="409" fill="#E5BE84">目标照片</text>'''
    (OUT/'training.svg').write_text(svg_shell('比较渲染与照片调整高斯参数',body))
    body='''<text x="48" y="62">看起来逼真，还不等于可打印</text><rect x="60" y="109" width="391" height="325" rx="19" fill="#173344"/><rect x="509" y="109" width="391" height="325" rx="19" fill="#173344"/>'''
    for ix in range(9):
        for iy in range(7):
            xx,yy=151+ix*25+9*math.sin(iy),182+iy*23
            body+=f'<ellipse cx="{xx:.1f}" cy="{yy}" rx="25" ry="19" fill="url(#cloud)"/>'
    for iy in range(6):
        for ix in range(6):
            x,y=595+ix*34,172+iy*28
            body+=f'<path d="M{x} {y}h34v28h-34z m0 0l34 28" fill="none" stroke="#8FC8ED" stroke-width="1.5"/>'
    body+='''<text x="128" y="393" fill="#8AE1B4">高斯：视觉展示</text><text x="577" y="393" fill="#8FC8ED">网格：明确表面</text>'''
    (OUT/'applications.svg').write_text(svg_shell('高斯视觉表示与网格表面区别',body))


CAPTIONS = [
    (0,6,"手机绕物体移动，从不同位置拍摄，才能获得视差。"),
    (6,12,"先用照片共同特征，估计每张照片的相机位置。"),
    (12,15,"场景由很多三维高斯组成，可以想成软边的椭球云团。"),
    (15,18,"每个云团都有位置、形状、透明度和颜色。"),
    (18,21,"渲染时，把三维高斯投影成屏幕上的软边椭圆。"),
    (21,24,"考虑深度和透明度叠加，就得到当前视角的画面。"),
    (24,30,"用相机原来的位置渲染，再与对应照片计算差异。"),
    (30,36,"根据误差调整参数；训练还可增加、拆分或清理高斯。"),
    (36,42,"多个视角反复约束，才能从新的角度观看场景。"),
    (42,48,"检查没参与训练的视角；逼真外观并不保证可打印。"),
]

SWIFT = r'''
import Foundation
import AVFoundation
import CoreGraphics
import ImageIO
import CoreVideo

let args = CommandLine.arguments
let dir = args[1], output = URL(fileURLWithPath: args[2])
let count = Int(args[3])!, fps = Int32(args[4])!
let w = 960, h = 540
let writer = try AVAssetWriter(outputURL: output, fileType: .mp4)
writer.shouldOptimizeForNetworkUse = true
let settings: [String: Any] = [AVVideoCodecKey: AVVideoCodecType.h264,
    AVVideoWidthKey: w, AVVideoHeightKey: h,
    AVVideoCompressionPropertiesKey: [AVVideoAverageBitRateKey: 1800000,
        AVVideoProfileLevelKey: AVVideoProfileLevelH264MainAutoLevel,
        AVVideoMaxKeyFrameIntervalKey: Int(fps)*2]]
let input = AVAssetWriterInput(mediaType: .video, outputSettings: settings)
let adaptor = AVAssetWriterInputPixelBufferAdaptor(assetWriterInput: input,
    sourcePixelBufferAttributes: [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32ARGB,
        kCVPixelBufferWidthKey as String: w, kCVPixelBufferHeightKey as String: h,
        kCVPixelBufferCGImageCompatibilityKey as String: true,
        kCVPixelBufferCGBitmapContextCompatibilityKey as String: true])
writer.add(input)
guard writer.startWriting() else { fatalError("start: \(String(describing: writer.error))") }
writer.startSession(atSourceTime: .zero)
for i in 0..<count {
    while !input.isReadyForMoreMediaData {
        if writer.status == .failed { fatalError("encode: \(String(describing: writer.error))") }
        usleep(2000)
    }
    autoreleasepool {
        let url = URL(fileURLWithPath: dir).appendingPathComponent(String(format: "%04d.png",i))
        guard let src = CGImageSourceCreateWithURL(url as CFURL, nil),
            let image = CGImageSourceCreateImageAtIndex(src, 0, nil) else { fatalError("bad image") }
        var buffer: CVPixelBuffer?
        guard CVPixelBufferPoolCreatePixelBuffer(nil, adaptor.pixelBufferPool!, &buffer) == kCVReturnSuccess else { fatalError("buffer") }
        let b = buffer!
        CVPixelBufferLockBaseAddress(b, [])
        let ctx = CGContext(data: CVPixelBufferGetBaseAddress(b), width: w, height: h,
            bitsPerComponent: 8, bytesPerRow: CVPixelBufferGetBytesPerRow(b),
            space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.noneSkipFirst.rawValue)!
        ctx.draw(image, in: CGRect(x: 0, y: 0, width: w, height: h))
        CVPixelBufferUnlockBaseAddress(b, [])
        guard adaptor.append(b, withPresentationTime: CMTime(value: Int64(i), timescale: fps)) else { fatalError("append: \(String(describing: writer.error))") }
    }
}
input.markAsFinished()
await writer.finishWriting()
guard writer.status == .completed else { fatalError("finish: \(String(describing: writer.error))") }
let asset = AVURLAsset(url: output)
let duration = try await asset.load(.duration)
let track = try await asset.loadTracks(withMediaType: .video).first!
let size = try await track.load(.naturalSize)
let format = try await track.load(.formatDescriptions).first!
let codec = CMFormatDescriptionGetMediaSubType(format)
let chars: [UInt8] = [UInt8((codec>>24)&255),UInt8((codec>>16)&255),UInt8((codec>>8)&255),UInt8(codec&255)]
print("verified seconds=\(duration.seconds), size=\(size), codec=\(String(bytes: chars, encoding: .ascii)!)")
'''


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--diagrams-only',action='store_true')
    args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    diagrams()
    frame(22).save(OUT/'poster.jpg',quality=95)
    storyboard=Image.new('RGB',(960,360),BG)
    for index,t in enumerate([3,14,21,28,39,47]):
        storyboard.paste(frame(t).resize((320,180)),((index%3)*320,(index//3)*180))
    storyboard.save(OUT/'storyboard.jpg',quality=95)
    def tc(s): return f"00:00:{s:02d}.000"
    (OUT/'zh.vtt').write_text('WEBVTT\n\n'+'\n\n'.join(f'{i+1}\n{tc(a)} --> {tc(b)}\n{caption}' for i,(a,b,caption) in enumerate(CAPTIONS))+'\n')
    metadata={"title":"48 秒看懂高斯溅射","duration_seconds":DURATION,"fps":FPS,"width":W,"height":H,"has_audio":False,"type":"original_schematic_animation","not_real_reconstruction":True,"chapters":[{"start":0,"end":12,"title":"移动相机，估计视角"},{"start":12,"end":24,"title":"高斯表示与投影叠加"},{"start":24,"end":36,"title":"对照照片，按误差调整"},{"start":36,"end":48,"title":"新视角检验与使用边界"}],"captions":[{"start":a,"end":b,"text":c} for a,b,c in CAPTIONS]}
    (OUT/'metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n')
    if args.diagrams_only: return
    video=OUT/'intro.mp4'
    with tempfile.TemporaryDirectory(prefix='brush-media-') as directory:
        temp=Path(directory)
        start=time.monotonic()
        for i in range(FPS*DURATION):
            frame(i/FPS).save(temp/f'{i:04d}.png',compress_level=1)
            if i%150==0: print(f'frame {i}/{FPS*DURATION}: {time.monotonic()-start:.1f}s',flush=True)
        swift=temp/'encode.swift'; swift.write_text(SWIFT)
        encoded = temp/'encoded.mp4'
        subprocess.run(['swift','-module-cache-path',str(temp/'module-cache'),str(swift),str(temp),str(encoded),str(FPS*DURATION),str(FPS)],check=True)
        encoded.replace(video)
    print(f'Created {video} ({video.stat().st_size:,} bytes)')


if __name__=='__main__': main()
