"""Unit tests for TaskStore, independent of Flask."""

from concurrent.futures import ThreadPoolExecutor

import pytest

from app.store import TaskNotFound


def test_create_and_get(store):
    task = store.create("Write report")
    assert store.get(task.id) == task


def test_returns_snapshots_not_live_objects(store):
    task = store.create("A")
    task.title = "mutated by caller"
    assert store.get(task.id).title == "A"


def test_get_missing_raises(store):
    with pytest.raises(TaskNotFound, match="Task 7 does not exist"):
        store.get(7)


def test_complete_is_idempotent(store):
    task = store.create("A")
    first = store.complete(task.id)
    second = store.complete(task.id)
    assert first.completed_at is not None
    assert second.completed_at == first.completed_at


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
