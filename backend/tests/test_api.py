"""Integration tests against the Flask test client: one class per endpoint."""

import pytest


class TestListTasks:
    def test_empty_list(self, client):
        res = client.get("/tasks")
        assert res.status_code == 200
        assert res.get_json() == []

    def test_lists_created_tasks_in_order(self, client, make_task):
        make_task("A")
        make_task("B")
        titles = [t["title"] for t in client.get("/tasks").get_json()]
        assert titles == ["A", "B"]

    def test_trailing_slash_accepted(self, client):
        assert client.get("/tasks/").status_code == 200

    @pytest.mark.parametrize("status,expected", [("pending", ["A"]), ("completed", ["B"]), ("all", ["A", "B"])])
    def test_status_filter(self, client, make_task, status, expected):
        make_task("A")
        b = make_task("B")
        client.put(f"/tasks/{b['id']}/complete")
        titles = [t["title"] for t in client.get(f"/tasks?status={status}").get_json()]
        assert titles == expected

    def test_invalid_status_filter(self, client):
        res = client.get("/tasks?status=done")
        assert res.status_code == 400
        assert res.get_json()["error"]["code"] == "validation_error"


class TestCreateTask:
    def test_creates_task(self, client):
        res = client.post("/tasks", json={"title": "Write report"})
        assert res.status_code == 201
        body = res.get_json()
        assert body["id"] == 1
        assert body["title"] == "Write report"
        assert body["completed"] is False
        assert body["completed_at"] is None
        assert body["created_at"].endswith("Z")

    def test_ids_increment(self, make_task):
        assert [make_task()["id"] for _ in range(3)] == [1, 2, 3]

    def test_title_is_trimmed(self, client):
        res = client.post("/tasks", json={"title": "  padded  "})
        assert res.get_json()["title"] == "padded"

    @pytest.mark.parametrize(
        "payload,fragment",
        [
            ({}, "required"),
            ({"title": ""}, "empty"),
            ({"title": "   "}, "empty"),
            ({"title": 42}, "string"),
            ({"title": None}, "string"),
            ({"title": "x" * 201}, "200"),
        ],
    )
    def test_rejects_bad_title(self, client, payload, fragment):
        res = client.post("/tasks", json=payload)
        assert res.status_code == 400
        err = res.get_json()["error"]
        assert err["code"] == "validation_error"
        assert fragment in err["message"]

    def test_accepts_max_length_title(self, client):
        assert client.post("/tasks", json={"title": "x" * 200}).status_code == 201

    def test_rejects_non_object_body(self, client):
        res = client.post("/tasks", json=["not", "an", "object"])
        assert res.status_code == 400
        assert "object" in res.get_json()["error"]["message"]

    def test_rejects_malformed_json(self, client):
        res = client.post("/tasks", data="{not json", content_type="application/json")
        assert res.status_code == 400
        assert res.get_json()["error"]["code"] == "validation_error"

    def test_rejects_wrong_content_type(self, client):
        res = client.post("/tasks", data="title=Write report", content_type="application/x-www-form-urlencoded")
        assert res.status_code == 415
        assert res.get_json()["error"]["code"] == "unsupported_media_type"


class TestGetTask:
    def test_get_existing(self, client, make_task):
        task = make_task()
        assert client.get(f"/tasks/{task['id']}").get_json() == task

    def test_get_missing(self, client):
        res = client.get("/tasks/999")
        assert res.status_code == 404
        assert res.get_json() == {"error": {"code": "not_found", "message": "Task 999 does not exist"}}


class TestCompleteTask:
    def test_marks_completed(self, client, make_task):
        task = make_task()
        res = client.put(f"/tasks/{task['id']}/complete")
        assert res.status_code == 200
        body = res.get_json()
        assert body["completed"] is True
        assert body["completed_at"] is not None

    def test_idempotent(self, client, make_task):
        task = make_task()
        first = client.put(f"/tasks/{task['id']}/complete").get_json()
        second = client.put(f"/tasks/{task['id']}/complete")
        assert second.status_code == 200
        assert second.get_json() == first

    def test_missing_task(self, client):
        res = client.put("/tasks/42/complete")
        assert res.status_code == 404
        assert res.get_json()["error"]["code"] == "not_found"


