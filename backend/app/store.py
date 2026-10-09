"""In-memory task storage.

The store is the only place task state lives. Routes never touch the dict
directly, so swapping this for SQLite or Postgres later is a one-class change.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from threading import Lock


def utc_now() -> str:
    """ISO-8601 UTC timestamp with second precision, e.g. 2026-10-09T14:03:21Z."""
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


@dataclass
class Task:
    id: int
    title: str
    completed: bool = False
    created_at: str = field(default_factory=utc_now)
    completed_at: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class TaskNotFound(LookupError):
    """Raised when a task id does not exist in the store."""

    def __init__(self, task_id: int):
        super().__init__(f"Task {task_id} does not exist")
        self.task_id = task_id


class TaskStore:
    """Thread-safe in-memory repository for tasks.

    IDs are integers that increase monotonically and are never reused, so a
    deleted task's id stays a 404 rather than silently pointing at a new task.

    Every method returns a snapshot copy taken while holding the lock, so a
    reader can never observe a half-applied update from another thread.
    """

    def __init__(self) -> None:
        self._tasks: dict[int, Task] = {}
        self._next_id = 1
        self._lock = Lock()

    def list(self, completed: bool | None = None) -> list[Task]:
        with self._lock:
            tasks = [replace(t) for t in self._tasks.values()]
        if completed is not None:
            tasks = [t for t in tasks if t.completed is completed]
        return tasks

    def get(self, task_id: int) -> Task:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                raise TaskNotFound(task_id)
            return replace(task)

    def create(self, title: str) -> Task:
        with self._lock:
            task = Task(id=self._next_id, title=title)
            self._tasks[task.id] = task
            self._next_id += 1
            return replace(task)

    def complete(self, task_id: int) -> Task:
        """Mark a task completed. Idempotent: completing twice is not an error."""
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                raise TaskNotFound(task_id)
            if not task.completed:
                task.completed = True
                task.completed_at = utc_now()
            return replace(task)

    def delete(self, task_id: int) -> None:
        with self._lock:
            if task_id not in self._tasks:
                raise TaskNotFound(task_id)
            del self._tasks[task_id]

    def stats(self) -> dict:
        with self._lock:
            total = len(self._tasks)
            completed = sum(1 for t in self._tasks.values() if t.completed)
        return {"total": total, "completed": completed, "pending": total - completed}
