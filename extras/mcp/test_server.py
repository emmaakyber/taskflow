"""End-to-end test for the MCP server.

Starts the real Flask app on a local port, launches server.py as a subprocess
(stdio transport, exactly as Claude Desktop would), and drives all six tools
through the MCP SDK's own client. Error cases check that the API's envelope
reaches the agent as readable text.
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import sys
import threading
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from werkzeug.serving import make_server

from app import create_app
from app.store import TaskStore

SERVER = Path(__file__).with_name("server.py")


@pytest.fixture(scope="module")
def api_url():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    app = create_app(store=TaskStore())
    server = make_server("127.0.0.1", port, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


def call_tools(api_url: str, calls: list[tuple[str, dict]]) -> list:
    """Run a sequence of tool calls in one MCP session; return CallToolResults."""

    async def run():
        params = StdioServerParameters(
            command=sys.executable,
            args=[str(SERVER)],
            env={**os.environ, "TASKFLOW_API_URL": api_url},
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                results = [tools]
                for name, args in calls:
                    results.append(await session.call_tool(name, args))
                return results

    return asyncio.run(run())


def payload(result) -> dict | list | str:
    """Decode a tool result. Prefer the SDK's structured output; fall back to text blocks
    (FastMCP 1.x emits one text block per list item)."""
    structured = getattr(result, "structuredContent", None)
    if structured and "result" in structured:
        return structured["result"]

    def decode(text: str):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text

    blocks = [decode(c.text) for c in result.content]
    return blocks[0] if len(blocks) == 1 else blocks


def test_all_six_tools_round_trip(api_url):
    tools, created, listed, completed, updated, stats, deleted, after = call_tools(
        api_url,
        [
            ("create_task", {"title": "Via MCP"}),
            ("list_tasks", {"status": "pending"}),
            ("complete_task", {"task_id": 1}),
            ("update_task", {"task_id": 1, "title": "Renamed via MCP", "completed": False}),
            ("task_stats", {}),
            ("delete_task", {"task_id": 1}),
            ("list_tasks", {}),
        ],
    )
    assert {t.name for t in tools.tools} == {
        "list_tasks",
        "create_task",
        "complete_task",
        "update_task",
        "delete_task",
        "task_stats",
    }
    assert payload(created)["title"] == "Via MCP" and payload(created)["completed"] is False
    assert [t["title"] for t in payload(listed)] == ["Via MCP"]
    assert payload(completed)["completed"] is True
    renamed = payload(updated)
    assert (renamed["title"], renamed["completed"], renamed["completed_at"]) == ("Renamed via MCP", False, None)
    assert payload(stats) == {"total": 1, "completed": 0, "pending": 1}
    assert payload(deleted) == "Task 1 deleted."
    assert payload(after) == []


def test_api_errors_reach_the_agent_as_text(api_url):
    _, missing, invalid = call_tools(
        api_url,
        [
            ("complete_task", {"task_id": 9999}),
            ("create_task", {"title": "   "}),
        ],
    )
    assert missing.isError and "not_found: Task 9999 does not exist" in missing.content[0].text
    assert invalid.isError and "validation_error: Field 'title' must not be empty." in invalid.content[0].text


def test_unreachable_backend_is_a_clean_error():
    (_, result) = call_tools("http://127.0.0.1:9", [("task_stats", {})])
    assert result.isError and "backend_unreachable" in result.content[0].text
