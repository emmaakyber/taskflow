"""One JSON error envelope for every failure the API can produce.

Shape:
    {"error": {"code": "not_found", "message": "Task 7 does not exist"}}

Both our own ApiError subclasses and Werkzeug's HTTPExceptions (the 404s and
405s Flask raises on its own) go through here, so a client never sees HTML.
"""

from __future__ import annotations

from flask import Flask, g, jsonify
from werkzeug.exceptions import HTTPException

from .store import TaskNotFound


class ApiError(Exception):
    status = 400
    code = "bad_request"

    def __init__(self, message: str, *, status: int | None = None, code: str | None = None):
        super().__init__(message)
        self.message = message
        if status is not None:
            self.status = status
        if code is not None:
            self.code = code


class ValidationError(ApiError):
    status = 400
    code = "validation_error"


class UnsupportedMediaTypeError(ApiError):
    status = 415
    code = "unsupported_media_type"


def error_response(status: int, code: str, message: str):
    return jsonify({"error": {"code": code, "message": message}}), status


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def handle_api_error(err: ApiError):
        return error_response(err.status, err.code, err.message)

    @app.errorhandler(TaskNotFound)
    def handle_task_not_found(err: TaskNotFound):
        return error_response(404, "not_found", str(err))

    @app.errorhandler(HTTPException)
    def handle_http_exception(err: HTTPException):
        # Covers errors Flask raises itself: unknown routes (404), wrong methods (405), etc.
        code = (err.name or "error").lower().replace(" ", "_")
        return error_response(err.code or 500, code, err.description or err.name)

    @app.errorhandler(Exception)
    def handle_unexpected(err: Exception):
        request_id = g.get("request_id", "-")
        app.logger.exception("Unhandled error [request_id=%s]", request_id)
        return error_response(500, "internal_error", f"Something went wrong on our side (request id {request_id}).")
