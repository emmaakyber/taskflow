"""Attach a request id to every request and response.

Clients may send X-Request-ID; otherwise one is generated. The id is echoed in
the response header and included in server-side error logs, so a user saying
"I got an error, id abc123" can be matched to a log line.
"""

from __future__ import annotations

import uuid

from flask import Flask, Response, g, request

HEADER = "X-Request-ID"


def register_request_id(app: Flask) -> None:
    @app.before_request
    def assign_request_id() -> None:
        incoming = request.headers.get(HEADER, "").strip()
        g.request_id = incoming[:64] if incoming else uuid.uuid4().hex[:12]

    @app.after_request
    def echo_request_id(response: Response) -> Response:
        response.headers[HEADER] = g.get("request_id", "")
        return response
