"""In-memory admin maintenance task state."""

import time
from enum import Enum

from fastapi import HTTPException


class TaskStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


_task_state: dict = {
    "reseed": {"status": TaskStatus.IDLE, "message": "", "started_at": None},
    "seed_abilities": {"status": TaskStatus.IDLE, "message": "", "started_at": None},
    "tag_sync": {"status": TaskStatus.IDLE, "message": "", "started_at": None},
    "tag_embeddings": {"status": TaskStatus.IDLE, "message": "", "started_at": None},
    "card_translations": {"status": TaskStatus.IDLE, "message": "", "started_at": None},
}


def set_task_state(task_name: str, status: TaskStatus, message: str = "") -> None:
    _task_state[task_name] = {
        "status": status,
        "message": message,
        "started_at": _task_state[task_name].get("started_at"),
    }
    if status == TaskStatus.RUNNING and not _task_state[task_name]["started_at"]:
        _task_state[task_name]["started_at"] = time.time()
    if status in (TaskStatus.DONE, TaskStatus.ERROR, TaskStatus.IDLE):
        _task_state[task_name]["started_at"] = None


def ensure_task_not_running(task_name: str, message: str) -> None:
    if _task_state[task_name]["status"] == TaskStatus.RUNNING:
        raise HTTPException(status_code=409, detail=message)


def get_task_state_snapshot() -> dict:
    now = time.time()
    return {
        key: {
            "status": value["status"],
            "message": value["message"],
            "started_at": value["started_at"],
            "elapsed_seconds": int(now - value["started_at"]) if value["started_at"] else 0,
        }
        for key, value in _task_state.items()
    }
