# 转录与模型

转录扩展使用独立页面 `/transcription`，可从侧栏或单集的转录区域进入。
原有设置页、LLM 配置、应用设置、摘要模板保持 GitHub master 的实现与菜单顺序。

页面读取 `/api/capabilities` 的实际状态，支持中英文与重新检测。
未安装、未启用、缺少模型或运行环境异常时，单集页禁用对应转录方式；
后端在任务提交与执行前再次检查。已有转录不受影响。

## 按需安装

在 `backend` 目录运行 `uv sync` 安装基础依赖。本地转录和云转录需要选择扩展：

```sh
uv sync --extra local-whisper
uv run --extra local-whisper python scripts/prepare_transcription.py --provider local_whisper
```

在 `backend/.env` 设置 `TRANSCRIPTION_LOCAL_ENABLED=1`，再重启后端。
WhisperX 使用 `--extra local-whisperx` 与 `--provider local_whisperx`。
需要多个扩展时，在同一次同步或启动命令里保留全部 `--extra`。
模型准备会下载文件；页面的环境检测不会下载模型或启动转录。

云转录使用 `--extra cloud-transcription`，并设置 `TRANSCRIPTION_CLOUD_ENABLED=1`
和 `ASSEMBLYAI_API_KEY`。它会上传音频并可能产生费用，不会被自动选为默认方式。

## 本次验证

- 与 master 比较，SettingsView、原 settings 组件目录及 LLM 设置 API 无差异。
- 转录相关后端测试 39 项、前端测试 6 项通过，生产构建通过。
- 浏览器验证独立路由、刷新后直接进入、中英文、侧栏入口、单集跳转与返回、不可用选项禁用。
- 当前没有安装转录模型；尚未验证实际本地推理或云转录。

本机仍使用既有数据库与配置。因 macOS 占用 5000 端口，开发进程通过启动参数
将前端代理指向 5001，原版 `vite.config.js` 和 `run.py` 未修改。
