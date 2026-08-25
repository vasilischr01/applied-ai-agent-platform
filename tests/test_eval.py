def test_evaluation_endpoint(client):
    r = client.post("/api/v1/eval/run")
    assert r.status_code == 200
    p = r.json()
    assert p["total_cases"] == 16
    assert p["tool_selection_accuracy"] == 1.0
    assert p["pass_rate"] == 1.0
