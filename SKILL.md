---
name: 007ai-image-skill
description: 当用户需要通过 007AI 异步图片接口批量生成图片、配置 API key、选择异步 GPT Image 或 Nano Banana 模型、选择画面比例并保存本地图片时使用。
---

# 007AI 异步批量生图 Skill

通过 https://007.007ai.cc/ 的异步图片接口生成一张或多张图片。所有模型统一提交到 POST /v1/videos，取得任务 ID 后轮询 GET /v1/videos/{task_id}，完成后下载图片并返回预览和本地路径。

## 固定交互顺序

1. 首次使用或运行环境不确定时，先通过统一入口执行环境自检：scripts/run_007ai_image.ps1。
2. 环境可用后先运行 --check-config（包含 imgBB 配置状态）；有参考图时，在提交前运行 `--model <ID> --image <参考图> --check-reference`。这只检查配置和输入，不上传、不创建任务，也不代表密钥已通过服务端验证。模型生成前可运行 --check-models 进行无计费的服务端模型校验。
3. 如果用户已经提供提示词，缓存提示词，不重复询问。
4. 每次进入模型选择阶段都必须实际执行 `--list-models --format markdown` 获取本次完整模型列表，并按下述固定格式逐项完整展示，让用户选择模型 ID；不得跳过命令、凭记忆列模型或仅展示部分模型。
5. 用户选择模型后，调用 --list-options 展示该模型支持的画面比例。
6. 用户选择比例后询问生成张数。
7. 张数明确后检查提示词、模型、比例、张数和参考图参数；完整则按下方“生成模式”执行。普通任务立即生成，不再询问“是否继续”；一致性任务需要先确认样稿。
8. 生成完成后直接返回图片 Markdown 预览和图片所在位置。

每次新的生图请求都必须重新展示模型列表，不复用上一次的模型、比例或张数。

## 简洁回复规则

- 默认采用“简短开始、必要进度、结果展示、异常说明”。本节只约束对话篇幅，不减少内部检查、任务记录、参考图处理或防重复提交措施；完整模型列表、比例选项和缺少图床 Key 时的固定指引仍按原规则展示，不得因此省略或缩写。
- 开始执行时用一句话说明本次生成目标，不复述整段提示词、全部参数或检查计划。除模型、比例选择的既定顺序外，能同时确认的缺失信息合并询问，不重复询问已明确的信息。
- 环境、密钥、图床、参考图与模型检查正常时内部执行，不逐项汇报成功结果；已自行解决且不影响结果的编码、命令和参数问题不展开调试经过。与本次目标模型无关的清单差异不向用户逐项播报。
- 轮询、进程检查、无新输出和继续等待不单独播报，不反复强调“不会重复提交”。长时间等待时适度给一句简短进度，遵守宿主要求的更新频率，不为每次查询发送消息，不凭空估计完成时间。
- 多图只汇报整体进度，例如“已完成 3/5 张”；仅在实际获得状态后报告，不逐张展开任务编号或请求过程。一致性模式展示样稿并明确请求确认；其余规范保存和检查过程简洁处理。
- 影响结果或需要用户处理的问题必须说明，包括生成失败、参考图无法采用、参数不支持、状态不明及部分图片未完成。使用“具体问题＋影响＋下一步”的简短说明；详细诊断按需提供，不用成功话术掩盖失败或未经核实的结果。
- 完成时直接展示图片预览和保存位置，必要时加一句结果说明；有失败项或一致性差异则简要列出，不再重述执行步骤。完成前未查看结果时，不声称已通过视觉检查。
- 不主动在正文粘贴完整命令、接口字段、轮询记录、任务编号或诊断 JSON；排查时按需查看本地日志和批次记录。用户明确要求技术细节时再展开，始终保护密钥和 Base64。

普通任务的回复示例：

> 正在生成，将保留人物与构图，把羊驼替换为老虎。

长时间等待时：

> 图片仍在生成中。

