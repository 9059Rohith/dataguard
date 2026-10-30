"""Bounded, unambiguous policy JSON and local operator authentication."""

import json
import os
import secrets
from pathlib import Path

from pydantic import ValidationError

from dataguard.limits import check_json_structure
from dataguard.policy_models import ImpactRequest

POLICY_MAX_BYTES = 65536


def decode_policy_json(raw: bytes):
    if len(raw) > POLICY_MAX_BYTES:
        raise ValueError("Policy document exceeds 64 KiB")
    check_json_structure(raw)

    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Invalid policy request")
            result[key] = value
        return result

    def reject_constant(_value):
        raise ValueError("Invalid policy request")

    try:
        return json.loads(
            raw.decode("utf-8"), object_pairs_hook=unique_pairs, parse_constant=reject_constant
        )
    except (UnicodeError, ValueError, RecursionError):
        raise ValueError("Invalid policy request") from None


def load_impact_file(path) -> ImpactRequest:
    # read_bytes() would allocate an unbounded local file before checking length.
    with Path(path).open("rb") as stream:
        raw = stream.read(POLICY_MAX_BYTES + 1)
    try:
        return ImpactRequest.model_validate(decode_policy_json(raw))
    except (ValidationError, ValueError):
        raise ValueError("Invalid policy request") from None


def authorize_operator(token_env="DATAGUARD_OPERATOR_TOKEN"):
    """Same configured token as HTTP; caller supplies it via a separate environment variable.

    Never accept token literals on the command line, where process listings and
    shell history can capture them. Database credentials alone are insufficient.
    """
    configured = os.getenv("DATAGUARD_TOKEN", "")
    if len(configured.strip()) < 32:
        raise ValueError("Operator token is not configured (minimum 32 characters)")
    if token_env == "DATAGUARD_TOKEN":
        raise ValueError("Use a separate operator token environment variable")
    supplied = os.getenv(token_env, "")
    if not supplied or not secrets.compare_digest(supplied.encode(), configured.encode()):
        raise ValueError("Invalid operator token")
