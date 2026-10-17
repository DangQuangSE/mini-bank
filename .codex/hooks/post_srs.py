#!/usr/bin/env python3
"""
Hook: PostToolUse (apply_patch) for Codex CLI.

For every file added or updated by the patch, this hook runs the relevant
plan or SRS validator. The result is returned as one
hookSpecificOutput.additionalContext JSON object; plain PostToolUse stdout is
not consumed as hook context by Codex.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _patch_utils import all_paths


# Keep validator dependencies inside .codex so this setup is self-contained.
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"


def is_plan_file(file_path: str) -> bool:
    path = Path(file_path)
    return path.suffix == ".md" and path.parent.name.lower() == "plan"


def is_srs_file(file_path: str) -> bool:
    path = Path(file_path)
    if path.suffix != ".md":
        return False
    path_str = str(path).lower().replace("\\", "/")
    return "srs" in path.name.lower() or "/srs/" in path_str


def run_script(script_name: str, args: list[str]) -> str | None:
    script = SCRIPTS_DIR / script_name
    if not script.exists():
        return None
    try:
        result = subprocess.run(
            [sys.executable, str(script), *args],
            capture_output=True,
            text=True,
            timeout=25,
            encoding="utf-8",
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
            "## Post-save: Plan Validation\n\n"
            f"{validation}\n\n"
            "> Fix ERROR findings before running $sr-generate - they will block "
            "the gate. WARNs (e.g. open [NEEDS USER INPUT] items) should be "
            "tracked in appendix-b-open-issues.md."
        )
        return

    if not is_srs_file(file_path):
        return

    path = Path(file_path)
    if path.parent.name.lower() == "srs":
        validation = run_script("srs_validator.py", ["--dir", str(path.parent)])
    else:
        validation = run_script("srs_validator.py", [file_path])
    if not validation:
        return

    print(
        "## Post-save: SRS Validation\n\n"
        f"{validation}\n\n"
        "> Fix any ERROR findings before marking the SRS as ready for review. "
        "WARN items should be resolved or explicitly acknowledged."
    )


def emit_post_tool_context(context: str) -> None:
    if not context:
        return
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": context,
                }
            },
            ensure_ascii=False,
        )
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

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        for file_path in all_paths(command):
            handle_path(file_path)
    emit_post_tool_context(output.getvalue().strip())


if __name__ == "__main__":
    main()