完成时：

> 已完成。
>
> 图片预览与打开所在文件夹的链接。

## 异步模型

### 对话展示规则

- **先执行，后回复**：每次新生图请求及每次重新进入模型选择阶段，都必须实际运行 `scripts/run_007ai_image.ps1 --list-models --format markdown`。只使用该次命令返回的清单；不得复用历史回复、静态清单、记忆中的模型，亦不得因为用户已附图或已给提示词而省略模型选择清单。
- **全量展示**：逐字保留脚本返回的全部分类标题、每个模型 ID 和结尾选择提示。不得筛选、摘要、排序重排、隐藏、截断或只列推荐/候选模型；不得用“也可选择列表中的其他模型”等措辞代替其余模型。不得把清单拆成“推荐模型”小列表。
- **固定回复结构**：若用户已提供提示词/图片主题，第一行必须为“已记下你的图片主题：**<原提示词或主题>**。请先选择生成模型：”；未提供时第一行使用“请选择图片生成模型：”。紧接着原样附上本次脚本输出的完整模型列表，包括它自己的分类标题和结尾提示。主题只做原文引用，不擅自改写或遗漏用户的关键编辑要求。
- 列表中的模型 ID 必须保持脚本输出的精确拼写和数量。可在列表前加主题引导语，但不得改写脚本输出的模型项目；不得增添清单之外的模型。
- 不将整个列表放进代码块、纯文本框、JSON 或附件，必须直接呈现在对话正文中。不要显示价格、费率、未经验证的性能排名或默认推荐。
- 若列表命令失败或输出为空，明确说明本次无法获取完整模型清单并停止模型选择；不得退而使用静态清单、历史列表、部分模型或自行编造内容。先排查命令/环境问题后再继续。
- 用户选定完整模型 ID 后，才进入比例选择；不因其曾在历史对话中选过模型而跳过本次列表展示。

GPT Image：
gpt_image2_1k_hi_z_yb、gpt_image2_1k_lo_z_yb、gpt_image2_1k_me_z_yb、gpt_image2_2k_hi_z_yb、gpt_image2_2k_lo_z_yb、gpt_image2_2k_me_z_yb、gpt_image2_4k_hi_z_yb、gpt_image2_4k_lo_z_yb、gpt_image2_4k_me_z_yb、gpt-image-2-2K-z-yb、gpt-image-2-4K-z-yb、gpt-image-2-g、gpt-image-2-g_yb、gpt-image-2-vip-g、gpt-image-2-vip-g_yb、gpt-image-2-z、gpt-image-2-z-yb、gpt_image_2.5_z_yb、gpt_image_2.5_g、gpt_image_2.5_flare_z_yb、gpt_image_2.5_flare_g、gpt_image_2.5_sunburst_z_yb、gpt_image_2.5_sunburst_g

Nano Banana：
banana_2_z_yb、banana_2_2k_z_yb、banana_2_4k_z_yb、banana_pro_1k_z_yb、banana_pro_2k_z_yb、banana_pro_4k_z_yb、nano-banana-2-g_yb、nano-banana-fast-g、nano-banana-fast-g_yb、nano-banana-g_yb、nano-banana-pro-g、nano-banana-pro-g_yb、nano-banana-pro-vt-g_yb

### 模型清单自动同步与维护

1. **自动同步机制**：在向用户展示模型列表前，优先通过 `https://ai-assistant-price.scd666.com/api/models` 接口获取「图片异步」分类下的最新模型列表。
   - 每次 skill 调用时在内存中刷新最新列表，不修改本地 `scripts/models.json`。
   - 若价格网站打不开、响应超过超时限制、返回格式异常或分类为空：**静默忽略，直接使用本地已有的模型列表展示**，价格网站与 007AI 实际生图完全解耦，绝不阻塞或中断正常生图流程。
   - 网站清单只负责模型发现；正式生成仍以 007AI 接口实际可用性为准。
