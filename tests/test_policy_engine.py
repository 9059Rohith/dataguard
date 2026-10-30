"""Actual retained SQL versions, independent decisions, and read-only safety."""

import copy
import json

import pytest
from sqlalchemy import event, text
from sqlalchemy.exc import DBAPIError
from test_pipeline import fixture_payload
from test_policy_models import amount_rule, policy

from dataguard.policy_engine import PolicyBudgetExceeded, PolicyLab, read_snapshot
from dataguard.policy_models import ImpactRequest

pytest_plugins = ["test_pipeline"]


def published_versions(pipeline):
    body = fixture_payload()
    body["trades"][0]["trade_id"] = "secret-trade-alpha"
    body["trades"][0]["settlement_id"] = "secret-settlement"
    body["settlements"][0]["settlement_id"] = "secret-settlement"
    body["trades"].append(dict(body["trades"][0], trade_id="secret-trade-beta", amount_cents=800))
    body["settlements"][0]["amount_cents"] = 2000
    first = pipeline.stage("secret-source-key-one", body)
    assert pipeline.process(first)["status"] == "published"
    second = copy.deepcopy(body)
    second["trades"][0]["amount_cents"] = 1800
    second["settlements"][0]["amount_cents"] = 2600
    last = pipeline.stage("secret-source-key-two", second)
    assert pipeline.process(last)["status"] == "published"
    return body["period"], first, last


def experiment(period, ids, baseline=None, candidate=None, samples=3):
    return ImpactRequest.model_validate(
        {
            "baseline": baseline or policy(),
            "candidate": candidate or policy(amount_rule()),
            "versions": [{"period": period, "batch_id": batch_id} for batch_id in ids],
            "sample_limit": samples,
        }
    )


def test_detects_false_rejection_on_retained_version_without_mutation(pipeline):
    period, first, last = published_versions(pipeline)
    snapshots = pipeline.snapshots()
    attempts = pipeline.summary()
    current = pipeline.current(period)
    strict = amount_rule()
    strict["maximum"] = 1500
    result = PolicyLab(pipeline.engine).impact(
        experiment(period, [first, last], candidate=policy(strict))
    )
    assert result.summary.model_dump() == {
        "evaluated_versions": 2,
        "unchanged_accept": 1,
        "new_rejection": 1,
        "new_acceptance": 0,
        "unchanged_reject": 0,
    }
    assert [version.transition for version in result.versions] == [
        "unchanged_accept",
        "new_rejection",
    ]
    assert result.versions[1].candidate.rules[0].violation_count == 1
    assert result.recommendation.stage == "block_candidate"
    assert not result.recommendation.installs_policy
    assert pipeline.snapshots() == snapshots
    assert pipeline.summary() == attempts
    assert pipeline.current(period) == current
    assert result.versions[0].provenance.sha256 == pipeline.batch(first)["digest"]
    assert result.versions[0].provenance.attempt_id == pipeline.batch(first)["attempts"][-1]["id"]
    rendered = result.model_dump_json()
    for secret in ["secret-trade", "secret-settlement", "secret-source-key", "1800", '"USD"']:
        assert secret not in rendered


