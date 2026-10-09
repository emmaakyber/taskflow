"""MCP server that exposes the TaskFlow API as tools.

Same API the React UI uses, different consumer: an agent in Claude Desktop,
Claude Code, or any MCP client can list, create, complete and delete tasks.

Run (stdio transport):
    pip install -r requirements.txt
    TASKFLOW_API_URL=http://localhost:5000 python server.py

Claude Desktop config:
    {"mcpServers": {"taskflow": {"command": "python3",
        "args": ["/abs/path/to/extras/mcp/server.py"],
        "env": {"TASKFLOW_API_URL": "http://localhost:5000"}}}}
"""

from __future__ import annotations

import os

import httpx
from mcp.server.fastmcp import FastMCP

API_URL = os.environ.get("TASKFLOW_API_URL", "http://localhost:5000").rstrip("/")

mcp = FastMCP("taskflow")


def _call(method: str, path: str, **kwargs) -> dict | list | None:
    """Hit the API and surface its error envelope as a readable exception."""
    try:
        with httpx.Client(base_url=API_URL, timeout=5.0) as client:
            res = client.request(method, path, **kwargs)
    except httpx.HTTPError as exc:
        raise RuntimeError(f"backend_unreachable: could not reach {API_URL} ({exc.__class__.__name__})") from exc
    if res.status_code == 204:
        return None
    try:
        body = res.json()
    except ValueError:
        raise RuntimeError(f"bad_response: HTTP {res.status_code} with a non-JSON body") from None
    if res.is_error:
        err = body.get("error", {})
        raise RuntimeError(f"{err.get('code', 'error')}: {err.get('message', res.text)}")
    return body


@mcp.tool()
def list_tasks(status: str = "all") -> list[dict]:
    """List tasks. status is one of: all, pending, completed."""
    return _call("GET", "/tasks", params={"status": status})


@mcp.tool()
def create_task(title: str) -> dict:
    """Create a task with the given title (1 to 200 characters)."""
    return _call("POST", "/tasks", json={"title": title})


@mcp.tool()
def complete_task(task_id: int) -> dict:
    """Mark a task as completed. Safe to call on an already-completed task."""
    return _call("PUT", f"/tasks/{task_id}/complete")


@mcp.tool()
def update_task(task_id: int, title: str | None = None, completed: bool | None = None) -> dict:
    """Rename a task and/or set completed (false re-opens it). Provide at least one field."""
    changes = {k: v for k, v in {"title": title, "completed": completed}.items() if v is not None}
    return _call("PATCH", f"/tasks/{task_id}", json=changes)


@mcp.tool()
def delete_task(task_id: int) -> str:
    """Delete a task by id."""
    _call("DELETE", f"/tasks/{task_id}")
    return f"Task {task_id} deleted."


@mcp.tool()
def task_stats() -> dict:
    """Return total, completed and pending task counts."""
    return _call("GET", "/tasks/stats")


if __name__ == "__main__":
    mcp.run()
