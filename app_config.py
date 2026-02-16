import os
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)


def _load_dotenv(path: Path) -> None:
    """Load KEY=VALUE lines from .env without overriding existing env vars."""
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue

        if value and len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]

        os.environ.setdefault(key, value)


_load_dotenv(BASE_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    app_secret: str
    database_url: str
    openrouter_api_key: str
    openrouter_model: str
    openrouter_chat_completions_url: str
    base_url: str
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    smtp_use_tls: bool
    request_timeout_sec: int
    provider_retries: int
    chat_system_prompt: str
    legacy_auth_key: str


def _as_bool(value: str, default: bool = True) -> bool:
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def load_settings() -> Settings:
    default_db = DATA_DIR / "demo.db"
    return Settings(
        app_secret=os.environ.get("APP_SECRET", "demo-secret-change-me"),
        database_url=os.environ.get("DATABASE_URL", f"sqlite:///{default_db}"),
        openrouter_api_key=os.environ.get("OPENROUTER_API_KEY", ""),
        openrouter_model=os.environ.get("OPENROUTER_MODEL", "openrouter/free"),
        openrouter_chat_completions_url=os.environ.get(
            "OPENROUTER_CHAT_COMPLETIONS_URL",
            "https://openrouter.ai/api/v1/chat/completions",
        ),
        base_url=os.environ.get("BASE_URL", "http://127.0.0.1:8000"),
        smtp_host=os.environ.get("SMTP_HOST", ""),
        smtp_port=int(os.environ.get("SMTP_PORT", "587")),
        smtp_username=os.environ.get("SMTP_USERNAME", ""),
        smtp_password=os.environ.get("SMTP_PASSWORD", ""),
        smtp_use_tls=_as_bool(os.environ.get("SMTP_USE_TLS"), default=True),
        request_timeout_sec=int(os.environ.get("REQUEST_TIMEOUT_SEC", "20")),
        provider_retries=int(os.environ.get("PROVIDER_RETRIES", "2")),
        chat_system_prompt=os.environ.get(
            "CHAT_SYSTEM_PROMPT",
            "You are a helpful and concise customer support representative. "
            "Keep replies clear, safe, and practical.",
        ),
        legacy_auth_key=os.environ.get("LEGACY_AUTH_KEY", "Pv7!n7h3W0rk"),
    )


settings = load_settings()
