import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


class BatchJournal:
    def __init__(self, path, data):
        self.path = Path(path)
        self.data = data
        self.lock = threading.Lock()

    def save(self):
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    def update(self, index, **values):
        with self.lock:
            self.data["tasks"][index].update(values)
            self.save()


def summarize_batch(journal):
    tasks = journal.data["tasks"]
    return {
        **journal.data,
        "journal_file": str(journal.path),
        "task_ids": [task["task_id"] for task in tasks if task.get("task_id")],
        "files": [task["file"] for task in tasks if task.get("file")],
        "completed_tasks": [
            {"task_id": task["task_id"], "image_url": task["image_url"]}
            for task in tasks if task.get("image_url")
        ],
        "has_errors": any(task["status"] != "saved" for task in tasks),
    }


def execute_batch(output_dir, metadata, prompts, submit, finish, concurrency=3):
    if concurrency < 1:
        raise RuntimeError("并发数必须大于等于 1。")
    path = Path(output_dir) / f"batch-{uuid.uuid4().hex}.json"
    journal = BatchJournal(path, {
        **metadata,
        "schema_version": 1,
        "tasks": [
            {"index": index + 1, "prompt": prompt, "status": "pending"}
            for index, prompt in enumerate(prompts)
        ],
    })
    journal.save()

    def submit_one(index):
        journal.update(index, status="submitting")
        try:
            task_id = submit(index)
        except Exception as exc:
            journal.update(index, status="submission_unconfirmed", error=str(exc))
            return None
        journal.update(index, status="submitted", task_id=task_id)
        return task_id

    def finish_one(index, task_id):
        try:
            finish(index, task_id, lambda **values: journal.update(index, **values))
        except Exception as exc:
            journal.update(index, status="needs_attention", error=str(exc))

    with ThreadPoolExecutor(max_workers=concurrency) as watchers:
        with ThreadPoolExecutor(max_workers=concurrency) as submissions:
            futures = {submissions.submit(submit_one, index): index for index in range(len(prompts))}
            for future in as_completed(futures):
                task_id = future.result()
                if task_id:
                    watchers.submit(finish_one, futures[future], task_id)
    return summarize_batch(journal)


def resume_batch(path, finish, concurrency=3):
    if concurrency < 1:
        raise RuntimeError("并发数必须大于等于 1。")
    path = Path(path).expanduser().resolve()
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if data.get("schema_version") != 1 or not isinstance(data.get("tasks"), list):
        raise RuntimeError("无法识别批量任务记录。")
    journal = BatchJournal(path, data)

    def finish_one(index, task):
        if not task.get("task_id") or task["status"] == "saved":
            return
        try:
            finish(index, task["task_id"], lambda **values: journal.update(index, **values))
        except Exception as exc:
            journal.update(index, status="needs_attention", error=str(exc))

    with ThreadPoolExecutor(max_workers=concurrency) as workers:
        futures = [workers.submit(finish_one, index, dict(task)) for index, task in enumerate(data["tasks"])]
        for future in futures:
            future.result()
    return summarize_batch(journal)


def load_series_plan(path, model_id, ratio, image_size, count):
    plan = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if plan.get("sample_approved") is not True or not plan.get("approval_note"):
        raise RuntimeError("样稿尚未确认，不能提交系列剩余图片。请先取得用户确认或明确的自动确认授权。")
    total = plan.get("total_count")
    generated = plan.get("generated_sample_count")
    if type(total) is not int or type(generated) is not int or total < 1 or generated not in (0, 1):
        raise RuntimeError("系列规范需要 total_count 正整数及 generated_sample_count（0 或 1）。")
    if count < 1 or count > total - generated:
        raise RuntimeError("本次张数超过扣除已生成样稿后的剩余数量。")
    for field, value in (("model", model_id), ("ratio", ratio), ("image_size", image_size)):
        if plan.get(field) != value:
            raise RuntimeError(f"系列规范的 {field} 与本次参数不一致。")
    if not isinstance(plan.get("style_prompt"), str) or not plan["style_prompt"].strip():
        raise RuntimeError("系列规范需要非空 style_prompt。")
    reference = plan.get("reference_image")
    if not isinstance(reference, str) or not reference.strip() or reference.lower().startswith("data:"):
        raise RuntimeError("系列规范需要固定样稿的本地路径或公网 URL，不保存 Base64。")
    if not reference.lower().startswith(("http://", "https://")):
        reference_path = Path(reference).expanduser()
        if not reference_path.is_absolute():
            reference_path = Path(path).resolve().parent / reference_path
        reference = str(reference_path.resolve())
    return plan, reference
