---
name: ck:test
description: Standalone testing skill — owns writing and running tests, verifying behavior, and two-pass TDD orchestration. Default mode analyzes changed scope and runs the relevant tests; `--unit`/`--integration`/`--e2e`/`--all` scope by test type; `--verify` reruns exactly the prior failures; `--all-phases <plan>` sweeps every completed phase for regression. `--tdd --prepare`/`--tdd --verify` bracket `ck:cook` for red-green TDD. Never edits production code, and blocks until a phase's `ck:quality` gate is APPROVED (except `--tdd --prepare`, which runs before any implementation exists).
user-invocable: true
---

# ck:test — Standalone Verification & TDD Orchestration

`ck:test` owns all verification. It never touches production code and never calls `ck:fix` itself — a failure always hands control back to the user.

Modes (pick exactly one; `--tdd` further requires `--prepare` or `--verify`):

- default `<plan-or-phase>` — analyze the changed scope, write any missing tests, run the relevant unit + integration suites.
- `--unit <target>` / `--integration <target>` / `--e2e <target>` — run only that test type against `<target>`.
- `--all <target>` — run every applicable suite for `<target>`'s scope (not necessarily the whole repo).
- `--verify <target>` — rerun exactly the tests that previously failed, plus directly related regression tests; does not redesign the suite.
- `--all-phases <plan-path>` — regression sweep across every already-completed phase in the plan.
- `--tdd --prepare <phase-file>` — write failing tests before `ck:cook` implements anything; confirm RED (failure is due to missing implementation, not a broken test); save a `RED_READY` artifact.
- `--tdd --verify <phase-file>` — after `ck:cook` implements, rerun; confirm GREEN plus regression; detect tests that were weakened, deleted, or modified to dodge a failure rather than fixed by the implementation.

---

### Step 1 — Quality Gate Check

Skip only for `--tdd --prepare`, or for `--unit`/`--tdd --verify` explicitly orchestrated by the active `ck:cook` phase after its Phase Checkpoint recorded tests=yes. This scoped exception lets tests and quality remain independent user choices; it does not apply to standalone test requests.

For every other mode, resolve the phase(s) in scope and verify each has a valid, current quality receipt:

```
python {ck-quality-skill-root}/scripts/receipt.py verify plans/{slug}/quality/{phase}-receipt.json
```

Resolve `{ck-quality-skill-root}` from the installed `ck:quality` skill directory for the active client; do not hardcode `skills/` or `.claude/skills/`.

A missing or invalid receipt stops the run before any test is written or executed:

```
BLOCKED: phase implementation has not passed the Code Quality Gate.
Run or resume /ck:cook for the current phase.
```

### Step 2 — Resolve Scope

- default / `--unit` / `--integration` / `--e2e` / `--all`: the phase's changed files (`git diff` since the phase's last session-notes timestamp), or the given `<target>` path.
- `--verify`: exactly the `failures[].related_files` from the report being verified, plus the tests that exercise them — refreshed against current `git diff` in case scope grew.
- `--all-phases`: every phase in `plan.md`/`plan.json` already `completed` with `quality.status: approved`.
- `--tdd --prepare` / `--tdd --verify`: the single named phase file.

### Step 3 — Run Tester

If a named **`tester`** agent is available, spawn it with: scope, mode, existing test conventions (read 2-3 sibling test files first), and — for `--tdd --verify` — the prepared `RED_READY` artifact's exact test file contents. Otherwise execute the tester process inline. The inline path follows every ownership constraint and writes the same report; it exists so the skill remains standalone on Codex and Antigravity.

`tester` may create or edit only test code, fixtures, mocks, and test helpers. It never touches production code, never weakens an assertion to make a test pass, never deletes a failing test, and never marks a test passed without having run it.

### Step 4 — Run and Verdict

Run the relevant suite(s) for the resolved scope (not necessarily the whole repo, unless `--all-phases`).

| Mode | Verdict values |
|---|---|
| `--tdd --prepare` | `RED_READY` (every new test fails only because the implementation doesn't exist yet) or `BLOCKED` (a test fails for an unrelated reason, e.g. a syntax error in the test itself) |
| default / `--unit` / `--integration` / `--e2e` / `--all` / `--verify` / `--all-phases` / `--tdd --verify` | `PASSED` or `FAILED` |

`--tdd --verify` additionally reports `FAILED` (category `WEAKENED_TEST`) if any prepared test's assertions were loosened, deleted, or its scope narrowed without a corresponding, justified change to the acceptance criteria — regardless of whether the suite otherwise passes.

### Step 5 — Report and Handoff

Write the report to `plans/{slug}/tests/{phase}-test-report.json` (matching `references/test-report-schema.json`); `--tdd --prepare` writes `plans/{slug}/tests/{phase}-tdd-ready.json` (matching `references/tdd-ready-schema.json`) instead. `--all-phases` writes one report per swept phase — never one aggregate file covering multiple phases — then prints a one-line PASSED/FAILED summary per phase.

Update the phase's `testing.status` (JSON) or Quality and Testing State section (Markdown) to mirror the verdict: `PASSED → passed`, `FAILED → failed`, `BLOCKED → blocked_on_quality`. `ck:test` owns this field; nothing else writes it. Field shape and allowed values are defined once in `ck-plan-json/rules/plan-design.md` § Quality and Testing State — don't redefine them here.

On `FAILED`, stop — **do not** call `ck:fix` automatically. Print:

```
[ck:test] {mode} → FAILED
Report: plans/{slug}/tests/{phase}-test-report.json
Next: /ck:fix --from-test plans/{slug}/tests/{phase}-test-report.json, then /ck:test --verify {phase}
```

On `RED_READY`, print the artifact path and hand control back to `ck:cook`:

```
[ck:test] --tdd --prepare → RED_READY
Artifact: plans/{slug}/tests/{phase}-tdd-ready.json
Next: /ck:cook {phase-file} --tdd
```

On `PASSED`, print a short summary (`passed`/`failed`/`skipped` counts) and the report path; no further action is implied.

## Constraints

- Never edit production code — only test code, fixtures, mocks, and test helpers.
- Never call `ck:fix` itself; a `FAILED` or `BLOCKED` report always hands off to the user.
- A phase without an `APPROVED`, current quality receipt blocks every mode except `--tdd --prepare`.
- Do not mark a test passed without having actually run it in this invocation.
- `--verify` and `--tdd --verify` re-run the full previously-failing set, not a subjective subset — do not declare `PASSED` on a partial rerun.

---

Report shape: `references/test-report-schema.json`. TDD-prepare artifact shape: `references/tdd-ready-schema.json`.
