"""Policy syntax must not become a SQL surface or silently coerce operator intent."""

import copy
import hashlib

import pytest
from pydantic import ValidationError

from dataguard.policy_models import ImpactRequest, Policy


def policy(*rules):
    return {"version": 1, "rules": list(rules)}


def amount_rule(**changes):
    return dict(
        id="amount-cap",
        kind="range",
        table="trades",
        field="amount_cents",
        minimum=1,
        maximum=2000,
        **changes,
    )


def test_hash_is_canonical_but_preserves_policy_meaning():
    category = {
        "id": "currencies",
        "kind": "categories",
        "table": "trades",
        "field": "currency",
        "values": ["USD", "EUR"],
    }
    first = Policy.model_validate(policy(amount_rule(), category))
    reordered = copy.deepcopy(category)
    reordered["values"].reverse()
    second = Policy.model_validate(policy(reordered, amount_rule()))
    assert first.canonical_json() == second.canonical_json()
    assert first.digest() == hashlib.sha256(first.canonical_json().encode()).hexdigest()
    changed = amount_rule()
    changed["maximum"] = 1999
    assert Policy.model_validate(policy(changed, category)).digest() != first.digest()
    assert first.digest() != Policy.model_validate(policy(category)).digest()


@pytest.mark.parametrize(
    "rule",
    [
        amount_rule(),
        {
            "id": "category",
            "kind": "categories",
            "table": "settlements",
            "field": "currency",
            "values": ["USD"],
        },
        {"id": "complete", "kind": "complete", "table": "trades", "field": "settlement_id"},
        {"id": "unique", "kind": "unique", "table": "trades", "field": "settlement_id"},
        {
            "id": "fresh",
            "kind": "freshness",
            "max_age_seconds": 86400,
            "future_tolerance_seconds": 300,
        },
        {"id": "refs", "kind": "reference", "match_currency": True},
        {"id": "totals", "kind": "totals", "tolerance_cents": 0},
    ],
)
def test_allowlisted_rules_roundtrip(rule):
    parsed = Policy.model_validate(policy(rule))
    assert Policy.model_validate_json(parsed.model_dump_json()) == parsed


@pytest.mark.parametrize(
    "change",
    [
        {"field": "amount_cents; DELETE FROM batches"},
        {"table": "batches"},
        {"field": "currency"},
        {"minimum": True},
        {"maximum": 2.5},
        {"maximum": "2000"},
        {"minimum": 3000},
        {"minimum": -(10**12) - 1},
        {"maximum": 10**12 + 1},
        {"sql": "1=1"},
        {"id": "bad\nrule"},
        {"id": "x" * 65},
        {"kind": "python"},
    ],
)
def test_range_rejects_unsafe_or_ambiguous_input(change):
    rule = amount_rule()
    rule.update(change)
    with pytest.raises(ValidationError):
        Policy.model_validate(policy(rule))


@pytest.mark.parametrize(
    "document",
    [
        {"version": True, "rules": []},
        {"version": "1", "rules": []},
        {"version": 2, "rules": []},
        {"version": 1, "rules": [], "sql": "SELECT 1"},
        policy(*[amount_rule() for _ in range(17)]),
        policy(amount_rule(), amount_rule()),
        policy(
            {
                "id": "cat",
                "kind": "categories",
                "table": "trades",
                "field": "trade_id",
                "values": ["USD"],
            }
        ),
        policy(
            {
                "id": "cat",
                "kind": "categories",
                "table": "trades",
                "field": "currency",
                "values": [],
            }
        ),
        policy(
            {
                "id": "cat",
                "kind": "categories",
                "table": "trades",
                "field": "currency",
                "values": ["USD", "USD"],
            }
        ),
        policy({"id": "unique", "kind": "unique", "table": "settlements", "field": "trade_id"}),
        policy({"id": "fresh", "kind": "freshness", "max_age_seconds": -1}),
        policy({"id": "fresh", "kind": "freshness", "max_age_seconds": 1.2}),
        policy({"id": "refs", "kind": "reference", "match_currency": 1}),
        policy({"id": "total", "kind": "totals", "tolerance_cents": -1}),
    ],
)
def test_document_rejects_unsupported_or_unbounded_policy(document):
    with pytest.raises(ValidationError):
        Policy.model_validate(document)


def request(**changes):
    return dict(
        baseline=policy(),
        candidate=policy(amount_rule()),
        versions=[{"period": "2026-10-30", "batch_id": 1}],
        **changes,
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("versions", []),
        ("versions", [{"period": "20261030", "batch_id": 1}]),
        ("versions", [{"period": "2026-10-30", "batch_id": True}]),
        ("versions", [{"period": "2026-10-30", "batch_id": 0}]),
        ("versions", [{"period": "2026-10-30", "batch_id": 2147483648}]),
        ("versions", [{"period": "2026-10-30", "batch_id": i} for i in range(1, 10)]),
        ("versions", [{"period": "2026-10-30", "batch_id": 1}] * 2),
        ("sample_limit", 6),
        ("sample_limit", -1),
        ("sample_limit", True),
    ],
)
def test_impact_bounds_are_shared_by_api_cli_and_python(field, value):
    document = request()
    document[field] = value
    with pytest.raises(ValidationError):
        ImpactRequest.model_validate(document)
