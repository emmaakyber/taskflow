"""Unit tests for TaskStore, independent of Flask."""
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.store import TaskNotFound, TaskStore


def test_create_and_get(store):
    task = store.create("Write report")
    assert store.get(task.id) is task


def test_get_missing_raises(store):
    with pytest.raises(TaskNotFound, match="Task 7 does not exist"):
        store.get(7)


def test_complete_is_idempotent(store):
    task = store.create("A")
    store.complete(task.id)
    first_stamp = task.completed_at
    store.complete(task.id)
    assert task.completed_at == first_stamp


def test_delete_then_stats(store):
    a, b = store.create("A"), store.create("B")
    store.complete(a.id)
    store.delete(b.id)
    assert store.stats() == {"total": 1, "completed": 1, "pending": 0}


def test_concurrent_creates_get_unique_ids(store):
    with ThreadPoolExecutor(max_workers=16) as pool:
        tasks = list(pool.map(lambda i: store.create(f"task {i}"), range(500)))
    ids = [t.id for t in tasks]
    assert len(set(ids)) == 500
    assert store.stats()["total"] == 500
