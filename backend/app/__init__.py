"""Flask application factory."""

from __future__ import annotations

import os

from flask import Flask, jsonify
from flask_cors import CORS

from .errors import register_error_handlers
from .openapi import SPEC
from .routes import bp as tasks_bp
from .sqlite_store import SqliteTaskStore
from .store import TaskStore


def store_from_env() -> TaskStore | SqliteTaskStore:
    """Pick the store from TASK_STORE: 'memory' (default) or 'sqlite'."""
    kind = os.environ.get("TASK_STORE", "memory").lower()
    if kind == "sqlite":
        return SqliteTaskStore(os.environ.get("TASK_DB_PATH", ":memory:"))
    if kind == "memory":
        return TaskStore()
    raise ValueError(f"Unknown TASK_STORE {kind!r}; expected 'memory' or 'sqlite'.")


def create_app(store: TaskStore | SqliteTaskStore | None = None) -> Flask:
    app = Flask(__name__)
    app.url_map.strict_slashes = False  # /tasks and /tasks/ both work
    app.json.sort_keys = False  # keep field order as defined on Task

    app.extensions["task_store"] = store if store is not None else store_from_env()

    # The frontend talks to us through its nginx proxy inside Docker, but CORS
    # keeps direct browser calls (e.g. Vite dev server) working too.
    CORS(app, origins=os.environ.get("CORS_ORIGINS", "*"))

    register_error_handlers(app)
    app.register_blueprint(tasks_bp)

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/openapi.json")
    def openapi():
        return jsonify(SPEC)

    return app
