#!/usr/bin/env python3
"""
Virtual Team Skill — Cross-Agent Flag Aggregator (Codex CLI port)

PostToolUse hook. Triggers automatically after team/qa/sign-off.md is
written, signalling that the full pipeline has completed.

Responsibilities (FR-39):
  - Scan all team artifact .md files for ## Flags from Previous Agents sections
  - Extract every FLAG-{ROLE}-{NNN} entry
  - Write a consolidated flags-summary.md to projects/{slug}/
  - Print a formatted WARNING to the terminal with severity counts

Ported from .claude/hooks/flag_aggregator.py. tool_input has a `command`
field (raw patch text) instead of file_path; _patch_utils splits out
every touched path so we can detect the sign-off write regardless of how
many other files were in the same apply_patch call. Since this is a
PostToolUse hook, the patch has already been applied — artifact files on
disk reflect their final content, so the flag scan itself (which reads
from disk, not from the patch) is unchanged from the Claude version.

Output:
  - projects/{slug}/flags-summary.md
  - Console: warning block (or clean confirmation if no flags)

Exit codes:
  0 -> always (this hook never blocks — it runs after the write succeeds)
"""
import json
import sys
import os
import re
import io
import argparse
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _patch_utils import all_paths

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

FLAGS_HEADING = "## Flags from Previous Agents"

NO_FLAG_MARKERS = frozenset({
    "no flags detected",
    "no flags detected.",
    "none",
    "none.",
    "no flags",
    "none detected",
    "none detected.",
})

FLAG_ID_RE = re.compile(r"FLAG-([A-Z]+)-(\d+)", re.IGNORECASE)

AGENT_SCAN_ORDER = [
    ("techlead", "TechLead Agent (reviewing BA artifacts)",            "team/techlead/architecture.md"),
    ("tester",   "Tester Agent (reviewing all preceding artifacts)",   "team/tester/test-plan.md"),
    ("qa",       "QA/QC Agent (reviewing all artifacts)",             "team/qa/quality-report.md"),
]

SEVERITY_RANK = {"blocker": 0, "critical": 0, "major": 1, "minor": 2, "unknown": 3}


def _norm(path: str) -> str:
    return path.replace("\\", "/")


def extract_slug(file_path: str) -> str:
    m = re.search(r"projects/([^/]+)/team/", _norm(file_path))
    return m.group(1) if m else None


def extract_project_root(file_path: str) -> str:
    n = _norm(file_path)
    # Match both absolute paths (Claude's Write) and repo-relative paths
    # (Codex's apply_patch, which has no leading prefix before "projects/").
    m = re.search(r"^(.*projects/[^/]+)/team/", n)
    return m.group(1) if m else None


def _read_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def _extract_flags_section(content: str) -> str:
    idx = content.find(FLAGS_HEADING)
    if idx == -1:
        return ""
    section = content[idx + len(FLAGS_HEADING):]
    stop = re.search(r"\n## ", section)
    return section[: stop.start()] if stop else section


def _is_empty_flags_section(section: str) -> bool:
    stripped = section.strip().lower()
    return not stripped or stripped in NO_FLAG_MARKERS or any(
        marker in stripped for marker in NO_FLAG_MARKERS
    )


def _parse_flag_blocks(section: str, source_file: str) -> list[dict]:
    flags: list[dict] = []
    blocks = re.split(r"(?m)^###\s+", section)

    for block in blocks:
        if not block.strip():
            continue

        flag_match = FLAG_ID_RE.search(block)
        if not flag_match:
            continue

        role = flag_match.group(1).upper()
        num = flag_match.group(2).zfill(3)
        flag_id = f"FLAG-{role}-{num}"

        severity_m  = re.search(r"\*\*Severity:\*\*\s*(.+?)(?:\n|$)", block, re.I)
        source_m    = re.search(r"\*\*Source artifact:\*\*\s*(.+?)(?:\n|$)", block, re.I)
        issue_m     = re.search(r"\*\*Issue:\*\*\s*(.+?)(?=\n\*\*|\Z)", block, re.I | re.DOTALL)
        suggestion_m = re.search(r"\*\*Suggestion:\*\*\s*(.+?)(?=\n\*\*|\Z)", block, re.I | re.DOTALL)

        severity = severity_m.group(1).strip() if severity_m else "Unknown"
        flags.append({
            "id":         flag_id,
            "role":       role,
            "severity":   severity,
            "source":     source_m.group(1).strip() if source_m else os.path.basename(source_file),
            "issue":      (issue_m.group(1).strip()[:300] if issue_m else block[:200].strip()),
            "suggestion": (suggestion_m.group(1).strip()[:200] if suggestion_m else ""),
            "found_in":   os.path.basename(source_file),
            "_rank":      SEVERITY_RANK.get(severity.lower(), 3),
        })

    return flags


def extract_flags_from_artifact(artifact_path: str) -> list[dict]:
    content = _read_file(artifact_path)
    if not content:
        return []
    section = _extract_flags_section(content)
    if _is_empty_flags_section(section):
        return []
    return _parse_flag_blocks(section, artifact_path)


