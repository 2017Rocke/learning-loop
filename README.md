# Learning Loop · 知行学习循环

把新知识变成能解释、能操作、能迁移、能回忆的能力。先看图和听讲，再做小实验，最后用自己的回答检验记忆。项目课与学科课共用这个流程，不只适用于编程。

项目包含安卓 APK、电脑端本地 App、可部署的手机网页，以及给学习助手使用的备课 skill。运行和学习不需要模型 API key；新课可由人工或学习助手核实资料后加入。

## 安卓优先体验

安卓版内置教学界面和初始课程，安装 APK 后可离线学习。在 App 填写自己的公开 GitHub `所有者/仓库名`，先检查课程版本，再点击下载更新；一般增加课程无需重装 APK，也不需要 GitHub 登录或 token。

日历提醒在每次确认并获得权限后，由 App 写入用户选择的可写日历；拒绝授权仍可学习。备份通过系统文件选择器保存，个人答案与进度不上传 GitHub。首次上手、空仓库发布步骤和预览 APK 限制见 [安卓安装与更新](docs/android.md)。

## 本地启动

需要 **Python 3.9 或以上**，只使用标准库。在项目根目录运行：

```sh
python3 learning_loop.py doctor
python3 learning_loop.py serve
```

打开 <http://127.0.0.1:8765>。macOS 也可双击 `启动学习循环.command`；macOS/Linux 可运行 `sh start.sh`，Windows 可双击 `start.cmd`。Windows 命令行中的 `python3` 通常可换成 `py -3`。

## 已有课程

| 课程 | 建立直觉 | 动手验证 |
| --- | --- | --- |
| 高斯溅射与 Brush | 48 秒原创字幕动画、四幅图、可旋转的合成高斯杯子、中文讲解与逐行源码说明 | 调整二维高斯，比较图像与误差，再规划真实采集 |
| 贝叶斯更新 | 四幅计数图、约 88 秒中文讲解，从“坏件会报警”推到“报警后是否坏” | 纸笔改变基准率或误报率，重新计算报警群体 |

动画和高斯杯子是原理示意，不是照片重建成果。贝叶斯例题数字为教学假设；本课聚焦概率判断，无需代码章节。项目课保留固定提交的源码与逐行解释；学科课使用教材、例题和推理。音频由本机中文音色合成，并提供完整文字稿。

观看、听讲、点击图解和选择课程都不会自动记为掌握。第一次保存自己的实验、应用或总结后，核心问题才进入复习计划。

## 手机网页作为补充

```sh
python3 scripts/build_site.py --output dist/site
```

将 `dist/site` 部署到 HTTPS 静态网站，例如 GitHub Pages。仓库自带 Pages 工作流，默认构建网页并跳过外部部署。需要自动部署时，先在仓库 Pages 设置中将来源选为 **GitHub Actions**，再添加仓库变量 `ENABLE_PAGES=true`；随后推送相关内容到 `main` 或手动触发工作流。部署成功后打开仓库显示的实际网址。步骤见 [手机使用与部署](docs/mobile.md)。

手机网页可添加到主屏幕，离线准备成功后可查看已缓存图解、音频与练习。记录保存在**当前浏览器**，支持导出和确认后导入手机端 JSON 备份。浏览器、安卓版和电脑端 SQLite 各自独立，当前没有云同步。网页关闭后不发后台推送；网页版本可导出日历文件，安卓版则在确认授权后直接写入日历。

## 学习循环

1. **发现**：电脑端读取公开 GitHub 候选，筛选 ≥100,000 Star、非 fork、非归档且许可元数据可识别的软件项目。按累计 Star 排序，合并相同主线、排除已学后最多展示 20 项，合格项目不足不凑数。手动选择项目或学科不受 Star 门槛限制。
2. **理解**：一次选一个问题，用图、短讲解、预测题和反例建立核心机制。主路径约 10～15 分钟，详细原理与源码按需展开。
3. **实验**：先预测，改变一个因素，记录观察。助手运行成功不等于学习者已完成。
4. **应用**：把同一思路用于真实场景，留下成果、限制和自己的总结。
5. **回忆**：先回答再看参考答案，自评后调整间隔。基础间隔 1/3/7/14/30/60 天，忘记后 10 分钟再练，提前练习不延长原计划。

累计 Star 表示受欢迎程度，不代表近期增长。电脑端至少保留 7 天真实快照后才计算近 7 日增长；网络失败保留缓存并说明时间。

## 添加想学的主题

所有命令在项目根目录运行。把示例题目换成自己真正想学的内容：

```sh
python3 learning_loop.py request-track --title "贝叶斯更新" --topic bayesian-reasoning --subject "概率与统计" --kind subject
python3 learning_loop.py list-courses
```

命令返回真实 `track_id`，将它填入下方 `TRACK_ID`，即可导入已备好的示例课：

```sh
python3 learning_loop.py validate-lesson --file content/bayes.json
python3 learning_loop.py import-lesson --track-id TRACK_ID --file content/bayes.json
```

新主题可用 `draft-lesson --track-id TRACK_ID --output content/my-topic-draft.json` 生成起点。草稿不能直接当成教材；请按 [备课指南](docs/authoring.md) 核实来源、制作媒体与实验，再验证和导入。共享课库在 `content/courses.json` 登记；`content/catalog.json` 只维护 GitHub 发现分类。

## 定时检查

Python App 与手机网页本身不包含持续调度器。可手动执行 `python3 learning_loop.py daily --refresh`，也可使用 `skill/learning-loop/` 与 [每日任务模板](docs/heartbeat-prompt.txt) 配置学习助手定期检查。

Codex 定时任务是可选适配，需要在自己的环境单独配置。仅当新课程、到期复习、候选实质变化或需处理的失败出现时通知，其他时候静默。网页里修改提醒时间只改变偏好，须同步更新实际调度器。电脑关闭、助手退出或断网时不保证执行。

## 项目结构

| 位置 | 用途 |
| --- | --- |
| `learning_loop.py` | 电脑端数据、发现、复习、校验、命令行与本地 API |
| `web/`、`web/mobile/` | 电脑界面、手机界面与共用教学组件 |
| `android/` | 安卓 Java 容器、课程更新、日历和系统文件备份 |
| `content/courses.json`、`content/*.json` | 课库清单、课件与旁白源 |
| `web/media/`、`web/lab/` | 原创教学媒体与小实验 |
| `skill/learning-loop/` | 可移植的研究、备课与伴学流程 |
| `data/` | 本机私人档案，不进入公开仓库或静态构建 |

更多说明：[安卓 APK](docs/android.md) · [架构](docs/architecture.md) · [备课](docs/authoring.md) · [手机网页](docs/mobile.md) · [维护](docs/maintenance.md)。许可见 [LICENSE](LICENSE)，外部源码与来源见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

学习记录不自动上传，导出文件也属于私人数据。当前没有多用户登录、跨设备同步、云端全天候备课或自动执行外部仓库代码。
