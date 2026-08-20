#!/usr/bin/env python3
"""
Session State — persist and restore session context.

State file: .claude/session-data/.last-state.md
Archives:   .claude/session-data/archive/*.md  (max 10)

Usage as script:
  python session-state.py save   # reads stdin JSON for transcript_path
  python session-state.py load   # outputs SessionStart additionalContext payload
"""
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from ck_config_utils import find_project_root as get_project_root, get_project_name, get_sessions_dir
from hook_logger import HookLogger, strip_ansi
from session_utils import ensure_dir, get_datetime_string

_log = HookLogger("session-state")

STATE_FILENAME = ".last-state.md"
ARCHIVE_DIR_NAME = "archive"
MAX_ARCHIVES = 10
MAX_STDIN = 1024 * 1024


# ── git helpers ────────────────────────────────────────────────────────────────

def _git(*args: str) -> str:
    try:
        r = subprocess.run(["git"] + list(args), capture_output=True, text=True, timeout=5)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def _get_git_info() -> dict:
    return {
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD") or "unknown",
        "commit": _git("log", "-1", "--format=%h %s"),
        "status": _git("status", "--short"),
    }


# ── plan detection ─────────────────────────────────────────────────────────────

def _read_active_plan() -> str:
    root = get_project_root()
    if not root:
        return ""
    for name in ("plan.md", "PLAN.md", ".claude/plan.md"):
        try:
            text = (root / name).read_text(encoding="utf-8").strip()
            if len(text) > 1200:
                text = text[:1200] + "\n... (truncated)"
            return text
        except Exception:
            pass
    return ""


# ── transcript extraction ──────────────────────────────────────────────────────

def _extract_from_transcript(path: str) -> dict:
    result = {
        "userMessages": [],
        "toolsUsed": set(),
        "filesModified": set(),
        "totalMessages": 0,
    }
    try:
        fh = open(path, encoding="utf-8", errors="replace")
    except Exception:
        return result

    with fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                role = (
                    entry.get("role")
                    or entry.get("type")
                    or (entry.get("message") or {}).get("role")
                )

                if role == "user":
                    raw = (entry.get("message") or {}).get("content") or entry.get("content")
                    if isinstance(raw, str):
                        text = raw
                    elif isinstance(raw, list):
                        text = " ".join((c or {}).get("text", "") for c in raw)
                    else:
                        text = ""
                    cleaned = strip_ansi(text).strip()
                    if cleaned and not cleaned.startswith("<") and not cleaned.startswith("["):
                        result["userMessages"].append(cleaned[:200])

                if entry.get("type") == "tool_use" or entry.get("tool_name"):
                    tool = entry.get("tool_name") or entry.get("name", "")
                    if tool:
                        result["toolsUsed"].add(tool)
                    fp = (
                        (entry.get("tool_input") or {}).get("file_path")
                        or (entry.get("input") or {}).get("file_path", "")
                    )
                    if fp and tool in ("Edit", "Write"):
                        result["filesModified"].add(fp)

                if entry.get("type") == "assistant":
                    for block in ((entry.get("message") or {}).get("content") or []):
                        if (block or {}).get("type") == "tool_use":
                            tool = block.get("name", "")
                            if tool:
                                result["toolsUsed"].add(tool)
                            fp = (block.get("input") or {}).get("file_path", "")
                            if fp and tool in ("Edit", "Write"):
                                result["filesModified"].add(fp)

            except Exception:
                pass

    result["totalMessages"] = len(result["userMessages"])
    result["toolsUsed"] = sorted(result["toolsUsed"])[:20]
    result["filesModified"] = list(result["filesModified"])[:30]
    result["userMessages"] = result["userMessages"][-10:]
    return result


# ── state file builder ─────────────────────────────────────────────────────────

def _build_state(transcript: dict, git: dict, plan: str, timestamp: str, project_name: str) -> str:
    lines = [
        "# Session State",
        f"**Updated:** {timestamp}",
        f"**Project:** {project_name}",
        f"**Branch:** {git['branch']}",
        f"**Worktree:** {os.getcwd()}",
    ]
    if git["commit"]:
        lines.append(f"**Last Commit:** {git['commit']}")
    lines.append("")

    if git["status"]:
        lines += ["## Git Changes", "```", git["status"][:500], "```", ""]

    if plan:
        lines += ["## Active Plan", plan, ""]

    if transcript["userMessages"] or transcript["filesModified"]:
        lines.append("## Session Summary")
        if transcript["userMessages"]:
            lines.append("### Tasks")
            for msg in transcript["userMessages"]:
                lines.append(f"- {msg.replace('\n', ' ')}")
            lines.append("")
        if transcript["filesModified"]:
            lines.append("### Files Modified")
            for f in transcript["filesModified"]:
                lines.append(f"- {f}")
            lines.append("")
        if transcript["toolsUsed"]:
            lines += ["### Tools", ", ".join(transcript["toolsUsed"]), ""]
        lines += ["### Stats", f"- {transcript['totalMessages']} user messages", ""]

    return "\n".join(lines).rstrip() + "\n"


# ── archive rotation ───────────────────────────────────────────────────────────

def _rotate(state_dir: Path) -> None:
    """Archive .last-state.md and prune to MAX_ARCHIVES."""
    current = state_dir / STATE_FILENAME
    if not current.exists():
        return
    archive_dir = state_dir / ARCHIVE_DIR_NAME
    ensure_dir(archive_dir)
    ts = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    try:
        current.rename(archive_dir / f"{ts}.md")
    except Exception as e:
        _log.warn(f"Archive failed: {e}")
        return
    try:
        archives = sorted(archive_dir.glob("*.md"), key=lambda p: p.name)
        for old in archives[:max(0, len(archives) - MAX_ARCHIVES)]:
            old.unlink(missing_ok=True)
            _log.info(f"Pruned archive: {old.name}")
    except Exception:
        pass


# ── public API ─────────────────────────────────────────────────────────────────

def save_state(transcript_path: str | None = None) -> None:
    state_dir = get_sessions_dir()
    ensure_dir(state_dir)

    transcript = (
        _extract_from_transcript(transcript_path)
        if transcript_path and Path(transcript_path).exists()
        else {"userMessages": [], "toolsUsed": [], "filesModified": [], "totalMessages": 0}
    )
    git = _get_git_info()
    plan = _read_active_plan()
    timestamp = get_datetime_string()
    project_name = get_project_name() or "unknown"

    _rotate(state_dir)
    content = _build_state(transcript, git, plan, timestamp, project_name)
    (state_dir / STATE_FILENAME).write_text(content, encoding="utf-8")
    _log.info(f"Saved → {STATE_FILENAME}")


def load_state() -> str:
    state_file = get_sessions_dir() / STATE_FILENAME
    if not state_file.exists():
        return ""
    try:
        return strip_ansi(state_file.read_text(encoding="utf-8").strip())
    except Exception:
        return ""


# ── CLI entry point ────────────────────────────────────────────────────────────

def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "save"

    if mode == "load":
        content = load_state()
        if content:
            sys.stdout.write(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": f"Previous session state:\n{content}",
                }
            }))
            sys.stdout.flush()
    else:
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
        _log.error(str(e))
        sys.exit(0)