def collect_all_flags(project_root: str) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {}
    for agent_key, _label, rel_path in AGENT_SCAN_ORDER:
        artifact_path = os.path.join(project_root, rel_path)
        flags = extract_flags_from_artifact(artifact_path)
        if flags:
            flags.sort(key=lambda f: f["_rank"])
            result[agent_key] = flags
    return result


def _severity_counts(all_flags: dict[str, list[dict]]) -> tuple[int, int, int]:
    critical = major = minor = 0
    for flags in all_flags.values():
        for f in flags:
            r = f["_rank"]
            if r == 0:
                critical += 1
            elif r == 1:
                major += 1
            else:
                minor += 1
    return critical, major, minor


def write_flags_summary(project_root: str, slug: str, all_flags: dict[str, list[dict]]) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    total = sum(len(v) for v in all_flags.values())
    critical, major, minor = _severity_counts(all_flags)

    lines: list[str] = [
        "# Cross-Agent Flags Summary",
        f"project: {slug}",
        f"generated: {timestamp}",
        f"total: {total} flag(s)  |  Blocker/Critical: {critical}  Major: {major}  Minor: {minor}",
        "",
    ]

    agent_label_map = {key: label for key, label, _ in AGENT_SCAN_ORDER}

    if not all_flags:
        lines += [
            "## Result",
            "",
            "No cross-agent flags detected. All agents reported clean artifacts.",
        ]
    else:
        for agent_key, flags in all_flags.items():
            label = agent_label_map.get(agent_key, agent_key.upper())
            lines.append(f"## Flags from {label}")
            lines.append("")
            for flag in flags:
                lines.append(f"### {flag['id']}")
                lines.append(f"**Severity:** {flag['severity']}")
                lines.append(f"**Source artifact:** {flag['source']}")
                lines.append(f"**Issue:** {flag['issue']}")
                if flag["suggestion"]:
                    lines.append(f"**Suggestion:** {flag['suggestion']}")
                lines.append("")

    content = "\n".join(lines)
    summary_path = os.path.join(project_root, "flags-summary.md")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(content)

    return summary_path


def print_report(all_flags: dict[str, list[dict]], summary_path: str, slug: str) -> None:
    total = sum(len(v) for v in all_flags.values())

    if total == 0:
        print()
        print("[Flag Aggregator] Pipeline is clean — no cross-agent flags detected.")
        print(f"[Flag Aggregator] Summary written: {summary_path}")
        print()
        return

    critical, major, minor = _severity_counts(all_flags)

    bar = "=" * 64
    print()
    print(bar)
    print(f"  WARNING  {total} cross-agent flag(s) detected — project: {slug}")
    print(f"  Blocker/Critical: {critical}   Major: {major}   Minor: {minor}")
    print(bar)

    agent_label_map = {key: label for key, label, _ in AGENT_SCAN_ORDER}
    for agent_key, flags in all_flags.items():
        label = agent_label_map.get(agent_key, agent_key.upper())
        print(f"\n  From {label}:")
        for flag in flags:
            sev_tag = f"[{flag['severity'][:8]:8s}]"
            issue_short = flag["issue"][:68].replace("\n", " ")
            print(f"    {sev_tag}  {flag['id']}")
            print(f"               {issue_short}")

    print()
    print(f"  See: {summary_path}")
    print(bar)
    print()


def _run_cli(team_dir: str) -> None:
    team_dir = os.path.abspath(team_dir)
    if os.path.basename(team_dir).lower() != "team":
        raise SystemExit("--dir must point to projects/{slug}/team/")

    project_root = os.path.dirname(team_dir)
    slug = os.path.basename(project_root)
    if not slug:
        raise SystemExit("Could not infer project slug from --dir")

    all_flags = collect_all_flags(project_root)
    summary_path = write_flags_summary(project_root, slug, all_flags)
    print_report(all_flags, summary_path, slug)


def main() -> None:
    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser(
            description="Aggregate cross-agent flags for a completed team pipeline."
        )
        parser.add_argument("--dir", required=True, help="Path to projects/{slug}/team/")
        args = parser.parse_args()
        _run_cli(args.dir)
        return

    try:
        hook_input = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    if hook_input.get("tool_name") != "apply_patch":
        sys.exit(0)

    command = hook_input.get("tool_input", {}).get("command", "")
    if not command:
        sys.exit(0)

    sign_off_path = next(
        (p for p in all_paths(command) if _norm(p).endswith("team/qa/sign-off.md")),
        None,
    )
    if not sign_off_path:
        sys.exit(0)

    slug = extract_slug(sign_off_path)
    project_root = extract_project_root(sign_off_path)

    if not slug or not project_root:
        sys.exit(0)

    all_flags = collect_all_flags(project_root)
    summary_path = write_flags_summary(project_root, slug, all_flags)
    print_report(all_flags, summary_path, slug)

    sys.exit(0)


if __name__ == "__main__":
    main()
