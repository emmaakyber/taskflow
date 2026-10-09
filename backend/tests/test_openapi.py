"""Contract test: the OpenAPI document and the Flask routing table must agree."""

import re

from app import create_app
from app.store import TaskStore

IGNORED_METHODS = {"HEAD", "OPTIONS"}


def _routes_from_flask() -> set[tuple[str, str]]:
    app = create_app(store=TaskStore())
    routes = set()
    for rule in app.url_map.iter_rules():
        if rule.endpoint == "static":
            continue
        path = re.sub(r"<(?:\w+:)?(\w+)>", r"{\1}", rule.rule)
        for method in rule.methods - IGNORED_METHODS:
            routes.add((path, method.lower()))
    return routes


def _routes_from_spec() -> set[tuple[str, str]]:
    from app.openapi import SPEC

    return {(path, method) for path, item in SPEC["paths"].items() for method in item if method != "parameters"}


def test_spec_matches_registered_routes():
    assert _routes_from_spec() == _routes_from_flask()


def test_spec_is_served():
    client = create_app(store=TaskStore()).test_client()
    res = client.get("/openapi.json")
    assert res.status_code == 200
    body = res.get_json()
    assert body["openapi"].startswith("3.0")
    assert "/tasks/stats" in body["paths"]
