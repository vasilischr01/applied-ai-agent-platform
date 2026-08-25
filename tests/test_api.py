from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError

from src.api.main import app
from src.db.session import get_db


def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
    }


def test_ready(client):
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
    }


def test_calculator_agent_flow(client):
    response = client.post(
        "/api/v1/agent/run",
        json={
            "message": "What is 17.5 multiplied by 8?",
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["tool_used"] == "calculator"
    assert payload["tool_output"]["result"] == 140.0


def test_document_search_agent_flow(client):
    response = client.post(
        "/api/v1/agent/run",
        json={
            "message": (
                "Search the local documents "
                "for observability in ML systems."
            ),
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["tool_used"] == "document_search"
    assert payload["tool_output"]["results"]


def test_database_stats_agent_flow(client):
    first = client.post(
        "/api/v1/agent/run",
        json={
            "message": "What is 2 + 2?",
        },
    )

    assert first.status_code == 200

    response = client.post(
        "/api/v1/agent/run",
        json={
            "message": (
                "Show me the database stats "
                "for previous runs."
            ),
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["tool_used"] == "database_stats"
    assert payload["tool_output"]["total_runs"] >= 1


def test_run_history(client):
    created = client.post(
        "/api/v1/agent/run",
        json={
            "message": "What is 5 * 5?",
        },
    ).json()

    response = client.get(
        f"/api/v1/agent/runs/{created['run_id']}"
    )

    assert response.status_code == 200
    assert response.json()["id"] == created["run_id"]


def test_unknown_run_returns_404(client):
    response = client.get(
        "/api/v1/agent/runs/"
        "run-that-does-not-exist"
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Run not found",
    }


def test_run_list_respects_limit(client):
    for expression in (
        "1 + 1",
        "2 + 2",
        "3 + 3",
    ):
        response = client.post(
            "/api/v1/agent/run",
            json={
                "message": (
                    f"What is {expression}?"
                ),
            },
        )

        assert response.status_code == 200

    response = client.get(
        "/api/v1/agent/runs?limit=2"
    )

    assert response.status_code == 200

    payload = response.json()

    assert isinstance(payload, list)
    assert len(payload) == 2


def test_invalid_run_limit_is_rejected(client):
    response = client.get(
        "/api/v1/agent/runs?limit=0"
    )

    assert response.status_code == 422

    response = client.get(
        "/api/v1/agent/runs?limit=501"
    )

    assert response.status_code == 422


def test_missing_message_is_rejected(client):
    response = client.post(
        "/api/v1/agent/run",
        json={},
    )

    assert response.status_code == 422


def test_session_id_is_returned(client):
    response = client.post(
        "/api/v1/agent/run",
        json={
            "message": "What is 2 + 2?",
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["session_id"]
    assert isinstance(
        payload["session_id"],
        str,
    )


def test_same_session_id_is_preserved(client):
    first = client.post(
        "/api/v1/agent/run",
        json={
            "message": "What is 2 + 2?",
        },
    ).json()

    session_id = first["session_id"]

    second = client.post(
        "/api/v1/agent/run",
        json={
            "message": "What is 3 + 3?",
            "session_id": session_id,
        },
    ).json()

    assert second["session_id"] == session_id


def test_session_memory_stores_document_search(
    client,
):
    response = client.post(
        "/api/v1/agent/run",
        json={
            "message": (
                "Search the local documents "
                "for observability in ML systems."
            ),
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["tool_used"] == "document_search"
    assert payload["tool_output"]["results"]
    assert payload["session_id"]


def test_clear_session(client):
    first = client.post(
        "/api/v1/agent/run",
        json={
            "message": "What is 10 + 5?",
        },
    ).json()

    session_id = first["session_id"]

    response = client.delete(
        f"/api/v1/sessions/{session_id}"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["session_id"] == session_id
    assert payload["cleared"] is True


def test_clear_unknown_session(client):
    response = client.delete(
        "/api/v1/sessions/"
        "session-that-does-not-exist"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["cleared"] is False


def test_follow_up_uses_session_context(
    client,
    monkeypatch,
):
    first = client.post(
        "/api/v1/agent/run",
        json={
            "message": (
                "Search the local documents "
                "for observability in ML systems."
            ),
        },
    )

    assert first.status_code == 200

    first_payload = first.json()
    session_id = first_payload["session_id"]

    def fake_contextual_answer(
        self,
        message: str,
        context: str,
    ) -> str:
        assert (
            message
            == "Summarize the first result."
        )
        assert "ml_systems.txt" in context

        return (
            "The first result discusses "
            "observability and monitoring "
            "of ML systems."
        )

    monkeypatch.setattr(
        "src.agent.planner."
        "Planner.contextual_answer",
        fake_contextual_answer,
    )

    second = client.post(
        "/api/v1/agent/run",
        json={
            "message": (
                "Summarize the first result."
            ),
            "session_id": session_id,
        },
    )

    assert second.status_code == 200

    payload = second.json()

    assert payload["session_id"] == session_id
    assert payload["tool_used"] is None
    assert payload["answer"] == (
        "The first result discusses "
        "observability and monitoring "
        "of ML systems."
    )


def test_agent_value_error_is_sanitized(
    client,
    monkeypatch,
):
    secret_message = (
        "internal validation implementation "
        "detail"
    )

    def fail_run(
        self,
        db,
        message,
        context=None,
    ):
        raise ValueError(
            secret_message
        )

    monkeypatch.setattr(
        "src.api.main.AgentService.run",
        fail_run,
    )

    response = client.post(
        "/api/v1/agent/run",
        json={
            "message": "Trigger error",
        },
    )

    assert response.status_code == 400

    payload = response.json()

    assert payload["detail"] == (
        "The agent could not process "
        "the request"
    )
    assert secret_message not in response.text


def test_agent_internal_error_is_sanitized(
    client,
    monkeypatch,
):
    secret_message = (
        "super-secret internal traceback "
        "information"
    )

    def fail_run(
        self,
        db,
        message,
        context=None,
    ):
        raise RuntimeError(
            secret_message
        )

    monkeypatch.setattr(
        "src.api.main.AgentService.run",
        fail_run,
    )

    response = client.post(
        "/api/v1/agent/run",
        json={
            "message": "Trigger failure",
        },
    )

    assert response.status_code == 500

    payload = response.json()

    assert payload["detail"] == (
        "Internal server error"
    )
    assert secret_message not in response.text


def test_agent_database_error_returns_503(
    client,
    monkeypatch,
):
    secret_message = (
        "private database connection details"
    )

    def fail_run(
        self,
        db,
        message,
        context=None,
    ):
        raise SQLAlchemyError(
            secret_message
        )

    monkeypatch.setattr(
        "src.api.main.AgentService.run",
        fail_run,
    )

    response = client.post(
        "/api/v1/agent/run",
        json={
            "message": "Trigger DB failure",
        },
    )

    assert response.status_code == 503

    payload = response.json()

    assert payload["detail"] == (
        "Database service unavailable"
    )
    assert secret_message not in response.text


def test_readiness_database_failure_returns_503(
    client,
):
    class BrokenSession:
        def execute(
            self,
            *args,
            **kwargs,
        ):
            raise SQLAlchemyError(
                "private database details"
            )

    def broken_db():
        yield BrokenSession()

    app.dependency_overrides[
        get_db
    ] = broken_db

    try:
        response = client.get(
            "/ready"
        )

        assert response.status_code == 503

        payload = response.json()

        assert payload["detail"] == (
            "Database is not ready"
        )
        assert (
            "private database details"
            not in response.text
        )

    finally:
        app.dependency_overrides.pop(
            get_db,
            None,
        )


def test_security_headers_are_present(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert (
        response.headers["X-Content-Type-Options"]
        == "nosniff"
    )
    assert (
        response.headers["X-Frame-Options"]
        == "DENY"
    )
    assert (
        response.headers["Referrer-Policy"]
        == "no-referrer"
    )
    assert (
        response.headers["Cache-Control"]
        == "no-store"
    )
    assert (
        "camera=()"
        in response.headers["Permissions-Policy"]
    )


def test_oversized_request_is_rejected(client):
    oversized_message = "x" * (70 * 1024)

    response = client.post(
        "/api/v1/agent/run",
        json={
            "message": oversized_message,
        },
    )

    assert response.status_code == 413
    assert response.json() == {
        "detail": "Request body too large",
    }


def test_rate_limit_is_enforced(client):
    from src.api.main import _request_history

    _request_history.clear()

    last_response = None

    for _ in range(61):
        last_response = client.get(
            "/health"
        )

    assert last_response is not None
    assert last_response.status_code == 429
    assert last_response.json() == {
        "detail": "Too many requests",
    }
    assert (
        last_response.headers["Retry-After"]
        == "60"
    )

    _request_history.clear()