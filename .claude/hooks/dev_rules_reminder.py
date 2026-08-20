#!/usr/bin/env python3
"""
UserPromptSubmit hook — inject session context and active plan info.

Detects the active /ck: command from the user message and picks the matching
context file. Falls back to .ck.json `context` field, then "dev".

Command → context mapping:
  /ck:cook, /ck:fix, /ck:test, /ck:docs-fe → dev
  /ck:brainstorm, /ck:plan, /ck:learn     → research
  /ck:quality, /ck:code-review             → review
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from ck_config_utils import find_project_root, load_ck_config

PLANS_DIR = "plans"
STATUS_ACTIVE = "🟡"
STATUS_COMPLETE = "✅"
MAX_ACTIVE_PLANS = 3
DEFAULT_CONTEXT = "dev"
FALLBACK_RULES = "YAGNI · KISS · DRY · Brutal honesty · Challenge assumptions"

COMMAND_CONTEXT_MAP: dict[str, str] = {
    "/ck:cook": "dev",
    "/ck:fix": "dev",
    "/ck:test": "dev",
    "/ck:docs-fe": "dev",
    "/ck:brainstorm": "research",
    "/ck:plan": "research",
    "/ck:learn": "research",
    "/ck:code-review": "review",
    "/ck:quality": "review",
}


def detect_context_from_message(message: str) -> str | None:
    """Return the context name if the message invokes a known /ck: command."""
    for command, ctx in COMMAND_CONTEXT_MAP.items():
        if command in message:
            return ctx
    return None


def _git(*args: str) -> str:
    try:
        r = subprocess.run(["git"] + list(args), capture_output=True, text=True, timeout=3)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def get_session_header() -> str:
    project = Path(os.getcwd()).name
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    parts = [f"Project: {project}"]
    if branch:
        parts.append(f"Branch: {branch}")
    return " | ".join(parts)


def load_context_file(root: Path, mode: str) -> str | None:
    ctx_file = root / ".claude" / "contexts" / f"{mode}.md"
    if ctx_file.exists():
        return ctx_file.read_text(encoding="utf-8", errors="replace").strip()
    return None


def find_active_plans(root: Path) -> list[dict]:
    plans_root = root / PLANS_DIR
    if not plans_root.exists():
        return []

    active = []
    for plan_dir in sorted(plans_root.iterdir()):
        if not plan_dir.is_dir():
            continue
        plan_file = plan_dir / "plan.md"
        if not plan_file.exists():
            continue

        content = plan_file.read_text(encoding="utf-8", errors="replace")
        if STATUS_COMPLETE in content:
            continue
        if STATUS_ACTIVE not in content:
            continue

        info = _parse_plan(plan_file, content)
        if info:
            active.append(info)

    active.sort(key=lambda p: p["mtime"], reverse=True)
    return active[:MAX_ACTIVE_PLANS]


def _parse_plan(plan_file: Path, content: str) -> dict | None:
    name_match = re.search(r"^#\s+Plan:\s+(.+)$", content, re.MULTILINE)
    mode_match = re.search(r"^Mode:\s+(.+)$", content, re.MULTILINE)

    name = name_match.group(1).strip() if name_match else plan_file.parent.name
    mode = mode_match.group(1).strip() if mode_match else "Unknown"

    phases = re.findall(r"- \[([ x])\] Phase \d+: (.+)", content)
    next_phase = None
    completed = sum(1 for done, _ in phases if done == "x")
    total = len(phases)
    for done, phase_name in phases:
        if done != "x" and next_phase is None:
            next_phase = phase_name.split("—")[0].strip()

    return {
        "name": name,
        "mode": mode,
        "path": str(plan_file),
        "next_phase": next_phase,
        "progress": f"{completed}/{total}",
        "mtime": plan_file.stat().st_mtime,
    }


def build_context(header: str, context_body: str, active_plans: list[dict]) -> str:
    lines = [header, "", context_body]

    if active_plans:
        lines.append("")
        for plan in active_plans:
            next_info = f"next → {plan['next_phase']}" if plan["next_phase"] else "all phases complete"
            lines.append(f"Active plan: [{plan['mode']}] {plan['name']} ({plan['progress']} phases) — {next_info}")
            lines.append(f"  Plan file: {plan['path']}")

    return "\n".join(lines)


def main():
    user_message = ""
    try:
        payload = json.loads(sys.stdin.read())
        user_message = payload.get("message", "") or ""
    except (json.JSONDecodeError, EOFError, AttributeError):
        pass

    root = find_project_root() or Path(os.getcwd())
    config = load_ck_config(root)

    detected = detect_context_from_message(user_message)
    context_mode = detected or config.get("context", DEFAULT_CONTEXT)

    context_body = load_context_file(root, context_mode)
    if context_body is None:
        context_body = f"Rules: {FALLBACK_RULES}"

    header = get_session_header()
    active_plans = find_active_plans(root)
    output = build_context(header, context_body, active_plans)

    sys.stdout.write(json.dumps({"hookSpecificOutput": {"additionalContext": output}}))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
