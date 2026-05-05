"""Small helpers for reporting long-running task progress."""

from collections.abc import Callable

StatusCallback = Callable[[str], None] | None


def emit_status(callback: StatusCallback, message: str) -> None:
    if callback:
        callback(message)


def make_progress_callback(callback: StatusCallback, prefix: str):
    """Adapt numeric progress callbacks to the task status message format."""
    if not callback:
        return None

    def _progress(done: int, total: int) -> None:
        callback(f"{prefix}（{done}/{total}）...")

    return _progress
