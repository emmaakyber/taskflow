import pytest

from app import create_app
from app.store import TaskStore


@pytest.fixture
def store():
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
