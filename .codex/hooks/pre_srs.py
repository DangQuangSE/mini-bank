#!/usr/bin/env python3
"""
Hook: UserPromptSubmit (Codex CLI port)
Fires before Codex processes each prompt.

If the prompt contains raw requirement text (heuristic: >50 words, no
skill mention), auto-runs gap_scanner.py and prints the result so Codex
skips re-deriving obvious patterns.

Ported from .claude/hooks/pre_srs.py. The UserPromptSubmit input schema
carries a `prompt` field under both Claude Code and Codex, so the
detection logic is unchanged. Differences:
  - "slash command" detection now also treats a leading `$` (Codex skill
    mention) as a command, not just `/`.
  - Output is plain text on stdout instead of a Claude-style
    {"additionalContext": ...} JSON blob.
  - Helper scripts live under .codex/scripts so the Codex setup is
    self-contained.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
MIN_WORDS_FOR_SCAN = 50
SRS_TRIGGER_KEYWORDS = {"srs", "requirement", "requirements", "cl-srs", "srs-generator"}


def is_skill_invocation(text: str) -> bool:
    return text.strip().startswith("/") or text.strip().startswith("$")


def looks_like_raw_requirements(text: str) -> bool:
    """Heuristic: long-ish text that isn't a skill invocation."""
    if is_skill_invocation(text):
        return False
    words = text.split()
    if len(words) < MIN_WORDS_FOR_SCAN:
        return False
    lower = text.lower()
    req_signals = {"user", "system", "shall", "should", "must", "admin",
                   "feature", "function", "login", "dashboard", "report"}
    return bool(req_signals & set(lower.split()))


def run_gap_scanner(text: str) -> str | None:
    scanner = SCRIPTS_DIR / "gap_scanner.py"
    if not scanner.exists():
        return None
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt",
                                     delete=False, encoding="utf-8") as f:
        f.write(text)
        tmp_path = f.name
    try:
        result = subprocess.run(
            [sys.executable, str(scanner), tmp_path],
            capture_output=True, text=True, timeout=15, encoding="utf-8"
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    prompt = event.get("prompt", "")

    lower = prompt.lower()
    is_srs_cmd = any(k in lower for k in SRS_TRIGGER_KEYWORDS)

    if not (is_srs_cmd or looks_like_raw_requirements(prompt)):
        sys.exit(0)

    scan_output = run_gap_scanner(prompt)
    if not scan_output:
        sys.exit(0)

    print(
        "## Pre-scan: Gap Scanner Results\n\n"
        f"{scan_output}\n\n"
        "> Use this as your Step 2 Gap Scan starting point. "
        "Validate, extend with Pattern 7 (contradictions) and semantic gaps, then proceed."
    )


if __name__ == "__main__":
    main()
