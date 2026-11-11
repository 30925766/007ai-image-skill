"""Local image-host configuration and imgBB upload helpers."""
import base64, hashlib, json, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path
from key_manager import get_skill_config_dir, get_skill_dir, redact_api_key
IMAGE_HOST_CONFIG_PATH = get_skill_config_dir() / "image-host.json"
IMGBB_KEY_PATH = get_skill_dir() / "imgbb-api-key.json"
IMGBB_UPLOAD_URL = "https://api.imgbb.com/1/upload"
IMGBB_MAX_BYTES = 32 * 1024 * 1024
IMGBB_EXPIRATION_SECONDS = 24 * 60 * 60
MISSING_IMAGE_HOST_MESSAGE = ("当前模型需要使用公网图片 URL，尚未配置图床。\n" "请先点击 [imgBB 注册或登录](https://imgbb.com/login)，然后进入 [imgBB API 页面](https://api.imgbb.com/) 添加API Key密钥。\n" "获取配置后，复制API密钥发送给我，我将为您保存至您本地配置里，后期无需再次配置此信息。\n" "温馨提示：参考图片将存储在第三方图床，请勿上传包含隐私或敏感信息的图片。")
UNKNOWN_IMAGE_INPUT_MESSAGE = ("模型 {model_id} 的参考图输入方式尚未确认，已停止提交以避免静默丢失图片或重复扣费。\n"
    "如果该接口明确要求公网图片 URL，请先配置 imgBB API Key；如果确认支持 Base64，可使用 --image-input base64 明确指定。")

def load_image_host_config():
    if not IMAGE_HOST_CONFIG_PATH.exists(): return {}
    try: value=json.loads(IMAGE_HOST_CONFIG_PATH.read_text(encoding="utf-8-sig"))
    except (OSError,json.JSONDecodeError): return {}
    if not isinstance(value,dict): return {}
    value.pop("imgbb_api_key",None)
    return value

def _read_imgbb_api_key():
    if not IMGBB_KEY_PATH.exists(): return None
    try: value=json.loads(IMGBB_KEY_PATH.read_text(encoding="utf-8-sig"))
    except (OSError,json.JSONDecodeError): return None
    key=value.get("api_key") if isinstance(value,dict) else None
    return key if isinstance(key,str) and key.strip() else None

def _write_imgbb_api_key(api_key):
    IMGBB_KEY_PATH.write_text(json.dumps({"api_key":api_key},ensure_ascii=False,indent=2),encoding="utf-8")

def save_imgbb_api_key(api_key):
    key=api_key.strip()
    if not key: raise RuntimeError("imgBB API Key 不能为空。")
    _write_imgbb_api_key(key)
    if IMAGE_HOST_CONFIG_PATH.exists():
        try: config=json.loads(IMAGE_HOST_CONFIG_PATH.read_text(encoding="utf-8-sig"))
        except (OSError,json.JSONDecodeError): config={}
        if isinstance(config,dict) and "imgbb_api_key" in config:
            config.pop("imgbb_api_key",None)
            IMAGE_HOST_CONFIG_PATH.write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding="utf-8")

def image_host_status():
    load_image_host_config()
    key=_read_imgbb_api_key()
    return {"configured":bool(key),"provider":"imgbb","key_validated":False,"config_file":str(IMGBB_KEY_PATH)}

def set_model_image_input(base_url,model_id,mode):
    if mode not in {"unknown","base64","public_url"}: raise RuntimeError("图片输入方式必须是 unknown、base64 或 public_url。")
    config=load_image_host_config(); provider=config.setdefault("capabilities",{}).setdefault(base_url.rstrip("/"),{}); provider[model_id]=mode
    IMAGE_HOST_CONFIG_PATH.parent.mkdir(parents=True,exist_ok=True); IMAGE_HOST_CONFIG_PATH.write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding="utf-8")

def get_image_input_mode(model,base_url,requested):
    if requested not in {"auto","base64","public_url"}: raise RuntimeError("--image-input 必须是 auto、base64 或 public_url。")
    if model.get("https_reference_only"):
        if requested == "base64": raise RuntimeError("当前模型仅接受公网 HTTPS 参考图，不能使用 Base64。")
        return "public_url"
    if requested != "auto": return requested
    configured=(load_image_host_config().get("capabilities") or {}).get(base_url.rstrip("/"),{}).get(model.get("id"))
    if configured in {"base64","public_url"}: return configured
    declared=model.get("image_input")
    if declared in {"base64","public_url"}: return declared
    if model.get("supports_base64") is True: return "base64"
    if model.get("supports_base64") is False or model.get("requires_reference_url") is True: return "public_url"
    return "unknown"

def reference_preflight(value,model,base_url,requested="auto"):
    status=image_host_status()
    if not value:
        return {"has_reference":False,"image_host":status,"upload_required":False}
    mode=get_image_input_mode(model,base_url,requested)
    lower=value.lower()
    public=lower.startswith(("http://","https://"))
    if public and model.get("https_reference_only") and not lower.startswith("https://"):
        raise RuntimeError("当前模型仅接受公网 HTTPS 参考图，不接受 HTTP 地址。")
    if not public:
        content,_filename=_read_image(value)
        if len(content)>IMGBB_MAX_BYTES and mode=="public_url":
            raise RuntimeError("参考图超过 imgBB 32 MB 限制。")
    needs_upload=mode=="public_url" and not public
    if needs_upload and not status["configured"]: raise RuntimeError(MISSING_IMAGE_HOST_MESSAGE)
    return {"has_reference":True,"input_mode":mode,"upload_required":needs_upload,
            "image_host":status,"fallback_available":status["configured"],
            "warning":MISSING_IMAGE_HOST_MESSAGE if mode=="unknown" and not status["configured"] else None,
            "note":"仅检查本地配置，未验证密钥或公网地址可用性。"}

