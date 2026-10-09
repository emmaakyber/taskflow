"""HTTP layer for /tasks. Validation happens here; state lives in TaskStore."""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from .errors import UnsupportedMediaTypeError, ValidationError
from .store import TaskStore

bp = Blueprint("tasks", __name__, url_prefix="/tasks")

TITLE_MAX_LENGTH = 200
STATUS_FILTERS = {"all": None, "pending": False, "completed": True}


def store() -> TaskStore:
    return current_app.extensions["task_store"]


def parse_task_payload() -> str:
    """Validate a create-task body and return the cleaned title."""
    if not request.is_json:
        raise UnsupportedMediaTypeError("Request body must be JSON (set Content-Type: application/json).")
    body = request.get_json(silent=True)
    if body is None:
        raise ValidationError("Request body is not valid JSON.")
    if not isinstance(body, dict):
        raise ValidationError("Request body must be a JSON object.")
    if "title" not in body:
        raise ValidationError("Field 'title' is required.")
    title = body["title"]
    if not isinstance(title, str):
        raise ValidationError("Field 'title' must be a string.")
    title = title.strip()
    if not title:
        raise ValidationError("Field 'title' must not be empty.")
    if len(title) > TITLE_MAX_LENGTH:
        raise ValidationError(f"Field 'title' must be at most {TITLE_MAX_LENGTH} characters.")
    return title


@bp.get("")
def list_tasks():
    status = request.args.get("status", "all")
    if status not in STATUS_FILTERS:
        raise ValidationError("Query 'status' must be one of: all, pending, completed.")
    tasks = store().list(completed=STATUS_FILTERS[status])
    return jsonify([t.to_dict() for t in tasks])


@bp.post("")
def create_task():
    title = parse_task_payload()
    task = store().create(title)
    return jsonify(task.to_dict()), 201


@bp.get("/stats")
def task_stats():
    return jsonify(store().stats())


@bp.get("/<int:task_id>")
def get_task(task_id: int):
    return jsonify(store().get(task_id).to_dict())


@bp.put("/<int:task_id>/complete")
def complete_task(task_id: int):
    return jsonify(store().complete(task_id).to_dict())


@bp.delete("/<int:task_id>")
def delete_task(task_id: int):
    store().delete(task_id)
    return "", 204
