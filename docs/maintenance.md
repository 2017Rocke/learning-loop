# 维护与数据保护

维护目标是课程可信、升级保留历史、发布不带私人信息。命令均从项目根目录运行。

## 检查

Python App 和构建使用 Python 3.9+ 标准库。已有媒体播放与制作环境无关。

```sh
python3 learning_loop.py doctor
python3 learning_loop.py list-courses
python3 learning_loop.py validate-lesson --file content/brush.json
python3 learning_loop.py validate-lesson --file content/bayes.json
python3 -B -m unittest discover -s tests -v
node tests/test_mobile.js
node tests/test_service_worker.js
python3 scripts/build_site.py --output dist/site
```

Node 22 用于前端维护检查，不是运行 Python App 或学习手机课库的依赖。`doctor` 检查环境、清单与资源存在性，不访问学习数据库或网络。`validate-lesson` 检查严格结构与媒体路径，不打开数据库。它们不解码媒体，也不判断事实正确性。

改状态规则使用临时数据库，不能往用户记录提交假答案。改教学组件检查桌面、窄屏、键盘、暂停拖动与源码旁注。改公式、素材或摘录应重新核对来源，不用结构通过代替语义审查。

## 电脑备份

设置页可导出完整 JSON，也可运行：

```sh
python3 learning_loop.py export --output learning-private-backup.json
```

把导出移到公开仓库之外，不要提交。完整档案位于 `data/learning.sqlite3`；运行时可能有 WAL/SHM 文件，不能在写入时只复制主文件。推荐 SQLite backup API 生成一致备份；人工恢复前停止服务、保留原数据目录副本，再替换已核验数据库。

当前电脑端没有通用 JSON 恢复向导。`init --snapshot` 用于 GitHub 发现快照，不是私人备份恢复；不要把未经验证 JSON 直接写入数据库。

## 手机备份

手机导入导出只处理自己的 JSON 格式，与 SQLite 独立。安卓版通过系统文件选择器保存和选择备份；浏览器使用下载与文件选择。导入经过验证与用户确认，整体替换、不合并、不上传 GitHub。换域名、浏览器、APK 签名或设备前导出。档案中的课程与问题须仍在当前课库，缺失时应保留原数据并恢复匹配课库。

## 安卓课程与 APK

```sh
python3 scripts/build_android_content.py --output dist/android-content --assets android/app/src/main/assets/site
python3 scripts/check_android.py
```

课程产物为 `manifest.json` 和 `courses-<hash>.zip`，通过 `publish-content.yml` 发布到固定 `course-content` Release。`check_android.py` 使用 JDK 17，在临时目录编译并检查实际课程包、日历时间与媒体 Range，不需要 Android 设备或 SDK；可通过 `JAVA_HOME` 或 PATH 提供 Java 工具。

APK 由 `android-apk.yml` 构建 debug 预览产物。本机构建需 JDK 17、Android SDK 35 和 Build Tools 35.0.0；准备资源后在 `android/` 执行 `./gradlew --no-daemon assembleDebug lintDebug`。支持 Android 8.0+，工具链不是普通学习或 Python 运行依赖。

课程包只有数据和允许的媒体，APK 内置 HTML/JavaScript 和原生代码；修改程序能力时应重新构建 APK，不能混入远程课程更新。`content/reminder.json` 的默认时间和分钟数纳入内容版本，修改后日历也不能静默同步，须再次请求用户确认。

检查更新只读小型清单，下载由用户再次点击触发。维护检查应覆盖校验失败、截断下载、ZIP 路径穿越和异常体积、禁止脚本文件、断电或写入失败后保留旧包，以及更新后个人记录不丢失。完整资源校验成功后才激活新版本。

当前已安装课程版本会保留，让仍打开的旧页面继续读取同一套媒体；多次更新会增加应用占用。进程被系统强制结束也可能留下临时下载。空间不足时更新会停止，先备份学习记录再排查，不能把“清除应用数据”作为默认处理。

日历检查覆盖取消确认、拒绝或撤销权限、没有可写日历、重复设置不产生重复每日事件、按课程最早到期归并、逾期时段处理，以及删除旧事件后重新设置。写入前持久化所有权标记，之后按标记找回事件，覆盖系统已写入但缓存事件 ID 前进程退出的情形。每次写入须重新确认，权限已授予不能代替本次同意；只写必要提醒，不包含私人答案。

