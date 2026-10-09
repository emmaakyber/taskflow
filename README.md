# TaskFlow

A small task manager: Flask REST API, React UI, both containerized and wired together with Docker Compose.

[![CI](https://github.com/emmaakyber/taskflow/actions/workflows/ci.yml/badge.svg)](https://github.com/emmaakyber/taskflow/actions/workflows/ci.yml)

## Run it

```bash
docker-compose up --build
```

| Service  | URL                   | What's there                                  |
|----------|-----------------------|-----------------------------------------------|
| Frontend | http://localhost:3000 | React UI (nginx serves the build, proxies `/api` to the backend) |
| Backend  | http://localhost:5000 | Flask API, called directly                    |

Then verify with the smoke test, which runs the exact sample calls from the brief plus the error cases:

```bash
./scripts/smoke.sh
```

> **macOS note:** port 5000 is often held by AirPlay Receiver. If the backend fails to bind, either turn AirPlay Receiver off in System Settings, or run `BACKEND_PORT=5001 docker-compose up --build` and `./scripts/smoke.sh http://localhost:5001`. The UI keeps working either way because it reaches the backend over the Compose network, not through the host port.

Run the backend tests inside the container:

```bash
docker-compose run --rm backend pytest
```

## How it fits together

```
 browser ──► :3000  nginx (frontend container)
                │   ├── /          → static React bundle
                │   └── /api/*     → proxy → http://backend:5000/*
                ▼
            :5000  gunicorn → Flask (backend container)
                   routes.py  (validate, map HTTP ↔ store)
                   store.py   (TaskStore: in-memory, thread-safe)
                   errors.py  (one JSON error envelope for everything)
```

The frontend never hardcodes a backend address. In Docker, nginx proxies `/api` to the `backend` service by name. In local dev, Vite's dev server does the same proxying. CORS is also enabled on the API so direct browser calls work if someone wires it up differently.

## API

| Method | Endpoint                | Success | Notes |
|--------|-------------------------|---------|-------|
| GET    | `/tasks`                | 200 `[Task]` | Optional `?status=all\|pending\|completed` |
| POST   | `/tasks`                | 201 `Task`   | Body `{"title": "..."}`; title is trimmed, 1 to 200 chars |
| GET    | `/tasks/<id>`           | 200 `Task`   | |
| PUT    | `/tasks/<id>/complete`  | 200 `Task`   | Idempotent: completing twice returns the same task, not an error |
| DELETE | `/tasks/<id>`           | 204          | IDs are never reused, so a deleted id stays a 404 |
| GET    | `/tasks/stats`          | 200 `{"total", "completed", "pending"}` | |
| GET    | `/health`               | 200 `{"status": "ok"}` | Used by the Docker healthcheck |

A task:

```json
{
  "id": 1,
  "title": "Write report",
  "completed": false,
  "created_at": "2026-10-09T16:18:21Z",
  "completed_at": null
}
```

Every error, including the ones Flask raises itself (unknown route, wrong method), has the same shape:

```json
{"error": {"code": "not_found", "message": "Task 7 does not exist"}}
```

| Status | `code`                   | When |
|--------|--------------------------|------|
| 400    | `validation_error`       | missing/empty/non-string/too-long title, invalid `status` filter, malformed JSON, body not an object |
| 404    | `not_found`              | unknown task id, or unknown route |
| 405    | `method_not_allowed`     | e.g. `PATCH /tasks` |
| 415    | `unsupported_media_type` | body sent without `Content-Type: application/json` |
| 500    | `internal_error`         | anything unexpected; logged server-side, generic message to the client |

## Project layout

```
backend/
  app/__init__.py     app factory, CORS, health route
  app/routes.py       /tasks blueprint and request validation
  app/store.py        Task dataclass + TaskStore (the only place state lives)
  app/errors.py       ApiError classes and the global error handlers
  tests/              39 tests: API integration (test client) + store unit tests
  Dockerfile          python:3.12-slim, non-root, gunicorn, healthcheck
frontend/
  src/api.js          fetch wrapper that turns the error envelope into thrown ApiErrors
  src/App.jsx         state + data flow; components/ are presentational
  nginx.conf          static serving + /api proxy
  Dockerfile          multi-stage: node builds, nginx serves
extras/mcp/           MCP server exposing the API as agent tools (optional)
scripts/smoke.sh      end-to-end check against a running stack
.github/workflows/    CI: pytest, frontend build, then a real compose up + smoke
docker-compose.yml
```

## Assumptions and simplifications

- **In-memory storage, one gunicorn worker.** Tasks live in the process. Running one worker with eight threads (instead of several workers) is deliberate: multiple workers would each hold a different task list. The store takes a lock around every mutation so the threads are safe. Restarting the container clears all tasks.
- **Integer IDs, monotonic, never reused.** Simpler for the sample `curl` commands than UUIDs, and a deleted id stays a clean 404.
- **Completing is idempotent.** A second `PUT .../complete` returns 200 with the unchanged task. A 409 would be defensible; I chose the behaviour that is friendlier to retries.
- **No un-complete, no title edit, no reordering.** Not in the brief; see "one extra hour".
- **No auth, no pagination, no persistence.** Out of scope for a two-hour exercise, and each would be a layer on top of the current structure rather than a rewrite.
- **Stats come from the API.** The UI calls `/tasks/stats` after every change rather than counting client-side, so the numbers shown are always the server's.
- **Dev dependencies are in the backend image** so `docker-compose run --rm backend pytest` works out of the box. In a production image I'd split a test stage.
- **Minimal styling, no component library.** Plain CSS, a handful of classes, accessible labels and `aria-live` on the stats.

## Extra: MCP server

`extras/mcp/server.py` wraps the same API as five MCP tools (`list_tasks`, `create_task`, `complete_task`, `delete_task`, `task_stats`) so an agent in Claude Desktop or Claude Code can manage tasks. It is a thin client, not part of `docker-compose up`, and it passes the API's own error messages through to the agent (a 404 arrives as `not_found: Task 9999 does not exist`) so the model can correct itself. Setup in [extras/mcp/README.md](extras/mcp/README.md).

## Questions

### How did you handle API errors?

One envelope, everywhere. The backend defines a small `ApiError` hierarchy (`ValidationError` → 400, `NotFoundError` → 404, and a 415 variant for wrong content type) and registers global Flask handlers for those, for the store's own `TaskNotFound`, for Werkzeug's `HTTPException` (so Flask's native 404/405 come back as JSON, never HTML), and for bare `Exception` (logged, returned as a generic 500 so internals never leak). Validation runs fully before any state changes, and messages are specific: `Field 'title' must be at most 200 characters.` rather than `Bad request`.

On the frontend, `api.js` is the only place `fetch` is called. It parses the envelope and throws an `ApiError` carrying the server's message, so components just catch and display. Form errors show inline under the input; list-level errors show in a banner with a retry. Buttons are disabled while their request is in flight so a double-click can't fire two deletes.

Each error class has a test: `tests/test_api.py::TestCreateTask::test_rejects_bad_title` is parametrized over six bad payloads, and `TestErrorEnvelope` checks that unknown routes and wrong methods are JSON too.

### What tests would you write if given more time?

- **Frontend component tests** (Vitest + React Testing Library): the form clears on success and shows the server message on failure; Complete/Delete disable while pending; the filter tabs request the right `status`.
- **A compose-level integration test in CI.** The current CI already does `docker compose up --build` and runs the smoke script, but I'd turn the smoke script into proper assertions with a JSON-aware tool and add the frontend path (`/api/tasks` through nginx) to it.
- **Property-based test on `TaskStore`** (Hypothesis): for any sequence of create/complete/delete operations, `stats()` always equals what you'd compute from `list()`, and ids are unique and increasing.
- **Concurrency test with real HTTP**: fire 200 parallel `POST`s at the running gunicorn and assert 200 unique ids. The store-level version of this exists (`test_store.py::test_concurrent_creates_get_unique_ids`); this would prove it through the whole stack.
- **Contract test** against an OpenAPI spec once one exists, so the docs can't drift from the implementation.

### What would you improve with 1 extra hour?

1. **Persistence behind the same interface.** `TaskStore` is already the only thing that knows where tasks live, so a `SqliteTaskStore` with the same five methods, selected by an environment variable, is about 40 lines plus a volume in `docker-compose.yml`. Then the one-worker constraint goes away too.
2. **`PATCH /tasks/<id>`** for renaming and un-completing, with the same validation path as create.
3. **An OpenAPI document** served at `/openapi.json`, generated from the route definitions, so the API is self-describing.
4. **Optimistic UI updates** with rollback on failure, so Complete and Delete feel instant instead of waiting for the round trip. Skipped deliberately: the refetch-after-mutation approach is simpler to reason about and always shows server truth.

## How I worked

I used Claude Code throughout: I set the structure and the decisions (store/route split, error envelope, idempotent complete, nginx proxy over CORS, one worker), it drafted the files, and I reviewed every one before it went in. Verification was the part I didn't delegate: tests green locally, then the whole stack brought up with `docker-compose up --build` and the smoke script run against it, then a fresh `git clone` into an empty directory and the same command again, because the version that matters is the one a reviewer runs from zero.
