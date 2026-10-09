import pytest

from app import create_app
from app.sqlite_store import SqliteTaskStore
from app.store import TaskStore


# Every test that uses `store` or `client` runs twice: once against the
# in-memory store and once against SQLite. Same contract, two backends.
@pytest.fixture(params=["memory", "sqlite"])
def store(request):
    if request.param == "sqlite":
        return SqliteTaskStore(":memory:")
    return TaskStore()


@pytest.fixture
def client(store):
    app = create_app(store=store)
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture
def make_task(client):
    def _make(title="Write report"):
        res = client.post("/tasks", json={"title": title})
        assert res.status_code == 201
        return res.get_json()

    return _make
