def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json() == {"status":"ok"}

def test_ready(client):
    r = client.get("/ready")
    assert r.status_code == 200

def test_calculator_agent_flow(client):
    p = client.post("/api/v1/agent/run", json={"message":"What is 17.5 multiplied by 8?"}).json()
    assert p["tool_used"] == "calculator"
    assert p["tool_output"]["result"] == 140.0

def test_document_search_agent_flow(client):
    p = client.post(
    "/api/v1/agent/run",
    json={
        "message": "Search the local documents for observability in ML systems."
    },
    ).json()
    assert p["tool_used"] == "document_search"
    assert p["tool_output"]["results"]

def test_database_stats_agent_flow(client):
    client.post("/api/v1/agent/run", json={"message":"What is 2 + 2?"})
    p = client.post(
    "/api/v1/agent/run",
    json={
        "message": "Show me the database stats for previous runs."
    },
    ).json()
    assert p["tool_used"] == "database_stats"
    assert p["tool_output"]["total_runs"] >= 1

def test_run_history(client):
    created = client.post("/api/v1/agent/run", json={"message":"What is 5 * 5?"}).json()
    r = client.get(f"/api/v1/agent/runs/{created['run_id']}")
    assert r.status_code == 200
    assert r.json()["id"] == created["run_id"]

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


def test_session_memory_stores_document_search(client):
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

    payload = first.json()

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
        "/api/v1/sessions/session-that-does-not-exist"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["cleared"] is False

def test_follow_up_uses_session_context(client, monkeypatch):
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
        assert message == "Summarize the first result."
        assert "ml_systems.txt" in context

        return (
            "The first result discusses observability "
            "and monitoring of ML systems."
        )

    monkeypatch.setattr(
        "src.agent.planner.Planner.contextual_answer",
        fake_contextual_answer,
    )

    second = client.post(
        "/api/v1/agent/run",
        json={
            "message": "Summarize the first result.",
            "session_id": session_id,
        },
    )

    assert second.status_code == 200

    second_payload = second.json()

    assert second_payload["session_id"] == session_id
    assert second_payload["tool_used"] is None
    assert (
        second_payload["answer"]
        == (
            "The first result discusses observability "
            "and monitoring of ML systems."
        )
    )