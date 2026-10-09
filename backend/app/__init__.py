"""Flask application factory."""
from __future__ import annotations

import os

from flask import Flask, jsonify
from flask_cors import CORS

from .errors import register_error_handlers
from .routes import bp as tasks_bp
from .store import TaskStore


def create_app(store: TaskStore | None = None) -> Flask:
    app = Flask(__name__)
    app.url_map.strict_slashes = False  # /tasks and /tasks/ both work
    app.json.sort_keys = False  # keep field order as defined on Task

    app.extensions["task_store"] = store or TaskStore()

    # The frontend talks to us through its nginx proxy inside Docker, but CORS
    # keeps direct browser calls (e.g. Vite dev server) working too.
    CORS(app, origins=os.environ.get("CORS_ORIGINS", "*"))

    register_error_handlers(app)
    app.register_blueprint(tasks_bp)

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    return app
