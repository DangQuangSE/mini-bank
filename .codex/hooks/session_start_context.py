#!/usr/bin/env python3
"""
Hook: SessionStart (Codex CLI port)
Fires once when a new session begins (new chat, /new, or resume).

Scans projects/ on disk and prints a status digest, so a fresh session
immediately knows which SRS / Virtual Team phases are done for each
project without the user having to re-explain or run $team-list manually.

Ported from .claude/hooks/session_start_context.py. The scan logic is
unchanged — this hook doesn't touch tool_input/file paths at all, only
`projects/` on disk, so the Claude vs Codex tool-call schema difference
doesn't apply here. The only change is the output: plain text on stdout
(Codex docs confirm this is added as extra developer context for
SessionStart hooks) instead of Claude's {"additionalContext": ...} JSON
envelope.
"""

import json
import sys
from pathlib import Path

PROJECTS_DIR = Path(__file__).parent.parent.parent / "projects"
MAX_PROJECTS = 8

TEAM_PHASES = [
    ("ba", "BA"),
    ("techlead", "TechLead"),
    ("pm", "PM"),
    ("be", "BE Dev"),
    ("fe", "FE Dev"),
    ("tester", "Tester"),
    ("qa", "QA/QC"),
]


def has_files(d: Path) -> bool:
    return d.is_dir() and any(d.iterdir())


def srs_status(project_dir: Path) -> str:
    steps = [
        ("brainstorm.md", (project_dir / "brainstorm.md").is_file()),
        ("spec.md", (project_dir / "spec.md").is_file()),
        ("plan/", has_files(project_dir / "plan")),
        ("srs/", has_files(project_dir / "srs")),
        ("_context/", has_files(project_dir / "_context")),
    ]
    return "  ".join(f"{name}{'OK' if done else '--'}" for name, done in steps)


def team_status(project_dir: Path):
    team_dir = project_dir / "team"
    if not team_dir.is_dir():
        return None
    config = team_dir / ".project-config.md"
    level = None
    if config.is_file():
        text = config.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            if "**level:**" in line.lower():
                level = line.split(":**", 1)[-1].strip()
                break
    phases = "  ".join(
        f"{label}{'OK' if has_files(team_dir / key) else '--'}"
        for key, label in TEAM_PHASES
    )
    flags = (project_dir / "flags-summary.md").is_file()
    return level, phases, flags


def build_report() -> str:
    if not PROJECTS_DIR.is_dir():
        return ""

    projects = [p for p in PROJECTS_DIR.iterdir() if p.is_dir()]
    if not projects:
        return ""

    projects.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    shown, rest = projects[:MAX_PROJECTS], projects[MAX_PROJECTS:]

    lines = ["## Project Progress (auto-loaded at session start)", ""]
    for p in shown:
        lines.append(f"### {p.name}")
        lines.append(f"- SRS workflow: {srs_status(p)}")
        team = team_status(p)
        if team:
            level, phases, flags = team
            lvl_str = f"level={level}" if level else "level=NOT SET"
            lines.append(f"- Team pipeline ({lvl_str}): {phases}")
            if flags:
                lines.append("- flags-summary.md present — check for unresolved cross-agent flags")
        else:
            lines.append("- Team pipeline: not started")
        lines.append("")

    if rest:
        lines.append(f"...and {len(rest)} more project(s). Run $team-list for the full list.")
        lines.append("")

    lines.append(
        "> Use --project {slug} on the relevant skill to resume from where a project left off."
    )
    return "\n".join(lines)


def main() -> None:
    try:
        json.load(sys.stdin)
    except Exception:
        pass

    report = build_report()
    if not report:
        sys.exit(0)

    print(report)


if __name__ == "__main__":
    main()
