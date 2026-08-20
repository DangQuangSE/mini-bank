#!/usr/bin/env python3
"""
Hook: PostToolUse (Write)
Fires after Claude writes a file.

If the written file is inside a 'plan/' directory, auto-runs plan_validator.py
(Phase 4 readiness gate). If it looks like an SRS (path contains 'srs' and ends
in .md), auto-runs srs_validator.py. Either way the verdict is injected as
additionalContext.
"""

import json
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"


def is_plan_file(file_path: str) -> bool:
    p = Path(file_path)
    return p.suffix == ".md" and p.parent.name.lower() == "plan"


def is_srs_file(file_path: str) -> bool:
    p = Path(file_path)
    if p.suffix != ".md":
        return False
    # Match: srs-*.md name OR file inside a path component named 'srs'
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


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    tool_name = event.get("tool_name", "")
    if tool_name != "Write":
        sys.exit(0)

    file_path = event.get("tool_input", {}).get("file_path", "")
    if not file_path:
        sys.exit(0)

    if is_plan_file(file_path):
        plan_dir = str(Path(file_path).parent)
        validation = run_script("plan_validator.py", ["--dir", plan_dir])
        if not validation:
            sys.exit(0)
        output = {
            "additionalContext": (
                f"## Post-save: Plan Validation\n\n"
                f"{validation}\n\n"
                "> Fix ERROR findings before running /sr:generate — they will block the gate. "
                "WARNs (e.g. open [NEEDS USER INPUT] items) should be tracked in appendix-b-open-issues.md."
            )
        }
        print(json.dumps(output))
        return

    if not is_srs_file(file_path):
        sys.exit(0)

    p = Path(file_path)
    # If file is inside a directory named 'srs', validate the whole directory
    if p.parent.name.lower() == "srs":
        validation = run_script("srs_validator.py", ["--dir", str(p.parent)])
    else:
        validation = run_script("srs_validator.py", [file_path])
    if not validation:
        sys.exit(0)

    output = {
        "additionalContext": (
            f"## Post-save: SRS Validation\n\n"
            f"{validation}\n\n"
            "> Fix any ERROR findings before marking the SRS as ready for review. "
            "WARN items should be resolved or explicitly acknowledged."
        )
    }
    print(json.dumps(output))


if __name__ == "__main__":
    main()
