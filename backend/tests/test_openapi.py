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


# ---- Response bodies must match the schemas the spec declares ----------------

import pytest  # noqa: E402
from jsonschema import Draft7Validator  # noqa: E402

from app.openapi import SPEC  # noqa: E402


def _jsonschema_compatible(node):
    """OpenAPI 3.0 uses `nullable: true`, which JSON Schema spells as a type union."""
    if isinstance(node, dict):
        node = {k: _jsonschema_compatible(v) for k, v in node.items()}
        if node.pop("nullable", False) and "type" in node:
            node["type"] = [node["type"], "null"]
        return node
    if isinstance(node, list):
        return [_jsonschema_compatible(v) for v in node]
    return node


def _validate(instance, schema: dict) -> None:
    # Resolve $ref against the spec's components, then validate strictly.
    # Note: `format: date-time` is documentation only here; asserting it would
    # need an extra RFC 3339 validator package, which isn't worth a dependency.
    resolver_schema = _jsonschema_compatible({**schema, "components": SPEC["components"]})
    errors = sorted(Draft7Validator(resolver_schema).iter_errors(instance), key=str)
    assert not errors, "\n".join(e.message for e in errors)


def _response_schema(path: str, method: str, status: str) -> dict:
    return SPEC["paths"][path][method]["responses"][status]["content"]["application/json"]["schema"]


@pytest.fixture
def api(client, make_task):
    return client


def test_task_responses_match_schema(api, make_task):
    created = make_task("Schema check")
    _validate(created, _response_schema("/tasks", "post", "201"))
    _validate(api.get("/tasks").get_json(), _response_schema("/tasks", "get", "200"))
    _validate(api.get(f"/tasks/{created['id']}").get_json(), _response_schema("/tasks/{task_id}", "get", "200"))
    _validate(
        api.put(f"/tasks/{created['id']}/complete").get_json(),
        _response_schema("/tasks/{task_id}/complete", "put", "200"),
    )
    _validate(
        api.patch(f"/tasks/{created['id']}", json={"completed": False}).get_json(),
        _response_schema("/tasks/{task_id}", "patch", "200"),
    )
    _validate(api.get("/tasks/stats").get_json(), _response_schema("/tasks/stats", "get", "200"))


@pytest.mark.parametrize(
    "method,path,kwargs,status",
    [
        ("get", "/tasks/999", {}, "404"),
        ("put", "/tasks/999/complete", {}, "404"),
        ("post", "/tasks", {"json": {"title": ""}}, "400"),
        ("post", "/tasks", {"data": "x", "content_type": "text/plain"}, "415"),
        ("get", "/tasks?status=bogus", {}, "400"),
        ("patch", "/tasks/999", {"json": {"title": "x"}}, "404"),
        ("patch", "/tasks/1", {"json": {}}, "400"),
    ],
)
def test_error_responses_match_schema(api, method, path, kwargs, status):
    res = getattr(api, method)(path, **kwargs)
    assert str(res.status_code) == status
    spec_path = re.sub(r"/\d+", "/{task_id}", path.split("?")[0])
    _validate(res.get_json(), _response_schema(spec_path, method, status))