def test_sql_rule_semantics_and_report_local_samples(pipeline):
    period, first, last = published_versions(pipeline)
    rules = [
        {
            "id": "categories",
            "kind": "categories",
            "table": "trades",
            "field": "currency",
            "values": ["EUR"],
        },
        {"id": "complete", "kind": "complete", "table": "trades", "field": "event_time"},
        {"id": "unique", "kind": "unique", "table": "trades", "field": "settlement_id"},
        {"id": "primary-key", "kind": "unique", "table": "trades", "field": "trade_id"},
        {"id": "refs", "kind": "reference", "match_currency": True},
        {"id": "totals", "kind": "totals", "tolerance_cents": 0},
        {"id": "fresh", "kind": "freshness", "max_age_seconds": 86400},
    ]
    request = experiment(
        period, [first, last], baseline=policy(*rules), candidate=policy(*rules), samples=1
    )
    report = PolicyLab(pipeline.engine).impact(request)
    version = report.versions[0]
    counts = {rule.id: rule.violation_count for rule in version.candidate.rules}
    assert counts == {
        "categories": 2,
        "complete": 0,
        "unique": 2,
        "primary-key": 0,
        "refs": 0,
        "totals": 0,
        "fresh": 0,
    }
    category = next(rule for rule in version.candidate.rules if rule.id == "categories")
    assert category.evaluated_rows == 2
    assert len(category.sample_tokens) == 1 and len(category.sample_tokens[0]) == 64
    assert category.samples_truncated
    assert version.baseline.rules == version.candidate.rules
    second = PolicyLab(pipeline.engine).impact(request)
    assert second.candidate_sha256 == report.candidate_sha256
    assert second.versions[0].candidate.rules[0].sample_tokens != category.sample_tokens
    assert report.recommendation.stage == "shadow_only"


def test_classifies_all_decision_transitions_and_removed_protection(pipeline):
    period, first, last = published_versions(pipeline)
    strict = amount_rule()
    strict["maximum"] = 1000
    rejected = policy(strict)
    accepted = policy(amount_rule())
    lab = PolicyLab(pipeline.engine)
    assert (
        lab.impact(experiment(period, [first], rejected, accepted)).versions[0].transition
        == "new_acceptance"
    )
    assert (
        lab.impact(experiment(period, [first], rejected, rejected)).versions[0].transition
        == "unchanged_reject"
    )
    report = lab.impact(experiment(period, [first], accepted, policy()))
    assert report.versions[0].transition == "unchanged_accept"
    assert report.versions[0].rule_changes[0].change == "removed"
    assert report.recommendation.stage == "shadow_only"
    assert (
        lab.impact(experiment(period, [first, last], accepted, accepted)).recommendation.stage
        == "limited_canary"
    )


def test_freshness_is_relative_to_publication_not_experiment_clock(pipeline):
    period, first, _ = published_versions(pipeline)
    with pipeline.engine.begin() as c:
        # Fixed test publication age: event precedes publication by precisely one hour.
        from datetime import datetime

        event_time = pipeline.batch(first)["payload"]["trades"][0]["event_time"]
        publication = datetime.fromisoformat(event_time).timestamp() + 3600
        c.execute(
            text("UPDATE attempts SET finished_at=:stamp WHERE batch_id=:id"),
            {"stamp": publication, "id": first},
        )
    loose = policy({"id": "fresh", "kind": "freshness", "max_age_seconds": 3600})
    tight = policy({"id": "fresh", "kind": "freshness", "max_age_seconds": 3599})
    report = PolicyLab(pipeline.engine).impact(experiment(period, [first], loose, tight))
    assert report.versions[0].baseline.accepted
    assert report.versions[0].candidate.rules[0].violation_count == 2
    assert report.versions[0].transition == "new_rejection"


@pytest.mark.parametrize(
    "state", ["staged", "rejected", "failed", "superseded", "wrong_period", "missing"]
)
def test_only_exact_successfully_published_versions_are_eligible(pipeline, state):
    period, first, last = published_versions(pipeline)
    body = fixture_payload()
    selected = pipeline.stage("unpublished", body)
    if state == "rejected":
        body["trades"][0]["amount_cents"] = 0
        selected = pipeline.stage("invalid", body)
        pipeline.process(selected)
    elif state == "failed":
        with pytest.raises(RuntimeError):
            pipeline.process(selected, fault="after_insert")
    elif state == "superseded":
        selected = pipeline.stage("old", body)
        newer = pipeline.stage("newer", body)
        pipeline.process(newer)
        assert pipeline.process(selected)["status"] == "superseded"
    elif state == "wrong_period":
        selected = first
        period = "2001-01-01"
    elif state == "missing":
        selected = 2147483647
    with pytest.raises(KeyError):
        PolicyLab(pipeline.engine).impact(experiment(period, [selected]))


