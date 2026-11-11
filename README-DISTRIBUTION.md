# 007AI Image Skill 分发版

此压缩包不包含任何 API key、运行时配置、缓存或已生成图片。

此版本没有内置或兜底密钥。007AI 只读取用户通过 `--set-api-key` 保存的
`007ai-image-key.json`；imgBB 只读取用户通过 `--set-imgbb-api-key` 保存的
`imgbb-api-key.json`。不从环境变量、其他 skill、旧配置字段或共享配置中读取密钥。
未配置密钥时会提示配置，不会使用备用密钥发起生图或图床上传。

首次使用：
1. 将整个目录安装到 Codex skills 目录，目录名保持为 007ai-image-skill。
2. 运行 scripts\run_007ai_image.ps1 --set-api-key 你的007AI_API_KEY。
3. 运行 scripts\run_007ai_image.ps1 --check-config。
4. 运行 scripts\run_007ai_image.ps1 --check-models。

API key 只保存到用户本机，不会写入分发包。不要把 007ai-image-key.json、.config 或 images 再次压缩分发。

更新 GitHub 时，上传本分发目录内的全部文件，包括 `.gitignore`，不要上传本机已使用的
skill 目录。`.gitignore` 仅防止新增跟踪；如果仓库曾经提交过密钥，需另外移除已跟踪文件并更换密钥。

需要公网图片 URL 的模型可先配置 imgBB：
`scripts\run_007ai_image.ps1 --set-imgbb-api-key 你的imgBB_API_KEY`

imgBB API Key 只保存到 skill 根目录的 `imgbb-api-key.json`，与 `007ai-image-key.json` 分开存放；图床缓存和模型能力覆盖保存在本机 `.config\image-host.json`。分发前不要包含这两个密钥文件或 `.config` 目录。模型能力不明确时不会凭模型名上传；可按实际接口要求配置覆盖：
`scripts\run_007ai_image.ps1 --set-model-image-input 模型ID public_url https://007.007ai.cc`
