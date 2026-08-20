#!/usr/bin/env python3
"""
Hook: UserPromptSubmit
Fires before Claude processes each prompt.

If the prompt contains raw requirement text (heuristic: >50 words, no slash
command), auto-runs gap_scanner.py and injects the result as additionalContext
so Claude skips re-deriving obvious patterns.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
MIN_WORDS_FOR_SCAN = 50
SRS_TRIGGER_KEYWORDS = {"srs", "requirement", "requirements", "cl:srs"}


def is_slash_command(text: str) -> bool:
    return text.strip().startswith("/")


def looks_like_raw_requirements(text: str) -> bool:
    """Heuristic: long-ish text that isn't a slash command."""
    if is_slash_command(text):
        return False
    words = text.split()
    if len(words) < MIN_WORDS_FOR_SCAN:
        return False
    # must contain at least one requirement-flavored keyword
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

    # Check if this is a /cl:srs invocation or a prompt with raw requirements
    lower = prompt.lower()
    is_srs_cmd = "cl:srs" in lower or any(k in lower for k in SRS_TRIGGER_KEYWORDS)

    if not (is_srs_cmd or looks_like_raw_requirements(prompt)):
        sys.exit(0)

    scan_output = run_gap_scanner(prompt)
    if not scan_output:
        sys.exit(0)

    # Inject gap scan as additionalContext
    output = {
        "additionalContext": (
            "## Pre-scan: Gap Scanner Results\n\n"
            f"{scan_output}\n\n"
            "> Use this as your Step 2 Gap Scan starting point. "
            "Validate, extend with Pattern 7 (contradictions) and semantic gaps, then proceed."
        )
    }
    print(json.dumps(output))


if __name__ == "__main__":
    main()
