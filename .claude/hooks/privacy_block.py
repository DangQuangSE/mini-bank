#!/usr/bin/env python3
"""
PreToolUse Read|Write|Edit|Bash hook — block access to sensitive files.

Detection logic lives in hooks/lib/privacy_checker.py.
Allow-list: add filenames/paths to privacyBlock.allowList in .ck.json to bypass.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from ck_config_utils import is_enabled
from hook_logger import HookLogger
from privacy_checker import check_bash, check_file, load_allow_list


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    if not is_enabled("privacyBlock"):
        sys.exit(0)

    log = HookLogger("privacy-block")
    allow_list = load_allow_list()
    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})

    if tool_name in ("Read", "Write", "Edit"):
        file_path = tool_input.get("file_path", "")
        match = check_file(file_path, allow_list)
        if match:
            sys.stderr.write(
                f"[privacy-block] Blocked: {Path(file_path).name!r} matches pattern '{match}'.\n"
                f"To allow, add the filename to privacyBlock.allowList in .ck.json "
                f"or ask the user for explicit permission."
            )
            sys.exit(2)

    elif tool_name == "Bash":
        cmd = tool_input.get("command", "")
        match = check_bash(cmd, allow_list)
        if match:
            sys.stderr.write(
                f"[privacy-block] Blocked: Bash command references sensitive file ({match!r}).\n"
                f"To allow, add the filename to privacyBlock.allowList in .ck.json "
                f"or ask the user for explicit permission."
            )
            sys.exit(2)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
