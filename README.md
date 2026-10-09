# TaskFlow

A small task manager: Flask REST API, React UI, both containerized and wired together with Docker Compose.

[![CI](https://github.com/emmaakyber/taskflow/actions/workflows/ci.yml/badge.svg)](https://github.com/emmaakyber/taskflow/actions/workflows/ci.yml)

## Run it

```bash
docker-compose up --build
```

(`docker compose up --build`, without the hyphen, works identically on Compose v2.)

| Service  | URL                   | What's there                                  |
|----------|-----------------------|-----------------------------------------------|
| Frontend | http://localhost:3000 | React UI (nginx serves the build, proxies `/api` to the backend) |
| Backend  | http://localhost:5000 | Flask API, called directly                    |

Then verify with the smoke test, which runs the exact sample calls from the brief plus the error cases:

```bash
./scripts/smoke.sh
```

> **macOS note:** port 5000 is often held by AirPlay Receiver. If the backend fails to bind, either turn AirPlay Receiver off in System Settings, or run `BACKEND_PORT=5001 docker-compose up --build` and `./scripts/smoke.sh http://localhost:5001`. The UI keeps working either way because it reaches the backend over the Compose network, not through the host port.

Run the backend tests inside the container (82 cases, each run against both storage backends):

```bash
docker-compose run --rm backend pytest
```

Frontend tests (Vitest + React Testing Library) run locally or in CI:

```bash
cd frontend && npm ci && npm test
```

Optional: persist tasks across restarts with the SQLite store instead of memory. Same API, same tests, one env var:

```bash
TASK_STORE=sqlite docker-compose up --build
```

## How it fits together

```
 browser ──► :3000  nginx (frontend container)
                │   ├── /          → static React bundle
                │   └── /api/*     → proxy → http://backend:5000/*
                ▼
            :5000  gunicorn → Flask (backend container)
                   routes.py        (validate, map HTTP ↔ store)
                   store.py         (TaskStore: in-memory, thread-safe)  ← default
                   sqlite_store.py  (SqliteTaskStore: same interface)    ← TASK_STORE=sqlite
                   errors.py        (one JSON error envelope for everything)
                   openapi.py       (spec served at /openapi.json)
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
| GET    | `/openapi.json`         | 200 OpenAPI 3.0 | A contract test keeps it in sync with the routing table |

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
  app/store.py        Task dataclass + TaskStore (in-memory; the only place state lives)
  app/sqlite_store.py SqliteTaskStore: same six methods, opt-in via TASK_STORE=sqlite
  app/errors.py       ApiError classes and the global error handlers
  app/openapi.py      OpenAPI 3.0 document
  tests/              82 cases: API integration + store unit tests, parametrized over both stores,
                      plus a contract test that the OpenAPI spec matches Flask's routing table
  pyproject.toml      Ruff config (lint + format, enforced in CI)
  Dockerfile          python:3.12-slim, non-root, gunicorn, healthcheck
  gunicorn.conf.py    1 worker / 8 threads (why: in-memory store), healthcheck log filter
frontend/
  src/api.js          fetch wrapper that turns the error envelope into thrown ApiErrors
  src/App.jsx         state + data flow; components/ are presentational
  src/test/           8 Vitest + React Testing Library tests (states, form, actions, filters)
  nginx.conf          static serving + /api proxy
  Dockerfile          multi-stage: node builds, nginx serves
extras/mcp/           MCP server exposing the API as agent tools (optional)
scripts/smoke.sh      end-to-end check against a running stack
.github/workflows/    CI: ruff + pytest, vitest + build, then a real compose up + smoke
docker-compose.yml
```

## Assumptions and simplifications

- **In-memory storage by default, one gunicorn worker.** Tasks live in the process, as the brief allows. Running one worker with eight threads (instead of several workers) is deliberate: multiple workers would each hold a different task list. The store takes a lock around every operation and hands back snapshot copies, so a reader can never see a half-applied update from another thread. Restarting the container clears all tasks.
- **SQLite is there to prove the boundary, not to change the default.** `SqliteTaskStore` implements the same six methods. The whole API test suite is parametrized to run against both, so "swap the store" is tested, not promised. With `TASK_STORE=sqlite` the data lives on a named volume and survives restarts.
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

One envelope, everywhere. The backend defines a small `ApiError` hierarchy (`ValidationError` → 400, `UnsupportedMediaTypeError` → 415) and registers global Flask handlers for those, for the store's own `TaskNotFound` (→ 404), for Werkzeug's `HTTPException` (so Flask's native 404/405 come back as JSON, never HTML), and for bare `Exception` (logged, returned as a generic 500 so internals never leak). Validation runs fully before any state changes, and messages are specific: `Field 'title' must be at most 200 characters.` rather than `Bad request`.

On the frontend, `api.js` is the only place `fetch` is called. It parses the envelope and throws an `ApiError` carrying the server's message, so components just catch and display. Form errors show inline under the input; list-level errors show in a banner with a retry. Buttons are disabled while their request is in flight so a double-click can't fire two deletes.

Each error class has a test: `tests/test_api.py::TestCreateTask::test_rejects_bad_title` is parametrized over six bad payloads, and `TestErrorEnvelope` checks that unknown routes and wrong methods are JSON too.

### What tests would you write if given more time?

- **More frontend tests.** Eight exist (`frontend/src/test/App.test.jsx`): render, empty state, create success and inline validation error, complete, delete, filter tabs, load-failure banner. I'd add: buttons disabled while a request is in flight, the stale-response guard when switching filters quickly, and `api.js` itself against a mocked `fetch` (204 handling, non-JSON bodies, network errors).
- **A compose-level integration test in CI.** The current CI already does `docker compose up --build` and runs the smoke script, but I'd turn the smoke script into proper assertions with a JSON-aware tool and add the frontend path (`/api/tasks` through nginx) to it.
- **Property-based test on `TaskStore`** (Hypothesis): for any sequence of create/complete/delete operations, `stats()` always equals what you'd compute from `list()`, and ids are unique and increasing.
- **Concurrency test with real HTTP**: fire 200 parallel `POST`s at the running gunicorn and assert 200 unique ids. The store-level version of this exists (`test_store.py::test_concurrent_creates_get_unique_ids`); this would prove it through the whole stack.
- **Schema validation against the OpenAPI spec.** The contract test today checks that paths and methods match the routing table. Next step is validating real responses against the schemas in the spec (e.g. with `openapi-core`), so a field rename fails a test.

### What would you improve with 1 extra hour?

1. **`PATCH /tasks/<id>`** for renaming and un-completing, with the same validation path as create, and an inline edit in the UI.
2. **Multi-worker gunicorn when SQLite is selected.** The one-worker constraint only exists for the in-memory store; with `TASK_STORE=sqlite` the config could scale workers, with WAL mode on the connection.
3. **A `docker-compose.dev.yml` override** with bind mounts, Flask reload and the Vite dev server, so the Docker path and the local-dev path are the same command.
4. **Optimistic UI updates** with rollback on failure, so Complete and Delete feel instant instead of waiting for the round trip. Skipped deliberately: the refetch-after-mutation approach is simpler to reason about and always shows server truth.

## What was verified before submitting

- `pytest`: 82 cases locally and inside the container, every API and store test against both backends.
- `npm test`: 8 frontend tests. `ruff check` and `ruff format --check` clean.
- `docker-compose up --build` from this checkout, then `scripts/smoke.sh` against it (the brief's sample calls plus error cases), then the UI through nginx including `/api/openapi.json`.
- Backend container restarted while the stack ran: the UI kept working (nginx re-resolves the service name).
- `TASK_STORE=sqlite`: created a task, restarted the backend, task still there.
- A fresh `git clone` into an empty directory and `docker-compose up --build` again, because the version that matters is the one a reviewer runs from zero.
- CI green on every push: lint, both test suites, and a real compose build with the smoke test.

## How I worked

I used Claude Code throughout: I set the structure and the decisions (store/route split, error envelope, idempotent complete, nginx proxy over CORS, one worker, SQLite as opt-in proof rather than a new default), it drafted the files, and I reviewed every one before it went in. After the first complete version I ran an independent review pass over the repo, which turned up ten small issues (a read that could observe a half-applied update, nginx caching the backend's IP, a stale-response race in the UI, and some README drift); all are fixed in the commit history. Verification was the part I didn't delegate.
