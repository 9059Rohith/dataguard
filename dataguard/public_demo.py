"""Small, persistent public AI quotas. The database stores HMACs, never client IPs."""

import hashlib
import hmac
import ipaddress
import json
import math
import os
import time

from fastapi import HTTPException, Request
from sqlalchemy import Column, Float, Integer, MetaData, String, Table, delete, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

PUBLIC_INVESTIGATE_PATH = "/api/quality/public-investigate"
PUBLIC_BODY_BYTES = 8192
quota_schema = MetaData()
buckets = Table(
    "quality_public_ai_buckets",
    quota_schema,
    Column("key", String(160), primary_key=True),
    Column("used", Integer, nullable=False),
    Column("expires_at", Float, nullable=False, index=True),
)
PUBLIC_LIMITS = {
    "per_client": {"limit": 3, "seconds": 600},
    "global_minute": {"limit": 2, "seconds": 60},
    "global_day": {"limit": 30, "seconds": 86400},
}


def client_hash(request: Request):
    secret = os.getenv("DATAGUARD_TOKEN", "").strip()
    if len(secret) < 32:
        raise HTTPException(
            503, "Public AI protection is not configured.", headers={"Retry-After": "60"}
        )
    identity = request.client.host if request.client else "unknown-peer"
    forwarded = request.headers.getlist("x-forwarded-for")
    if os.getenv("VERCEL") == "1" and len(forwarded) == 1:
        try:
            # A comma-separated chain, duplicate header, or malformed address is
            # not a Vercel-overwritten single address and never becomes identity.
            identity = ipaddress.ip_address(forwarded[0].strip()).compressed
        except ValueError:
            pass
    try:
        identity = ipaddress.ip_address(identity).compressed
    except ValueError:
        pass  # Test clients and non-IP socket names still get a keyed identity.
    return hmac.new(
        secret.encode(), b"dataguard-public-ai:" + identity.encode(), hashlib.sha256
    ).hexdigest()


def check_origin(request: Request):
    origins = request.headers.getlist("origin")
    if not origins:
        return  # Nonbrowser clients are allowed, with exactly the same quotas.
    allowed = {
        "https://rohith-dataguard.vercel.app",
        "https://dataguard-one.vercel.app",
        f"{request.url.scheme}://{request.url.netloc}",
    }
    if len(origins) != 1 or origins[0] not in allowed:
        raise HTTPException(403, "Public AI requests must use this site's origin.")


class PublicQuota:
    def __init__(self, engine):
        self.engine = engine

    def initialize(self):
        quota_schema.create_all(self.engine)

    def reserve(self, identity, now=None):
        clock = time.time() if now is None else now
        scopes = (
            ("global_day", "day", 30, 86400),
            ("global_minute", "minute", 2, 60),
            ("per_client", "client:" + identity, 3, 600),
        )
        remaining = {}
        resets = {}
        dialect_insert = pg_insert if self.engine.dialect.name == "postgresql" else sqlite_insert
        # Each conditional increment and every other bucket reservation commit
        # together. ON CONFLICT plus UPDATE acquires real database write locks;
        # another worker cannot pass the same remaining slot concurrently.
        with self.engine.begin() as connection:
            connection.execute(delete(buckets).where(buckets.c.expires_at <= clock))
            for label, scope, limit, duration in scopes:
                start = int(clock // duration) * duration
                end = start + duration
                bucket_key = f"{scope}:{start}"
                connection.execute(
                    dialect_insert(buckets)
                    .values(
                        key=bucket_key,
                        used=0,
                        expires_at=end,
                    )
                    .on_conflict_do_nothing(index_elements=["key"])
                )
                value = connection.execute(
                    update(buckets)
                    .where(buckets.c.key == bucket_key, buckets.c.used < limit)
                    .values(used=buckets.c.used + 1)
                    .returning(buckets.c.used)
                ).scalar_one_or_none()
                if value is None:
                    # Raising inside the transaction rolls back every earlier
                    # increment. Rejected requests consume no other quota slot.
                    retry = str(max(1, math.ceil(end - clock)))
                    raise HTTPException(
                        429,
                        "Public investigation limit reached. Please retry after the cooldown.",
                        headers={"Retry-After": retry},
                    )
                remaining[label] = limit - value
                resets[label] = max(1, math.ceil(end - clock))
        return {
            "remaining": remaining,
            "resets_in_seconds": resets,
            "limits": PUBLIC_LIMITS,
            "policy": "Fixed UTC windows. A reserved investigation counts even if its provider request fails.",
        }


def public_result(result, quota):
    """Bound the response while preserving actual model text and evidence identity."""
    if not isinstance(result.get("answer"), str) or len(result["answer"]) > 6000:
        raise HTTPException(502, "The model answer exceeded the public response budget.")

    def summary(document):
        if not isinstance(document, dict):
            return {"error": "Unsupported evidence result"}
        if "error" in document:
            return {"error": str(document["error"])[:200]}
        return {
            key: str(document[key])[:200] if isinstance(document[key], str) else document[key]
            for key in (
                "id",
                "name",
                "source",
                "visibility",
                "captured_at",
                "digest",
                "row_count",
                "status",
            )
            if key in document
        }

    trace = []
    for item in result.get("trace", [])[:6]:
        evidence = item.get("result")
        arguments = item.get("arguments", {})
        trace.append(
            {
                "tool": str(item.get("tool", ""))[:64],
                "arguments": {"capture_id": str(arguments["capture_id"])[:64]}
                if isinstance(arguments, dict) and "capture_id" in arguments
                else {},
                "result": [summary(document) for document in evidence[:6]]
                if isinstance(evidence, list)
                else summary(evidence),
            }
        )
    response = {
        **{
            key: result[key]
            for key in (
                "answer",
                "provider",
                "model",
                "public_data_only",
                "provider_requests",
                "created_at",
            )
            if key in result
        },
        "trace": trace,
        "public_demo": True,
        "quota": quota,
        "evidence_notice": "Trace summaries identify the actual public evidence read. Full records remain available in Datasets.",
    }
    if len(json.dumps(response, ensure_ascii=False).encode()) > 64000:
        raise HTTPException(502, "The public response exceeded its evidence budget.")
    return response
