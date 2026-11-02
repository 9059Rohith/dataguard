"""Bounded, pure repository acceptance experiments over immutable public evidence."""

import hashlib
import json
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

IMPACT_PATH = "/api/quality/contract-impact"
IMPACT_MAX_BYTES = 16384
FACET_SCHEMA = "https://openlineage.io/spec/facets/1-1-0/DataQualityAssertionsDatasetFacet.json"
MetadataField = Literal["id", "full_name", "description", "language", "license", "default_branch"]
Language = Annotated[str, Field(strict=True, min_length=1, max_length=40, pattern=r"^[\w#+. -]+$")]


def content_hash(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def clock(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None or not 2000 <= result.year <= 2100:
        raise ValueError("A timezone-aware clock between 2000 and 2100 is required")
    return result.astimezone(UTC)


class RepositoryContract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    required_metadata: list[MetadataField] = Field(default=["id", "full_name"], max_length=6)
    accepted_languages: list[Language] = Field(default_factory=list, max_length=12)
    reject_archived: bool = False
    max_push_age_hours: int | None = Field(default=None, ge=0, le=87600)
    min_stars: int = Field(default=0, ge=0, le=1_000_000_000)
    max_open_issues: int | None = Field(default=None, ge=0, le=1_000_000_000)

    @field_validator("required_metadata", "accepted_languages")
    @classmethod
    def unique(cls, value):
        if len(set(value)) != len(value):
            raise ValueError("Duplicate selection")
        return value


class ContractImpactRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    capture_id: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9-]+$")
    analysis_at: str = Field(min_length=20, max_length=40)
    baseline: RepositoryContract
    candidate: RepositoryContract

    @field_validator("analysis_at")
    @classmethod
    def valid_clock(cls, value):
        return clock(value).isoformat()


def evaluate_repository(row, contract, analysis_at):
    checks = []

    def add(rule, actual, expected, success, explanation, enabled=True):
        checks.append(
            {
                "rule": rule,
                "actual": actual,
                "expected": expected,
                "success": bool(success),
                "enabled": enabled,
                "explanation": explanation,
            }
        )

    missing = [
        field
        for field in contract.required_metadata
        if row.get(field) is None or row.get(field) in ("", [], {})
    ]
    add(
        "metadata",
        {field: row.get(field) for field in contract.required_metadata},
        contract.required_metadata,
        not missing,
        "Missing or empty: " + ", ".join(missing) if missing else "Required metadata is present.",
    )
    enabled = bool(contract.accepted_languages)
    add(
        "language",
        row.get("language"),
        contract.accepted_languages,
        not enabled or row.get("language") in contract.accepted_languages,
        "Exact source language must be in the accepted list."
        if enabled
        else "Any source language accepted.",
        enabled,
    )
    add(
        "archived",
        row.get("archived"),
        False if contract.reject_archived else "any",
        not contract.reject_archived or row.get("archived") is False,
        "Source archived flag must be exactly false."
        if contract.reject_archived
        else "Archive restriction disabled.",
        contract.reject_archived,
    )
    age = None
    valid_time = False
    reason = "Push freshness restriction disabled."
    if contract.max_push_age_hours is not None:
        try:
            age = (clock(analysis_at) - clock(row.get("pushed_at"))).total_seconds() / 3600
            valid_time = 0 <= age <= contract.max_push_age_hours
            reason = (
                "Source push is in the future relative to the analysis clock."
                if age < 0
                else f"Push age {age:.6f}h; maximum {contract.max_push_age_hours}h."
            )
        except (ValueError, TypeError, AttributeError, OverflowError):
            reason = "Source pushed_at is missing or invalid."
    add(
        "freshness",
        {"pushed_at": row.get("pushed_at"), "age_hours": age},
        contract.max_push_age_hours,
        contract.max_push_age_hours is None or valid_time,
        reason,
        contract.max_push_age_hours is not None,
    )
    stars = row.get("stargazers_count")
    add(
        "min_stars",
        stars,
        contract.min_stars,
        type(stars) is int and stars >= contract.min_stars,
        f"Source stars must be an integer ≥ {contract.min_stars}.",
    )
    issues = row.get("open_issues_count")
    add(
        "max_open_issues",
        issues,
        contract.max_open_issues,
        contract.max_open_issues is None
        or (type(issues) is int and 0 <= issues <= contract.max_open_issues),
        "GitHub open_issues_count includes issues and pull requests; this is a selection criterion."
        if contract.max_open_issues is not None
        else "Open issue count restriction disabled.",
        contract.max_open_issues is not None,
    )
    return {"accepted": all(check["success"] for check in checks), "checks": checks}


def compare_contracts(document, request):
    """No writes, network, implicit wall clock, or generated repository data."""
    from dataguard.quality import is_public_github_capture

    if (
        not is_public_github_capture(document)
        or not 1 <= len(document["records"]) <= 8
        or content_hash(document["records"]) != document.get("digest")
    ):
        raise HTTPException(404, "Public source capture not found")
    if clock(request.analysis_at) < clock(document["captured_at"]):
        raise HTTPException(422, "Analysis clock must be at or after source capture")
    records = []
    transitions = dict.fromkeys(
        [
            "accepted_to_accepted",
            "accepted_to_rejected",
            "rejected_to_accepted",
            "rejected_to_rejected",
        ],
        0,
    )
    for index, row in enumerate(document["records"]):
        baseline = evaluate_repository(row, request.baseline, request.analysis_at)
        candidate = evaluate_repository(row, request.candidate, request.analysis_at)
        transition = (
            ("accepted" if baseline["accepted"] else "rejected")
            + "_to_"
            + ("accepted" if candidate["accepted"] else "rejected")
        )
        transitions[transition] += 1
        records.append(
            {
                "index": index,
                "identity": row["full_name"],
                "repository_id": row["id"],
                "baseline": baseline,
                "candidate": candidate,
                "transition": transition,
            }
        )

    def summarize(side):
        rules = {}
        for rule in records[0][side]["checks"]:
            key = rule["rule"]
            witnesses = [
                r["identity"]
                for r in records
                if not next(c for c in r[side]["checks"] if c["rule"] == key)["success"]
            ]
            rules[key] = {
                "failed": len(witnesses),
                "tested": len(records),
                "witnesses": witnesses,
                "enabled": rule["enabled"],
            }
        policy = getattr(request, side).model_dump()
        return {
            "policy": policy,
            "sha256": content_hash(policy),
            "rules": rules,
            "accepted": sum(r[side]["accepted"] for r in records),
            "rejected": sum(not r[side]["accepted"] for r in records),
        }

    baseline, candidate = summarize("baseline"), summarize("candidate")
    facet = {
        "_producer": "https://github.com/9059Rohith/dataguard",
        "_schemaURL": FACET_SCHEMA,
        "assertions": [],
    }
    for index, (rule, summary) in enumerate(candidate["rules"].items()):
        if not summary["enabled"]:
            continue
        check = records[0]["candidate"]["checks"][index]
        facet["assertions"].append(
            {
                "assertion": rule,
                "name": "candidate_" + rule,
                "success": summary["failed"] == 0,
                "severity": "error",
                "expected": json.dumps(check["expected"], sort_keys=True),
                "actual": f"{summary['failed']} of {summary['tested']} repositories failed",
                "description": f"Candidate {rule} acceptance criterion across this immutable capture.",
                "contentType": "json",
                "content": json.dumps(candidate["policy"], sort_keys=True),
                "params": {
                    "capture_id": document["id"],
                    "capture_sha256": document["digest"],
                    "analysis_at": request.analysis_at,
                    "policy_sha256": candidate["sha256"],
                    "enabled": summary["enabled"],
                    "witnesses": summary["witnesses"],
                },
            }
        )
    report = {
        "version": "1.0",
        "analysis_at": request.analysis_at,
        "scope": "Acceptance criteria for this captured sample; not a software quality or security score.",
        "capture": {
            "id": document["id"],
            "sha256": document["digest"],
            "source": document["source"],
            "captured_at": document["captured_at"],
            "rows": len(records),
            "age_hours": (
                clock(request.analysis_at) - clock(document["captured_at"])
            ).total_seconds()
            / 3600,
        },
        "baseline": baseline,
        "candidate": candidate,
        "transitions": transitions,
        "records": records,
        "openlineage_facet": facet,
    }
    report["sha256"] = content_hash(report)
    return report
