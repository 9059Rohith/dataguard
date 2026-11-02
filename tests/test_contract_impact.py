import copy
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dataguard.api import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATAGUARD_TOKEN", "test-contract-impact-operator-0000000000")
    with TestClient(create_app(f"sqlite:///{tmp_path / 'impact.db'}")) as client:
        yield client


def request(client):
    capture = client.get("/api/quality/workspace").json()["captures"][0]
    return {
        "capture_id": capture["id"],
        "analysis_at": capture["captured_at"],
        "baseline": {},
        "candidate": {},
    }, capture


def test_actual_capture_transitions_witnesses_and_no_writes(client):
    body, capture = request(client)
    before = client.get("/api/quality/workspace").json()
    body["candidate"] = {"accepted_languages": ["Rust"]}
    response = client.post("/api/quality/contract-impact", json=body)
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["transitions"]["accepted_to_rejected"] == len(capture["records"])
    assert report["capture"]["sha256"] == capture["digest"]
    assert report["capture"]["id"] == capture["id"]
    assert report["candidate"]["rules"]["language"]["failed"] == 8
    for result, row in zip(report["records"], capture["records"], strict=True):
        assert result["identity"] == row["full_name"]
        assert result["candidate"]["checks"][1]["actual"] == row["language"]
        assert "Rust" in result["candidate"]["checks"][1]["expected"]
    after = client.get("/api/quality/workspace").json()
    for field in ("captures", "contract", "actions", "restored"):
        assert after[field] == before[field]
    assert client.post("/api/quality/contract-impact", json=body).json() == report


def test_freshness_clock_and_thresholds_are_exact(client):
    body, capture = request(client)
    body["candidate"] = {"max_push_age_hours": 0, "min_stars": 100000}
    report = client.post("/api/quality/contract-impact", json=body).json()
    assert report["candidate"]["rules"]["freshness"]["failed"] == 8
    assert report["candidate"]["rules"]["min_stars"]["failed"] == sum(
        row["stargazers_count"] < 100000 for row in capture["records"]
    )
    body["analysis_at"] = "2020-01-01T00:00:00Z"
    assert client.post("/api/quality/contract-impact", json=body).status_code == 422


@pytest.mark.parametrize(
    "change",
    [
        {"baseline": {"min_stars": True}},
        {"baseline": {"min_stars": "10"}},
        {"candidate": {"sql": "SELECT secret"}},
        {"candidate": {"accepted_languages": ["x"] * 13}},
        {"candidate": {"required_metadata": ["secret"]}},
        {"candidate": {"max_push_age_hours": -1}},
        {"analysis_at": "2026-11-02T00:00:00"},
    ],
)
def test_strict_declarative_input(client, change):
    body, _ = request(client)
    body.update(change)
    response = client.post("/api/quality/contract-impact", json=body)
    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid public contract request"}


def test_public_boundary_private_unknown_origin_and_body(client):
    body, _ = request(client)
    headers = {"Authorization": "Bearer test-contract-impact-operator-0000000000"}
    private = client.post(
        "/api/quality/uploads", headers=headers, json={"name": "private", "records": [{"id": 123}]}
    ).json()
    for identity in (private["id"], "unknown-capture"):
        body["capture_id"] = identity
        response = client.post("/api/quality/contract-impact", json=body, headers=headers)
        assert response.status_code == 404
        assert "private" not in response.text
    assert (
        client.post(
            "/api/quality/contract-impact", json=body, headers={"Origin": "https://evil.example"}
        ).status_code
        == 403
    )
    assert client.post("/api/quality/contract-impact", content=b"x" * 16385).status_code == 413
    raw = json.dumps(body).replace('"baseline": {}', '"baseline": {}, "baseline": {}')
    assert client.post("/api/quality/contract-impact", content=raw).status_code == 422
    assert client.post("/api/quality/recheck", json=body).status_code == 401


def test_engine_fails_missing_bad_types_future_and_metadata():
    from dataguard.contract_impact import RepositoryContract, evaluate_repository

    row = {
        "id": 1,
        "full_name": "owner/repo",
        "stargazers_count": True,
        "archived": "false",
        "pushed_at": "2026-11-03T00:00:00Z",
        "license": {},
    }
    contract = RepositoryContract(
        required_metadata=["license"], reject_archived=True, max_push_age_hours=24
    )
    result = evaluate_repository(row, contract, "2026-11-02T00:00:00Z")
    assert not result["accepted"]
    checks = {item["rule"]: item for item in result["checks"]}
    assert all(
        not checks[key]["success"] for key in ("metadata", "archived", "freshness", "min_stars")
    )
    assert "future" in checks["freshness"]["explanation"]
    assert row["stargazers_count"] is True


def test_source_digest_and_visibility_fail_closed(client):
    from dataguard.contract_impact import ContractImpactRequest, compare_contracts, content_hash

    body, capture = request(client)
    parsed = ContractImpactRequest.model_validate(body)
    for key, value in (
        ("visibility", "private"),
        ("digest", "0" * 64),
        ("source", "https://untrusted.example"),
    ):
        changed = copy.deepcopy(capture)
        changed[key] = value
        with pytest.raises(Exception) as error:
            compare_contracts(changed, parsed)
        assert error.value.status_code == 404
    response = client.post("/api/quality/contract-impact", json=body).json()
    expected = response.pop("sha256")
    assert content_hash(response) == expected


def test_openlineage_facet_validates_offline_and_catches_invalid_success(client):
    from jsonschema import Draft202012Validator, FormatChecker
    from referencing import Registry, Resource

    body, _ = request(client)
    body["candidate"] = {"accepted_languages": ["Rust"]}
    report = client.post("/api/quality/contract-impact", json=body).json()
    root = Path(__file__).parents[1] / "docs" / "schemas"
    facet = json.loads((root / "DataQualityAssertionsDatasetFacet.json").read_text())
    core = json.loads((root / "OpenLineage.json").read_text())
    registry = Registry().with_resources(
        [(core["$id"], Resource.from_contents(core)), (facet["$id"], Resource.from_contents(facet))]
    )
    schema = {"$ref": facet["$id"] + "#/$defs/DataQualityAssertionsDatasetFacet"}
    validator = Draft202012Validator(schema, registry=registry, format_checker=FormatChecker())
    validator.validate(report["openlineage_facet"])
    assert len(report["openlineage_facet"]["assertions"]) == 3
    assert all(item["params"]["enabled"] for item in report["openlineage_facet"]["assertions"])
    invalid = copy.deepcopy(report["openlineage_facet"])
    invalid["assertions"][0]["success"] = "true"
    assert list(validator.iter_errors(invalid))