当前同步一个每日安排与最多 20 门课程的单次提醒，退出当前复习表的旧单次事件暂不自动删除；不能宣称日历实时跟随每次回答。SAF 文件备份应检查取消、无效 JSON、导入前确认与恢复后的记录一致性。

全新 CI 运行生成的 debug 签名可能不同，预览 APK 不保证覆盖原安装。换包前先备份；正式版使用用户保管的稳定签名，密钥不进 Git 或聊天。构建完成、远端工作流成功和真机验收分别记录，不混称已完成。

面向手机试用者发布时，将已审核 APK 和 SHA-256 校验文件附到独立的 Android Release（例如 `android-v0.2.1`），不要覆盖 `course-content`。Release 版本须与 APK 的 versionName/versionCode 一致。后续 APK 必须复用上一份 Release 的签名文件，并用 `apksigner verify --print-certs` 比较证书摘要；签名文件由发布者在仓库外保管和备份，不能上传到公开构建产物。若签名不同，须明确这是需备份换装的迁移，而不能声称可直接升级。Actions 的临时 debug 构建仅用于开发验证。

### 安卓媒体分段读取

`WebViewMediaResponse` 专用于 `shouldInterceptRequest` 返回的流，不能当成普通 HTTP 服务器的已裁剪响应。Chromium 会先以流的 `available()` 计算完整资源范围，再按 Range 起点 `skip()`；App 不能提前跳过起点。保持 206 / Content-Range / Content-Length 的正确语义，把零位置的流交给 WebView，并在读取时限制闭区间终点。范围回归检查使用真实课件音频重放这个消费顺序，对完整播放、非零偏移、后缀范围、闭区间与分片重组逐字节验证；桌面 Python 服务器和 service worker 的普通 HTTP Range 实现不采用这个适配方式。

依据为 [Chromium 130 固定提交的 InputStreamReader](https://chromium.googlesource.com/chromium/src/+/3a50e012e4c9b8a410a4e2b12bf577e69ee8f755/components/embedder_support/android/util/input_stream_reader.cc) 与 [AndroidStreamReaderURLLoader](https://chromium.googlesource.com/chromium/src/+/3a50e012e4c9b8a410a4e2b12bf577e69ee8f755/components/embedder_support/android/util/android_stream_reader_url_loader.cc)；不据此推断用户手机的具体 WebView 版本。原生范围回归和音频完整解码不能代替真机播放；播放错误提示的 MediaError 编号用于后续区分读取失败、解码失败和格式不可用。

## 升级

- 保持课程 ID 和 `questions[].id` 稳定，改文字或补媒体不重置用户历史。
- `catalog.json` 维护 GitHub 分类，`courses.json` 是公开课库，不可互相覆盖。
- 新字段兼容旧课，检查 `code_insight: null` 学科课路径。
- 导入改版后验证旧证据、复习时间和历史保留；新教材不代表已学。
- 必须变更格式时先提供可验证迁移与备份，不能静默丢弃记录。

## 媒体与公开发布

生成媒体后查看图片，解码音视频、测时长、核对文字稿，并验证真实播放器。音频制作器可选且仅用于 macOS 已安装音色，普通运行不依赖它。公式重算，源码核对固定提交与连续行号；合成数据、原理图与真实结果分别标明。

公开内容不应含 `data/`、数据库、私人导出、`.env`、令牌、机器路径、私人实现证据或 `generation-record.json`。`.gitignore` 只是初步过滤，仍要检查实际暂存内容。构建器只发布登记课程与引用资源；拒绝覆盖无构建标记的非空目录时，选择新空目录排查，不随意删除原目录。

部署使用 HTTPS，检查仓库子路径与离线更新。没有实际测试前，不声称真实手机、安装、后台声音或通知已验收。

## 调度与排障

调度是可选集成，网页时间仅是偏好，修改外部任务须使用实际环境工具并核实配置。不要写入私人自动化 ID，不承诺关机或退出助手后仍运行。

排查依次看环境检查、课件资产、本地服务或部署地址、浏览器状态、可选调度器。发现失败保留缓存；媒体不显示核对引用；手机看不到电脑进度先说明档案独立。不要默认清空数据库、浏览器存储或学习状态。
