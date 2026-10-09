"""SQLite-backed task store with the same interface as the in-memory TaskStore.

Opt in with TASK_STORE=sqlite. Nothing in the HTTP layer changes, which is the
point: the store boundary is real, not aspirational. The API test suite runs
against both implementations.
"""

from __future__ import annotations

import sqlite3
from threading import Lock

from .store import Task, TaskNotFound, utc_now

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,  -- AUTOINCREMENT: ids are never reused
    title        TEXT    NOT NULL,
    completed    INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT    NOT NULL,
    completed_at TEXT
)
"""


def _row_to_task(row: sqlite3.Row) -> Task:
    return Task(
        id=row["id"],
        title=row["title"],
        completed=bool(row["completed"]),
        created_at=row["created_at"],
        completed_at=row["completed_at"],
    )


class SqliteTaskStore:
    """Thread-safe SQLite repository. One connection, serialized by a lock."""

    def __init__(self, path: str = ":memory:") -> None:
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = Lock()
        with self._lock:
            self._conn.execute(_SCHEMA)
            self._conn.commit()

    def list(self, completed: bool | None = None) -> list[Task]:
        sql = "SELECT * FROM tasks"
        params: tuple = ()
        if completed is not None:
            sql += " WHERE completed = ?"
            params = (int(completed),)
        with self._lock:
            rows = self._conn.execute(sql + " ORDER BY id", params).fetchall()
        return [_row_to_task(r) for r in rows]

    def get(self, task_id: int) -> Task:
        with self._lock:
            row = self._conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise TaskNotFound(task_id)
        return _row_to_task(row)

    def create(self, title: str) -> Task:
        created_at = utc_now()
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO tasks (title, completed, created_at) VALUES (?, 0, ?)", (title, created_at)
            )
            self._conn.commit()
            task_id = cur.lastrowid
        return Task(id=task_id, title=title, completed=False, created_at=created_at)

    def complete(self, task_id: int) -> Task:
        with self._lock:
            # Matching 0 rows is fine: the task was already completed (idempotent).
            self._conn.execute(
                "UPDATE tasks SET completed = 1, completed_at = ? WHERE id = ? AND completed = 0",
                (utc_now(), task_id),
            )
            self._conn.commit()
            row = self._conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise TaskNotFound(task_id)
        return _row_to_task(row)

    def update(self, task_id: int, *, title: str | None = None, completed: bool | None = None) -> Task:
        with self._lock:
            row = self._conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if row is None:
                raise TaskNotFound(task_id)
            new_title = row["title"] if title is None else title
            new_completed = bool(row["completed"]) if completed is None else completed
            if new_completed == bool(row["completed"]):
                new_completed_at = row["completed_at"]
            else:
                new_completed_at = utc_now() if new_completed else None
            self._conn.execute(
                "UPDATE tasks SET title = ?, completed = ?, completed_at = ? WHERE id = ?",
                (new_title, int(new_completed), new_completed_at, task_id),
            )
            self._conn.commit()
            row = self._conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return _row_to_task(row)

    def delete(self, task_id: int) -> None:
        with self._lock:
            cur = self._conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            self._conn.commit()
        if cur.rowcount == 0:
            raise TaskNotFound(task_id)

    def stats(self) -> dict:
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) AS total, COALESCE(SUM(completed), 0) AS completed FROM tasks"
            ).fetchone()
        total, completed = row["total"], row["completed"]
        return {"total": total, "completed": completed, "pending": total - completed}
