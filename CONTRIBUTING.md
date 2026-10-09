# 维护与贡献

先读 [AGENTS.md](AGENTS.md)，再看 [架构](docs/architecture.md) 和 [备课流程](docs/authoring.md)。运行只需 Python 3.9+；手机网页不需要 Python。Node.js 仅用于运行手机学习逻辑的测试。

课程改动沿用稳定的课程 ID、topic ID 和问题 ID。用真实来源核实核心机制，为引用的代码提供固定 commit 和逐行解释，为图片和音频提供等价文字。新增课程与媒体后更新 `content/courses.json`，不要提交自己的数据库、学习回答、备份或凭据。

提交前运行：

```sh
python3 -B -m unittest discover -s tests
node tests/test_mobile.js
node tests/test_service_worker.js
python3 learning_loop.py doctor
python3 scripts/build_site.py --output dist/site
```

修改会写记录的流程时，使用 `--db` 指向临时数据库验证。不要把示例、自动测试或助手完成的实验记为用户成果。界面修改还需检查手机窄屏、音频、键盘操作和子目录部署；无法检查的项目明确记录。

提交说明写清触发场景、现在的行为及实际运行的验证。新依赖、云同步、模型调用或用户数据上传必须显式设计和说明。
