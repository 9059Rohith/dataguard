"""Small reproducible policy decision study, isolated from operator databases.

The expected outcomes below are literal scenario labels chosen before engine
execution. This measures these controlled decisions only, not model accuracy.
"""

import copy
import platform
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from dataguard.policy_engine import PolicyLab
from dataguard.policy_models import ImpactRequest, Policy
from dataguard.service import Pipeline


def _amount_policy(maximum):
    return {
        "version": 1,
        "rules": [
            {
                "id": "business-check",
                "kind": "range",
                "table": "trades",
                "field": "amount_cents",
                "minimum": 1,
                "maximum": maximum,
            }
        ],
    }


def _payload(now, amounts, currency):
    return {
        "period": now.date().isoformat(),
        "produced_at": now.isoformat(),
        "trades": [
            {
                "trade_id": f"synthetic-trade-{i}",
                "settlement_id": "synthetic-settlement",
                "amount_cents": amount,
                "currency": currency,
                "event_time": now.isoformat(),
            }
            for i, amount in enumerate(amounts)
        ],
        "settlements": [
            {
                "settlement_id": "synthetic-settlement",
                "currency": currency,
                "amount_cents": sum(amounts),
            }
        ],
    }


def _request(baseline, candidate, period, ids):
    return ImpactRequest.model_validate(
        {
            "baseline": baseline,
            "candidate": candidate,
            "sample_limit": 0,
            "versions": [{"period": period, "batch_id": batch_id} for batch_id in ids],
        }
    )


def _evaluate_in_disposable_database(pipeline):
    now = datetime.now(UTC)
    dataset = [
        _payload(now, [100, 200], "USD"),
        _payload(now, [100, 900], "USD"),
        _payload(now, [100, 200], "EUR"),
    ]
    ids = []
    for i, payload in enumerate(dataset):
        batch_id = pipeline.stage(f"controlled-version-{i}", payload)
        if pipeline.process(batch_id)["status"] != "published":
            raise RuntimeError("Controlled valid fixture was not published")
        ids.append(batch_id)
    period = dataset[0]["period"]
    baseline = _amount_policy(10000)
    scenarios = [
        ("compatible-cap", _amount_policy(2000), [True, True, True], [0, 0, 0]),
        ("overstrict-cap", _amount_policy(500), [True, False, True], [0, 1, 0]),
        (
            "overstrict-currency",
            {
                "version": 1,
                "rules": [
                    {
                        "id": "business-check",
                        "kind": "categories",
                        "table": "trades",
                        "field": "currency",
                        "values": ["USD"],
                    }
                ],
            },
            [True, True, False],
            [0, 0, 2],
        ),
        (
            "overstrict-settlement-uniqueness",
            {
                "version": 1,
                "rules": [
                    {
                        "id": "business-check",
                        "kind": "unique",
                        "table": "trades",
                        "field": "settlement_id",
                    }
                ],
            },
            [False, False, False],
            [2, 2, 2],
        ),
    ]
    lab = PolicyLab(pipeline.engine)
    state_before = (pipeline.snapshots(), pipeline.summary(), pipeline.current(period))
    results = []
    for name, candidate, expected, expected_counts in scenarios:
        report = lab.impact(_request(baseline, candidate, period, ids))
        observed = [version.candidate.accepted for version in report.versions]
        counts = [version.candidate.rules[0].violation_count for version in report.versions]
        # A failed expectation aborts the study instead of producing plausible metrics.
        if observed != expected or counts != expected_counts:
            raise RuntimeError("Controlled policy decisions differed from independent labels")
        results.append(
            {
                "name": name,
                "expected_acceptance": expected,
                "observed_acceptance": observed,
                "expected_violation_counts": expected_counts,
                "observed_violation_counts": counts,
                "baseline_sha256": report.baseline_sha256,
                "candidate_sha256": report.candidate_sha256,
                "newly_rejected_published_versions": report.summary.new_rejection,
                "recommendation": report.recommendation.stage,
            }
        )
    if state_before != (pipeline.snapshots(), pipeline.summary(), pipeline.current(period)):
        raise RuntimeError("Policy experiment changed publication state")

    invalid_policies = {}
    bad_column = _amount_policy(500)
    bad_column["rules"][0]["field"] = "amount_cents; DELETE FROM batches"
    boolean_bound = _amount_policy(True)
    unknown_version = dict(_amount_policy(500), version=2)
    for name, document in (
        ("sql-column", bad_column),
        ("boolean-bound", boolean_bound),
        ("unknown-version", unknown_version),
    ):
        try:
            Policy.model_validate(document)
        except ValidationError:
            invalid_policies[name] = "rejected"
        else:
            raise RuntimeError("Invalid policy was accepted")

    excluded = {}
    for fault in ("negative", "duplicate", "total-mismatch"):
        invalid = copy.deepcopy(dataset[0])
        if fault == "negative":
            invalid["trades"][0]["amount_cents"] = -1
        elif fault == "duplicate":
            invalid["trades"].append(copy.deepcopy(invalid["trades"][0]))
        else:
            invalid["settlements"][0]["amount_cents"] += 1
        batch_id = pipeline.stage(f"controlled-invalid-{fault}", invalid)
        if pipeline.process(batch_id)["status"] != "rejected":
            raise RuntimeError("Invalid controlled input was admitted")
        try:
            lab.impact(_request(baseline, baseline, period, [batch_id]))
        except KeyError:
            excluded[fault] = "excluded"
        else:
            raise RuntimeError("Unpublished controlled input was evaluated")

    return {
        "scope": "controlled_synthetic_policy_decisions",
        "generated_at": now.isoformat(),
        "environment": {
            "python": platform.python_version(),
            "database": "sqlite",
            "database_scope": "disposable_temporary_directory",
        },
        "published_versions": len(ids),
        "trades_per_version": 2,
        "settlements_per_version": 1,
        "dataset_recipe": [
            {"amounts_cents": [100, 200], "currency": "USD"},
            {"amounts_cents": [100, 900], "currency": "USD"},
            {"amounts_cents": [100, 200], "currency": "EUR"},
        ],
        "expected_decisions_match": True,
        "policy_scenarios": results,
        "invalid_policy_cases": invalid_policies,
        "unpublished_cases": excluded,
        "mutation_check": "publication_state_unchanged",
        "limitations": [
            "Three hand-constructed valid versions and four policy scenarios are a finite regression study.",
            "Synthetic values shown in the recipe are deliberately public; operator reports never include source values.",
            "Labels encode compatibility with these known valid synthetic fixtures, not general business correctness.",
            "No production accuracy, false-positive rate, statistical confidence, or model-performance estimate follows.",
            "Negative/duplicate/total-mismatch batches demonstrate admission and eligibility boundaries, not anomaly-model recall.",
        ],
    }


def controlled_evaluation():
    """Always create a disposable SQLite database; never use DATABASE_URL."""
    with tempfile.TemporaryDirectory(prefix="dataguard-policy-evaluation-") as directory:
        database = Path(directory) / "controlled.db"
        pipeline = Pipeline(f"sqlite:///{database.as_posix()}")
        try:
            pipeline.initialize()
            return _evaluate_in_disposable_database(pipeline)
        finally:
            pipeline.engine.dispose()
