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
