"""PolicyLab v1 language and wire contracts. No expressions or SQL are accepted."""

import hashlib
import json
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

TableName = Literal["trades", "settlements"]
TextField = Literal["trade_id", "settlement_id", "currency", "event_time"]
RuleId = Annotated[str, Field(pattern=r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$", max_length=64)]
MinorUnits = Annotated[int, Field(ge=-(10**12), le=10**12)]
BatchNumber = Annotated[int, Field(ge=1, le=2_147_483_647)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class RuleBase(StrictModel):
    id: RuleId


class RangeRule(RuleBase):
    """Inclusive minor-unit bounds; null is always a violation."""

    kind: Literal["range"]
    table: TableName
    field: Literal["amount_cents"]
    minimum: MinorUnits
    maximum: MinorUnits

    @model_validator(mode="after")
    def ordered(self):
        if self.minimum > self.maximum:
            raise ValueError("minimum must not exceed maximum")
        return self


class CategoriesRule(RuleBase):
    kind: Literal["categories"]
    table: TableName
    field: Literal["currency"]
    values: Annotated[
        list[Annotated[str, Field(pattern=r"^[A-Z]{3}$", max_length=3)]],
        Field(min_length=1, max_length=6),
    ]

    @field_validator("values")
    @classmethod
    def unique_categories(cls, values):
        from dataguard.contracts import CURRENCIES

        if len(set(values)) != len(values) or not set(values) <= CURRENCIES:
            raise ValueError("categories must be distinct supported currencies")
        return values


class TextRule(RuleBase):
    table: TableName
    field: TextField

    @model_validator(mode="after")
    def existing_column(self):
        if self.table == "settlements" and self.field in {"trade_id", "event_time"}:
            raise ValueError("field does not exist in selected table")
        return self


class CompleteRule(TextRule):
    """Require non-null, nonempty text after SQL TRIM (ASCII spaces)."""

    kind: Literal["complete"]


class UniqueRule(TextRule):
    """Each member of a repeated value group is counted, including repeated nulls."""

    kind: Literal["unique"]


class FreshnessRule(RuleBase):
    """Event age relative to immutable successful publication time, never current time."""

    kind: Literal["freshness"]
    max_age_seconds: Annotated[int, Field(ge=0, le=604800)]
    future_tolerance_seconds: Annotated[int, Field(ge=0, le=86400)] = 300


class ReferenceRule(RuleBase):
    kind: Literal["reference"]
    match_currency: bool = True


class TotalsRule(RuleBase):
    """One violation per settlement outside the absolute minor-unit tolerance."""

    kind: Literal["totals"]
    tolerance_cents: Annotated[int, Field(ge=0, le=10**12)] = 0


Rule = Annotated[
    RangeRule
    | CategoriesRule
    | CompleteRule
    | UniqueRule
    | FreshnessRule
    | ReferenceRule
    | TotalsRule,
    Field(discriminator="kind"),
]


class Policy(StrictModel):
    version: Literal[1]
    rules: Annotated[list[Rule], Field(max_length=16)]

    @field_validator("version", mode="before")
    @classmethod
    def integer_version(cls, value):
        # Literal accepts bool==1 in some Pydantic releases; explicitly forbid it.
        if type(value) is not int:
            raise ValueError("version must be integer 1")
        return value

    @field_validator("rules")
    @classmethod
    def distinct_ids(cls, rules):
        if len({rule.id for rule in rules}) != len(rules):
            raise ValueError("rule IDs must be unique within a policy")
        return rules

    def canonical_json(self) -> str:
        document = self.model_dump()
        document["rules"].sort(key=lambda rule: rule["id"])
        for rule in document["rules"]:
            if rule["kind"] == "categories":
                rule["values"].sort()
        return json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False)

    def digest(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()


class VersionSelection(StrictModel):
    period: Annotated[str, Field(min_length=10, max_length=10)]
    batch_id: BatchNumber

    @field_validator("period")
    @classmethod
    def canonical_period(cls, value):
        if date.fromisoformat(value).isoformat() != value:
            raise ValueError("period must be canonical YYYY-MM-DD")
        return value


class ImpactRequest(StrictModel):
    baseline: Policy
    candidate: Policy
    versions: Annotated[list[VersionSelection], Field(min_length=1, max_length=8)]
    sample_limit: Annotated[int, Field(ge=0, le=5)] = 3

    @field_validator("versions")
    @classmethod
    def unique_versions(cls, values):
        if len({value.batch_id for value in values}) != len(values):
            raise ValueError("select each batch only once")
        return values


class PolicyProvenance(StrictModel):
    period: str
    batch_id: int
    sha256: str
    attempt_id: int
    published_at: float


class RuleOutcome(StrictModel):
    id: str
    kind: str
    table: TableName
    evaluated_rows: int
    violation_count: int
    sample_tokens: list[str]
    samples_truncated: bool


class PolicyOutcome(StrictModel):
    policy_sha256: str
    accepted: bool
    failed_rules: int
    rules: list[RuleOutcome]


Transition = Literal["unchanged_accept", "new_rejection", "new_acceptance", "unchanged_reject"]
RuleChange = Literal["added", "removed", "more_violations", "fewer_violations", "same_count"]


class RuleDelta(StrictModel):
    id: str
    change: RuleChange
    definition_changed: bool
    baseline_violations: int | None
    candidate_violations: int | None


class VersionImpact(StrictModel):
    provenance: PolicyProvenance
    baseline: PolicyOutcome
    candidate: PolicyOutcome
    transition: Transition
    rule_changes: list[RuleDelta]


class ImpactSummary(StrictModel):
    evaluated_versions: int
    unchanged_accept: int
    new_rejection: int
    new_acceptance: int
    unchanged_reject: int


class RolloutRecommendation(StrictModel):
    stage: Literal["block_candidate", "shadow_only", "limited_canary"]
    reasons: list[str]
    requires_operator_review: Literal[True] = True
    installs_policy: Literal[False] = False


class ImpactReport(StrictModel):
    report_version: Literal[1] = 1
    baseline_sha256: str
    candidate_sha256: str
    source: Literal["immutable_published_sql"] = "immutable_published_sql"
    freshness_reference: Literal["successful_publication_time"] = "successful_publication_time"
    sample_scope: Literal["opaque_report_local_not_reidentifiable_without_secret"] = (
        "opaque_report_local_not_reidentifiable_without_secret"
    )
    summary: ImpactSummary
    versions: list[VersionImpact]
    recommendation: RolloutRecommendation
    limitations: list[str]
