"""The experiment surface stays private, typed, bounded and non-disclosing."""

import json
import os
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient
from test_policy_engine import published_versions
from test_policy_models import amount_rule, policy

from dataguard.api import create_app
from dataguard.policy_io import load_impact_file
from dataguard.service import Pipeline

TOKEN = "policylab-operator-token-with-at-least-32-characters"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}


def document(period, first, last):
    cap = amount_rule()
    cap["maximum"] = 1500
    return {
        "baseline": policy(),
        "candidate": policy(cap),
        "versions": [{"period": period, "batch_id": first}, {"period": period, "batch_id": last}],
    }


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATAGUARD_TOKEN", TOKEN)
    monkeypatch.setenv("DATAGUARD_PUBLIC_DEMO", "true")
    monkeypatch.setenv("DATAGUARD_SEED_DEMO", "false")
    with TestClient(create_app(f"sqlite:///{tmp_path / 'policy.db'}")) as client:
        yield client


def test_private_api_has_typed_report_and_leaves_publication_state_unchanged(client):
    pipeline = client.app.state.pipeline
    period, first, last = published_versions(pipeline)
    body = document(period, first, last)
    before = pipeline.current(period)
    assert client.post("/policies/impact", json=body).status_code == 401
    response = client.post("/policies/impact", json=body, headers=HEADERS)
    assert response.status_code == 200, response.text
    assert response.json()["summary"]["new_rejection"] == 1
    assert response.json()["recommendation"]["stage"] == "block_candidate"
    assert "secret-" not in response.text
    assert response.headers["Cache-Control"] == "no-store"
    assert pipeline.current(period) == before
    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/policies/impact"]["post"]
    assert operation["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/ImpactRequest"
    )
    assert operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/ImpactReport"
    )


@pytest.mark.parametrize(
    "malformed",
    [
        {"baseline": {"version": 1, "rules": [{"id": "x", "kind": "secret-raw-input"}]}},
        {"unknown-secret-field": "secret-raw-input"},
        {"baseline": "secret-raw-input"},
    ],
)
def test_invalid_policy_errors_do_not_reflect_values_or_field_names(client, malformed):
    response = client.post("/policies/impact", json=malformed, headers=HEADERS)
    assert response.status_code == 422
    assert "secret" not in response.text
    assert response.json() == {"detail": "Invalid policy request"}


def test_unpublished_and_wrong_period_are_indistinguishable(client):
    period, first, last = published_versions(client.app.state.pipeline)
    body = document(period, first, last)
    body["versions"][0]["period"] = "2001-01-01"
    wrong = client.post("/policies/impact", json=body, headers=HEADERS)
    body["versions"][0] = {"period": period, "batch_id": 2147483647}
    absent = client.post("/policies/impact", json=body, headers=HEADERS)
    assert wrong.status_code == absent.status_code == 404
    assert wrong.json() == absent.json() == {"detail": "Record not found"}


def test_policy_body_is_bounded_before_parsing_and_duplicate_keys_are_rejected(client):
    huge = '{"baseline":"' + "secret" * 12000 + '"}'
    response = client.post("/policies/impact", content=huge, headers=HEADERS)
    assert response.status_code == 413
    duplicate = '{"baseline":{},"baseline":{"secret":"value"}}'
    response = client.post("/policies/impact", content=duplicate, headers=HEADERS)
    assert response.status_code == 422
    assert "secret" not in response.text
    assert client.post("/policies/impact", content=huge).status_code == 401


def test_policy_file_reader_rejects_nonfinite_duplicates_and_oversize(tmp_path):
    path = tmp_path / "policy.json"
    for raw in ['{"baseline":NaN}', '{"baseline":{},"baseline":{}}', "[" * 40, " " * 65537]:
        path.write_text(raw)
        with pytest.raises(ValueError):
            load_impact_file(path)


def test_cli_checks_operator_token_and_executes_same_readonly_report(tmp_path):
    url = f"sqlite:///{tmp_path / 'cli-policy.db'}"
    pipeline = Pipeline(url)
    pipeline.initialize()
    period, first, last = published_versions(pipeline)
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(document(period, first, last)))
    command = [sys.executable, "-m", "dataguard.cli", "--database", url, "policy-impact", str(path)]
    env = dict(os.environ, DATAGUARD_TOKEN=TOKEN, DATAGUARD_OPERATOR_TOKEN="incorrect")
    denied = subprocess.run(
        command, env=env, capture_output=True, text=True, timeout=20, check=False
    )
    assert denied.returncode == 2
    assert "Invalid operator token" in denied.stderr
    env["DATAGUARD_OPERATOR_TOKEN"] = TOKEN
    result = subprocess.run(
        command, env=env, capture_output=True, text=True, timeout=20, check=False
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["summary"]["new_rejection"] == 1
    assert report["recommendation"]["installs_policy"] is False
    assert "secret-" not in result.stdout
    assert pipeline.summary() == {"published": 2}


def test_cli_validation_failure_never_prints_operator_token_or_input(tmp_path):
    path = tmp_path / "bad-policy.json"
    path.write_text('{"secret-source":"private-value"}')
    env = dict(os.environ, DATAGUARD_TOKEN=TOKEN, DATAGUARD_OPERATOR_TOKEN=TOKEN)
    result = subprocess.run(
        [sys.executable, "-m", "dataguard.cli", "policy-impact", str(path)],
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 2
    assert "Invalid policy request" in result.stderr
    assert "secret-source" not in result.stderr
    assert "private-value" not in result.stderr
    assert TOKEN not in result.stderr


def test_controlled_cli_does_not_construct_or_connect_the_operator_database():
    env = dict(
        os.environ,
        DATABASE_URL="unsupported://must-not-be-used",
        DATAGUARD_TOKEN=TOKEN,
        DATAGUARD_OPERATOR_TOKEN=TOKEN,
    )
    result = subprocess.run(
        [sys.executable, "-m", "dataguard.cli", "policy-evaluate"],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert (
        json.loads(result.stdout)["environment"]["database_scope"]
        == "disposable_temporary_directory"
    )
