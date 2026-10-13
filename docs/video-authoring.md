# 原理动画维护

Bayes 和 VoiceStudio 的视频由本项目原创图形逐帧生成，再合入晓晓中文女声。它们解释课程中的机制，不是实际检测数据、VoiceStudio 模型运行录像或学习成绩。贝叶斯动画先用 100 个等权点表示 10,000 件产品（每点 100 件），汇入报警池时明确改成每点 1 件，完整绘制 90 个坏件和 495 个正常件。

旁白在 `content/bayes-video-narration.json` 和 `content/voicestudio-video-narration.json`。渲染器在 `scripts/generate_course_videos.py`。只修改旁白或绘图，不更改课程、问题或源码摘录的稳定 ID。

制作环境需自行准备 Pillow、edge-tts、FFmpeg 和可显示中文的字体。它们是可选作者工具，手机和静态站点不安装这些依赖。先明确检查本次旁白适合公开，再显式生成音频；该步骤会把旁白发送给在线语音服务：

```sh
python3 scripts/generate_neural_audio.py --input content/bayes-video-narration.json --output-dir web/media/bayes/video-audio --ffmpeg ffmpeg
python3 scripts/generate_neural_audio.py --input content/voicestudio-video-narration.json --output-dir web/media/voicestudio/video-audio --ffmpeg ffmpeg
```

然后提供实际字体文件路径。下面 `path/to/chinese-font.ttf` 必须替换为当前环境已有字体；QA 输出应放在不提交的本地目录：

```sh
python3 scripts/generate_course_videos.py --course all --font path/to/chinese-font.ttf --ffmpeg ffmpeg --review-output dist/video-review
python3 learning_loop.py validate-lesson --file content/bayes.json
python3 learning_loop.py validate-lesson --file content/voicestudio.json
```

渲染器不访问网络。它完整解码每段 MP3，使用实测语音长度安排镜头并追加一秒观察空隙，输出 960×540、15 fps、H.264/yuv420p + AAC 视频、JPEG 封面、VTT 字幕以及课程的 `visual_lesson.video`。字幕按短句及实测段落时长分配窗口，不宣称词级对齐；完整旁白保留为分镜文字稿。每次写入课程前重新读取 JSON，只替换视频字段。当前渲染输出的时长是 Bayes 73.0 秒、VoiceStudio 91.2 秒；编辑旁白后会重新计算。

检查 QA 输出中的分镜图、18 秒音色试听和验证报告，再实际打开视频检查播放、暂停、拖动、字幕以及音画含义。特别核对计数单位、分支、遗漏后局部修复的人工职责和交叉淡化边界。内容构建只携带课程引用的视频、封面与字幕；原始分段音频用于作者重建。`generation-record.json` 是本地缓存记录，不提交、不进课程包。更换手机前仍需在目标设备上实际播放验证，解码成功不能代替设备测试。
