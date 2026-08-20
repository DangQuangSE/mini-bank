#!/usr/bin/env python3
"""
Virtual Team Skill — Level Gate Hook

PreToolUse/Write hook. Blocks writes to projects/{slug}/team/ directories
unless projects/{slug}/team/.project-config.md exists and contains a valid level.

This enforces that every project must have a level selected before any agent
can write artifacts. The level determines code depth, architecture complexity,
and QA compliance standards for the entire pipeline.

Valid levels:
  fresh   — School project (Fresher)
  junior  — Graduation thesis (Junior+)
  mid     — Production, medium complexity (Mid)
  senior  — Production, high complexity (Senior)

Exit codes:
  0 -> allow the write
  2 -> block the write, show error message to agent
"""
import json
import sys
import io
import os
import re
from pathlib import Path

# Force UTF-8 output (Windows cp1252 default)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

VALID_LEVELS = ("fresh", "junior", "mid", "senior")

LEVEL_LABELS = {
    "fresh":  "School project (Fresher level)",
    "junior": "Graduation thesis (Junior+ level)",
    "mid":    "Production — Medium complexity (Mid level)",
    "senior": "Production — High complexity (Senior level)",
}

# Paths that are always allowed even without a project-config
_ALWAYS_ALLOW_SUFFIXES = (
    ".project-config.md",   # the config file itself
)
_ALWAYS_ALLOW_SEGMENTS = (
    "/validation-errors/",  # error logs from retry_controller
)


# ─────────────────────────────────────────────
# PATH HELPERS
# ─────────────────────────────────────────────

def normalize(path: str) -> str:
    return path.replace("\\", "/")


def is_team_write(path: str) -> bool:
    n = normalize(path)
    return "/projects/" in n and "/team/" in n


def is_exempt(path: str) -> bool:
    n = normalize(path)
    if any(n.endswith(s) for s in _ALWAYS_ALLOW_SUFFIXES):
        return True
    if any(seg in n for seg in _ALWAYS_ALLOW_SEGMENTS):
        return True
    return False


def extract_slug(path: str):
    """Return project slug from 'projects/{slug}/team/...' path."""
    m = re.search(r"projects/([^/]+)/team/", normalize(path))
    return m.group(1) if m else None


# ─────────────────────────────────────────────
# CONFIG HELPERS
# ─────────────────────────────────────────────

def find_config(slug: str) -> Path:
    """Return Path to .project-config.md regardless of CWD depth."""
    # Try relative first (most common case — hook runs from workspace root)
    candidate = Path(f"projects/{slug}/team/.project-config.md")
    if candidate.exists():
        return candidate
    # Also try parent dirs in case CWD is inside the project
    for parent in Path.cwd().parents:
        candidate = parent / "projects" / slug / "team" / ".project-config.md"
        if candidate.exists():
            return candidate
    return Path(f"projects/{slug}/team/.project-config.md")  # not found but return path


def read_level(config_path: Path):
    """Extract level string from .project-config.md. Returns None if not found."""
    try:
        text = config_path.read_text(encoding="utf-8")
        m = re.search(r"\*\*level:\*\*\s*(\w+)", text)
        return m.group(1).strip().lower() if m else None
    except Exception:
        return None


# ─────────────────────────────────────────────
# BLOCK MESSAGE
# ─────────────────────────────────────────────

def block_message(slug: str, reason: str) -> str:
    levels_list = "\n".join(
        f"  --level {lvl:8s}  {LEVEL_LABELS[lvl]}"
        for lvl in VALID_LEVELS
    )
    return (
        f"[Level Gate] ✗ {reason}\n\n"
        f"Project: {slug}\n\n"
        f"Every project must declare a level before agents can write artifacts.\n"
        f"Choose one and re-run:\n\n"
        f"{levels_list}\n\n"
        f"Full pipeline example:\n"
        f"  /team \"your requirement\" --project {slug} --level mid\n\n"
        f"Per-agent example (BA creates the config automatically):\n"
        f"  /team-ba \"your requirement\" --project {slug} --level mid\n\n"
        f"Config location: projects/{slug}/team/.project-config.md"
    )


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    try:
        hook_input = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    if hook_input.get("tool_name") != "Write":
        sys.exit(0)

    tool_input = hook_input.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    # Only intercept team artifact writes
    if not is_team_write(file_path):
        sys.exit(0)

    # Exempt paths (config file itself, validation errors)
    if is_exempt(file_path):
        sys.exit(0)

    slug = extract_slug(file_path)
    if not slug:
        sys.exit(0)  # Cannot determine slug — don't block

    config_path = find_config(slug)

    # ── Gate 1: config file must exist ───────────────────────
    if not config_path.exists():
        print(
            block_message(slug, "No project level configured."),
            file=sys.stdout,
        )
        sys.exit(2)

    # ── Gate 2: level field must be present ──────────────────
    level = read_level(config_path)
    if level is None:
        print(
            block_message(
                slug,
                ".project-config.md exists but is missing the **level:** field.",
            ),
            file=sys.stdout,
        )
        sys.exit(2)

    # ── Gate 3: level must be a recognised value ─────────────
    if level not in VALID_LEVELS:
        print(
            block_message(
                slug,
                f".project-config.md has unrecognised level '{level}'. "
                f"Valid values: {', '.join(VALID_LEVELS)}.",
            ),
            file=sys.stdout,
        )
        sys.exit(2)

    # All gates passed — allow the write
    sys.exit(0)


if __name__ == "__main__":
    main()
