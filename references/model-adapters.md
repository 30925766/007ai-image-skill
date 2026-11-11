# 模型接口及参考图预检

## 已验证的 GR Flare 模型

来源：https://snskj3j8df.apifox.cn/531084030e0，核对日期 2026-11-07。
适用服务域名：007.007ai.cc。只对精确模型 ID 应用，不能推及名字相似的其他模型。

模型：`gptimage2.5flare_gr`（命令行也接受大写拼写，经不区分大小写匹配后使用服务端规范 ID）。
创建：`POST /v1/videos`；查询：`GET /v1/videos/{task_id}`。

```json
{
  "model": "gptimage2.5flare_gr",
  "prompt": "保留参考图主体，生成新的设计",
  "aspect_ratio": "9:16",
  "image_size": "4K",
  "images": ["https://example.com/reference.png"]
}
```

参考图只能使用公网 HTTPS 地址。本地图片或 Base64 先经 imgBB 转换；已有 HTTPS URL 直接透传。`image_size` 必须由用户选择，支持 1K、2K、4K。档位不保证具体像素宽高，交付前需要检查实际输出尺寸。

## 提交前检查

```powershell
.\scripts\run_007ai_image.ps1 --check-config
.\scripts\run_007ai_image.ps1 --model gptimage2.5flare_gr --image 'C:\images\reference.png' --check-reference
.\scripts\run_007ai_image.ps1 --model gptimage2.5flare_gr --ratio 9:16 --image-size 4K --count 1 --prompt '设计要求' --image 'C:\images\reference.png' --dry-run
```

这些检查不上传或创建任务。`configured: true` 仅说明本地保存了非空密钥，`key_validated: false` 明确说明未联网验证。正式上传若服务端拒绝密钥，提示更新有效 Key，不打印密钥或完整请求。

## 错误处理

- 必须上传但缺少 Key：停止提交，显示注册及 API Key 配置指引。
- 输入能力未知且无 Key：提前提醒图床回退不可用；保留首次 Base64 尝试。
- 明确不支持 Base64：无任务 ID 时允许一次图床回退。
- 普通参数错误、鉴权错误、超时：不触发图床回退。
- 已取得任务 ID：不得为同一图片自动重新提交，优先查询原任务。
