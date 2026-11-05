"""Fail closed Linux build gate; receipts attest executed checks, not cloud coverage."""

import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree


def fingerprint(root: Path, paths: list[str]) -> str:
    digest = hashlib.sha256()
    files = set()
    for name in paths:
        path = root / name
        if not path.exists():
            raise ValueError(f"Missing verification input: {name}")
        files.update(path.rglob("*") if path.is_dir() else [path])
    for path in sorted(files):
        relative = path.relative_to(root)
        if not path.is_file() or any(
            part.startswith(".") or part == "__pycache__" or part.endswith(".pyc")
            for part in relative.parts
        ):
            continue
        digest.update(relative.as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def parse_junit(path: Path) -> dict:
    cases = list(ElementTree.parse(path).iter("testcase"))  # noqa: S314
    failures = sum(case.find("failure") is not None for case in cases)
    errors = sum(case.find("error") is not None for case in cases)
    skips = [case.find("skipped") for case in cases if case.find("skipped") is not None]
    if not cases or failures or errors:
        raise ValueError("JUnit must contain tests and no failures or errors")
    return {
        "total": len(cases),
        "passed": len(cases) - len(skips),
        "failures": failures,
        "errors": errors,
        "skipped": len(skips),
        "skip_reasons": sorted({skip.get("message", skip.text or "unspecified") for skip in skips}),
    }


def run_gate(root: Path, receipt: Path, *, commands: list[list[str]] | None = None) -> dict:
    receipt.unlink(missing_ok=True)
    receipt.parent.mkdir(parents=True, exist_ok=True)
    junit = receipt.parent / "junit.xml"
    junit.unlink(missing_ok=True)
    commands = (
        commands
        if commands is not None
        else [
            [
                sys.executable,
                "-m",
                "ruff",
                "check",
                "dataguard",
                "tests",
                "scripts/verify_build.py",
            ],
            [
                sys.executable,
                "-m",
                "ruff",
                "format",
                "--check",
                "dataguard",
                "tests",
                "scripts/verify_build.py",
            ],
            [sys.executable, "-m", "bandit", "-r", "dataguard", "-ll"],
            [sys.executable, "-m", "pytest", "-q", f"--junitxml={junit}"],
        ]
    )
    environment = os.environ.copy()
    # Hosted production variables must not turn unit tests into live provider/DB calls.
    for key in list(environment):
        if any(word in key.upper() for word in ("TOKEN", "SECRET", "PASSWORD", "API_KEY")) or (
            key.startswith(("DATAGUARD_", "OPENAI_", "GEMINI_", "GOOGLE_", "AWS_"))
            or key in {"DATABASE_URL", "TEST_DATABASE_URL", "QUALITY_DATABASE_URL"}
        ):
            environment.pop(key)
    for command in commands:
        print("VERIFY:", " ".join(command), flush=True)
        subprocess.run(command, cwd=root, env=environment, check=True)  # noqa: S603
    result = {
        "schema_version": 1,
        "gate": "vercel-linux-build-verification",
        "status": "passed",
        "completed_at": datetime.now(UTC).isoformat(),
        "python": platform.python_version(),
        "checks": [command[2:] for command in commands],
        "pytest": parse_junit(junit),
        "fingerprints_sha256": {
            "source": fingerprint(root, ["dataguard", "dags"]),
            "tests": fingerprint(root, ["tests", "docs/schemas"]),
            "locks_and_gate": fingerprint(
                root,
                [
                    "requirements.lock",
                    "requirements-ci.lock",
                    "requirements-dev.lock",
                    "pyproject.toml",
                    "Dockerfile",
                    "scripts/verify_build.py",
                ],
            ),
        },
        "coverage_limits": [
            "SQLite unit/default suite; optional TEST_DATABASE_URL PostgreSQL rerun not executed",
            "No live AI provider, Airflow runtime, Terraform apply, GitHub Actions or AWS claim",
            "Bandit source scan; dependency and container vulnerability scans are separate checks",
        ],
    }
    receipt.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("VERIFICATION_RECEIPT:", json.dumps(result, sort_keys=True), flush=True)
    return result


if __name__ == "__main__":
    run_gate(Path.cwd(), Path(sys.argv[1] if len(sys.argv) > 1 else "/verification/receipt.json"))
