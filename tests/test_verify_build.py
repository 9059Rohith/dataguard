import sys
from pathlib import Path

import pytest

from scripts.verify_build import fingerprint, parse_junit, run_gate


def test_junit_counts_cases_once_and_preserves_skip_reason(tmp_path):
    report = tmp_path / "junit.xml"
    report.write_text(
        '<testsuites><testsuite tests="2"><testcase name="ok" />'
        '<testcase name="optional"><skipped message="PostgreSQL not configured" />'
        "</testcase></testsuite></testsuites>",
        encoding="utf-8",
    )
    assert parse_junit(report) == {
        "total": 2,
        "passed": 1,
        "failures": 0,
        "errors": 0,
        "skipped": 1,
        "skip_reasons": ["PostgreSQL not configured"],
    }


@pytest.mark.parametrize(
    "case", ["<testcase><failure /></testcase>", "<testcase><error /></testcase>", ""]
)
def test_failed_or_empty_junit_cannot_be_a_passing_receipt(tmp_path, case):
    report = tmp_path / "junit.xml"
    report.write_text(f"<testsuites><testsuite>{case}</testsuite></testsuites>")
    with pytest.raises(ValueError):
        parse_junit(report)


def test_failed_command_removes_stale_receipt_and_stops_gate(tmp_path):
    receipt = tmp_path / "receipt.json"
    receipt.write_text('{"status":"passed"}')
    marker = tmp_path / "must-not-exist"
    commands = [
        [sys.executable, "-c", "raise SystemExit(7)"],
        [sys.executable, "-c", f"open({str(marker)!r}, 'w').close()"],
    ]
    with pytest.raises(Exception, match="exit status 7"):
        run_gate(tmp_path, receipt, commands=commands)
    assert not receipt.exists()
    assert not marker.exists()


def test_fingerprint_changes_with_contents_but_excludes_cache_and_credentials(tmp_path):
    source = tmp_path / "dataguard"
    source.mkdir()
    tracked = source / "app.py"
    tracked.write_text("value = 1\n")
    first = fingerprint(tmp_path, ["dataguard"])
    (source / "__pycache__").mkdir()
    (source / "__pycache__" / "app.pyc").write_bytes(b"cache")
    (source / ".env.private").write_text("SECRET=private")
    assert fingerprint(tmp_path, ["dataguard"]) == first
    tracked.write_text("value = 2\n")
    assert fingerprint(tmp_path, ["dataguard"]) != first


def test_runtime_requires_receipt_without_copying_test_tools():
    dockerfile = (Path(__file__).parents[1] / "Dockerfile").read_text()
    runtime = dockerfile.split("FROM ${RUNTIME_IMAGE}", 1)[1]
    assert "COPY --from=verify /verification/receipt.json /app/build-verification.json" in runtime
    assert "/test-tools" not in runtime
    assert "COPY tests" not in runtime
