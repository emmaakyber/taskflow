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


def json_body() -> dict:
    """Return the request body as a dict, or raise the right 4xx."""
    if not request.is_json:
        raise UnsupportedMediaTypeError("Request body must be JSON (set Content-Type: application/json).")
    body = request.get_json(silent=True)
    if body is None:
        raise ValidationError("Request body is not valid JSON.")
    if not isinstance(body, dict):
        raise ValidationError("Request body must be a JSON object.")
    return body


def clean_title(value) -> str:
    """Validate a title value and return it trimmed."""
    if not isinstance(value, str):
        raise ValidationError("Field 'title' must be a string.")
    title = value.strip()
    if not title:
        raise ValidationError("Field 'title' must not be empty.")
    try:
        title.encode("utf-8")
    except UnicodeEncodeError:
        raise ValidationError("Field 'title' contains invalid characters.") from None
    if len(title) > TITLE_MAX_LENGTH:
        raise ValidationError(f"Field 'title' must be at most {TITLE_MAX_LENGTH} characters.")
    return title


def parse_task_payload() -> str:
    """Validate a create-task body and return the cleaned title."""
    body = json_body()
    if "title" not in body:
        raise ValidationError("Field 'title' is required.")
    return clean_title(body["title"])


def parse_update_payload() -> dict:
    """Validate a PATCH body: at least one of title / completed, nothing else."""
    body = json_body()
    unknown = set(body) - {"title", "completed"}
    if unknown:
        raise ValidationError(f"Unknown field(s): {', '.join(sorted(unknown))}. Allowed: title, completed.")
    if not body:
        raise ValidationError("Provide at least one of 'title' or 'completed'.")
    changes: dict = {}
    if "title" in body:
        changes["title"] = clean_title(body["title"])
    if "completed" in body:
        if not isinstance(body["completed"], bool):
            raise ValidationError("Field 'completed' must be true or false.")
        changes["completed"] = body["completed"]
    return changes


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


@bp.patch("/<int:task_id>")
def update_task(task_id: int):
    changes = parse_update_payload()
    return jsonify(store().update(task_id, **changes).to_dict())


@bp.delete("/<int:task_id>")
def delete_task(task_id: int):
    store().delete(task_id)
    return "", 204
