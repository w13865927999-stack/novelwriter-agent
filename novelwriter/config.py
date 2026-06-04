"""Configuration loading for NovelWriter Agent."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dependency is optional at runtime
    load_dotenv = None


BASE_DIR = Path(__file__).resolve().parent.parent


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(slots=True)
class AppConfig:
    """Runtime configuration for model calls and storage."""

    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_model: str = "gpt-4o-mini"
    mock: bool = True
    temperature: float = 0.8
    max_tokens: int = 4096
    novels_dir: Path = BASE_DIR / "novels"

    @classmethod
    def load(cls) -> "AppConfig":
        env_file = BASE_DIR / ".env"
        if load_dotenv is not None and env_file.exists():
            load_dotenv(env_file)

        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        mock = _as_bool(os.getenv("NOVELWRITER_MOCK"), default=not bool(api_key))
        novels_dir = Path(os.getenv("NOVELWRITER_NOVELS_DIR", str(BASE_DIR / "novels")))
        if not novels_dir.is_absolute():
            novels_dir = (BASE_DIR / novels_dir).resolve()

        return cls(
            openai_api_key=api_key,
            openai_base_url=os.getenv("OPENAI_BASE_URL", "").strip(),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini",
            mock=mock,
            temperature=float(os.getenv("NOVELWRITER_TEMPERATURE", "0.8")),
            max_tokens=int(os.getenv("NOVELWRITER_MAX_TOKENS", "4096")),
            novels_dir=novels_dir,
        )
