"""Read-only quality-policy experiments on retained, successfully published versions.

Only fixed SQLAlchemy expressions are compiled. All business data stays inside
this boundary; reports contain counts and keyed, report-local sample tokens.
"""

import hashlib
import hmac
import json
import secrets
import time
from collections import Counter
from contextlib import contextmanager
from datetime import UTC, datetime

from sqlalchemy import and_, event, func, or_, select
from sqlalchemy.exc import DBAPIError

from dataguard.policy_models import (
    ImpactReport,
    ImpactRequest,
    ImpactSummary,
    PolicyOutcome,
    PolicyProvenance,
    RolloutRecommendation,
    RuleDelta,
    RuleOutcome,
    VersionImpact,
)
from dataguard.service import attempts, batches, settlements, trades

MAX_SOURCE_ROWS = 10000
EXPERIMENT_SECONDS = 20
TABLES = {"trades": trades, "settlements": settlements}
KEYS = {"trades": "trade_id", "settlements": "settlement_id"}

LIMITATIONS = [
    "Selected published versions are accepted historical evidence, not a labelled production corpus.",
    "New rejection means rejection of previously published data; business correctness needs review.",
    "Matching aggregate counts does not prove identical violating records or equivalent policies.",
    "No estimate of production accuracy, false-positive rate, or future generalization is made.",
    "Checks overlap; rule violation counts must not be summed as distinct rejected rows.",
    "Samples are bounded and report-local; policies are never installed or enforced by this report.",
]


class PolicyBudgetExceeded(Exception):
    """Work was stopped without publishing a partial report."""


@contextmanager
def read_snapshot(engine, seconds=EXPERIMENT_SECONDS):
    """One consistent read-only transaction; pooled connection settings always restored.

    PostgreSQL gets REPEATABLE READ, READ ONLY, and a per-statement timeout
    capped at 10s and the remaining wall-clock budget. SQLite gets an explicit
    read transaction, query_only, and a VM progress deadline. Statements and
    Python-side timestamp parsing also check the overall budget.
    """
    deadline = time.monotonic() + seconds
    if seconds <= 0:
        raise PolicyBudgetExceeded("Policy experiment work budget exceeded")
    if engine.dialect.name not in {"postgresql", "sqlite"}:
        raise ValueError("PolicyLab requires PostgreSQL or SQLite")
    with engine.connect() as c:
        postgres = engine.dialect.name == "postgresql"
        driver = None
        previous_query_only = 0
        listener_attached = False

        def before_statement(_connection, cursor, _statement, _parameters, _context, _many):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise PolicyBudgetExceeded("Policy experiment work budget exceeded")
            if postgres:
                milliseconds = max(1, min(10000, int(remaining * 1000)))
                # Integer comes only from the monotonic clock, never policy input.
                cursor.execute(f"SET LOCAL statement_timeout = '{milliseconds}ms'")

        try:
            if postgres:
                c = c.execution_options(isolation_level="REPEATABLE READ")
                c.begin()
                c.exec_driver_sql("SET TRANSACTION READ ONLY")
                c.exec_driver_sql("SET LOCAL statement_timeout = '10s'")
            else:
                driver = c.connection.driver_connection
                previous_query_only = driver.execute("PRAGMA query_only").fetchone()[0]
                driver.execute("PRAGMA query_only=ON")
                driver.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
                c.exec_driver_sql("BEGIN")
            event.listen(c, "before_cursor_execute", before_statement)
            listener_attached = True
            yield c
            if time.monotonic() > deadline:
                raise PolicyBudgetExceeded("Policy experiment work budget exceeded")
        except DBAPIError as error:
            if time.monotonic() >= deadline or getattr(error.orig, "sqlstate", None) == "57014":
                raise PolicyBudgetExceeded("Policy experiment work budget exceeded") from None
            raise
        finally:
            if listener_attached:
                event.remove(c, "before_cursor_execute", before_statement)
            c.rollback()
            if driver is not None:
                driver.set_progress_handler(None, 0)
                driver.execute(f"PRAGMA query_only={int(previous_query_only)}")


