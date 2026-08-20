"""
Project root detection, .ck.json config access, and common path helpers.

Usage:
    from ck_config_utils import (
        find_project_root, get_project_name, get_claude_dir, get_sessions_dir,
        load_ck_config, get_section, is_enabled,
    )
"""
import json
import os
import subprocess
from pathlib import Path

SESSION_DATA_DIR = "session-data"


# ── project root ──────────────────────────────────────────────────────────────

def find_project_root(cwd: str | None = None) -> Path | None:
    """Locate the git project root. Uses git CLI for worktree support,
    falls back to .git-directory walk, then CLAUDE_PROJECT_DIR env var."""
    work_dir = cwd or os.getcwd()
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True, text=True, timeout=5, cwd=work_dir,
        )
        if r.returncode == 0 and r.stdout.strip():
            p = Path(r.stdout.strip())
            if p.name == ".git":
                return p.parent
            s = str(p)
            marker = os.sep + ".git"
            idx = s.lower().rfind(marker.lower())
            if idx > 0:
                return Path(s[:idx])
    except Exception:
        pass

    # Fallback: walk up for .git directory
    start = Path(work_dir)
    for p in [start, *start.parents]:
        if (p / ".git").exists():
            return p

    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env and Path(env).exists():
        return Path(env)

    return None


# ── path helpers ──────────────────────────────────────────────────────────────

def get_home_dir() -> Path:
    explicit = os.environ.get("HOME") or os.environ.get("USERPROFILE")
    return Path(explicit) if explicit else Path.home()


def get_claude_dir() -> Path:
    return get_home_dir() / ".claude"


def get_sessions_dir(cwd: str | None = None) -> Path:
    root = find_project_root(cwd)
    if root:
        return root / ".claude" / SESSION_DATA_DIR
    return get_claude_dir() / SESSION_DATA_DIR


def get_project_name(cwd: str | None = None) -> str | None:
    work_dir = cwd or os.getcwd()
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5, cwd=work_dir,
        )
        if r.returncode == 0 and r.stdout.strip():
            return Path(r.stdout.strip()).name
    except Exception:
        pass
    return Path(work_dir).name or None


# ── .ck.json config ───────────────────────────────────────────────────────────

def load_ck_config(root: Path | None = None) -> dict:
    """Load .ck.json from project root. Returns empty dict on any failure."""
    r = root or find_project_root()
    if not r:
        return {}
    ck = r / ".ck.json"
    if not ck.exists():
        return {}
    try:
        return json.loads(ck.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def get_section(key: str, default: dict | None = None, root: Path | None = None) -> dict:
    """Return a top-level config section, or default if missing."""
    return load_ck_config(root).get(key, default if default is not None else {})


def is_enabled(key: str, root: Path | None = None) -> bool:
    """Return True if the config section exists and has enabled != false."""
    return get_section(key, root=root).get("enabled", True)
