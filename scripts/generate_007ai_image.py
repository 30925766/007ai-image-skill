import argparse
import base64
import json
import mimetypes
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import urllib.parse
from pathlib import Path

from key_manager import get_api_key, get_base_url, redact_api_key, save_provider_config
from image_host import get_image_input_mode, image_host_status, prepare_reference_image, reference_preflight, save_imgbb_api_key, set_model_image_input
from batch_jobs import execute_batch, load_series_plan, resume_batch

MODELS_PATH = Path(__file__).with_name("models.json")
DEFAULT_OUTPUT_SUBDIR = Path("images")
REMOTE_MODEL_CATALOG_URL = "https://ai-assistant-price.scd666.com/api/models"
REMOTE_MODEL_TIMEOUT = 8
NANO_BANANA_RATIOS = [
    "auto",
    "1:1",
    "16:9",
    "9:16",
    "4:3",
    "3:4",
    "3:2",
    "2:3",
    "5:4",
    "4:5",
    "21:9",
    "1:4",
    "4:1",
    "1:8",
    "8:1",
]
GPT_IMAGE_RATIOS = [
    "1:1",
    "5:4",
    "9:16",
    "21:9",
    "16:9",
    "3:2",
    "4:3",
    "4:5",
    "3:4",
    "2:3",
]
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
WINDOWS_RESERVED_FILENAMES = {
    "CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "COM5",
    "COM6", "COM7", "COM8", "COM9", "LPT1", "LPT2", "LPT3", "LPT4",
    "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}


def load_models() -> dict[str, dict]:
    raw = json.loads(MODELS_PATH.read_text(encoding="utf-8"))
    return {model["id"]: model for model in raw.get("models") or []}


def model_from_remote_name(name: object) -> dict | None:
    if not isinstance(name, str):
        return None
    model_id = name.strip()
    if not model_id:
        return None
    lowered = model_id.lower()
    if "banana" in lowered:
        family = "nano-banana"
        ratios = NANO_BANANA_RATIOS
    elif "gpt" in lowered or "image" in lowered:
        family = "gpt-image-2"
        ratios = GPT_IMAGE_RATIOS
    else:
        return None
    return {
        "id": model_id,
        "display_name": model_id,
        "family": family,
        "transport": "video-async",
        "api_model": model_id,
        "size_mode": "ratio",
        "allowed_ratios": list(ratios),
    }


def sync_remote_models(local_models: dict[str, dict]) -> dict[str, dict]:
    request = urllib.request.Request(
        REMOTE_MODEL_CATALOG_URL,
        headers={
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=REMOTE_MODEL_TIMEOUT) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
        category = payload.get("图片异步")
        raw_models = category.get("models") if isinstance(category, dict) else category
        if not isinstance(raw_models, list):
            raise ValueError("图片异步分类格式无效")
        synced = {}
        for item in raw_models:
            name = item.get("name") if isinstance(item, dict) else item
            model = model_from_remote_name(name)
            if model:
                synced[model["id"]] = model
        if not synced:
            raise ValueError("图片异步分类为空")
        return synced
    except (OSError, ValueError, TypeError, json.JSONDecodeError, urllib.error.URLError):
        return local_models


def load_runtime_models() -> dict[str, dict]:
    local_models = load_models()
    models = sync_remote_models(local_models)
    profiles = json.loads(Path(__file__).with_name("model-profiles.json").read_text(encoding="utf-8"))
    provider_host = urllib.parse.urlsplit(get_base_url() or "").hostname
    for model_id, profile in profiles.items():
        if provider_host not in profile["provider_hosts"]:
            continue
        model = models.get(model_id) or model_from_remote_name(model_id)
        models[model_id] = {**model, **profile}
    return models


def api_root_v1(base_url: str) -> str:
    root = base_url.rstrip("/")
    return root if root.endswith("/v1") else root + "/v1"


def build_task_endpoint(base_url: str, task_id: str | None = None) -> str:
    endpoint = api_root_v1(base_url) + "/videos"
    return f"{endpoint}/{task_id}" if task_id else endpoint


def output_dir_from_arg(output_dir: str | None) -> Path:
    if output_dir:
        path = Path(output_dir).expanduser()
    else:
        path = Path(__file__).resolve().parent.parent / DEFAULT_OUTPUT_SUBDIR
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def request_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json, text/event-stream",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
    }


def parse_json_or_sse(raw_text: str) -> dict:
    text = raw_text.strip()
    if not text:
        raise RuntimeError("接口返回为空响应。")
    if text.startswith("data:") or "\ndata:" in text:
        events = []
        for line in text.splitlines():
            line = line.strip()
            if not line.startswith("data:"):
                continue
            value = line[5:].strip()
            if not value or value == "[DONE]":
                continue
            try:
                events.append(json.loads(value))
            except json.JSONDecodeError:
                events.append({"text": value})
        if not events:
            raise RuntimeError(f"SSE 响应中没有可解析数据: {text[:500]}")
        return events[0] if len(events) == 1 else {"events": events}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"接口返回不是 JSON/SSE: {text[:500]}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"接口返回不是 JSON 对象: {text[:500]}")
    return payload


def request_json(url: str, api_key: str, method: str, payload: dict | None = None) -> dict:
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = request_headers(api_key)
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            return parse_json_or_sse(response.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {raw}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"请求失败: {exc}") from exc


def download_file(url: str, referer: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": referer,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"下载图片失败：HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"下载图片失败: {exc}") from exc


def normalize_image_source(value: str) -> str:
    lower = value.lower()
    if lower.startswith(("http://", "https://", "data:")):
        return value
    path = Path(value).expanduser().resolve()
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"未找到参考图: {path}")
    if path.suffix.lower() not in ALLOWED_IMAGE_EXTENSIONS:
        raise RuntimeError("参考图只支持 PNG、JPG、JPEG 或 WEBP 格式。")
    mime_type = mimetypes.guess_type(str(path))[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def detect_image_suffix(content: bytes) -> str:
    if content.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if content.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return ".webp"
    return ".png"


def unique_file_path(output_dir: Path, stem: str, suffix: str) -> Path:
    candidate = output_dir / f"{stem}{suffix}"
    counter = 2
    while candidate.exists():
        candidate = output_dir / f"{stem}-{counter}{suffix}"
        counter += 1
    return candidate


def save_image_content(content: bytes, output_dir: Path, stem: str) -> Path:
    path = unique_file_path(output_dir, stem, detect_image_suffix(content))
    path.write_bytes(content)
    return path


def sanitize_filename_stem(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "-", value).strip(" .-")
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"-{2,}", "-", cleaned)
    if not cleaned:
        return None
    if cleaned.upper() in WINDOWS_RESERVED_FILENAMES:
        cleaned += "-image"
    return cleaned


