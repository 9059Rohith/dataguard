# PolicyLab verification — 2026-10-30

This evidence concerns the local PolicyLab changes. The existing public deployment has not been updated.

| Check | Observed result | Evidence |
| --- | --- | --- |
| Full suite, Windows Python 3.12.14 / SQLite | 150 passed, 1 skipped | [Output](policylab-sqlite-tests.txt) |
| Full suite, native Python 3.15.1 / SQLite | 150 passed, 1 skipped | [Command and observation](policylab-native-sqlite.json) |
| Full suite, native Python 3.15.1 / PostgreSQL | 151 passed | [Output](policylab-native-postgres-tests.txt) |
| Earlier Windows PostgreSQL run before final review fixes | 147 passed; superseded by the final native PostgreSQL run above | [Historical output](policylab-postgres-tests.txt) |
| Ruff | `python -m ruff check dataguard tests scripts/policylab-smoke.py` passed | Agent command output |
| Bandit medium/high severity | Zero reported findings; existing entrypoint `nosec` annotation warnings remain | [JSON](policylab-bandit.json) |
| Controlled policy study, native Python 3.15.1 | All independent decisions/counts matched; invalid policies rejected and unpublished inputs excluded | [Study](policylab-controlled.json) |
| Final minimal production image build | `dataguard:policylab` built successfully, pinned Python 3.15.1, UID 10001 | [Runtime/image identity](policylab-native-http.json) |
| Actual HTTP against final image and PostgreSQL | Auth, OpenAPI, redaction, bounded samples, quarantine exclusion and no publication mutation passed; exact 0 / 9,599 violations on 2 / 10,000-trade versions | [HTTP proof](policylab-native-http.json) |
| Net Python code growth | 841 production, 660 tests, 146 verification-script lines; excludes blank/comment/docstring lines and documentation/evidence | [Definition and per-file counts](policylab-code-lines.json) |

The SQLite skip is the existing PostgreSQL-only `EXPLAIN ANALYZE` planner-work regression. PostgreSQL ran against isolated databases named `dataguard_policylab_test`, `dataguard_policylab_native_test`, and `dataguard_policylab_http_test` on the existing local server. The credential was captured in memory from the local PostgreSQL container and passed by environment; it is absent from evidence and command arguments. Only those disposable `_test` databases received test fixture changes. The HTTP container was removed after the probe.

The final image identifier returned by Docker inspection is `sha256:a9d2885987a49f60d1ef73ff04e324af81720da6750640ce339c66c93dc85567`. HTTP ran with a read-only root filesystem, dropped capabilities, no-new-privileges, a bounded temporary filesystem and loopback-only published port. Full native tests used a derived minimal-runtime test image with pinned pure-Python test tooling added separately and current source mounted read-only; that tooling is absent from the production image. An initial attempt to install the entire dev lock into the native test image encountered the unavailable PyYAML 3.15 binary wheel. The completed test runner instead installed only the pinned pure-Python tooling needed by the suite; project dependencies and lockfiles were unchanged.

Independent review identified that empty candidate policies or changed definitions with equal sampled outcomes must not receive a canary recommendation. Separate failing tests reproduced both cases; the fix keeps them in shadow mode while preserving new-rejection block priority. Author review also added failing regressions for externally purged published rows and isolated evaluation accidentally constructing the operator database. All four fixes passed their focused tests and the complete final suites.

The study is deliberately small: three known-valid synthetic versions and four policy scenarios. It demonstrates compatibility decisions and false rejections on those fixtures, not production model accuracy, precision, recall or generalization. The HTTP duration is one measured request, not a latency distribution. No database schema change, new project dependency, workflow edit, remote push or deployment was performed.
