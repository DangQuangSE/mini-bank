#!/usr/bin/env python3
"""
Hook: PostToolUse (apply_patch) — Codex CLI port

Fires after Codex applies a patch. For every file added/updated by the
patch: if the path is inside a 'plan/' directory, auto-runs
plan_validator.py (Phase 4 readiness gate). If it looks like an SRS (path
contains 'srs' and ends in .md), auto-runs srs_validator.py. Either way
the verdict is printed to stdout so Codex picks it up as extra context.

Ported from .claude/hooks/post_srs.py. tool_input has a `command` field
(raw patch text) instead of file_path; _patch_utils splits out every
touched path. Output is plain text on stdout instead of a Claude-style
{"additionalContext": ...} JSON blob — Codex docs confirm plain stdout
text is added as extra developer context for PostToolUse hooks too.
"""

import json
import subprocess
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _patch_utils import all_paths

# Keep validator dependencies inside .codex so this setup is self-contained.
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"


def is_plan_file(file_path: str) -> bool:
    p = Path(file_path)
    return p.suffix == ".md" and p.parent.name.lower() == "plan"


def is_srs_file(file_path: str) -> bool:
    p = Path(file_path)
    if p.suffix != ".md":
        return False
    path_str = str(p).lower().replace("\\", "/")
    return "srs" in p.name.lower() or "/srs/" in path_str


def run_script(script_name: str, args: list[str]) -> str | None:
    script = SCRIPTS_DIR / script_name
    if not script.exists():
        return None
    try:
        result = subprocess.run(
            [sys.executable, str(script), *args],
            capture_output=True, text=True, timeout=25, encoding="utf-8"
        )
        return result.stdout.strip()
    except Exception:
        return None


def handle_path(file_path: str) -> None:
    if is_plan_file(file_path):
        plan_dir = str(Path(file_path).parent)
        validation = run_script("plan_validator.py", ["--dir", plan_dir])
        if not validation:
            return
        print(
            f"## Post-save: Plan Validation\n\n"
            f"{validation}\n\n"
            "> Fix ERROR findings before running $sr-generate — they will block the gate. "
            "WARNs (e.g. open [NEEDS USER INPUT] items) should be tracked in appendix-b-open-issues.md."
        )
        return

    if not is_srs_file(file_path):
        return

    p = Path(file_path)
    if p.parent.name.lower() == "srs":
        validation = run_script("srs_validator.py", ["--dir", str(p.parent)])
    else:
        validation = run_script("srs_validator.py", [file_path])
    if not validation:
        return

    print(
        f"## Post-save: SRS Validation\n\n"
        f"{validation}\n\n"
        "> Fix any ERROR findings before marking the SRS as ready for review. "
        "WARN items should be resolved or explicitly acknowledged."
    )


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    if event.get("tool_name", "") != "apply_patch":
        sys.exit(0)

    command = event.get("tool_input", {}).get("command", "")
    if not command:
        sys.exit(0)

    for file_path in all_paths(command):
        handle_path(file_path)


if __name__ == "__main__":
    main()