def build_output_stem(output_name: str | None, model_id: str, timestamp: str, index: int, count: int) -> str:
    safe_name = sanitize_filename_stem(output_name)
    if safe_name:
        return safe_name if count == 1 else f"{safe_name}-{index + 1}"
    safe_model = re.sub(r"[^A-Za-z0-9._-]+", "-", model_id).strip("-") or "image"
    return f"{safe_model}-async-{timestamp}-{index + 1}"


def extract_error(payload: object) -> str | None:
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, str) and error:
            return error
        if isinstance(error, dict) and isinstance(error.get("message"), str):
            return error["message"]
        for child in payload.values():
            found = extract_error(child)
            if found:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = extract_error(item)
            if found:
                return found
    return None


def extract_result_url(payload: object) -> str | None:
    if isinstance(payload, dict):
        for key in ("url", "video_url", "image_url"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
        for child in payload.values():
            found = extract_result_url(child)
            if found:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = extract_result_url(item)
            if found:
                return found
    return None


def validate_model(model_id: str | None, models: dict[str, dict]) -> dict:
    if not model_id:
        raise RuntimeError("请先选择异步生图模型。")
    model = models.get(model_id) or models.get(model_id.lower())
    if not model:
        raise RuntimeError(f"不支持的模型: {model_id}。可用模型: {', '.join(sorted(models))}")
    return model


def validate_ratio(model: dict, ratio: str | None) -> str:
    allowed = model.get("allowed_ratios") or []
    if not ratio:
        raise RuntimeError(f"请先选择画面比例。可用比例: {'、'.join(allowed)}")
    if ratio not in allowed:
        raise RuntimeError(f"模型 {model['id']} 不支持比例 {ratio}。可用比例: {'、'.join(allowed)}")
    return ratio


def validate_count(count: int | None) -> int:
    if count is None or count < 1:
        raise RuntimeError("生成张数必须是大于等于 1 的整数。")
    return count


def validate_image_size(model: dict, image_size: str | None) -> str | None:
    allowed = model.get("allowed_image_sizes")
    if allowed and image_size not in allowed:
        raise RuntimeError(f"模型 {model['id']} 需要明确指定 --image-size，可用值: {'、'.join(allowed)}")
    if image_size and not allowed:
        raise RuntimeError(f"模型 {model['id']} 未声明独立尺寸参数，请使用模型 ID 中的尺寸档位。")
    return image_size


def build_async_payload(model: dict, prompt: str, ratio: str, image: str | None, image_source: str | None = None, image_size: str | None = None, output_format: str | None = None) -> dict:
    validate_image_size(model, image_size)
    if model.get("request_schema") == "gr-flat":
        payload = {"model": model["api_model"], "prompt": prompt, "aspect_ratio": ratio, "image_size": image_size}
        if output_format:
            payload["output_format"] = output_format
        if image:
            source = image_source or image
            if not source.startswith("https://"):
                raise RuntimeError("当前模型的参考图必须是公网 HTTPS URL，请先使用图床转换。")
            payload["images"] = [source]
        return payload
    metadata = {"urls": [image_source or normalize_image_source(image)] if image else []}
    if model["family"] == "gpt-image-2":
        metadata["aspect_ratio"] = ratio
    else:
        metadata["aspectRatio"] = ratio
    return {"model": model["api_model"], "prompt": prompt, "metadata": metadata}


def is_base64_unsupported_error(message: str) -> bool:
    lowered = message.lower().replace(" ", "")
    if "unsupportedrequestfield" in lowered or "unknownfield" in lowered:
        return False
    image_input_markers = (
        "base64", "dataurl", "data:image", "inlineimage", "inline_data",
        "imageinput", "inputimage", "referenceimage", "imagetoimage",
        "参考图", "图生图", "图片输入", "图像输入",
    )
    unsupported_markers = (
        "notsupported", "unsupported", "doesnotsupport", "doesn'tsupport",
        "不支持", "不接受", "无法处理",
    )
    return any(marker in lowered for marker in image_input_markers) and any(
        marker in lowered for marker in unsupported_markers
    )


def wait_for_task(api_key: str, base_url: str, task_id: str, poll_interval: float, timeout: float) -> dict:
    deadline = time.monotonic() + timeout
    last_payload: dict = {}
    while time.monotonic() <= deadline:
        last_payload = request_json(build_task_endpoint(base_url, task_id), api_key, "GET")
        status = str(last_payload.get("status") or "").lower()
        if status == "completed":
            if not extract_result_url(last_payload):
                raise RuntimeError("任务已完成，但响应中没有图片 URL。")
            return last_payload
        if status == "failed":
            raise RuntimeError(extract_error(last_payload) or "异步生图任务失败。")
        if status not in {"queued", "processing", "in_progress", "pending"}:
            raise RuntimeError(f"异步任务返回未知状态: {status}")
        time.sleep(max(0.1, poll_interval))
    raise RuntimeError(f"异步任务 {task_id} 等待超过 {timeout:g} 秒。")


def generate_async(api_key: str, base_url: str, model: dict, prompt: str, image: str | None, ratio: str, count: int, output_dir: Path, output_name: str | None, poll_interval: float, wait_timeout: float, dry_run: bool, image_input: str = "auto", image_size: str | None = None, output_format: str | None = None, concurrency: int = 3, prompts: list[str] | None = None, series_plan: dict | None = None) -> dict:
    endpoint = build_task_endpoint(base_url)
    validate_count(count)
    if concurrency < 1:
        raise RuntimeError("并发数必须大于等于 1。")
    prompts = prompts if prompts is not None else [prompt] * count
    if len(prompts) != count or any(not isinstance(item, str) or not item.strip() for item in prompts):
        raise RuntimeError("逐张提示词数量必须与 --count 一致，且每条提示词不能为空。")
    if series_plan:
        prompts = [series_plan["style_prompt"] + "\n\n本张内容：\n" + item for item in prompts]
    validate_image_size(model, image_size)
    preflight = reference_preflight(image, model, base_url, image_input)
    if preflight.get("warning"):
        sys.stderr.write("参考图能力尚未确认；当前先尝试 Base64，公网地址回退暂不可用。\n"
                         "如需图床，请到 https://imgbb.com/login 注册，并在 https://api.imgbb.com/ 获取 API Key 后配置。\n")
    prepared_image = None
    image_meta = {}
    auto_image_fallback = False
    if image:
        mode = get_image_input_mode(model, base_url, image_input)
        if mode == "unknown" and image_input == "auto":
            mode = "base64"
        auto_image_fallback = image_input == "auto" and mode == "base64"
        prepared_image, image_meta = prepare_reference_image(image, mode, dry_run=dry_run, model_id=model["id"])
    payload = build_async_payload(model, prompts[0], ratio, image, prepared_image, image_size, output_format)
    result = {
        "api_key": redact_api_key(api_key),
        "endpoint": endpoint,
        "transport": "video-async",
        "model": model["id"],
        "api_model": model["api_model"],
        "mode": "image-to-image" if image else "text-to-image",
        "prompts": prompts,
        "ratio": ratio,
        "count": count,
        "output_dir": str(output_dir),
        "poll_interval": poll_interval,
        "wait_timeout": wait_timeout,
        "reference_preflight": preflight,
        "image_size": image_size,
        "output_format": output_format,
        "concurrency": concurrency,
        "execution": "concurrent-submission",
        "series_plan": series_plan,
    }
    if image:
        result["image_source"] = "<prepared-reference>"
        result["image_input"] = image_meta
    if output_name:
        result["output_name"] = output_name
    if dry_run:
        result["dry_run"] = True
        result["payload"] = payload
        if image:
            if model.get("request_schema") == "gr-flat":
                result["payload"]["images"] = ["https://imgbb.example.invalid/reference/<dry-run>"]
            else:
                result["payload"]["metadata"]["urls"] = ["<reference-redacted>"]
        return result

    timestamp = time.strftime("%Y%m%d-%H%M%S")
    result["timestamp"] = timestamp
    result["output_name"] = output_name
    result["dry_run"] = False
    fallback_lock = threading.Lock()

    def submit_one(index):
        nonlocal prepared_image, auto_image_fallback, image_meta
        with fallback_lock:
            source = prepared_image
        for attempt in range(2):
            task_payload = build_async_payload(model, prompts[index], ratio, image, source, image_size, output_format)
            try:
                submitted = request_json(endpoint, api_key, "POST", task_payload)
                task_id = submitted.get("id") or submitted.get("task_id")
                if isinstance(task_id, str) and task_id:
                    return task_id
                raise RuntimeError(extract_error(submitted) or "接口未返回任务 ID；提交结果待核实，不会自动重提。")
            except RuntimeError as exc:
                if attempt or not is_base64_unsupported_error(str(exc)):
                    raise
                with fallback_lock:
                    if source == prepared_image:
                        if not auto_image_fallback:
                            raise
                        prepared_image, image_meta = prepare_reference_image(
                            image, "public_url", dry_run=False, model_id=model["id"]
                        )
                        auto_image_fallback = False
                    source = prepared_image
        raise RuntimeError("参考图回退提交失败。")

    def finish_one(index, task_id, update):
        completed = wait_for_task(api_key, base_url, task_id, poll_interval, wait_timeout)
        result_url = extract_result_url(completed)
        update(status="completed", image_url=result_url)
        stem = build_output_stem(output_name, model["id"], timestamp, index, count)
        content = download_file(result_url, api_root_v1(base_url) + "/")
        file_path = str(save_image_content(content, output_dir, stem))
        update(status="saved", file=file_path, error=None)

    return execute_batch(output_dir, result, prompts, submit_one, finish_one, concurrency)


def resume_generation(path, api_key, base_url, concurrency):
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if data.get("endpoint") != build_task_endpoint(base_url):
        raise RuntimeError("任务记录接口与当前配置不一致，停止查询。")
    output_dir = output_dir_from_arg(data["output_dir"])

    def finish_one(index, task_id, update):
        task = data["tasks"][index]
        result_url = task.get("image_url")
        if not result_url:
            completed = wait_for_task(api_key, base_url, task_id, data["poll_interval"], data["wait_timeout"])
            result_url = extract_result_url(completed)
            update(status="completed", image_url=result_url)
        stem = build_output_stem(data.get("output_name"), data["model"], data["timestamp"], index, data["count"])
        content = download_file(result_url, api_root_v1(base_url) + "/")
        update(status="saved", file=str(save_image_content(content, output_dir, stem)), error=None)

    return resume_batch(path, finish_one, concurrency)


def summarize_model(model: dict) -> dict:
    ratios = model.get("allowed_ratios") or []
    return {
        "id": model["id"],
        "display_name": model["display_name"],
        "family": model["family"],
        "transport": model["transport"],
        "supports_text_to_image": True,
        "supports_image_to_image": True,
        "size_mode": "ratio",
        "allowed_ratios": ratios,
        "display_options": [{"category": "画面比例", "display": ratio, "value": ratio} for ratio in ratios],
        "request_schema": model.get("request_schema", "metadata"),
        "image_input": model.get("image_input", "unknown"),
        "allowed_image_sizes": model.get("allowed_image_sizes", []),
    }


def list_models(models: dict[str, dict]) -> dict:
    return {"models": [summarize_model(model) for model in sorted(models.values(), key=lambda item: item["id"])]}


def check_remote_models(api_key: str, base_url: str, models: dict[str, dict]) -> dict:
    payload = request_json(api_root_v1(base_url) + "/models", api_key, "GET")
    remote_ids = {item.get("id") for item in payload.get("data", []) if isinstance(item, dict) and item.get("id")}
    configured_ids = set(models)
    return {
        "ok": bool(remote_ids) and configured_ids.issubset(remote_ids),
        "configured_count": len(configured_ids),
        "remote_count": len(remote_ids),
        "missing_on_server": sorted(configured_ids - remote_ids),
    }


def render_model_choices(models: dict[str, dict]) -> str:
    groups = {}
    for model in sorted(models.values(), key=lambda item: item["id"]):
        model_id = model["id"]
        if model["family"] == "nano-banana":
            group = "Nano Banana 系列"
        elif "2.5" in model_id:
            group = "GPT Image 2.5 系列"
        elif model["family"] == "gpt-image-2":
            group = "GPT Image 2 系列"
        else:
            group = "其他模型"
        groups.setdefault(group, []).append(model_id)
    lines = ["请选择图片生成模型，已按系列分类：", ""]
    for group in ("GPT Image 2.5 系列", "GPT Image 2 系列", "Nano Banana 系列", "其他模型"):
        if group not in groups:
            continue
        lines.extend([f"**{group}**", ""])
        lines.extend(f"- `{model_id}`" for model_id in groups[group])
        lines.append("")
    lines.append("请回复完整模型名称，选好后再选择画面比例。")
    return "\n".join(lines) + "\n"


def render_markdown_result(result: dict) -> str:
    files = result.get("files") or []
    lines = [f"\u5df2\u751f\u6210 {len(files)} \u5f20\u56fe\u7247", ""]
    for file_path in files:
        absolute = Path(file_path).resolve()
        folder_uri = absolute.parent.as_uri()
        lines.extend([
            f"![]({absolute.as_posix()})",
            "",
            f"[\u6253\u5f00\u56fe\u7247\u6240\u5728\u4f4d\u7f6e]({folder_uri})",
            "",
        ])
    for task in result.get("tasks", []):
        if task["status"] != "saved":
            lines.append(f"- 第 {task['index']} 张：{task['status']}；任务编号：{task.get('task_id', '尚未确认')}；{task.get('error') or '请核对任务记录'}")
    if result.get("journal_file"):
        lines.extend(["", f"任务记录：{result['journal_file']}"])
    return "\n".join(lines).rstrip() + "\n"


def open_folder_for_file(file_path: str) -> None:
    target = Path(file_path).resolve()
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(target)])
        else:
            subprocess.Popen(["explorer", "/select,", str(target)])
    except Exception:
        pass


