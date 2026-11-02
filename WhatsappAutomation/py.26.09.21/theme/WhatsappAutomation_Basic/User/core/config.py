from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

APP_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = APP_DIR / "data"
DB_DIR = APP_DIR / "db"
RUNTIME_DIR = APP_DIR / "Runtime"
LOG_DIR = RUNTIME_DIR / "logs"
DB_PATH = DB_DIR / "whatsapp_automation.sqlite3"
SETTINGS_PATH = DATA_DIR / "settings.json"

DEFAULT_SETTINGS: dict[str, Any] = {
    "theme": "dark",
    "language": "en",
    "ocr_language": "eng",
    "tesseract_cmd": "",
    "automation_delay_seconds": 1.0,
    "screenshot_retention_days": 0,
    "require_confirmation_for_gui_actions": True,
}


@dataclass(frozen=True)
class AppConfig:
    app_name: str = "WhatsApp Workspace"
    version: str = "0.1.0"
    debug: bool = False


def ensure_directories() -> None:
    for directory in (DATA_DIR, DB_DIR, LOG_DIR):
        directory.mkdir(parents=True, exist_ok=True)
    if not SETTINGS_PATH.exists():
        SETTINGS_PATH.write_text(
            json.dumps(DEFAULT_SETTINGS, indent=2), encoding="utf-8"
        )


def load_settings() -> dict[str, Any]:
    ensure_directories()
    try:
        loaded = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        loaded = {}
    return {**DEFAULT_SETTINGS, **loaded}


def save_settings(settings: dict[str, Any]) -> dict[str, Any]:
    current = load_settings()
    allowed = set(DEFAULT_SETTINGS)
    clean = {key: value for key, value in settings.items() if key in allowed}
    if "theme" in clean and clean["theme"] not in {"dark", "light"}:
        raise ValueError("theme must be 'dark' or 'light'")
    if "ocr_language" in clean:
        language = str(clean["ocr_language"])
        if not re.fullmatch(r"[A-Za-z0-9_-]{2,12}", language):
            raise ValueError("ocr_language must be a valid Tesseract language code")
        clean["ocr_language"] = language
    if "tesseract_cmd" in clean:
        command = str(clean["tesseract_cmd"])
        if len(command) > 500:
            raise ValueError("tesseract_cmd path is too long")
        clean["tesseract_cmd"] = command
    if "automation_delay_seconds" in clean:
        try:
            delay = float(clean["automation_delay_seconds"])
        except (TypeError, ValueError) as exc:
            raise ValueError("automation_delay_seconds must be numeric") from exc
        if not math.isfinite(delay) or not 0.4 <= delay <= 5.0:
            raise ValueError("automation_delay_seconds must be between 0.4 and 5")
        clean["automation_delay_seconds"] = delay
    if "screenshot_retention_days" in clean:
        days = int(clean["screenshot_retention_days"])
        if not 0 <= days <= 30:
            raise ValueError("screenshot_retention_days must be between 0 and 30")
        clean["screenshot_retention_days"] = days
    merged = {**current, **clean}
    SETTINGS_PATH.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    return merged
