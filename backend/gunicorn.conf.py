"""Gunicorn settings for the container.

One worker on purpose: with the default in-memory store, tasks live in process
memory, so multiple workers would each hold a different task list. Threads
provide concurrency instead; the store's lock keeps them safe. (With
TASK_STORE=sqlite this constraint could be lifted.)
"""

import logging

bind = "0.0.0.0:5000"
workers = 1
threads = 8
accesslog = "-"


class _SkipHealthChecks(logging.Filter):
    """Keep the Docker healthcheck from flooding the access log every few seconds."""

    def filter(self, record: logging.LogRecord) -> bool:
        return "/health " not in record.getMessage()


def when_ready(server):
    logging.getLogger("gunicorn.access").addFilter(_SkipHealthChecks())
