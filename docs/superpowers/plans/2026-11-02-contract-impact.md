# Contract Impact Workbench Implementation Plan

**Goal:** Compare bounded user-authored source contracts against actual public evidence.

**Architecture:** A pure evaluator and strict Pydantic request model, mounted as a public
side-effect-free quality route, plus a dedicated page within the existing console.

**Spec:** docs/contract-impact-design.md

- [x] Write failing API/engine tests for transitions, witnesses, strict bounds, private boundary,
  deterministic clocks, immutable state, and offline OpenLineage schema validation.
- [x] Implement the evaluator and guarded endpoint, verify tests turn green.
- [x] Build paired accessible policy forms, source selector, evidence results, exports, and mobile CSS.
- [x] Run complete Python suite, JS checks, lint/format/security, and bounded benchmark.
- [x] Deploy, verify ready and canonical public response, commit and push.