def print_error_and_exit(message: str) -> None:
    if message.startswith("当前模型需要使用公网图片 URL，尚未配置图床。"):
        sys.stderr.write(f"{message}\n")
    else:
        sys.stderr.write(f"错误：{message}\n")
    raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="通过 007AI 异步图片任务生成图片。")
    parser.add_argument("--model", help="异步生图模型 ID")
    parser.add_argument("--prompt", help="提示词")
    parser.add_argument("--prompts-file", help="JSON 字符串数组，每张图片一条提示词，数量须与 --count 一致")
    parser.add_argument("--series-plan", help="用户已确认的系列样稿与统一规范 JSON")
    parser.add_argument("--concurrency", type=int, default=3, help="同时提交请求数和查询工作线程数，默认 3；不限制已创建任务总数")
    parser.add_argument("--resume-batch", help="恢复任务记录中的查询和下载，绝不创建新任务")
    parser.add_argument("--ratio", help="画面比例")
    parser.add_argument("--size", help="兼容旧参数；异步模型使用 --ratio")
    parser.add_argument("--image-tier", help="兼容旧参数；档位已包含在异步模型 ID 中")
    parser.add_argument("--count", type=int, help="生成张数")
    parser.add_argument("--name", help="输出文件名，不含扩展名")
    parser.add_argument("--output-dir", help="图片保存目录")
    parser.add_argument("--image", help="参考图路径、URL 或 data URL")
    parser.add_argument("--image-input", choices=["auto", "base64", "public_url"], default="auto", help="参考图输入方式")
    parser.add_argument("--image-size", choices=["1K", "2K", "4K"], help="仅支持独立尺寸的模型使用，必须明确选择")
    parser.add_argument("--output-format", choices=["png", "gif", "svg"], help="输出格式；2.6 系列支持 GIF，gptimage2.6_gr 还支持 SVG")
    parser.add_argument("--check-reference", action="store_true", help="检查参考图输入方式和图床配置，不上传或创建任务")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--poll-interval", type=float, default=3.0)
    parser.add_argument("--wait-timeout", type=float, default=1800.0)
    parser.add_argument("--list-models", action="store_true")
    parser.add_argument("--list-options", action="store_true")
    parser.add_argument("--check-config", action="store_true")
    parser.add_argument("--check-models", action="store_true", help="非计费地检查配置的模型是否存在于服务端")
    parser.add_argument("--set-api-key")
    parser.add_argument("--set-base-url")
    parser.add_argument("--set-imgbb-api-key", help="保存 imgBB 图片上传 API Key")
    parser.add_argument("--check-image-host", action="store_true")
    parser.add_argument("--set-model-image-input", nargs=3, metavar=("MODEL_ID", "MODE", "BASE_URL"), help="设置模型图片输入能力")
    args = parser.parse_args()

    if args.set_imgbb_api_key:
        save_imgbb_api_key(args.set_imgbb_api_key)
        sys.stderr.write("imgBB API Key 已保存到本机配置\n")
        return
    if args.check_image_host:
        print(json.dumps(image_host_status(), ensure_ascii=False, indent=2))
        return
    if args.set_model_image_input:
        model_id, mode, base_url = args.set_model_image_input
        set_model_image_input(base_url, model_id, mode)
        sys.stderr.write("模型图片输入能力已保存到本机配置\n")
        return

    models = load_runtime_models()

    if args.list_models:
        if args.format == "markdown":
            sys.stdout.write(render_model_choices(models))
        else:
            print(json.dumps(list_models(models), ensure_ascii=False, indent=2))
        return
    if args.list_options:
        print(json.dumps(summarize_model(validate_model(args.model, models)), ensure_ascii=False, indent=2))
        return
    if args.set_api_key:
        save_provider_config(args.set_api_key, get_base_url() or "https://007.007ai.cc")
        sys.stderr.write("007AI API key 已保存\n")
        return
    if args.set_base_url:
        save_provider_config(get_api_key() or "", args.set_base_url)
        sys.stderr.write("base_url 已保存\n")
        return
    if args.check_config:
        api_key = get_api_key()
        base_url = get_base_url()
        print(json.dumps({"ok": bool(api_key and base_url), "has_api_key": bool(api_key), "has_base_url": bool(base_url), "base_url": base_url, "image_host": image_host_status()}, ensure_ascii=False, indent=2))
        return

    if args.check_models:
        api_key = get_api_key()
        base_url = get_base_url()
        if not api_key or not base_url:
            print_error_and_exit("请先配置 007AI API key 和 base_url。")
        print(json.dumps(check_remote_models(api_key, base_url, models), ensure_ascii=False, indent=2))
        return

    api_key = get_api_key()
    base_url = get_base_url()
    if not api_key or not base_url:
        print_error_and_exit("请先配置 007AI API key 和 base_url。")
    if args.resume_batch:
        if args.dry_run:
            raise RuntimeError("--resume-batch 不支持 --dry-run；请直接读取任务记录检查状态。")
        result = resume_generation(args.resume_batch, api_key, base_url, args.concurrency)
        if args.format == "markdown":
            sys.stdout.write(render_markdown_result(result))
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        if result.get("has_errors"):
            raise SystemExit(2)
        return
    model = validate_model(args.model, models)
    if args.check_reference:
        if not args.image:
            raise RuntimeError("请提供 --image 以检查参考图配置。")
        print(json.dumps(reference_preflight(args.image, model, base_url, args.image_input), ensure_ascii=False, indent=2))
        return
    if model["transport"] != "video-async":
        raise RuntimeError(f"模型 {model['id']} 不是异步图片模型。")
    if bool(args.prompt) == bool(args.prompts_file):
        raise RuntimeError("--prompt 与 --prompts-file 必须且只能提供一个。")
    ratio = validate_ratio(model, args.ratio)
    count = validate_count(args.count)
    prompts = None
    if args.prompts_file:
        prompts = json.loads(Path(args.prompts_file).read_text(encoding="utf-8-sig"))
        if not isinstance(prompts, list):
            raise RuntimeError("--prompts-file 必须是 JSON 字符串数组。")
    series_plan = None
    image = args.image
    if args.series_plan:
        series_plan, reference = load_series_plan(args.series_plan, model["id"], ratio, args.image_size, count)
        if image and image != reference:
            raise RuntimeError("--image 与已确认系列样稿不一致，请先合并并确认参考素材。")
        image = reference
    result = generate_async(api_key, base_url, model, args.prompt, image, ratio, count, output_dir_from_arg(args.output_dir), args.name, args.poll_interval, args.wait_timeout, args.dry_run, args.image_input, args.image_size, args.output_format, args.concurrency, prompts, series_plan)
    if args.format == "markdown" and not args.dry_run:
        sys.stdout.write(render_markdown_result(result))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    if not args.dry_run and result.get("files"):
        open_folder_for_file(result["files"][0])
    if result.get("has_errors"):
        raise SystemExit(2)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, FileNotFoundError, json.JSONDecodeError, urllib.error.URLError) as exc:
        print_error_and_exit(str(exc))