def _token(secret, batch_id, table, key):
    # HMAC (not an unkeyed source hash): low-entropy IDs cannot be dictionary-matched.
    message = f"{batch_id}\0{table}\0{key}".encode()
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def _violation_query(rule, batch_id):
    """Return (logical table, one-column violating-row query), with values bound."""
    kind = rule.kind
    if kind in {"range", "categories", "complete", "unique"}:
        table = TABLES[rule.table]
        key = table.c[KEYS[rule.table]]
        value = table.c[rule.field]
        selected = select(key.label("record_key")).where(table.c.batch_id == batch_id)
        if kind == "range":
            condition = or_(value.is_(None), value < rule.minimum, value > rule.maximum)
        elif kind == "categories":
            condition = or_(value.is_(None), value.not_in(rule.values))
        elif kind == "complete":
            condition = or_(value.is_(None), func.length(func.trim(value)) == 0)
        else:
            # Window partitions count all duplicate-group members, including NULLs.
            ranked = (
                select(
                    key.label("record_key"),
                    func.count().over(partition_by=value).label("frequency"),
                )
                .where(table.c.batch_id == batch_id)
                .subquery()
            )
            return rule.table, select(ranked.c.record_key).where(ranked.c.frequency > 1)
        return rule.table, selected.where(condition)
    if kind == "reference":
        joined = trades.outerjoin(
            settlements,
            and_(
                trades.c.batch_id == settlements.c.batch_id,
                trades.c.settlement_id == settlements.c.settlement_id,
            ),
        )
        missing = settlements.c.settlement_id.is_(None)
        condition = (
            or_(missing, trades.c.currency != settlements.c.currency)
            if rule.match_currency
            else missing
        )
        return "trades", select(trades.c.trade_id.label("record_key")).select_from(joined).where(
            trades.c.batch_id == batch_id, condition
        )
    if kind == "totals":
        totals = (
            select(
                trades.c.settlement_id,
                func.sum(trades.c.amount_cents).label("actual"),
            )
            .where(trades.c.batch_id == batch_id)
            .group_by(trades.c.settlement_id)
            .subquery()
        )
        joined = settlements.outerjoin(
            totals, settlements.c.settlement_id == totals.c.settlement_id
        )
        return "settlements", select(settlements.c.settlement_id.label("record_key")).select_from(
            joined
        ).where(
            settlements.c.batch_id == batch_id,
            func.abs(func.coalesce(totals.c.actual, 0) - settlements.c.amount_cents)
            > rule.tolerance_cents,
        )
    raise ValueError("Unsupported policy rule")


def _freshness(c, rule, provenance, limit, secret):
    """Published event_time is ISO text, not a database timestamp column.

    Parse with the same Python ISO semantics as admission to avoid backend
    disagreements on offsets/basic/week-date forms. At most 10,000 rows can
    be fetched after the source budget check; no source values leave here.
    """
    count = 0
    samples = []
    reference = provenance.published_at
    for row in c.execute(
        select(trades.c.trade_id, trades.c.event_time)
        .where(trades.c.batch_id == provenance.batch_id)
        .order_by(trades.c.trade_id)
    ):
        try:
            stamp = datetime.fromisoformat(row.event_time)
            if stamp.utcoffset() is None:
                raise ValueError
            age = reference - stamp.astimezone(UTC).timestamp()
            invalid = not -rule.future_tolerance_seconds <= age <= rule.max_age_seconds
        except (ValueError, TypeError, OverflowError):
            invalid = True
        if invalid:
            count += 1
            if len(samples) < limit:
                samples.append(_token(secret, provenance.batch_id, "trades", row.trade_id))
    return count, samples


def _rule_outcome(c, rule, provenance, sizes, sample_limit, secret):
    if rule.kind == "freshness":
        table = "trades"
        count, samples = _freshness(c, rule, provenance, sample_limit, secret)
    else:
        table, query = _violation_query(rule, provenance.batch_id)
        violations = query.subquery()
        count = c.execute(select(func.count()).select_from(violations)).scalar_one()
        samples = []
        if count and sample_limit:
            keys = c.execute(
                select(violations.c.record_key)
                .order_by(violations.c.record_key)
                .limit(sample_limit)
            ).scalars()
            samples = [_token(secret, provenance.batch_id, table, key) for key in keys]
    return RuleOutcome(
        id=rule.id,
        kind=rule.kind,
        table=table,
        evaluated_rows=sizes[table],
        violation_count=count,
        sample_tokens=samples,
        samples_truncated=count > len(samples),
    )


def _outcome(c, policy, provenance, sizes, sample_limit, secret, cache):
    outcomes = []
    for rule in sorted(policy.rules, key=lambda item: item.id):
        canonical = rule.model_dump_json()
        if canonical not in cache:
            cache[canonical] = _rule_outcome(c, rule, provenance, sizes, sample_limit, secret)
        outcomes.append(cache[canonical])
    failed = sum(rule.violation_count > 0 for rule in outcomes)
    return PolicyOutcome(
        policy_sha256=policy.digest(), accepted=failed == 0, failed_rules=failed, rules=outcomes
    )


def _deltas(baseline, candidate, before, after):
    definitions_old = {rule["id"]: rule for rule in json.loads(baseline.canonical_json())["rules"]}
    definitions_new = {rule["id"]: rule for rule in json.loads(candidate.canonical_json())["rules"]}
    counts_old = {rule.id: rule.violation_count for rule in before.rules}
    counts_new = {rule.id: rule.violation_count for rule in after.rules}
    result = []
    for rule_id in sorted(definitions_old.keys() | definitions_new.keys()):
        old, new = counts_old.get(rule_id), counts_new.get(rule_id)
        if old is None:
            change = "added"
        elif new is None:
            change = "removed"
        elif new > old:
            change = "more_violations"
        elif new < old:
            change = "fewer_violations"
        else:
            change = "same_count"
        result.append(
            RuleDelta(
                id=rule_id,
                change=change,
                definition_changed=definitions_old.get(rule_id) != definitions_new.get(rule_id),
                baseline_violations=old,
                candidate_violations=new,
            )
        )
    return result


