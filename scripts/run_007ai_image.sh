#!/bin/bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python_path="$(/bin/bash "$script_dir/bootstrap_environment.sh")"
exec "$python_path" "$script_dir/generate_007ai_image.py" "$@"
