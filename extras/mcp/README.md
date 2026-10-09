# TaskFlow MCP server (extra)

A small [MCP](https://modelcontextprotocol.io) server that wraps the TaskFlow API as five tools: `list_tasks`, `create_task`, `complete_task`, `delete_task`, `task_stats`. It lets an agent (Claude Desktop, Claude Code, any MCP client) manage tasks through the same API the React UI uses.

Not part of `docker-compose up`; it is a thin client that runs wherever the agent runs.

```bash
pip install -r requirements.txt
TASKFLOW_API_URL=http://localhost:5000 python server.py
```

Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "taskflow": {
      "command": "python3",
      "args": ["/absolute/path/to/taskflow/extras/mcp/server.py"],
      "env": { "TASKFLOW_API_URL": "http://localhost:5000" }
    }
  }
}
```

Errors from the API (404 on a missing id, 400 on an empty title) are surfaced to the agent with the API's own `code: message` text, so the model can correct itself rather than guess.
