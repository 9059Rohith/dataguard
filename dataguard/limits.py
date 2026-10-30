"""Bounded JSON and identifier contracts shared by HTTP, CLI and staging."""

import re

MAX_BODY_BYTES = 8_000_000
MAX_JSON_DEPTH = 32
MAX_JSON_STRUCTURE = 250_000
SAFE_KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z", re.ASCII)


def check_json_structure(raw: bytes):
    """Reject pathological nesting/width before a JSON parser allocates its tree."""
    depth = structures = 0
    quoted = escaped = False
    for char in raw:
        if quoted:
            if escaped:
                escaped = False
            elif char == 92:
                escaped = True
            elif char == 34:
                quoted = False
        elif char == 34:
            quoted = True
        elif char in (123, 91):
            depth += 1
            structures += 1
            if depth > MAX_JSON_DEPTH:
                raise ValueError("JSON nesting limit exceeded")
        elif char in (125, 93):
            depth -= 1
        elif char in (58, 44):
            structures += 1
        if structures > MAX_JSON_STRUCTURE:
            raise ValueError("JSON structural limit exceeded")


def check_json_value(value):
    """Keep programmatic staging bounded and reject non-UTF8 strings before persistence."""
    pending = [(value, 0)]
    visited = 0
    while pending:
        item, depth = pending.pop()
        visited += 1
        if visited > MAX_JSON_STRUCTURE or depth > MAX_JSON_DEPTH:
            raise ValueError("JSON nesting or structural limit exceeded")
        if isinstance(item, str):
            try:
                item.encode("utf-8")
            except UnicodeError:
                raise ValueError("JSON text must contain valid Unicode") from None
        elif isinstance(item, dict):
            if any(not isinstance(key, str) for key in item):
                raise ValueError("JSON object keys must be strings")
            for key, child in item.items():
                pending.append((key, depth + 1))
                pending.append((child, depth + 1))
        elif isinstance(item, list):
            pending.extend((child, depth + 1) for child in item)
        elif item is not None and type(item) not in (bool, int, float):
            raise ValueError("Expected JSON-compatible values")
