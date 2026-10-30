from datetime import UTC, datetime

from fastapi.testclient import TestClient
from test_pipeline import fixture_payload

from dataguard.api import create_app
from dataguard.contracts import validate


def test_event_partition_uses_utc_date():
    payload = fixture_payload()
    payload["period"] = "2024-01-02"
    payload["trades"][0]["event_time"] = "2024-01-01T23:30:00-02:00"
    assert validate(payload, datetime.now(UTC)) == []


def test_non_ascii_authorization_is_a_clean_unauthorized_response(tmp_path, monkeypatch):
    monkeypatch.setenv("DATAGUARD_TOKEN", "a" * 32)
    with TestClient(create_app(f"sqlite:///{tmp_path / 'auth.db'}")) as client:
        result = client.post("/recover", headers={"authorization": b"Bearer \xff\xfe"})
        assert result.status_code == 401


def test_whitespace_operator_token_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setenv("DATAGUARD_TOKEN", " " * 40)
    with TestClient(create_app(f"sqlite:///{tmp_path / 'auth.db'}")) as client:
        assert client.post("/recover").status_code == 503


def test_control_character_identifiers_are_contract_errors():
    payload = fixture_payload()
    payload["trades"][0]["trade_id"] = "bad\x00identifier"
    errors = validate(payload, datetime.now(UTC))
    assert any(e["field"] == "trade_id" and e["rule"] == "allowed_value" for e in errors)


def test_streamed_oversized_body_is_rejected_before_publication(tmp_path, monkeypatch):
    monkeypatch.setenv("DATAGUARD_TOKEN", "a" * 32)
    with TestClient(create_app(f"sqlite:///{tmp_path / 'size.db'}")) as client:
        result = client.post(
            "/batches",
            content=iter([b"a" * 4_000_001, b"b" * 4_000_001]),
            headers={"Authorization": "Bearer " + "a" * 32},
        )
        assert result.status_code == 413
        assert client.get("/snapshots").json() == []
