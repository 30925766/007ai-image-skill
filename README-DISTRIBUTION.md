# 007AI Image Skill 分发版

当前版本：**1.1**。支持 Windows PowerShell 与 macOS Bash 入口。

macOS 使用 `bash scripts/run_007ai_image.sh` 代替下文的 `scripts\run_007ai_image.ps1`，参数相同。例如：

```bash
bash scripts/run_007ai_image.sh --set-api-key 你的007AI_API_KEY
bash scripts/run_007ai_image.sh --check-config
bash scripts/run_007ai_image.sh --list-models --format markdown
```

macOS 需要 Python 3.10+；入口会自动检测，不会自动安装软件。可通过 `CODEX_007AI_PYTHON` 指定解释器路径，路径含空格时需引用。macOS 的环境检测结果保存为 `.config/runtime-macos.json`；生成成功后使用 Finder 定位图片。Windows 继续使用原 PowerShell 入口。

此压缩包不包含任何 API key、运行时配置、缓存或已生成图片。

本分发版无内置或兜底密钥。007AI 只读取用户配置的 `007ai-image-key.json`，
imgBB 只读取用户配置的 `imgbb-api-key.json`；不会从环境变量、旧配置、
共享配置或其他 skill 中读取密钥。未配置必要密钥时，停止对应的生成或上传操作。

首次使用：
1. 将整个目录安装到 Codex skills 目录，目录名保持为 007ai-image-skill。
2. 运行 scripts\run_007ai_image.ps1 --set-api-key 你的007AI_API_KEY。
3. 运行 scripts\run_007ai_image.ps1 --check-config。
4. 运行 scripts\run_007ai_image.ps1 --check-models。

API key 只保存到用户本机，不会写入分发包。不要把 007ai-image-key.json、.config 或 images 再次压缩分发。

上传 GitHub 时包含 `.gitignore`，不要上传本机已使用的整个 skill 目录。
`.gitignore` 无法移除已跟踪的敏感文件；如果曾提交真实密钥，需要移除敏感内容并更换密钥。

需要公网图片 URL 的模型可先配置 imgBB：
`scripts\run_007ai_image.ps1 --set-imgbb-api-key 你的imgBB_API_KEY`

imgBB API Key 只保存到 skill 根目录的 `imgbb-api-key.json`，与 `007ai-image-key.json` 分开存放；图床缓存和模型能力覆盖保存在本机 `.config\image-host.json`。分发前不要包含这两个密钥文件或 `.config` 目录。模型能力不明确时不会凭模型名上传；可按实际接口要求配置覆盖：
`scripts\run_007ai_image.ps1 --set-model-image-input 模型ID public_url https://007.007ai.cc`
