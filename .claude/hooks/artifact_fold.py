#!/usr/bin/env python3
"""
Hook: PostToolUse Read|Grep|Bash
Detects large tool responses and emits ARTIFACT_FOLD_TRIGGERED, instructing
Claude to save the full output to .claude/artifacts/ and use a path reference.

Design: signal-only. PostToolUse hooks cannot prevent a large response from
entering context — this signals Claude to fold it in its next reply.

Thresholds from .ck.json artifactFolding.threshold.
"""

import sys
import json
import os
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from ck_config_utils import find_project_root as find_repo_root, get_section, is_enabled


def extract_response_text(tool_response) -> str:
    """Handle both bare string and {"output": ...} / {"content": ...} dict shapes."""
    if tool_response is None:
        return ""
    if isinstance(tool_response, str):
        return tool_response
    if isinstance(tool_response, dict):
        return tool_response.get("output") or tool_response.get("content") or ""
    return ""


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    # Skip sub-agents
    if payload.get("agent_id"):
        return

    response_text = extract_response_text(payload.get("tool_response"))
    if not response_text:
        return

    cwd = payload.get("cwd", os.getcwd())
    root = find_repo_root(cwd)
    if not root:
        return

    if not is_enabled("artifactFolding", root=root):
        return

    af = get_section("artifactFolding", root=root)
    thresh = af.get("threshold", {})
    try:
        max_chars = int(thresh.get("maxChars", 4000))
        max_lines = int(thresh.get("maxLines", 120))
        preview_lines = int(thresh.get("previewLines", 10))
    except Exception:
        max_chars, max_lines, preview_lines = 4000, 120, 10

    chars = len(response_text)
    lines = response_text.count("\n") + 1

    if chars <= max_chars and lines <= max_lines:
        return

    tool_name = payload.get("tool_name", "unknown").lower()
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    artifact_path = f".claude/artifacts/artifact-{ts}-{tool_name}.md"

    preview = "\n".join(response_text.splitlines()[:preview_lines])

    msg = (
        f"ARTIFACT_FOLD_TRIGGERED: {tool_name} output is {chars} chars / {lines} lines "
        f"(threshold: {max_chars} chars / {max_lines} lines). "
        f"Save full output to `{artifact_path}` and reference that path instead.\n"
        f"Preview (first {preview_lines} lines):\n{preview}\n..."
    )

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": msg
        }
    }))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # Never block Claude on hook errors
