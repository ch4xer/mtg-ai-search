import os

DEFAULT_ALLOWED_ORIGINS = (
    "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173"
)


def get_allowed_origins() -> list[str]:
    """Return CORS origins from env, defaulting to local dev servers."""
    raw_origins = os.getenv("ALLOWED_ORIGINS", DEFAULT_ALLOWED_ORIGINS)
    return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]


def get_admin_credentials() -> tuple[str | None, str | None]:
    """Return optional built-in admin credentials from the environment."""
    return os.getenv("ADMIN_USERNAME"), os.getenv("ADMIN_PASSWORD")


def get_startup_retry_config() -> dict[str, int]:
    """Return startup initialization retry settings from env."""
    max_attempts = int(os.getenv("STARTUP_INIT_MAX_ATTEMPTS", "5"))
    retry_delay_seconds = int(os.getenv("STARTUP_INIT_RETRY_DELAY_SECONDS", "15"))
    return {
        "max_attempts": max(1, max_attempts),
        "retry_delay_seconds": max(1, retry_delay_seconds),
    }


def get_log_level() -> str:
    """Return the application log level name from the environment."""
    return os.getenv("LOG_LEVEL", "INFO").upper()


def get_tag_bootstrap_config() -> dict:
    """Return startup tag expansion/embedding settings."""
    return {
        "enabled": os.getenv("TAG_BOOTSTRAP_ENABLED", "true").lower() in {"1", "true", "yes", "on"},
        "expansion_batch_size": max(1, int(os.getenv("TAG_EXPANSION_BATCH_SIZE", "10"))),
        "embedding_batch_size": max(1, int(os.getenv("TAG_EMBEDDING_BATCH_SIZE", "64"))),
        "sample_size": max(0, int(os.getenv("TAG_SAMPLE_SIZE", "3"))),
        "scryfall_delay_seconds": max(0.0, float(os.getenv("SCRYFALL_SAMPLE_REQUEST_DELAY_SECONDS", "0.8"))),
        "print_embedding_text": os.getenv("TAG_PRINT_EMBEDDING_TEXT", "true").lower() in {"1", "true", "yes", "on"},
    }


# ── Mutable rate-limit settings ──────────────────────────────────

_rate_limits = {
    "anon_hourly": 3,
    "user_hourly": 30,
}


def get_rate_limits() -> dict[str, int]:
    return dict(_rate_limits)


def update_rate_limits(anon_hourly: int | None = None, user_hourly: int | None = None) -> dict[str, int]:
    if anon_hourly is not None:
        _rate_limits["anon_hourly"] = anon_hourly
    if user_hourly is not None:
        _rate_limits["user_hourly"] = user_hourly
    return dict(_rate_limits)
