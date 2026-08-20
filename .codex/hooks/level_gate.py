#!/usr/bin/env python3
"""
Virtual Team Skill — Level Gate Hook (Codex CLI port)

PreToolUse/apply_patch hook. Blocks writes to projects/{slug}/team/
directories unless projects/{slug}/team/.project-config.md exists and
contains a valid level.

This enforces that every project must have a level selected before any
agent can write artifacts. The level determines code depth, architecture
complexity, and QA compliance standards for the entire pipeline.

Ported from .claude/hooks/level_gate.py. Differences from the Claude
Code version:
  - Codex reports tool_name as "apply_patch" (not "Write"), even though
    the hooks.json matcher alias is "Write".
  - tool_input has a single `command` field containing the raw patch
    text instead of separate file_path/content fields — see
    _patch_utils.py for the parser. A single apply_patch call can touch
    multiple files, so every path in the patch is checked.
  - Codex reads the PreToolUse block reason from stderr (exit code 2),
    not stdout.

Valid levels:
  fresh   — School project (Fresher)
  junior  — Graduation thesis (Junior+)
  mid     — Production, medium complexity (Mid)
  senior  — Production, high complexity (Senior)

Exit codes:
  0 -> allow the write
  2 -> block the write, show error message to the agent (via stderr)
"""
import json
import sys
import io
import os
import re
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _patch_utils import all_paths

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

VALID_LEVELS = ("fresh", "junior", "mid", "senior")

LEVEL_LABELS = {
    "fresh":  "School project (Fresher level)",
    "junior": "Graduation thesis (Junior+ level)",
    "mid":    "Production — Medium complexity (Mid level)",
    "senior": "Production — High complexity (Senior level)",
}

_ALWAYS_ALLOW_SUFFIXES = (
    ".project-config.md",
)
_ALWAYS_ALLOW_SEGMENTS = (
    "/validation-errors/",
)


def normalize(path: str) -> str:
    return path.replace("\\", "/")


def is_team_write(path: str) -> bool:
    n = normalize(path)
    # Codex's apply_patch paths are typically repo-relative ("projects/x/team/...")
    # while Claude's Write tool gives absolute paths — match both.
    return re.search(r"(^|/)projects/", n) is not None and "/team/" in n


def is_exempt(path: str) -> bool:
    n = normalize(path)
    if any(n.endswith(s) for s in _ALWAYS_ALLOW_SUFFIXES):
        return True
    if any(seg in n for seg in _ALWAYS_ALLOW_SEGMENTS):
        return True
    return False


def extract_slug(path: str):
    m = re.search(r"projects/([^/]+)/team/", normalize(path))
    return m.group(1) if m else None


def find_config(slug: str) -> Path:
    candidate = Path(f"projects/{slug}/team/.project-config.md")
    if candidate.exists():
        return candidate
    for parent in Path.cwd().parents:
        candidate = parent / "projects" / slug / "team" / ".project-config.md"
        if candidate.exists():
            return candidate
    return Path(f"projects/{slug}/team/.project-config.md")


def read_level(config_path: Path):
    try:
        text = config_path.read_text(encoding="utf-8")
        m = re.search(r"\*\*level:\*\*\s*(\w+)", text)
        return m.group(1).strip().lower() if m else None
    except Exception:
        return None


def block_message(slug: str, reason: str) -> str:
    levels_list = "\n".join(
        f"  --level {lvl:8s}  {LEVEL_LABELS[lvl]}"
        for lvl in VALID_LEVELS
    )
    return (
        f"[Level Gate] X {reason}\n\n"
        f"Project: {slug}\n\n"
        f"Every project must declare a level before agents can write artifacts.\n"
        f"Choose one and re-run:\n\n"
        f"{levels_list}\n\n"
        f"Full pipeline example:\n"
        f"  $team \"your requirement\" --project {slug} --level mid\n\n"
        f"Per-agent example (BA creates the config automatically):\n"
        f"  $team-ba \"your requirement\" --project {slug} --level mid\n\n"
        f"Config location: projects/{slug}/team/.project-config.md"
    )


def check_path(file_path: str):
    """Returns a block message string, or None if this path is allowed."""
    if not is_team_write(file_path) or is_exempt(file_path):
        return None

    slug = extract_slug(file_path)
    if not slug:
        return None

    config_path = find_config(slug)

    if not config_path.exists():
        return block_message(slug, "No project level configured.")

    level = read_level(config_path)
    if level is None:
        return block_message(
            slug, ".project-config.md exists but is missing the **level:** field."
        )

    if level not in VALID_LEVELS:
        return block_message(
            slug,
            f".project-config.md has unrecognised level '{level}'. "
            f"Valid values: {', '.join(VALID_LEVELS)}.",
        )

    return None


def main():
    try:
        hook_input = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    if hook_input.get("tool_name") != "apply_patch":
        sys.exit(0)

    command = hook_input.get("tool_input", {}).get("command", "")
    if not command:
        sys.exit(0)

    for file_path in all_paths(command):
        message = check_path(file_path)
        if message:
            print(message, file=sys.stderr)
            sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
