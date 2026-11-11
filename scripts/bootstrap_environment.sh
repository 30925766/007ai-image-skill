#!/bin/bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
skill_root="$(dirname "$script_dir")"

if [[ "$(uname -s)" != "Darwin" ]]; then
    printf '%s\n' "此环境检测入口仅用于 macOS。" >&2
    exit 2
fi

candidates=()
if [[ -n "${CODEX_007AI_PYTHON:-}" ]]; then
    candidates+=("$CODEX_007AI_PYTHON")
fi
candidates+=("python3" "/opt/homebrew/bin/python3" "/usr/local/bin/python3" "python")

for candidate in "${candidates[@]}"; do
    if ! command -v "$candidate" >/dev/null 2>&1; then
        continue
    fi
    if python_path="$("$candidate" -c 'import sys; sys.exit(1) if sys.version_info < (3, 10) else print(sys.executable)' 2>/dev/null)"; then
        "$python_path" - "$skill_root" <<'PY'
import datetime
import json
import sys
from pathlib import Path

config_dir = Path(sys.argv[1]) / ".config"
config_dir.mkdir(parents=True, exist_ok=True)
payload = {
    "platform": sys.platform,
    "python_command": [sys.executable],
    "python_executable": sys.executable,
    "python_version": sys.version.split()[0],
    "checked_at": datetime.datetime.now().astimezone().isoformat(),
    "dependency_mode": "python-stdlib-only",
}
(config_dir / "runtime-macos.json").write_text(
    json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
)
PY
        printf '%s\n' "$python_path"
        exit 0
    fi
done

printf '%s\n' "未找到 Python 3.10+。请先安装 Python 3.10 或更高版本，再运行本入口；也可通过 CODEX_007AI_PYTHON 指定 Python 可执行文件的完整路径。" >&2
exit 2
