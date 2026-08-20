#!/usr/bin/env python3
"""Stop Hook — persist session state after each response."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
sys.path.insert(0, str(Path(__file__).parent))
from hook_logger import HookLogger
from session_state import save_state

MAX_STDIN = 1024 * 1024


def main() -> None:
    stdin_data = sys.stdin.read(MAX_STDIN)
    transcript_path = None
    try:
        transcript_path = json.loads(stdin_data).get("transcript_path")
    except Exception:
        transcript_path = os.environ.get("CLAUDE_TRANSCRIPT_PATH")
    save_state(transcript_path)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        HookLogger("session-end").error(str(e))
        sys.exit(0)
