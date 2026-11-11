import json
from pathlib import Path


def get_skill_dir() -> Path:
    """?? skill ???"""
    script_dir = Path(__file__).resolve().parent
    return script_dir.parent


def get_skill_config_dir() -> Path:
    """?? skill ????????"""
    config_dir = get_skill_dir() / ".config"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_config_file_path() -> Path:
    """?????????????? base_url ?? key ??"""
    return get_skill_config_dir() / "config.json"


def get_key_file_path() -> Path:
    """?? 007AI key ????"""
    return get_skill_dir() / "007ai-image-key.json"


def load_json_file(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return {}


def save_json_file(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_config() -> dict:
    """????????"""
    return load_json_file(get_config_file_path())


def save_config(config: dict) -> None:
    """????????"""
    safe_config = dict(config)
    safe_config.pop("api_key", None)
    save_json_file(get_config_file_path(), safe_config)


def load_key_config() -> dict:
    """?? 007AI key ??"""
    return load_json_file(get_key_file_path())


def save_key_config(config: dict) -> None:
    """?? 007AI key ??"""
    save_json_file(get_key_file_path(), config)


def get_api_key() -> str | None:
    """???? key ???? 007AI API key?"""
    key_config = load_key_config()
    return key_config.get("api_key")


def get_base_url() -> str | None:
    """?????? base_url"""
    config = load_config()
    return config.get("base_url")


def save_api_key(api_key: str) -> None:
    """?? 007AI API key ? 007ai-image-key.json"""
    save_key_config({"api_key": api_key})


def save_base_url(base_url: str) -> None:
    """?? base_url ? .config/config.json"""
    config = load_config()
    config["base_url"] = base_url
    save_config(config)


def save_provider_config(api_key: str, base_url: str) -> None:
    """???? 007AI API key ? base_url"""
    if api_key:
        save_api_key(api_key)
    if base_url:
        save_base_url(base_url)


def has_valid_config() -> bool:
    """????????????"""
    api_key = get_api_key()
    base_url = get_base_url()
    return bool(api_key and base_url)


def redact_api_key(api_key: str | None) -> str:
    """?? API key ????"""
    if not api_key:
        return "???"
    if len(api_key) > 12:
        return api_key[:6] + "..." + api_key[-4:]
    return "***"
