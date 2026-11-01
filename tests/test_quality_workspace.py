import pytest
from fastapi.testclient import TestClient

from dataguard.api import create_app

TOKEN = "quality-test-operator-token-000000000000"
HEADERS = {"Authorization": "Bearer " + TOKEN}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATAGUARD_TOKEN", TOKEN)
    with TestClient(create_app(f"sqlite:///{tmp_path / 'quality.db'}")) as c:
        yield c


def test_public_source_provenance_and_all_pages(client):
    response = client.get("/api/quality/workspace")
    assert response.status_code == 200
    data = response.json()
    assert data["captures"]
    capture = data["captures"][0]
    assert capture["visibility"] == "public"
    assert capture["source"].startswith("https://api.github.com/")
    assert len(capture["digest"]) == 64
    for page in [
        "overview",
        "datasets",
        "contracts",
        "checks",
        "batches",
        "quarantine",
        "versions",
        "lineage",
        "incidents",
        "recovery",
        "agent",
        "connections",
        "settings",
    ]:
        result = client.get("/console/" + page)
        assert result.status_code == 200
        assert "DataGuard" in result.text


def test_private_upload_validation_and_public_boundary(client):
    body = {
        "name": "private customer input",
        "records": [
            {
                "id": 1,
                "full_name": "private-secret",
                "stargazers_count": -1,
                "open_issues_count": 1,
                "updated_at": "2026-01-01T00:00:00Z",
            }
        ],
    }
    assert client.post("/api/quality/uploads", json=body).status_code == 401
    result = client.post("/api/quality/uploads", json=body, headers=HEADERS)
    assert result.status_code == 201
    capture = result.json()
    assert capture["status"] == "quarantined"
    assert any(x["failed"] for x in capture["checks"])
    assert "private-secret" not in client.get("/api/quality/workspace").text
    assert client.get("/api/quality/captures/" + capture["id"]).status_code == 401
    assert client.get("/api/quality/captures/" + capture["id"], headers=HEADERS).status_code == 200
    assert (
        client.post(
            "/api/quality/restore", json={"capture_id": capture["id"]}, headers=HEADERS
        ).status_code
        == 409
    )


def test_contract_changes_recheck_with_immutable_versions(client):
    workspace = client.get("/api/quality/workspace", headers=HEADERS).json()
    first = workspace["captures"][0]
    contract = workspace["contract"]
    contract["max_age_hours"] = 1
    assert client.put("/api/quality/contract", json=contract, headers=HEADERS).status_code == 200
    result = client.post("/api/quality/recheck", json={"capture_id": first["id"]}, headers=HEADERS)
    assert result.status_code == 201
    assert result.json()["id"] != first["id"]
    assert result.json()["parent_id"] == first["id"]
    assert client.get("/api/quality/captures/" + first["id"]).json()["digest"] == first["digest"]


