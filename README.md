# 007AI Image Skill

当前版本：**1.1** · [下载分发包](https://github.com/30925766/007ai-image-skill/releases/download/v1.1/007ai-image-skill-v1.1.zip)

通过 007AI 异步图片接口完成文生图、参考图编辑和批量生图的 Codex Skill，支持 GPT Image、Nano Banana 及专用模型适配。

**本仓库为无内置密钥、无密钥兜底的分发版。** 使用前必须配置自己的 007AI API Key；需要上传参考图时，还需配置自己的 imgBB API Key。

## 功能

- 通过异步任务生成图片，自动轮询结果并下载到本地。
- 从远程目录刷新模型列表，获取失败时使用随包提供的模型清单。
- 支持模型比例选择、单张生图、多张并发和逐张不同提示词。
- 支持本地图片、图片 URL 和 Base64 data URL 作为参考图，具体能力由模型与服务接口决定。
- 为明确要求系列风格一致的任务提供样稿确认与统一规范流程。
- 保存批次记录，中断后可恢复已知任务的查询和下载，避免重复提交。
- 提供 JSON 结果或 Markdown 图片预览。

## 运行环境

- Windows 与 PowerShell，或 macOS 与 Bash：分别提供启动和环境初始化入口。
- Python 3.10 或更高版本：仅使用标准库，无需安装 pip 依赖。
- 可访问 007AI 服务；参考图上传时需能访问 imgBB。
- 使用 Git 安装时需先安装 Git；也可下载 ZIP 后手动解压安装。

Windows 启动脚本会探测 Python 并保存本地运行环境配置。未找到可用 Python 时，会尝试通过 `winget` 安装 Python 3.12。

macOS 入口只检测 Python，不会自动安装软件；未找到 Python 3.10+ 时会提示安装后重试。可通过 `CODEX_007AI_PYTHON` 指定解释器路径。两种系统使用独立的运行环境配置文件。

## 安装

### 使用 Git

在 PowerShell 中执行：

```powershell
git clone https://github.com/30925766/007ai-image-skill.git "$env:USERPROFILE\.codex\skills\007ai-image-skill"
```

目标目录需要不存在或为空。如果已安装此 skill，请先处理原目录，避免覆盖本机配置。

macOS 在终端执行：

```bash
mkdir -p "$HOME/.codex/skills"
git clone https://github.com/30925766/007ai-image-skill.git "$HOME/.codex/skills/007ai-image-skill"
```

### 使用分发包

下载 [1.1 无 key 兜底分发包](https://github.com/30925766/007ai-image-skill/releases/download/v1.1/007ai-image-skill-v1.1.zip)，将其中的 `007ai-image-skill` 目录解压到：

```text
%USERPROFILE%\.codex\skills\007ai-image-skill
```

确保 `SKILL.md` 位于该目录根部，不要多嵌套一层同名目录。

macOS 安装路径为 `~/.codex/skills/007ai-image-skill`。

## 首次配置

以下命令均在 PowerShell 中执行。先进入安装目录：

```powershell
Set-Location "$env:USERPROFILE\.codex\skills\007ai-image-skill"
```

前往 [007AI](https://007.007ai.cc/) 获取自己的 API Key，然后将示例占位文本替换为实际密钥：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_007ai_image.ps1 --set-api-key 'YOUR_007AI_API_KEY'
```

该命令同时设置默认服务地址 `https://007.007ai.cc`。检查本地配置与服务端模型：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_007ai_image.ps1 --check-config
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_007ai_image.ps1 --check-models
```

`--check-config` 仅检查本地配置是否存在，不代表密钥已通过服务端验证。`--check-models` 会访问服务端模型接口，不创建生图任务。

### macOS 首次配置

```bash
cd "$HOME/.codex/skills/007ai-image-skill"
bash scripts/run_007ai_image.sh --set-api-key 'YOUR_007AI_API_KEY'
bash scripts/run_007ai_image.sh --check-config
bash scripts/run_007ai_image.sh --check-models
```

下文所有 PowerShell 示例在 macOS 上均可将 `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_007ai_image.ps1` 替换为 `bash scripts/run_007ai_image.sh`，后续参数保持一致，文件路径改为本机路径。无需为 Shell 脚本添加执行权限。图片生成成功后，macOS 使用 Finder 定位图片。

### 配置参考图上传

部分模型只接受公网 HTTPS 参考图。如果使用本地图片，需要先配置 imgBB：

1. 在 [imgBB](https://imgbb.com/login) 注册或登录。
2. 在 [imgBB API 页面](https://api.imgbb.com/) 获取 API Key。
3. 执行配置命令：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_007ai_image.ps1 --set-imgbb-api-key 'YOUR_IMGBB_API_KEY'
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_007ai_image.ps1 --check-image-host
```

纯文生图无需 imgBB。模型支持 Base64 时优先使用 Base64；模型要求公网 URL 时才上传。已提供公网 URL 的参考图直接使用该地址。

参考图上传到 imgBB 后会存储在第三方服务，脚本设置有效期为 24 小时。请勿上传包含隐私或敏感信息的图片。

## 在 Codex 中使用

安装后，在对话中明确调用此 skill，例如：

```text
使用 $007ai-image-skill，帮我生成一张产品展示图：白色无线耳机，浅灰背景，柔和棚拍光线。
```

Skill 会展示本次完整模型列表，再依次确认比例和张数。收到参考图时会将其用于生成；明确要求多图风格一致时，会先确认样稿。

## 命令行示例

以下示例均从安装目录运行；`MODEL_ID` 需替换为模型清单中的实际 ID。比例、尺寸和输出格式以所选模型支持的选项为准。

### 查看模型与比例

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_007ai_image.ps1 --list-models --format markdown
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_007ai_image.ps1 --model 'MODEL_ID' --list-options
```

### 文生图与批量生图

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_007ai_image.ps1 --model 'MODEL_ID' --ratio 1:1 --count 1 --prompt '白色无线耳机，浅灰背景，柔和棚拍光线' --format markdown
```

将 `--count` 改为所需张数即可批量生成。默认提交并发数为 3，可通过 `--concurrency` 调整；实际使用需遵守服务端限额。

### 使用参考图

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_007ai_image.ps1 --model 'MODEL_ID' --ratio 1:1 --count 1 --prompt '保留产品外观，将背景改为浅灰色' --image 'C:\images\reference.png' --format markdown
```

部分专用模型还要求显式传入 `--image-size`。例如 `gptimage2.5flare_gr` 支持 `1K`、`2K`、`4K`，并要求公网 HTTPS 参考图。详见 [模型接口说明](references/model-adapters.md)。

### 检查参考图与预演

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_007ai_image.ps1 --model 'MODEL_ID' --image 'C:\images\reference.png' --check-reference
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_007ai_image.ps1 --model 'MODEL_ID' --ratio 1:1 --count 1 --prompt '产品展示图' --dry-run
```

预检和预演不上传图片、不创建生成任务；需要的本地配置和模型参数仍须完整。

### 恢复中断的批次

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_007ai_image.ps1 --resume-batch 'C:\images\batch-example.json' --format markdown
```

请将示例路径替换为实际批次记录。恢复只查询和下载已有任务，不补交尚未提交或提交结果不明的图片。

## 输出与错误处理

图片默认保存在 skill 目录下的 `images`，可用 `--output-dir` 指定其他目录。批次记录以 `batch-<唯一标识>.json` 命名，记录每张图片的任务状态与结果。

任务默认每 3 秒查询一次，单任务最多等待 30 分钟，可用 `--poll-interval` 和 `--wait-timeout` 调整。部分失败不影响其他图片继续处理；存在失败或未完成项时，批次命令返回退出码 `2`，已完成图片和记录仍会保留。

已获得任务 ID 后不会自动重提。请求超时且未取得任务 ID 时，应先核实原任务状态，避免重复生成。仅在服务端明确拒绝 Base64 且未取得任务 ID 时，允许一次图床转换重试。

## 密钥与分发

| 文件或目录 | 用途 | 是否纳入 Git |
| --- | --- | --- |
| `007ai-image-key.json` | 用户本机的 007AI 密钥 | 否 |
| `imgbb-api-key.json` | 用户本机的 imgBB 密钥 | 否 |
| `.config/` | 服务地址、运行环境、参考图缓存与能力覆盖 | 否 |
| `images/` | 默认图片输出与批次记录 | 否 |
| `scripts/`、`references/`、`agents/` | 运行脚本、参考文档与 skill 元数据 | 是 |

007AI 和 imgBB 只读取各自的本机密钥文件，不使用内置密钥、环境变量密钥、其他 skill 的密钥或旧配置中的密钥兜底。未配置必要密钥时会停止对应的生成或上传操作。

这些密钥文件为本地明文配置，请妥善保管。不要将真实密钥写进 README、提示词示例或提交记录，也不要将已使用的整个 skill 目录直接重新打包。自定义输出目录同样需要自行排除。

仓库提供的 `.gitignore` 用于避免意外新增跟踪，但无法移除已提交的敏感文件；如果曾提交过真实密钥，应移除敏感内容并更换密钥。

## 更多说明

### 1.1 更新

- 新增 macOS Bash 启动与 Python 环境检测入口。
- macOS 使用独立的 `.config/runtime-macos.json`，不覆盖 Windows 运行环境配置。
- macOS 生成成功后通过 Finder 定位图片。
- 保持无内置密钥、无密钥兜底的分发方式。

- [Skill 完整工作流](SKILL.md)
- [分发说明](README-DISTRIBUTION.md)
- [模型接口与参考图预检](references/model-adapters.md)
- [系列风格一致性流程](references/series-consistency.md)

本项目通过第三方服务调用图片模型。模型可用性、账户权限和实际费用以服务提供方为准。