def test_read_snapshot_rejects_writes_and_restores_connection(pipeline):
    with pytest.raises(DBAPIError), read_snapshot(pipeline.engine) as c:
        c.execute(text("UPDATE publication_gate SET revision=revision+1"))
    with pipeline.engine.begin() as c:
        c.execute(text("UPDATE publication_gate SET revision=revision+1"))
    with read_snapshot(pipeline.engine) as c:
        assert c.execute(text("SELECT count(*) FROM publication_gate")).scalar() == 1
        if pipeline.engine.dialect.name == "postgresql":
            assert c.exec_driver_sql("SHOW statement_timeout").scalar() == "10s"
            assert c.exec_driver_sql("SHOW transaction_isolation").scalar() == "repeatable read"


def test_statement_budget_aborts_work_and_does_not_poison_pool(pipeline):
    with pytest.raises(PolicyBudgetExceeded), read_snapshot(pipeline.engine, seconds=0):
        pass
    assert pipeline.ready()


def test_rule_delta_marks_definition_change_even_with_equal_counts(pipeline):
    period, first, _ = published_versions(pipeline)
    loose = amount_rule()
    loose["maximum"] = 1900
    report = PolicyLab(pipeline.engine).impact(
        experiment(period, [first], policy(amount_rule()), policy(loose))
    )
    delta = report.versions[0].rule_changes[0]
    assert delta.change == "same_count" and delta.definition_changed
    assert delta.baseline_violations == delta.candidate_violations == 0


def test_no_staged_json_or_sensitive_columns_are_loaded(pipeline):
    period, first, last = published_versions(pipeline)
    statements = []

    def inspect(_c, _cursor, statement, _params, _context, _many):
        statements.append(statement.lower())

    event.listen(pipeline.engine, "before_cursor_execute", inspect)
    try:
        report = PolicyLab(pipeline.engine).impact(experiment(period, [first, last], samples=0))
    finally:
        event.remove(pipeline.engine, "before_cursor_execute", inspect)
    assert report.versions[0].candidate.rules[0].sample_tokens == []
    assert not any("batches.key" in statement for statement in statements)
    assert not any("select batches.payload" in statement for statement in statements)
    assert json.loads(report.model_dump_json())["source"] == "immutable_published_sql"


def test_category_reordering_does_not_claim_a_definition_change(pipeline):
    period, first, _ = published_versions(pipeline)
    rule = {
        "id": "currency",
        "kind": "categories",
        "table": "trades",
        "field": "currency",
        "values": ["USD", "EUR"],
    }
    reordered = dict(rule, values=["EUR", "USD"])
    report = PolicyLab(pipeline.engine).impact(
        experiment(period, [first], policy(rule), policy(reordered))
    )
    assert report.baseline_sha256 == report.candidate_sha256
    assert report.versions[0].rule_changes[0].definition_changed is False


def test_snapshot_does_not_mix_concurrent_committed_revisions(pipeline):
    if pipeline.engine.dialect.name == "sqlite":
        with pipeline.engine.connect() as c:
            c.exec_driver_sql("PRAGMA journal_mode=WAL")
    with read_snapshot(pipeline.engine) as c:
        before = c.execute(text("SELECT revision FROM publication_gate WHERE id=1")).scalar_one()
        with pipeline.engine.begin() as other:
            other.execute(text("UPDATE publication_gate SET revision=revision+1 WHERE id=1"))
        assert (
            c.execute(text("SELECT revision FROM publication_gate WHERE id=1")).scalar_one()
            == before
        )
    with pipeline.engine.connect() as c:
        assert (
            c.execute(text("SELECT revision FROM publication_gate WHERE id=1")).scalar_one()
            == before + 1
        )


def test_corrupted_source_above_admission_size_is_refused_before_rule_evaluation(pipeline):
    from dataguard.service import trades

    period, first, _ = published_versions(pipeline)
    template = pipeline.current(period)["trades"][0]
    # Simulate an operator bypassing admission, not a supported ingestion path.
    with pipeline.engine.begin() as c:
        c.execute(
            trades.insert(),
            [dict(template, batch_id=first, trade_id=f"oversize-{i}") for i in range(9999)],
        )
    with pytest.raises(PolicyBudgetExceeded, match="row budget"):
        PolicyLab(pipeline.engine).impact(experiment(period, [first]))


