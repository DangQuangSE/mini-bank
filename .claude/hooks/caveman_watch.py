#!/usr/bin/env python3
"""
Hook: UserPromptSubmit
Reads the tool-call counter (written by suggest_compact.py) and emits
CAVEMAN_TRIGGERED / CAVEMAN_RELEASED via additionalContext at orange/red
thresholds from .ck.json cavemanMode.threshold.

Only emits on state transitions (active → inactive, inactive → active)
to avoid re-triggering every prompt.

State: .claude/session-data/caveman-{session_id}.json  { "active": bool }
Counter: {TEMP}/claude-tool-count-{session_id}  (same path as suggest_compact.py)
"""

import sys
import json
import os
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from ck_config_utils import find_project_root as find_repo_root


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    # Skip sub-agents
    if payload.get("agent_id"):
        return

    # Match suggest_compact.py fallback chain so both hooks target the same counter file
    session_id = os.environ.get("CLAUDE_SESSION_ID") or os.environ.get("PPID", "default")
    if not session_id:
        return

    cwd = payload.get("cwd", os.getcwd())
    root = find_repo_root(cwd)
    if not root:
        return

    # Read .ck.json thresholds via shared lib
    from ck_config_utils import get_section, is_enabled as _is_enabled
    cm = get_section("cavemanMode", root=root)
    enabled = _is_enabled("cavemanMode", root=root)
    thresh = cm.get("threshold", {})
    try:
        orange = int(thresh.get("orange", 50))
        red = int(thresh.get("red", 100))
    except Exception:
        orange, red = 50, 100

    if not enabled:
        return

    # Read tool-call counter (same path pattern as suggest_compact.py)
    tmp_dir = Path(os.environ.get("TEMP", os.environ.get("TMPDIR", tempfile.gettempdir())))
    counter_file = tmp_dir / f"claude-tool-count-{session_id}"
    try:
        count = int(counter_file.read_text(encoding="utf-8").strip())
    except Exception:
        count = 0

    # Read current caveman state
    state_dir = root / ".claude" / "session-data"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / f"caveman-{session_id}.json"
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
        currently_active = bool(state.get("active", False))
    except Exception:
        currently_active = False

    # Determine desired state and message
    if count >= red:
        desired_active = True
        msg = (
            f"CAVEMAN_TRIGGERED: {count} tool calls (≥{red}, RED zone) — "
            f"activate caveman skill immediately. Run /compact at next boundary."
        )
    elif count >= orange:
        desired_active = True
        msg = (
            f"CAVEMAN_TRIGGERED: {count} tool calls (≥{orange}) — "
            f"activate caveman skill for terse output until /compact."
        )
    else:
        desired_active = False
        msg = "CAVEMAN_RELEASED: tool call count below threshold — normal output mode."

    # Only emit on state transition to avoid re-triggering every prompt
    if desired_active == currently_active:
        return

    # Atomic boolean write (no read-modify-write race)
    state_file.write_text(json.dumps({"active": desired_active}), encoding="utf-8")

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": msg
        }
    }))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # Never block Claude on hook errors
