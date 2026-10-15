# 原理动画维护

Bayes、VoiceStudio、电容与去耦、MOS 管开关的视频由本项目原创图形逐帧生成，再合入晓晓中文女声。它们解释课程中的机制，不是实际检测数据、模型运行录像、开发板实测波形或学习成绩。贝叶斯动画先用 100 个等权点表示 10,000 件产品（每点 100 件），汇入报警池时明确改成每点 1 件，完整绘制 90 个坏件和 495 个正常件。

旁白在 `content/<课程>-video-narration.json`，课程标识为 `bayes`、`voicestudio`、`capacitor`、`mosfet`。渲染入口在 `scripts/generate_course_videos.py`；嵌入式两课的分镜绘图在 `scripts/embedded_video_scenes.py`。只修改旁白或绘图，不更改课程、问题或源码摘录的稳定 ID。

## 初学者先看什么

先让学习者认清对象和端点，再追踪一条因果，最后引入术语或公式。例如先看电容的两块极板与中间介质，再看接上电源发生什么；先找 MOS 的 G 控制入口和 D/S 负载通路，再解释栅极充放电。主旁白用短句串起这些变化，参数表、损耗计算和选型条件留在后面的独立案例。

当前嵌入式课程按以下机制分镜。场数服务于解释，不是所有课程都要遵守的模板：

| 课程 | 分镜顺序 | 每镜的任务 |
| --- | --- | --- |
| 电容与去耦 | 结构 → 充电 → 稳态 → 外路放电 → 去耦 | 先认极板和介质；再看外部导线使极板电荷分离；到达稳态时停止净充电；接外部负载后经外路释放能量；最后迁移到芯片瞬时用电。 |
| MOS 管开关 | 控制与供电 → 栅极充放电 → PWM 时间 → 关断续流 | 分清谁发令、谁出力；说明栅源电压是两端差；只讲一周期内开多久；最后沿外部二极管追踪不穿 MOS 断口的闭环。 |

MOS 的 PWM 镜头不同时显示发热公式；I²R 放在独立进阶例子。电容的 ΔV≈IΔt/C 同样先说明“短时间多要电，电压会变化”，再在后置例子列出恒流与理想容量项的假设。新迁移题的结果只放在作答反馈或折叠答案中，不提前写进图、字幕、替代文字或旁白。

## 电路里的运动符号

| 符号 | 表示什么 | 画面边界 |
| --- | --- | --- |
| 带负号的电子标记 | 明确范围内的电子净迁移或电荷分离示意 | 不表示实测粒子数或速度；不穿过理想电容介质或 MOS 栅极绝缘层。 |
| 约定电流箭头 | 电流采用的方向约定 | 标清“约定电流”；不要把箭头或沿路径移动的图标称为电子。 |
| 电场符号 | 电场方向或作用区域 | 与电子标记外形不同；跨介质的电场作用不等于电子跨介质运输。 |

有起点、终点的电子路径使用有限单程，抵达端点后停止或结束。禁止对这类路径直接取模循环，造成电子突然回绕、穿过器件或凭空出现在起点。闭合回路可以按讲解目的使用流向标记，但仍要区分充电瞬态、稳态和放电阶段；稳态不能继续暗示电容一直被净充电。

检查路径时把标记半径、描边和尾迹一并纳入边界，整颗符号都不得触碰或进入不应经过的介质区域。栅极处的控制作用通过电场解释，不画成电荷横穿绝缘层进入负载通路。电容放电只经已画明的外部导线和负载，电流标记不能穿过电容介质闭环。

MOS 动画用紫色控制与蓝色负载电流区分两条路径；珊瑚红续流从线圈下端经外部二极管回上端，再沿原方向穿过线圈。二极管 K 接电源正端、A 接漏极；普通低端 N 沟道 MOS 管的体二极管不能替代这条回路。关断画面须有清楚断口，续流箭头不能经过该断口。方框只是简化器件，不是内部结构图。

## 生成与时长

制作环境需自行准备 Pillow、edge-tts、FFmpeg 和可显示中文的字体。它们是可选作者工具，手机和静态站点不安装这些依赖。先明确检查本次旁白适合公开，再显式生成音频；该步骤会把旁白发送给在线语音服务：

```sh
python3 scripts/generate_neural_audio.py --input content/bayes-video-narration.json --output-dir web/media/bayes/video-audio --ffmpeg ffmpeg
python3 scripts/generate_neural_audio.py --input content/voicestudio-video-narration.json --output-dir web/media/voicestudio/video-audio --ffmpeg ffmpeg
python3 scripts/generate_neural_audio.py --input content/capacitor-video-narration.json --output-dir web/media/capacitor/video-audio --ffmpeg ffmpeg
python3 scripts/generate_neural_audio.py --input content/mosfet-video-narration.json --output-dir web/media/mosfet/video-audio --ffmpeg ffmpeg
```

然后提供实际字体文件路径。下面 `path/to/chinese-font.ttf` 必须替换为当前环境已有字体；QA 输出应放在不提交的本地目录：

```sh
python3 scripts/generate_course_videos.py --course capacitor --font path/to/chinese-font.ttf --ffmpeg ffmpeg --review-output dist/video-review
python3 scripts/generate_course_videos.py --course mosfet --font path/to/chinese-font.ttf --ffmpeg ffmpeg --review-output dist/video-review
python3 learning_loop.py validate-lesson --file content/capacitor.json
python3 learning_loop.py validate-lesson --file content/mosfet.json
```

只重建修改过的课程；`--course all` 会重建上述四门课，需要它们各自完整的分段音频。渲染器不访问网络。它完整解码每段 MP3，使用实测语音长度安排镜头并追加一秒观察空隙，输出 960×540、15 fps、H.264/yuv420p + AAC 视频、JPEG 封面、VTT 字幕以及课程的 `visual_lesson.video`。字幕按短句及实测段落时长分配窗口，每行最多 23 字、最多两行，过长句子须先改写；不宣称词级对齐。完整旁白保留为分镜文字稿。每次写入课程前重新读取 JSON，只替换视频字段。

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
