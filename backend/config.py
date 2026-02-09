"""Runtime configuration with .env loading and live updates."""

from __future__ import annotations

import os
from pathlib import Path
from threading import Lock

from dotenv import load_dotenv

from backend.models import AppConfig

# Load .env from project root
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)

_config = AppConfig(gemini_api_key=os.getenv("GEMINI_API_KEY", ""))
_lock = Lock()


def get_config() -> AppConfig:
    with _lock:
        return _config.model_copy()


def update_config(updates: dict) -> AppConfig:
    global _config
    # Fields that are Optional and can legitimately be set to None
    _nullable_fields = {"target_window"}
    with _lock:
        data = _config.model_dump()
        for k, v in updates.items():
            if v is not None or k in _nullable_fields:
                data[k] = v
        _config = AppConfig(**data)
        return _config.model_copy()