class TestUpdateTask:
    def test_rename(self, client, make_task):
        task = make_task("Old")
        res = client.patch(f"/tasks/{task['id']}", json={"title": "  New  "})
        assert res.status_code == 200
        assert res.get_json()["title"] == "New"

    def test_undo_complete_clears_timestamp(self, client, make_task):
        task = make_task()
        client.put(f"/tasks/{task['id']}/complete")
        res = client.patch(f"/tasks/{task['id']}", json={"completed": False})
        body = res.get_json()
        assert body["completed"] is False
        assert body["completed_at"] is None
        assert client.get("/tasks/stats").get_json() == {"total": 1, "completed": 0, "pending": 1}

    def test_complete_via_patch_sets_timestamp(self, client, make_task):
        task = make_task()
        body = client.patch(f"/tasks/{task['id']}", json={"completed": True}).get_json()
        assert body["completed"] is True
        assert body["completed_at"] is not None

    def test_same_completion_keeps_timestamp(self, client, make_task):
        task = make_task()
        first = client.put(f"/tasks/{task['id']}/complete").get_json()
        again = client.patch(f"/tasks/{task['id']}", json={"completed": True}).get_json()
        assert again["completed_at"] == first["completed_at"]

    @pytest.mark.parametrize(
        "payload,fragment",
        [
            ({}, "at least one"),
            ({"completed": "yes"}, "true or false"),
            ({"title": ""}, "empty"),
            ({"colour": "red"}, "Unknown field"),
        ],
    )
    def test_rejects_bad_payload(self, client, make_task, payload, fragment):
        task = make_task()
        res = client.patch(f"/tasks/{task['id']}", json=payload)
        assert res.status_code == 400
        assert fragment in res.get_json()["error"]["message"]

    def test_missing_task(self, client):
        assert client.patch("/tasks/42", json={"title": "x"}).status_code == 404


class TestDeleteTask:
    def test_deletes(self, client, make_task):
        task = make_task()
        assert client.delete(f"/tasks/{task['id']}").status_code == 204
        assert client.get(f"/tasks/{task['id']}").status_code == 404
        assert client.get("/tasks").get_json() == []

    def test_missing_task(self, client):
        assert client.delete("/tasks/42").status_code == 404

    def test_deleted_id_is_not_reused(self, client, make_task):
        first = make_task()
        client.delete(f"/tasks/{first['id']}")
        assert make_task()["id"] == first["id"] + 1


class TestStats:
    def test_empty(self, client):
        assert client.get("/tasks/stats").get_json() == {"total": 0, "completed": 0, "pending": 0}

    def test_counts(self, client, make_task):
        a = make_task("A")
        make_task("B")
        c = make_task("C")
        client.put(f"/tasks/{a['id']}/complete")
        client.delete(f"/tasks/{c['id']}")
        assert client.get("/tasks/stats").get_json() == {"total": 2, "completed": 1, "pending": 1}

    def test_stats_route_not_shadowed_by_id_route(self, client):
        # /tasks/stats must never be parsed as /tasks/<id>
        assert client.get("/tasks/stats").status_code == 200


class TestErrorEnvelope:
    def test_unknown_route_is_json(self, client):
        res = client.get("/nope")
        assert res.status_code == 404
        assert res.is_json
        assert res.get_json()["error"]["code"] == "not_found"

    def test_wrong_method_is_json(self, client):
        res = client.patch("/tasks")
        assert res.status_code == 405
        assert res.get_json()["error"]["code"] == "method_not_allowed"

    def test_health(self, client):
        assert client.get("/health").get_json() == {"status": "ok"}

    def test_every_response_carries_a_request_id(self, client):
        generated = client.get("/tasks/stats").headers["X-Request-ID"]
        assert len(generated) == 12
        echoed = client.get("/nope", headers={"X-Request-ID": "trace-7"}).headers["X-Request-ID"]
        assert echoed == "trace-7"