2. **分类展示原则**：模型名称按上述对话展示规则分类呈现，保留引导语和分类标题；不显示价格、费率或扣费数字。
3. **分类推导规则**：
   - 模型名包含 `banana` 时：`family` 填 `nano-banana`（走 `metadata.aspectRatio`），支持 15 种比例。
   - 模型名包含 `gpt` 或 `image` 时：`family` 填 `gpt-image-2`（走 `metadata.aspect_ratio`），支持 10 种比例。
   - `size_mode` 统一为 `ratio`，`transport` 统一为 `video-async`，`api_model` 与 `id` 相同。
4. **手动/服务端兜底**：若用户报出的模型 ID 不在清单且上述接口未包含，可访问 007AI 服务端 `GET /v1/models` 核对（需带浏览器 User-Agent），确认存在后按上述规则补入 `models.json` 使用。

通常模型档位已编码在模型 ID 中，使用 --ratio，不使用旧参数 --image-tier。例外：已验证的 `gptimage2.5flare_gr` 支持独立尺寸，必须明确指定 `--image-size 1K|2K|4K`，不得隐藏默认值。用户已给模型、比例、尺寸、张数时直接采用，不重复要求选择。专用适配参见 [模型接口说明](references/model-adapters.md)。

## 参数要求

- 必填：--model、--ratio、--count、--prompt。
- 图生图可追加：--image '<本地图片路径、URL 或 data URL>'。
- 普通 GPT Image 请求使用 metadata.aspect_ratio；`gptimage2.5flare_gr` 使用顶层 `aspect_ratio`、`image_size`、`images`，不得使用 metadata 或 input_reference。
- Nano Banana 请求使用 metadata.aspectRatio。
- 普通模型参考图放入 metadata.urls，支持 Base64 data URL 或可访问 URL，最多 5 张；专用模型使用其已验证字段及输入约束。当前命令行 --image 接受一张参考图。
- 不为模型、比例、张数或提示词使用隐藏默认值。

## 生成模式

| 用户需求 | 执行方式 |
|---|---|
| 单张图片 | 提交单个任务，等待完成并下载 |
| 多张图片，未要求风格一致 | 默认并发提交全部任务，不等待上一张生成完成；各张完成后立即下载 |
| 多张图片，明确要求风格一致 | 确认样稿 → 保存统一规范 → 并发提交剩余图片 → 汇总对照检查 |
| 已提供并明确认可样稿，要求风格一致 | 直接保存统一规范，并发提交待生成图片，不另做样稿 |

- 只有用户明确表达“风格一致、统一配色、同一套视觉、系列风格统一”等意图时启用一致性流程，不因张数多或主题相关而自动启用。
- 并发提交指独立创建多个任务，不承诺一个 HTTP 请求生成所有图片。默认 `--concurrency 3` 控制同时发送请求的数量；按已知服务限额调整，遇限流报告该张结果，不自动重新提交。
- 提交池和查询下载池分离：前面的图片仍在生成时，继续提交后面的图片。此参数不限制服务端已创建任务总数；若服务端明确限制活跃任务数量，先按其限制分批调用，避免超额。
- 多张相同提示词使用 `--prompt` 与 `--count`；不同提示词使用 `--prompts-file` JSON 字符串数组，其长度必须等于 `--count`。不要启动多个互不记录状态的临时脚本代替内置批处理。
- 每张独立记录提示词、任务 ID、状态、完成 URL 和本地文件；某张失败不阻断其他任务。结果按原始顺序汇总，下载按完成顺序进行。
- 批次在输出目录生成 `batch-<唯一标识>.json`，每次状态变化立即保存。中断后使用 `--resume-batch <记录路径>` 只恢复已知任务的查询和下载；不会创建新任务，不会补交尚未提交或结果不明的图片。
- 已取得任务 ID 后禁止自动重新提交；无 ID 的超时、连接中断或响应异常标记 `submission_unconfirmed`，先核实。明确拒绝 Base64 时仍可按原有规则回退图床一次；其他错误不自动重试。
- 一致性流程的样稿确认、规范文件结构和检查清单见 [系列风格一致性流程](references/series-consistency.md)，触发此模式时必须阅读并执行。

