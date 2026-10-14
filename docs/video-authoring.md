# 原理动画维护

Bayes、VoiceStudio、电容与去耦、MOS 管开关的视频由本项目原创图形逐帧生成，再合入晓晓中文女声。它们解释课程中的机制，不是实际检测数据、模型运行录像、开发板实测波形或学习成绩。贝叶斯动画先用 100 个等权点表示 10,000 件产品（每点 100 件），汇入报警池时明确改成每点 1 件，完整绘制 90 个坏件和 495 个正常件。

旁白在 `content/<课程>-video-narration.json`，课程标识为 `bayes`、`voicestudio`、`capacitor`、`mosfet`。渲染入口在 `scripts/generate_course_videos.py`；嵌入式两课的分镜绘图在 `scripts/embedded_video_scenes.py`。只修改旁白或绘图，不更改课程、问题或源码摘录的稳定 ID。

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

只重建修改过的课程；`--course all` 会重建上述四门课，需要它们各自完整的分段音频。渲染器不访问网络。它完整解码每段 MP3，使用实测语音长度安排镜头并追加一秒观察空隙，输出 960×540、15 fps、H.264/yuv420p + AAC 视频、JPEG 封面、VTT 字幕以及课程的 `visual_lesson.video`。字幕按短句及实测段落时长分配窗口，每行最多 23 字、最多两行，过长句子须先改写；不宣称词级对齐。完整旁白保留为分镜文字稿。每次写入课程前重新读取 JSON，只替换视频字段。当前输出时长是 Bayes 73.0 秒、VoiceStudio 91.2 秒、电容 88.9 秒、MOS 管 87.3 秒；编辑旁白后会重新计算。

电容动画用紫色电容符号、绿色电流标记和完整回流路径说明局部补给；电压下滑公式只计算理想容量项，不包含 ESR、ESL 和电源补给。MOS 动画用紫色信号与蓝色负载电流区分两条路径，关断后的珊瑚红续流从负载下端经二极管返回上端。二极管 K 接电源正端、A 接漏极；低端 N 沟道 MOS 管的体二极管不能替代这条回路。方框表示简化器件，移动标记表示传统电流方向，不代表电子运动速度。迁移题结果只放在反馈或折叠答案中，不提前写进图、字幕或旁白。

## 嵌入式两课的原创视觉主题

电容与 MOS 管采用「星灯工坊」主题：深靛蓝星空、黄铜细框和圆拱书架围绕暖羊皮纸画布，薄荷色棱晶灯灵配悬浮铜环作为原创向导。图解与视频共享这些元素。夜色用于外围和字幕区，核心电路保持浅底深字；浮光只作外围装饰，不混入电流箭头、计数单位或波形。

基础颜色为星空 `#17233F`、羊皮纸 `#FFF4DB`、黄铜 `#C5A367`、正文 `#24324C`；机制颜色为紫 `#7352A0`、蓝 `#2775A6`、绿 `#287858`、珊瑚红 `#BF514A`，仍以文字、端点和箭头辅助区分。晶体灯灵只是课堂向导，不能用魔法来替代电场储能、栅极控制或续流的物理解释。

这是独立设计的奇幻研习室，不直接使用影视作品的角色、学校名称、徽章、独有造型、专有字体、配乐或台词，也不把商业作品名称用于课程宣传。图形由本项目绘图脚本和静态 SVG 制作，继续使用既有晓晓语音；没有加入第三方影视素材。原创设计说明记录制作边界，不代表法律风险为零或完成商标检索。

调整画风只更新 SVG、视频、封面与对应替代文字。科学内容、公式、来源、问题 ID 和音频文字稿保持一致；仍要检查 298px 图宽下的标签、箭头和字幕。深色画框不改变 App 主界面的配色。

检查 QA 输出中的分镜图、18 秒音色试听和验证报告，再实际打开视频检查播放、暂停、拖动、字幕以及音画含义。特别核对计数单位、分支、遗漏后局部修复的人工职责和交叉淡化边界。内容构建只携带课程引用的视频、封面与字幕；原始分段音频用于作者重建。`generation-record.json` 是本地缓存记录，不提交、不进课程包。更换手机前仍需在目标设备上实际播放验证，解码成功不能代替设备测试。
