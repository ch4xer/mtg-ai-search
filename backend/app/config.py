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
