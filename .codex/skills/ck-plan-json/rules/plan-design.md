# Phased Plan JSON Design Rules

## Ownership

- **One goal per plan.** Split unrelated features into separate plan bundles.
- **Master orchestration source of truth.** `plan.json` owns plan status, `current_phase`, global context, phase ordering, dependencies, phase summaries, and phase-file references. It never contains step objects.
- **Phase step detail source of truth.** Each `phase-XX-{name}.json` owns its `current_step`, steps, generated-file records, and debug logs. A step appears in exactly one phase file.
- **No duplicated steps.** Never copy phase steps or step runtime data into the master manifest.
- **No legacy compatibility.** The phased manifest contract replaces the old single-file plan and has no backward-compatibility or mixed-format branch.

## Identity, Ordering, and Files

- `plan_id` is identical in the master and every referenced phase file.
- `phase_id` values are one-indexed, unique, sequential, and ordered as `1..phase_count`.
- `step_id` values are one-indexed, unique, sequential, and ordered as `1..step_count` within each phase.
- A phase reference is a basename-only sibling of `plan.json` and matches `phase-{phase_id:02d}-{kebab-case-name}.json`.
- Each `depends_on` entry references a unique earlier `phase_id`. Self, forward, missing, and cyclic dependencies are invalid.
- Maximum 15 steps per phase. Add another phase instead of exceeding the limit.

## Status and Cursor Lifecycle

- Plan and phase statuses are `pending`, `in_progress`, `completed`, or `blocked`.
- Step statuses are `pending`, `in_progress`, `completed`, `failed`, or `blocked`.
- New bundles initialize every status to `pending`, `current_phase` to `1`, and every `current_step` to `1`.
- `pending` means no item before the cursor is incomplete and no later item has started.
- `in_progress` means every item before the cursor is `completed`, the cursor identifies the active item, and every later item is `pending`.
- A retryable execution error remains step-local `failed` and must include at least one concise `debug_logs` entry.
- Any `blocked` step immediately propagates `blocked` to its phase file, matching master phase entry, and plan without advancing either cursor. A retryable failure is promoted to `blocked` after three distinct remediation cycles.
- A completed phase has every step `completed` and `current_step = step_count + 1`.
- A completed plan has every phase `completed` and `current_phase = phase_count + 1`.
- A master phase entry and its phase file have equal status at every stable checkpoint.

## Quality and Testing State

- A phase carries an optional `design_constraints` array (non-empty strings) and an optional `quality_profile` object — repository conventions, boundaries, applicable rules, and allowed exceptions gathered during Cook's preflight step. Both are written once, before implementation, and never invented from a generic template.
- New phase files carry a required `quality` object: `status` (`not_evaluated` | `changes_required` | `approved` | `skipped_by_user`), `report` and `receipt` paths, and `remediation_cycles`. `ck:quality --gate` owns review verdicts; `ck:cook` may record `skipped_by_user` only after the phase checkpoint and must also write `decision: user_confirmed_skip`. A completed phase must mirror either `approved` or `skipped_by_user` in the master.
- New phase files carry a `testing` object: `status` (`not_started` | `blocked_on_quality` | `in_progress` | `passed` | `failed`) and a `report` path. `ck:test` owns writing this; it defaults to `not_started` until that skill runs.
- All four fields are optional so plans written before this schema addition remain valid. A present field must still match its documented shape — missing fields receive runtime defaults, not validation errors.
- The master's compact phase entry mirrors only `quality_status` and `testing_status` (never the full profile/report). When both the entry and its phase file declare a status, they must match.
- `phase.status = "completed"` means implementation completed. The receipt-gate hook requires a fresh receipt when quality is `approved`, and permits completion without one only when the explicit phase decision is `skipped_by_user`.

## Step Quality

- **Step atomicity.** Each step produces at least one verifiable output, such as a file change or passing test.
- **Input purity.** `input_files` reference existing codebase files or outputs from earlier steps or completed dependency phases.
- **Output ownership.** `output_files` list every file the step creates or modifies.
- **Success criteria.** Every step has at least one automation-verifiable condition; avoid phrases such as "works correctly".
- **Debug logs.** Each entry records the timestamp, error, and attempted fix. Keep at most the three remediation records required by the retry policy.

## Safe Writes and Recovery

- Write the phase first, then the master second for activation, completion, and blocked propagation.
- During generation, write all complete phase files before writing `plan.json`.
- During execution, persist step and phase detail before mirroring phase status or advancing `current_phase` in the master.
- Strict bundle validation runs after the master write at a stable checkpoint. Proposed phase writes receive local structural validation so legitimate phase-first transitions are not rejected mid-update.
- On resume, an active phase may be exactly one legal monotonic transition ahead of the master. Replay only the corresponding master update and validate again. Master-ahead state, identity drift, dependency drift, or multiple inferred transitions require human intervention.
- On completion, cursors use numeric sentinels rather than `null`: `current_step = step_count + 1` and `current_phase = phase_count + 1`.