def test_agent_missing_provider_is_explicit(client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert client.get("/api/quality/provider").json()["configured"] is False
    response = client.post(
        "/api/quality/investigate", json={"question": "Investigate freshness"}, headers=HEADERS
    )
    assert response.status_code == 503
    assert "provider" in response.json()["detail"].lower()


def test_invalid_authorization_never_downgrades_to_public(client):
    response = client.get("/api/quality/workspace", headers={"Authorization": "Bearer wrong"})
    assert response.status_code == 401


def test_minimum_volume_and_live_contract_block_restore(client):
    capture = client.get("/api/quality/workspace").json()["captures"][0]
    changed = {
        "min_rows": 10,
        "max_age_hours": 72,
        "require_license": False,
        "reject_archived": False,
    }
    assert client.put("/api/quality/contract", json=changed, headers=HEADERS).status_code == 200
    assert (
        client.post(
            "/api/quality/restore", json={"capture_id": capture["id"]}, headers=HEADERS
        ).status_code
        == 409
    )
    result = client.post(
        "/api/quality/recheck", json={"capture_id": capture["id"]}, headers=HEADERS
    ).json()
    assert result["status"] == "quarantined"
    assert result["contract"]["min_rows"] == 10
    assert result["records"] == capture["records"]
    original = client.get("/api/quality/captures/" + capture["id"]).json()
    assert original["status"] == "published"
    assert original["contract"]["min_rows"] == 1


def test_restore_and_notes_persist_without_public_notes(client):
    capture = client.get("/api/quality/workspace").json()["captures"][0]
    assert (
        client.post(
            "/api/quality/restore", json={"capture_id": capture["id"]}, headers=HEADERS
        ).status_code
        == 200
    )
    note = {"capture_id": capture["id"], "note": "private investigation finding"}
    assert client.post("/api/quality/notes", json=note, headers=HEADERS).status_code == 201
    assert "private investigation finding" not in client.get("/api/quality/workspace").text
    private = client.get("/api/quality/workspace", headers=HEADERS).json()
    assert private["restored"]["capture_id"] == capture["id"]
    assert private["actions"][0]["note"] == note["note"]


def test_schema_duplicate_boolean_and_timestamp_checks_are_independent():
    from dataguard.quality import Contract, evaluate, stamp

    records = [
        {
            "id": 1,
            "full_name": "actual/input",
            "updated_at": "invalid",
            "stargazers_count": True,
            "open_issues_count": -1,
        },
        {"id": 1},
    ]
    result = {check["key"]: check for check in evaluate(records, stamp(), Contract().model_dump())}
    assert result["uniqueness"]["indices"] == [1]
    assert result["counters"]["indices"] == [0, 1]
    assert result["schema"]["indices"] == [1]
    assert result["timestamps"]["indices"] == [0, 1]


def test_stale_capture_is_quarantined_without_touching_record_timestamps():
    from dataguard.quality import Contract, evaluate

    result = evaluate([], "2020-01-01T00:00:00+00:00", Contract().model_dump())
    assert next(x for x in result if x["key"] == "freshness")["failed"] == 1


def test_sync_source_failure_has_no_partial_capture(client, monkeypatch):
    import urllib.error

    import dataguard.quality as module

    before = len(client.get("/api/quality/workspace").json()["captures"])

    def fail():
        raise urllib.error.URLError("private transport diagnostic")

    monkeypatch.setattr(module, "fetch_repositories", fail)
    result = client.post("/api/quality/sync", headers=HEADERS)
    assert result.status_code == 502
    assert "private transport diagnostic" not in result.text
    assert len(client.get("/api/quality/workspace").json()["captures"]) == before


def provider_replies(monkeypatch, replies):
    import io
    import json

    import dataguard.quality as module

    captured = []
    monkeypatch.setenv("OPENAI_API_KEY", "unit-test-credential-never-sent-to-network")

    def respond(request, timeout):
        assert request.full_url == "https://api.openai.com/v1/chat/completions"
        assert timeout == 20
        captured.append(json.loads(request.data))
        return io.BytesIO(json.dumps({"choices": [{"message": replies.pop(0)}]}).encode())

    monkeypatch.setattr(module.urllib.request, "urlopen", respond)
    return captured


def test_agent_uses_real_store_evidence_in_tool_roundtrip(client, monkeypatch):
    sent = provider_replies(
        monkeypatch,
        [
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "list_captures", "arguments": "{}"},
                    }
                ],
            },
            {"role": "assistant", "content": "The capture passed its stored contract."},
        ],
    )
    result = client.post(
        "/api/quality/investigate", json={"question": "Inspect actual captures"}, headers=HEADERS
    )
    assert result.status_code == 200
    assert len(sent) == 2
    assert result.json()["trace"][0]["tool"] == "list_captures"
    evidence = result.json()["trace"][0]["result"][0]
    assert evidence["source"].startswith("https://api.github.com/")
    assert "records" not in evidence
    assert sent[1]["messages"][-1]["role"] == "tool"
    assert evidence["digest"] in sent[1]["messages"][-1]["content"]


def test_agent_rejects_unverified_text_and_unknown_tool_claims(client, monkeypatch):
    provider_replies(
        monkeypatch, [{"role": "assistant", "content": "Fabricated claim without evidence"}]
    )
    response = client.post(
        "/api/quality/investigate", json={"question": "Inspect actual captures"}, headers=HEADERS
    )
    assert response.status_code == 502
    assert "Fabricated claim" not in response.text
    provider_replies(
        monkeypatch,
        [
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "bad",
                        "type": "function",
                        "function": {"name": "publish_data", "arguments": "{}"},
                    }
                ],
            },
            {"role": "assistant", "content": "I changed your data."},
        ],
    )
    response = client.post(
        "/api/quality/investigate", json={"question": "Inspect actual captures"}, headers=HEADERS
    )
    assert response.status_code == 502


def test_agent_enforces_six_call_budget(client, monkeypatch):
    call = {
        "id": "read",
        "type": "function",
        "function": {"name": "list_captures", "arguments": "{}"},
    }
    sent = provider_replies(
        monkeypatch,
        [
            {"role": "assistant", "tool_calls": [call, call, call]},
            {"role": "assistant", "tool_calls": [call, call, call]},
            {"role": "assistant", "tool_calls": [call]},
        ],
    )
    result = client.post(
        "/api/quality/investigate", json={"question": "Inspect actual captures"}, headers=HEADERS
    )
    assert result.status_code == 422
    assert "six-call" in result.text
    assert len(sent) == 3


def test_unknown_console_route_is_not_a_misleading_success(client):
    assert client.get("/console/nonexistent").status_code == 404
