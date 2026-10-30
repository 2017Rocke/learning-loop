# 原理动画维护

五门课的当前入门动画由本项目原创图形逐帧生成，再合入晓晓中文女声。它们解释机制，不是实际重建结果、模型运行录像、开发板测量或学习成绩。图解、正文、主章听讲和动画须沿同一个例子；完整教学方法见 [先懂再深入](../skill/learning-loop/references/beginner-first.md)。

## 当前入口与历史素材

| 课程 | 贯穿例子 | 当前渲染脚本 | 视频分段语音目录 |
| --- | --- | --- | --- |
| Brush | 同一个静止杯子：拍摄、软色斑、投影、比对调整、新视角 | `scripts/generate_brush_beginner_media.py` | `web/media/brush-beginner/video/audio/` |
| 贝叶斯 | 同一批100盏灯：10故障、90正常 → 8真报警、9误报 → 在17盏里数 | `scripts/generate_bayes_beginner_media.py` | `web/media/bayes-beginner/video/audio/` |
| VoiceStudio | 同一段三句中文：分段、配对、按序拼接、试听 | `scripts/generate_voicestudio_beginner_media.py` | `web/media/voicestudio-beginner/video-audio/` |
| 电容 | 同一芯片：稳定、突然多用电、电源接力、负载回落、回充 | `scripts/generate_capacitor_beginner_media.py` | `web/media/capacitor-beginner/video/audio/` |
| MOS 管 | 同一盏小灯：控制与供能分开，导通、主动拉低关断 | `scripts/generate_mosfet_beginner_video.py` | `web/media/mosfet-beginner/video/audio/` |

旁白源均为 `content/<课程>-beginner-video-narration.json`；主章听讲使用 `content/<课程>-beginner-narration.json`，输出至 `web/media/<课程>-beginner/audio/`。每个新视频在相应媒体目录的 `video/` 下。旧 `generate_course_videos.py`、旧旁白与旧素材保留作历史参考；不要用它们或其 `--course all` 结果覆盖当前入门课。课程和回忆题继续使用原稳定 ID。

贝叶斯每个计数点始终表示一盏灯，不再切换单位。末幕只把误报9改为3，先让学习者预测，答案在作答反馈。原10,000件产品组件仍在课程中明确标为进阶选学，不能与基础例子的数字混用。Brush 的杯把调整是单参数教学演示，不冒充 Brush 的完整优化器。VoiceStudio 的卡片与波形是示意，真实分块不保证一块一句。

## 初学者先看什么

先让学习者认清对象和端点，再追踪一条因果，最后引入术语或公式。例如先看电容的两块极板与中间介质，再看接上电源发生什么；先找 MOS 的 G 控制入口和 D/S 负载通路，再解释栅极充放电。主旁白用短句串起这些变化，参数表、损耗计算和选型条件留在后面的独立案例。

当前嵌入式课程按以下机制分镜。场数服务于解释，不是所有课程都要遵守的模板：

| 课程 | 分镜顺序 | 每镜的任务 |
| --- | --- | --- |
| 电容与去耦 | 认元件 → 临时水杯类比 → 芯片突忙 → 电源接力 → 恢复回充 | 电容并在供电两端，提供短时差额；电源持续供能，需求降低后经外部回路补回电荷，稳定后不再净充电。 |
| MOS 管入门 | 电子开关用途 → 水龙头类比 → 合适栅源电压 → 小灯回路 → 主动拉低关断 | 同一盏小灯贯穿；先分清控制与供能，再看电压怎样改变导通状态。悬空不保证关闭；PWM、续流与发热留到选学。 |

MOS 的 PWM 镜头不同时显示发热公式；I²R 放在独立进阶例子。电容的 ΔV≈IΔt/C 同样先说明“短时间多要电，电压会变化”，再在后置例子列出恒流与理想容量项的假设。新迁移题的结果只放在作答反馈或折叠答案中，不提前写进图、字幕、替代文字或旁白。

## 电路里的运动符号

| 符号 | 表示什么 | 画面边界 |
| --- | --- | --- |
| 带负号的电子标记 | 明确范围内的电子净迁移或电荷分离示意 | 不表示实测粒子数或速度；不穿过理想电容介质或 MOS 栅极绝缘层。 |
| 约定电流箭头 | 电流采用的方向约定 | 标清“约定电流”；不要把箭头或沿路径移动的图标称为电子。 |
| 电场符号 | 电场方向或作用区域 | 与电子标记外形不同；跨介质的电场作用不等于电子跨介质运输。 |

有起点、终点的电子路径使用有限单程，抵达端点后停止或结束。禁止对这类路径直接取模循环，造成电子突然回绕、穿过器件或凭空出现在起点。闭合回路可以按讲解目的使用流向标记，但仍要区分充电瞬态、稳态和放电阶段；稳态不能继续暗示电容一直被净充电。

检查路径时把标记半径、描边和尾迹一并纳入边界，整颗符号都不得触碰或进入不应经过的介质区域。栅极处的控制作用通过电场解释，不画成电荷横穿绝缘层进入负载通路。电容放电只经已画明的外部导线和负载，电流标记不能穿过电容介质闭环。

当前 MOS 入门动画用紫色表示控制、绿色箭头表示约定负载电流。小灯按无电感的电阻负载理解；关断时停止负载电流，保留清楚断口。方框只是功能示意，不是器件内部剖面。旧进阶动画中的珊瑚红续流只适用于其线圈场景：二极管 K 接电源正端、A 接漏极，普通低端 N 沟道 MOS 管的体二极管不能替代这条回路；不要把线圈续流套到入门小灯示意中。

## 生成与时长

