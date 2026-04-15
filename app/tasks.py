from __future__ import annotations

import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime
from threading import Lock
from typing import Any, Callable


@dataclass
class TaskState:
    id: str
    kind: str
    status: str
    created_at: str
    started_at: str = ""
    finished_at: str = ""
    message: str = ""
    progress_current: int = 0
    progress_total: int = 0
    logs: list[str] = field(default_factory=list)
    result: Any = None
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TaskContext:
    def __init__(self, manager: "TaskManager", task_id: str) -> None:
        self.manager = manager
        self.task_id = task_id

    def set_message(self, message: str) -> None:
        self.manager._update(self.task_id, message=message)

    def set_progress(self, current: int, total: int, message: str | None = None) -> None:
        update: dict[str, Any] = {"progress_current": current, "progress_total": total}
        if message is not None:
            update["message"] = message
        self.manager._update(self.task_id, **update)

    def log(self, message: str) -> None:
        self.manager._append_log(self.task_id, message)


class TaskManager:
    def __init__(self) -> None:
        self.executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="uestc-tt")
        self._tasks: dict[str, TaskState] = {}
        self._lock = Lock()

    def submit(self, kind: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> TaskState:
        task_id = uuid.uuid4().hex
        state = TaskState(
            id=task_id,
            kind=kind,
            status="queued",
            created_at=datetime.now().astimezone().isoformat(),
        )
        with self._lock:
            self._tasks[task_id] = state
        self.executor.submit(self._run, task_id, fn, *args, **kwargs)
        return state

    def _run(self, task_id: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        self._update(task_id, status="running", started_at=datetime.now().astimezone().isoformat())
        ctx = TaskContext(self, task_id)
        try:
            result = fn(ctx, *args, **kwargs)
            self._update(
                task_id,
                status="completed",
                finished_at=datetime.now().astimezone().isoformat(),
                result=result,
                message="完成",
            )
        except Exception as exc:
            self._append_log(task_id, traceback.format_exc())
            self._update(
                task_id,
                status="failed",
                finished_at=datetime.now().astimezone().isoformat(),
                error=str(exc),
                message="失败",
            )

    def _update(self, task_id: str, **changes: Any) -> None:
        with self._lock:
            state = self._tasks[task_id]
            for key, value in changes.items():
                setattr(state, key, value)

    def _append_log(self, task_id: str, message: str) -> None:
        with self._lock:
            self._tasks[task_id].logs.append(message)

    def get(self, task_id: str) -> TaskState | None:
        with self._lock:
            return self._tasks.get(task_id)


task_manager = TaskManager()