## 环境和配置

- Python 要求 3.10+，仅使用 Python 标准库。
- API key 文件：~/.codex/skills/007ai-image-skill/007ai-image-key.json。
- 基础配置：~/.codex/skills/007ai-image-skill/.config/config.json。
- 运行时配置：~/.codex/skills/007ai-image-skill/.config/runtime.json。
- API key 缺失时，只引导用户到 https://007.007ai.cc/ 获取并通过 --set-api-key 保存。
- 分发包不包含 API key、运行时配置或已生成图片；首次使用必须由用户自行提供 key，不使用任何内置或兜底 key。
- 不输出完整 API key、原始 Base64 或完整请求 payload。

## 参考图公网 URL 流程

- 用户提供参考图时必须保留并传入生成请求；不得静默丢弃参考图，也不得在需要 URL 时改成纯文生图。
- 在 Codex 中收到图片附件后，应取得该附件的本地绝对路径并作为 `--image` 传入脚本；不能只把图片描述写进提示词。
- 图片输入能力按“007AI `base_url` + 模型 ID”判断，不能仅按模型名称推断。优先读取本机 `.config/image-host.json` 中针对接口和模型的人工覆盖，其次读取模型清单的 `image_input`、`supports_base64` 或 `requires_reference_url` 能力声明。
- 已确认支持 Base64（`image_input=base64` 或 `supports_base64=true`）时，默认优先 Base64，不上传图床；仅在用户明确要求或接口配置要求时才覆盖为 `public_url`。
- 已确认不支持 Base64（`image_input=public_url`、`supports_base64=false` 或 `requires_reference_url=true`）时，参考图必须先转换为公网 URL。已配置 imgBB 则上传本地图片或 data URL，使用返回的 `data.url` 作为 `metadata.urls`；用户已经提供公网 URL 时直接透传，不重复上传。上传有效期 24 小时，并按图片 SHA-256 缓存直链。
- 模型专用配置来自 `scripts/model-profiles.json`，按服务域名生效，与网站发现的模型列表合并，不能在刷新列表时丢失。`gptimage2.5flare_gr` 已确认只接受公网 HTTPS 地址，因此自动检查 imgBB 后上传或复用有效缓存，并将直链放入顶层 `images`。不接受 HTTP 或 Base64 强制覆盖，不得靠模型名称相似猜测接口格式。
- 如需上传却未配置 Key，在任何生图提交之前展示下方固定配置指引并停止；已配置但无效时说明“密钥无效或权限不足”，网络失败、图床响应异常、模型字段不兼容分别报错。仅本地存在 Key 不代表密钥有效。输入能力未知且尚未配置图床时，提前提醒回退不可用，可以继续首次 Base64 尝试；不向不需要图床的纯文生图任务强制要求 Key。
- 输入能力未知且模式为 `auto` 时，先自动用 Base64 提交；仅当接口明确返回 Base64/`data URL` 不受支持时，才自动上传到 imgBB 并以公网 URL 重试一次。不得把网络超时、鉴权失败、普通参数错误、任务超时或生成失败误判为 Base64 不支持；已经取得任务 ID 后也不得自动重提任务。若自动回退时缺少 imgBB Key，按下方固定文案提示用户配置，不要询问用户是否确认切换方式。
- 用户已上传参考图并确认提示词、模型、比例、张数后，立即调用生图脚本完成图生图；不得再询问用户选择 Base64 还是公网 URL，也不得在这两种方式间停下来等待确认。
- 明确要求公网 URL 但未配置 imgBB Key 时，必须在生成任务提交前逐行原样回复以下内容，不添加模型选择或其它前后说明：

  当前模型需要使用公网图片 URL，尚未配置图床。
  请先点击 [imgBB 注册或登录](https://imgbb.com/login)，然后进入 [imgBB API 页面](https://api.imgbb.com/) 添加API Key密钥。
  获取配置后，复制API密钥发送给我，我将为您保存至您本地配置里，后期无需再次配置此信息。
  温馨提示：参考图片将存储在第三方图床，请勿上传包含隐私或敏感信息的图片。

- 仅在用户显式将 `--image-input` 设为 `base64` 或 `public_url` 时尊重该单次指定；通常使用 `auto` 以启用 Base64 优先及明确拒绝后的图床自动回退。

- 用户发送 Key 后，通过 `--set-imgbb-api-key '<key>'` 保存到 skill 根目录的 `imgbb-api-key.json`，不得在回复、日志或结果 JSON 中输出完整 Key。图床缓存和模型能力覆盖仍保存在 `.config/image-host.json`。
- 配置检查：`run_007ai_image.ps1 --check-image-host`。模型能力覆盖：`--set-model-image-input <model-id> <base64|public_url|unknown> <base-url>`。单次明确指定方式可使用 `--image-input base64` 或 `--image-input public_url`；默认 `auto` 在能力未知时先试 Base64，仅对明确的 Base64 不支持错误回退图床。
- 预演模式不得上传图片或创建任务；生成异常不得自动重新创建任务，避免重复扣费。任务超时优先查询原任务状态。
- `unsupported request field: metadata` 或 `input_reference` 是接口字段不兼容，不是 Base64 拒绝；不能据此上传图床或更换模型重试。明确的 Base64 拒绝且未取得任务 ID 时才允许一次图床回退。

## 常用命令

列出全部模型：

powershell -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\.codex\skills\007ai-image-skill\scripts\run_007ai_image.ps1" --list-models --format markdown

列出某模型的比例：

powershell -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\.codex\skills\007ai-image-skill\scripts\run_007ai_image.ps1" --model <model-id> --list-options

GPT Image 异步生图：

powershell -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\.codex\skills\007ai-image-skill\scripts\run_007ai_image.ps1" --model <model-id> --ratio 16:9 --count 1 --prompt '<提示词>' --format markdown

Nano Banana 异步生图：

powershell -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\.codex\skills\007ai-image-skill\scripts\run_007ai_image.ps1" --model <model-id> --ratio 1:1 --count 1 --prompt '<提示词>' --format markdown

图生图追加：--image '<本地图片路径或 URL>'。

## 任务轮询

- 提交接口：POST /v1/videos。
- 查询接口：GET /v1/videos/{task_id}。
- 接受状态：queued、processing、in_progress、pending、completed、failed。
- GPT Image 完成结果读取 video_url。
- Nano Banana 完成结果读取 url。
- 默认每 3 秒轮询，单任务默认最多等待 30 分钟，可通过 --poll-interval 和 --wait-timeout 调整。
- 批量生成默认并发提交，逐张查询并下载，最终按请求顺序展示；不覆盖已有文件。样稿阶段只提交一张，确认后再并发提交剩余图片。
- 图片 URL 有效期有限，拿到完成 URL 后立即下载到 images 目录或用户指定的 --output-dir。

## 结果和错误

- 默认输出 JSON；使用 --format markdown 直接输出图片预览和“打开图片所在位置”的 file:/// 可点击链接，不显示裸路径。
- 生成成功后保存本地文件并打开资源管理器定位首张图片。
- 任务失败时提取 error.message 并给出简洁可操作的错误信息。
- JSON 的 `has_errors` 和逐张 `tasks` 状态决定是否有失败或未完成项；批次有未完成项时 CLI 返回退出码 2，已完成结果与任务记录仍保留。Markdown 同样列出失败项和任务记录路径，不能只展示成功图片而隐瞒失败。
- 不把单独的数字张数当成提示词。