制作环境需自行准备 Pillow、edge-tts、FFmpeg 和可显示中文的字体。它们是可选作者工具，手机和静态站点不安装这些依赖。先明确检查本次旁白适合公开，再显式生成音频；该步骤会把旁白发送给在线语音服务：

```sh
python3 scripts/generate_neural_audio.py --input content/bayes-beginner-video-narration.json --output-dir web/media/bayes-beginner/video/audio --ffmpeg ffmpeg
python3 scripts/generate_neural_audio.py --input content/bayes-beginner-narration.json --output-dir web/media/bayes-beginner/audio --ffmpeg ffmpeg
```

其他课程按上表选择对应输入和输出，VoiceStudio 视频分段语音的目录名是 `video-audio`。然后提供当前环境已有的中文字体；`path/to/chinese-font.ttf` 是需替换的占位路径。只重建本次改动的课程，QA 放在不提交的本地目录：

```sh
python3 scripts/generate_bayes_beginner_media.py --input content/bayes-beginner-video-narration.json --audio-dir web/media/bayes-beginner/video/audio --font path/to/chinese-font.ttf --ffmpeg ffmpeg --review-output dist/bayes-beginner-review
python3 scripts/generate_voicestudio_beginner_media.py --input content/voicestudio-beginner-video-narration.json --audio-dir web/media/voicestudio-beginner/video-audio --font path/to/chinese-font.ttf --ffmpeg ffmpeg --review-output dist/voicestudio-beginner-review
python3 scripts/generate_brush_beginner_media.py --video --font path/to/chinese-font.ttf --ffmpeg ffmpeg --review-output dist/brush-beginner-review
python3 scripts/generate_capacitor_beginner_media.py --font path/to/chinese-font.ttf --ffmpeg ffmpeg --review-output dist/capacitor-beginner-review
python3 scripts/generate_mosfet_beginner_video.py --input content/mosfet-beginner-video-narration.json --audio-dir web/media/mosfet-beginner/video/audio --font path/to/chinese-font.ttf --ffmpeg ffmpeg --review-output dist/mos-beginner-video-review
```

渲染器不访问网络；使用实测语音长度安排镜头并留观察空隙，输出960×540、15fps、H.264/yuv420p + AAC视频、JPEG封面和VTT字幕。字幕窗口按短句长度分配，不宣称词级对齐。完整旁白保留为分镜文字稿。

先检查 QA 目录中的 `video-metadata.json`，再合入课程的 `visual_lesson.video`；主章音频对应媒体目录 `audio/metadata.json`，合入 `audio_lesson`。电容脚本目前会在本地校验完成后直接合并这两个字段，务必检查其 diff；其余脚本只输出素材和元数据。VoiceStudio 保留准确的旧源码精讲时，仅替换五个主章节，不丢弃 `code` 和逐行深讲条目。每次写入前重读课程 JSON，避免覆盖同时完成的正文修改。

```sh
python3 learning_loop.py validate-lesson --file content/bayes.json
```

时长以本次生成后的媒体测量为准，再写入 `duration_seconds` 和分镜 `transcript[].time`，不沿用旧版本时长或用字数估计冒充实测。增加或删减分镜后，逐项对齐旁白源、分段音频元数据、镜头数量、字幕窗口与课程文字稿。

## 嵌入式两课的原创视觉主题

电容与 MOS 管采用「星灯工坊」主题：深靛蓝星空、黄铜细框和圆拱书架围绕暖羊皮纸画布，薄荷色棱晶灯灵配悬浮铜环作为原创向导。图解与视频共享这些元素。夜色用于外围和字幕区，核心电路保持浅底深字；浮光只作外围装饰，不混入电流箭头、计数单位或波形。

基础颜色为星空 `#17233F`、羊皮纸 `#FFF4DB`、黄铜 `#C5A367`、正文 `#24324C`；机制颜色为紫 `#7352A0`、蓝 `#2775A6`、绿 `#287858`、珊瑚红 `#BF514A`，仍以文字、端点和箭头辅助区分。晶体灯灵只是课堂向导，不能用魔法来替代电场储能、栅极控制或续流的物理解释。

这是独立设计的奇幻研习室，不直接使用影视作品的角色、学校名称、徽章、独有造型、专有字体、配乐或台词，也不把商业作品名称用于课程宣传。图形由本项目绘图脚本和静态 SVG 制作，继续使用既有晓晓语音；没有加入第三方影视素材。原创设计说明记录制作边界，不代表法律风险为零或完成商标检索。

调整画风只更新 SVG、视频、封面与对应替代文字。科学内容、公式、来源、问题 ID 和音频文字稿保持一致；仍要检查 298px 图宽下的标签、箭头和字幕。深色画框不改变 App 主界面的配色。

## 检查画面与播放

先查 QA 输出中的分镜图、音色试听和验证报告，再实际打开视频检查播放、暂停、拖动、字幕以及音画含义。手机画面以约 298px 图宽审查，覆盖整个过程和镜头切换。逐帧重点检查粒子起止与停止、绝缘间隙两侧、路径回绕、开关断口、前后两幕的导通状态；不能只凭每幕首、中、尾的三张图判定运动正确。几何边界检查要包含整个符号半径，报告通过的帧数和场景范围。

同时核对计数单位、因果分支、需要人工定位的操作及交叉淡化边界。完整解码、坐标检查、窄屏画面检查和真实播放分别记录；某项未执行，就不能用其他项代替它。目标 Android 设备的播放仍需单独验证，桌面浏览器通过不等于真机通过。

内容构建只携带课程引用的视频、封面与字幕；原始分段音频用于作者重建。`generation-record.json` 是本地缓存记录，不提交、不进课程包。
