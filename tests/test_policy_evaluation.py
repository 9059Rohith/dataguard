"""Controlled scenarios are executable experiments, not invented model metrics."""

from dataguard.policy_evaluation import controlled_evaluation


def test_controlled_evaluation_measures_compatible_invalid_and_overstrict_policies():
    evidence = controlled_evaluation()
    assert evidence["scope"] == "controlled_synthetic_policy_decisions"
    assert evidence["published_versions"] == 3
    assert evidence["expected_decisions_match"]
    scenarios = {case["name"]: case for case in evidence["policy_scenarios"]}
    assert scenarios["compatible-cap"]["observed_acceptance"] == [True, True, True]
    assert scenarios["overstrict-cap"]["observed_acceptance"] == [True, False, True]
    assert scenarios["overstrict-currency"]["observed_acceptance"] == [True, True, False]
    assert scenarios["overstrict-settlement-uniqueness"]["observed_acceptance"] == [
        False,
        False,
        False,
    ]
    assert scenarios["compatible-cap"]["recommendation"] == "shadow_only"
    assert scenarios["overstrict-cap"]["recommendation"] == "block_candidate"
    assert scenarios["overstrict-cap"]["observed_violation_counts"] == [0, 1, 0]
    assert scenarios["overstrict-settlement-uniqueness"]["observed_violation_counts"] == [2, 2, 2]
    assert evidence["invalid_policy_cases"] == {
        "sql-column": "rejected",
        "boolean-bound": "rejected",
        "unknown-version": "rejected",
    }
    assert evidence["unpublished_cases"] == {
        "negative": "excluded",
        "duplicate": "excluded",
        "total-mismatch": "excluded",
    }
    assert evidence["mutation_check"] == "publication_state_unchanged"
    assert "production" in " ".join(evidence["limitations"]).lower()
    assert "precision" not in evidence and "accuracy" not in evidence
