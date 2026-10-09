# 制作一门可用的短课

先确定学习者能解释或完成什么，再设计图与实验。一个主题只讲一个可迁移的机制。完整字段见 [教学包规范](../skill/learning-loop/references/teaching.md)，教学流程见 [skill](../skill/learning-loop/SKILL.md)。

## 建立选题

```sh
python3 learning_loop.py request-track --title "贝叶斯更新" --topic bayesian-reasoning --subject "概率与统计" --kind subject
```

项目课用 `--kind project`，可加真实的 `--repo-url`。取返回的 `track_id` 替换以下 `TRACK_ID`；同主题或同仓库会复用已有主线。

```sh
python3 learning_loop.py draft-lesson --track-id TRACK_ID --output content/my-topic-draft.json
```

草稿排他创建，不覆盖已有文件；带 `_draft` 与占位内容，不能直接作为 ready 教材。完成查证、媒体和全部内容后移除草稿标记，再验证。

## 取证与设计

项目查官方文档与固定提交源码；学科查权威教材、讲义或原始研究。只引用真正读过的来源。提炼 3～5 个核心思想，解释为什么需要、怎样工作、删掉会怎样、何时失效。标清事实、类比与假设；贝叶斯工厂数字是合成例题，不是实际统计。

先设计 3～5 幅因果图，每幅一个机制、一句结论和一个预测问题，提供替代文字。动态过程可加短视频和字幕，但不是每课必须有视频。只使用已实现且适合本课的交互；没有合适组件就设 `interactive: null`。

尽量提供真实生成的中文音频，用口语说明变量角色和因果，提醒暂停后看图或动手。部分课程只有核心音频时标明覆盖范围。声音不能替代文字稿，文字稿也不能冒充声音。

资产在 `web/media/课程名/`，引用 `/media/课程名/文件名`。静态 SVG 不含外部引用、脚本或 HTML。音视频生成后实际解码、测时长和核对文字稿，不预填虚拟数字。原理示意不能声称真实重建成果。

## 代码与学科推理

代码课先用短伪代码建立全局，再展示真实连续片段。保留原文、准确起始行号与完整提交 ID；逐行中文解释存在 `notes`，每个非空行都讲“做什么”和“为什么”。不能把自己的改写冒充源代码。

无代码的学科课设 `code_insight: null`，用推理、例题、反例和纸笔操作承载思想，不硬套程序。

## 实验与回忆

主路径安排 3～5 分钟操作，按主题补充完整实验。先预测，再只改一个因素，记录观察与可验收成果。实际应用要有真实场景与边界。

回忆题覆盖解释、预测、诊断和迁移。保留稳定课程 ID 与 `questions[].id`，改版不重置历史。不要填写学习者的答案、验收结果和评分。

## 可选音频制作

App 播放不需要制作工具。macOS 可复用本地生成器；先确认已有音色，不假定其他机器安装 Tingting，也不自动下载：

```sh
python3 scripts/generate_brush_audio.py --input content/bayes-narration.json --output-dir web/media/bayes/audio
```

核对输出 `metadata.json` 的实测时长、文字稿、章节和路径，再合并到 `audio_lesson`。不公开本机路径与生成记录。

## 校验与共享

```sh
python3 learning_loop.py validate-lesson --file content/my-topic.json
python3 learning_loop.py import-lesson --track-id TRACK_ID --file content/my-topic.json
```

结构校验不替代事实核对和播放验收。先看实物图与窄屏布局，验证视频暂停、音频拖动、文字稿、预测反馈与代码行对应。导入后重读 `state`，确认课程及原历史。

共享时将课件登记在 `content/courses.json` 的 `courses` 数组中，外层 `schema_version` 为 1：

```json
{
  "id": "bayes-basics",
  "title": "贝叶斯：看到证据后怎样更新判断",
  "topic_id": "bayesian-reasoning",
  "subject": "概率与统计",
  "kind": "subject",
  "repo_full_name": "",
  "repo_url": "",
  "lesson_file": "bayes.json"
}
```

`lesson_file` 相对 `content/`；学科仓库字段留空。保留 `content/catalog.json` 的 GitHub 分类用途。运行 `doctor` 和 `python3 scripts/build_site.py --output dist/site`，再按 [部署指南](mobile.md) 发布。课库不能混入私人档案。
