"""OpenAPI 3.0 description of the API, served at GET /openapi.json.

Hand-written and kept small. tests/test_openapi.py asserts that every route
Flask actually registers appears here with the right methods, and vice versa,
so this document cannot silently drift from the implementation.
"""

from __future__ import annotations

TASK_SCHEMA = {
    "type": "object",
    "required": ["id", "title", "completed", "created_at", "completed_at"],
    "properties": {
        "id": {"type": "integer", "example": 1},
        "title": {"type": "string", "maxLength": 200, "example": "Write report"},
        "completed": {"type": "boolean"},
        "created_at": {"type": "string", "format": "date-time", "example": "2026-10-09T16:18:21Z"},
        "completed_at": {"type": "string", "format": "date-time", "nullable": True},
    },
}

ERROR_SCHEMA = {
    "type": "object",
    "required": ["error"],
    "properties": {
        "error": {
            "type": "object",
            "required": ["code", "message"],
            "properties": {
                "code": {"type": "string", "example": "not_found"},
                "message": {"type": "string", "example": "Task 7 does not exist"},
            },
        }
    },
}


def _error(description: str) -> dict:
    return {
        "description": description,
        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}},
    }


def _task(description: str) -> dict:
    return {
        "description": description,
        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Task"}}},
    }


TASK_ID_PARAM = {"name": "task_id", "in": "path", "required": True, "schema": {"type": "integer"}}

SPEC = {
    "openapi": "3.0.3",
    "info": {
        "title": "TaskFlow API",
        "version": "1.0.0",
        "description": "Create, complete, delete and count tasks. All errors share one envelope.",
    },
    "paths": {
        "/tasks": {
            "get": {
                "summary": "List tasks",
                "parameters": [
                    {
                        "name": "status",
                        "in": "query",
                        "schema": {"type": "string", "enum": ["all", "pending", "completed"], "default": "all"},
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Tasks in creation order",
                        "content": {
                            "application/json": {
                                "schema": {"type": "array", "items": {"$ref": "#/components/schemas/Task"}}
                            }
                        },
                    },
                    "400": _error("Invalid status filter"),
                },
            },
            "post": {
                "summary": "Create a task",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["title"],
                                "properties": {"title": {"type": "string", "minLength": 1, "maxLength": 200}},
                            }
                        }
                    },
                },
                "responses": {
                    "201": _task("Created"),
                    "400": _error("Missing, empty, non-string or too-long title; malformed JSON"),
                    "415": _error("Body is not JSON"),
                },
            },
        },
        "/tasks/{task_id}": {
            "parameters": [TASK_ID_PARAM],
            "get": {"summary": "Get one task", "responses": {"200": _task("The task"), "404": _error("No such task")}},
            "patch": {
                "summary": "Rename a task and/or set its completion (e.g. undo a complete)",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "minProperties": 1,
                                "additionalProperties": False,
                                "properties": {
                                    "title": {"type": "string", "minLength": 1, "maxLength": 200},
                                    "completed": {"type": "boolean"},
                                },
                            }
                        }
                    },
                },
                "responses": {
                    "200": _task("The updated task"),
                    "400": _error("Empty body, unknown field, bad title or non-boolean completed"),
                    "404": _error("No such task"),
                    "415": _error("Body is not JSON"),
                },
            },
            "delete": {
                "summary": "Delete a task",
                "responses": {"204": {"description": "Deleted"}, "404": _error("No such task")},
            },
        },
        "/tasks/{task_id}/complete": {
            "parameters": [TASK_ID_PARAM],
            "put": {
                "summary": "Mark a task completed (idempotent)",
                "responses": {"200": _task("The completed task"), "404": _error("No such task")},
            },
        },
        "/tasks/stats": {
            "get": {
                "summary": "Task counts",
                "responses": {
                    "200": {
                        "description": "Totals",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["total", "completed", "pending"],
                                    "properties": {
                                        "total": {"type": "integer"},
                                        "completed": {"type": "integer"},
                                        "pending": {"type": "integer"},
                                    },
                                }
                            }
                        },
                    }
                },
            }
        },
        "/health": {"get": {"summary": "Liveness check", "responses": {"200": {"description": '{"status": "ok"}'}}}},
        "/openapi.json": {
            "get": {"summary": "This document", "responses": {"200": {"description": "OpenAPI 3.0 JSON"}}}
        },
    },
    "components": {"schemas": {"Task": TASK_SCHEMA, "Error": ERROR_SCHEMA}},
}