def _recommendation(versions, summary):
    if summary.new_rejection:
        return RolloutRecommendation(
            stage="block_candidate",
            reasons=[
                "Candidate newly rejects previously published versions; review rule-level evidence before enforcement.",
                "Published acceptance is evidence of compatibility, not proof of business correctness.",
            ],
        )
    removed = any(
        delta.change == "removed" for version in versions for delta in version.rule_changes
    )
    changed = any(
        delta.definition_changed for version in versions for delta in version.rule_changes
    )
    no_candidate_checks = any(not version.candidate.rules for version in versions)
    if (
        summary.unchanged_reject
        or summary.new_acceptance
        or removed
        or changed
        or no_candidate_checks
        or summary.evaluated_versions < 2
    ):
        return RolloutRecommendation(
            stage="shadow_only",
            reasons=[
                "Rejections, changed definitions, absent checks, or fewer than two versions need shadow observation and operator review.",
                "Choose representative future partitions and labelled adverse cases before considering enforcement.",
            ],
        )
    return RolloutRecommendation(
        stage="limited_canary",
        reasons=[
            "The nonempty candidate is canonically unchanged and no selected published version changes acceptance.",
            "Use an operator-approved limited canary with rollback; this finite evidence does not establish future safety.",
        ],
    )


class PolicyLab:
    def __init__(self, engine):
        self.engine = engine

    def impact(self, request: ImpactRequest) -> ImpactReport:
        # Revalidate a defensive copy: frozen Pydantic models can contain mutable lists.
        request = ImpactRequest.model_validate(request.model_dump())
        secret = secrets.token_bytes(32)
        versions = []
        with read_snapshot(self.engine) as c:
            selected = request.versions
            accepted = {
                row.batch_id: row
                for row in c.execute(
                    select(
                        batches.c.id.label("batch_id"),
                        batches.c.digest.label("sha256"),
                        batches.c.payload["period"].as_string().label("period"),
                        attempts.c.id.label("attempt_id"),
                        attempts.c.finished_at.label("published_at"),
                    )
                    .select_from(batches.join(attempts, batches.c.id == attempts.c.batch_id))
                    .where(
                        batches.c.id.in_([version.batch_id for version in selected]),
                        attempts.c.status == "published",
                    )
                ).mappings()
            }
            if any(
                version.batch_id not in accepted
                or accepted[version.batch_id]["period"] != version.period
                for version in selected
            ):
                raise KeyError("published version")
            for selection in sorted(selected, key=lambda item: (item.period, item.batch_id)):
                provenance = PolicyProvenance.model_validate(dict(accepted[selection.batch_id]))
                sizes = {}
                for label, table in TABLES.items():
                    # LIMIT caps counting even if storage was externally corrupted/enlarged.
                    limited = (
                        select(table.c.batch_id)
                        .where(table.c.batch_id == selection.batch_id)
                        .limit(MAX_SOURCE_ROWS + 1)
                        .subquery()
                    )
                    sizes[label] = c.execute(select(func.count()).select_from(limited)).scalar_one()
                    if sizes[label] == 0:
                        # A successful attempt without retained rows is not evidence.
                        raise KeyError("published version")
                    if sizes[label] > MAX_SOURCE_ROWS:
                        raise PolicyBudgetExceeded("Published version exceeds policy row budget")
                cache = {}
                before = _outcome(
                    c, request.baseline, provenance, sizes, request.sample_limit, secret, cache
                )
                after = _outcome(
                    c, request.candidate, provenance, sizes, request.sample_limit, secret, cache
                )
                transition = {
                    (True, True): "unchanged_accept",
                    (True, False): "new_rejection",
                    (False, True): "new_acceptance",
                    (False, False): "unchanged_reject",
                }[(before.accepted, after.accepted)]
                versions.append(
                    VersionImpact(
                        provenance=provenance,
                        baseline=before,
                        candidate=after,
                        transition=transition,
                        rule_changes=_deltas(request.baseline, request.candidate, before, after),
                    )
                )
        counts = Counter(version.transition for version in versions)
        summary = ImpactSummary(
            evaluated_versions=len(versions),
            **{
                key: counts[key]
                for key in (
                    "unchanged_accept",
                    "new_rejection",
                    "new_acceptance",
                    "unchanged_reject",
                )
            },
        )
        return ImpactReport(
            baseline_sha256=request.baseline.digest(),
            candidate_sha256=request.candidate.digest(),
            versions=versions,
            summary=summary,
            recommendation=_recommendation(versions, summary),
            limitations=LIMITATIONS,
        )