def test_cross_table_checks_detect_adverse_storage_and_apply_inclusive_tolerance(pipeline):
    period, first, _ = published_versions(pipeline)
    # Storage-adversarial test: normal publication forbids both inconsistencies.
    with pipeline.engine.begin() as c:
        c.execute(
            text(
                "UPDATE published_settlements SET amount_cents=1001,currency='EUR' WHERE batch_id=:id"
            ),
            {"id": first},
        )
    baseline = policy(
        {"id": "total", "kind": "totals", "tolerance_cents": 999},
        {"id": "ref", "kind": "reference", "match_currency": False},
    )
    candidate = policy(
        {"id": "total", "kind": "totals", "tolerance_cents": 998},
        {"id": "ref", "kind": "reference", "match_currency": True},
    )
    report = PolicyLab(pipeline.engine).impact(experiment(period, [first], baseline, candidate))
    version = report.versions[0]
    assert version.baseline.accepted
    assert {rule.id: rule.violation_count for rule in version.candidate.rules} == {
        "ref": 2,
        "total": 1,
    }
    assert version.transition == "new_rejection"


def test_completeness_and_freshness_handle_invalid_stored_text_without_leaking_it(pipeline):
    period, first, _ = published_versions(pipeline)
    with pipeline.engine.begin() as c:
        c.execute(
            text(
                "UPDATE published_trades SET currency='   ',event_time='secret-invalid-time' WHERE batch_id=:id"
            ),
            {"id": first},
        )
    candidate = policy(
        {"id": "complete", "kind": "complete", "table": "trades", "field": "currency"},
        {"id": "fresh", "kind": "freshness", "max_age_seconds": 86400},
    )
    report = PolicyLab(pipeline.engine).impact(experiment(period, [first], candidate=candidate))
    assert [rule.violation_count for rule in report.versions[0].candidate.rules] == [2, 2]
    assert "secret-invalid-time" not in report.model_dump_json()


def test_active_query_deadline_cancels_database_work_and_pool_recovers(pipeline):
    with pytest.raises(PolicyBudgetExceeded), read_snapshot(pipeline.engine, seconds=0.02) as c:
        if pipeline.engine.dialect.name == "postgresql":
            c.exec_driver_sql("SELECT pg_sleep(0.2)")
        else:
            c.exec_driver_sql(
                "WITH RECURSIVE work(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM work WHERE n<100000000) SELECT sum(n) FROM work"
            ).scalar_one()
    assert pipeline.ready()


def test_removed_published_rows_are_not_evidence_of_a_passing_policy(pipeline):
    period, first, _ = published_versions(pipeline)
    with pipeline.engine.begin() as c:
        c.execute(text("DELETE FROM published_trades WHERE batch_id=:id"), {"id": first})
    with pytest.raises(KeyError):
        PolicyLab(pipeline.engine).impact(experiment(period, [first]))


def test_empty_policy_and_changed_definitions_remain_shadow_only_without_new_rejections(pipeline):
    period, first, last = published_versions(pipeline)
    lab = PolicyLab(pipeline.engine)
    empty = lab.impact(experiment(period, [first, last], policy(), policy()))
    assert empty.summary.unchanged_accept == 2
    assert empty.recommendation.stage == "shadow_only"


def test_widened_same_id_rule_does_not_infer_safety_from_equal_sampled_counts(pipeline):
    period, first, last = published_versions(pipeline)
    lab = PolicyLab(pipeline.engine)
    widened = amount_rule()
    widened["maximum"] = 3000
    report = lab.impact(experiment(period, [first, last], policy(amount_rule()), policy(widened)))
    assert report.summary.unchanged_accept == 2
    assert report.recommendation.stage == "shadow_only"
    assert all(version.rule_changes[0].definition_changed for version in report.versions)
