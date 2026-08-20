---
description: Standalone testing skill. Default `<plan-or-phase>` analyzes changed scope and runs relevant tests; `--unit`/`--integration`/`--e2e`/`--all <target>` scope by type; `--verify <target>` reruns prior failures; `--all-phases <plan>` sweeps every completed phase. `--tdd --prepare <phase>`/`--tdd --verify <phase>` bracket ck:cook for red-green TDD. Never edits production code; blocks until the phase's ck:quality gate is APPROVED (except `--tdd --prepare`).
---

Load the `ck:test` skill and run it with `$ARGUMENTS`.