def _read_image(value):
    if value.lower().startswith("data:"):
        header,encoded=value.split(",",1)
        if ";base64" not in header.lower(): raise RuntimeError("参考图 data URL 必须使用 Base64 格式。")
        try: return base64.b64decode(encoded,validate=True),"reference"
        except (ValueError,base64.binascii.Error) as exc: raise RuntimeError("参考图 data URL 无法解析。") from exc
    path=Path(value).expanduser().resolve()
    if not path.exists() or not path.is_file(): raise FileNotFoundError(f"未找到参考图: {path}")
    if path.suffix.lower() not in {".png",".jpg",".jpeg",".webp"}: raise RuntimeError("参考图只支持 PNG、JPG、JPEG 或 WEBP 格式。")
    return path.read_bytes(),path.name

def _upload_to_imgbb(api_key,content,filename):
    if len(content)>IMGBB_MAX_BYTES: raise RuntimeError("参考图超过 imgBB 32 MB 限制。")
    body=urllib.parse.urlencode({"key":api_key,"image":base64.b64encode(content).decode("ascii"),"name":Path(filename).stem[:80] or "reference","expiration":str(IMGBB_EXPIRATION_SECONDS)}).encode("ascii")
    req=urllib.request.Request(IMGBB_UPLOAD_URL,data=body,method="POST",headers={"Content-Type":"application/x-www-form-urlencoded","Accept":"application/json"})
    try:
        with urllib.request.urlopen(req,timeout=60) as response: payload=json.loads(response.read().decode("utf-8",errors="replace"))
    except urllib.error.HTTPError as exc:
        try: detail=json.loads(exc.read().decode("utf-8",errors="replace"))
        except (ValueError,OSError): detail={}
        message=str((detail.get("error") or {}).get("message","")).lower()
        if exc.code in (401,403) or "api" in message and "key" in message:
            raise RuntimeError("imgBB API Key 无效或权限不足，请重新配置有效密钥。") from exc
        raise RuntimeError(f"imgBB 上传被拒绝：HTTP {exc.code}。请检查图片限制或稍后重试；未提交生图任务。") from exc
    except (urllib.error.URLError,TimeoutError) as exc: raise RuntimeError("imgBB 网络连接失败或超时；未提交生图任务，请稍后重试。") from exc
    except json.JSONDecodeError as exc: raise RuntimeError("imgBB 返回格式异常；未提交生图任务。") from exc
    url=((payload.get("data") or {}).get("url") if isinstance(payload,dict) else None)
    if isinstance(payload,dict) and not payload.get("success"):
        detail=payload.get("error") or {}
        message=str(detail.get("message","")).lower() if isinstance(detail,dict) else ""
        if "api" in message and "key" in message:
            raise RuntimeError("imgBB API Key 无效或权限不足，请重新配置有效密钥。")
        raise RuntimeError("imgBB 上传失败；未提交生图任务，请检查图床服务状态。")
    if not isinstance(payload,dict) or not payload.get("success") or not isinstance(url,str) or not url.startswith("https://"): raise RuntimeError("imgBB 上传失败：接口未返回有效 HTTPS 图片直链。")
    return url

def prepare_reference_image(value,mode,dry_run=False,model_id=None):
    lower=value.lower()
    if mode == "unknown":
        raise RuntimeError(UNKNOWN_IMAGE_INPUT_MESSAGE.format(model_id=model_id or "当前模型"))
    if mode != "public_url": return value,{"input_mode":"base64" if not lower.startswith(("http://","https://","data:")) else "passthrough"}
    if lower.startswith(("http://","https://")): return value,{"input_mode":"public_url","uploaded":False}
    config=load_image_host_config(); api_key=_read_imgbb_api_key()
    if not isinstance(api_key,str) or not api_key.strip(): raise RuntimeError(MISSING_IMAGE_HOST_MESSAGE)
    content,filename=_read_image(value); cache=config.setdefault("cache",{}); cache_key=hashlib.sha256(content).hexdigest(); cached=cache.get(cache_key)
    if isinstance(cached,dict) and str(cached.get("url","")).startswith("https://") and float(cached.get("expires_at",0)) > time.time()+60: return cached["url"],{"input_mode":"public_url","uploaded":False,"cached":True}
    if dry_run: return "https://imgbb.example.invalid/reference/<dry-run>",{"input_mode":"public_url","uploaded":False,"dry_run":True}
    url=_upload_to_imgbb(api_key,content,filename); cache[cache_key]={"url":url,"expires_at":time.time()+IMGBB_EXPIRATION_SECONDS}; IMAGE_HOST_CONFIG_PATH.write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding="utf-8")
    return url,{"input_mode":"public_url","uploaded":True,"cached":False}
