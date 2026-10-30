"""Executable settlement contract v1; amounts use integer minor units."""

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

CURRENCIES = {"USD", "EUR", "GBP", "INR", "SGD", "JPY"}
SCHEMAS = {
    "trades": {
        "trade_id": str,
        "settlement_id": str,
        "amount_cents": int,
        "currency": str,
        "event_time": str,
    },
    "settlements": {"settlement_id": str, "amount_cents": int, "currency": str},
}


def validate(payload, now):
    errors = []

    def report(table, row, field, rule, message):
        if len(errors) < 1000:
            errors.append(dict(table=table, row=row, field=field, rule=rule, message=message))

    if not isinstance(payload, dict) or set(payload) != {
        "period",
        "produced_at",
        "trades",
        "settlements",
    }:
        report(
            "batch", None, None, "schema", "Expected period, produced_at, trades, settlements only"
        )
        return errors
    try:
        period = date.fromisoformat(payload["period"])
        if period.isoformat() != payload["period"]:
            raise ValueError("non-canonical period")
    except (ValueError, TypeError):
        report("batch", None, "period", "type", "Expected YYYY-MM-DD")
        period = None
    try:
        produced = datetime.fromisoformat(payload["produced_at"])
        if produced.utcoffset() is None:
            raise ValueError("timezone required")
        if not now - timedelta(hours=24) <= produced <= now + timedelta(minutes=5):
            report("batch", None, "produced_at", "freshness", "Must be within past 24h / future 5m")
    except (ValueError, TypeError):
        report("batch", None, "produced_at", "type", "Expected timezone-aware ISO timestamp")
    valid = {}
    for table, schema in SCHEMAS.items():
        rows = payload[table]
        valid[table] = []
        if not isinstance(rows, list) or not 1 <= len(rows) <= 10000:
            report(table, None, None, "range", "Expected 1..10000 rows")
            continue
        seen = set()
        pk = "trade_id" if table == "trades" else "settlement_id"
        for i, row in enumerate(rows):
            before = len(errors)
            if not isinstance(row, dict):
                report(table, i, None, "type", "Expected object")
                continue
            if set(row) - set(schema):
                report(table, i, None, "schema", "Unknown fields are forbidden")
            for field, expected in schema.items():
                if field not in row:
                    report(table, i, field, "required", "Required field missing")
                elif type(row[field]) is not expected:
                    report(
                        table,
                        i,
                        field,
                        "type",
                        f"Expected {expected.__name__}; received {type(row[field]).__name__}",
                    )
                elif expected is str and not 1 <= len(row[field]) <= 100:
                    report(table, i, field, "range", "Expected 1..100 characters")
                elif expected is str and (
                    not row[field].strip() or any(ord(c) < 32 or ord(c) == 127 for c in row[field])
                ):
                    report(
                        table,
                        i,
                        field,
                        "allowed_value",
                        "Blank/control-character strings are forbidden",
                    )
            if any(
                field not in row or type(row[field]) is not expected
                for field, expected in schema.items()
            ):
                continue
            if row[pk] in seen:
                report(table, i, pk, "unique", "Duplicate primary key in batch")
            seen.add(row[pk])
            if row["currency"] not in CURRENCIES:
                report(table, i, "currency", "allowed_value", "Unsupported ISO currency")
            lower = 1 if table == "trades" else 0
            if not lower <= row["amount_cents"] <= 10**12:
                report(table, i, "amount_cents", "range", f"Expected {lower}..10^12 minor units")
            if table == "trades":
                try:
                    stamp = datetime.fromisoformat(row["event_time"])
                    if stamp.utcoffset() is None:
                        raise ValueError("timezone required")
                    if stamp.astimezone(UTC).date() != period:
                        report(
                            table,
                            i,
                            "event_time",
                            "freshness",
                            "Event date must equal partition date",
                        )
                except (ValueError, TypeError):
                    report(table, i, "event_time", "type", "Expected timezone-aware ISO timestamp")
            if len(errors) == before:
                valid[table].append((i, row))
    references = {r["settlement_id"]: r for _, r in valid["settlements"]}
    totals = defaultdict(int)
    for i, row in valid["trades"]:
        ref = references.get(row["settlement_id"])
        if ref is None:
            report(
                "trades",
                i,
                "settlement_id",
                "foreign_key",
                "Settlement does not exist in same batch",
            )
        elif row["currency"] != ref["currency"]:
            report(
                "trades",
                i,
                "currency",
                "foreign_key",
                "Currency differs from referenced settlement",
            )
        totals[row["settlement_id"]] += row["amount_cents"]
    for i, row in valid["settlements"]:
        actual = totals[row["settlement_id"]]
        if actual != row["amount_cents"]:
            report(
                "settlements",
                i,
                "amount_cents",
                "settlement_total",
                f"Trade total {actual} differs from declared {row['amount_cents']}",
            )
    return errors
