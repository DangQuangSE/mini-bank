#!/usr/bin/env python3
"""
Virtual Team Skill — Cross-Agent Flag Aggregator

PostToolUse hook. Triggers automatically after team/qa/sign-off.md is written,
signalling that the full pipeline has completed.

Responsibilities (FR-39):
  - Scan all team artifact .md files for ## Flags from Previous Agents sections
  - Extract every FLAG-{ROLE}-{NNN} entry
  - Write a consolidated flags-summary.md to projects/{slug}/
  - Print a formatted WARNING to the terminal with severity counts

Output:
  - projects/{slug}/flags-summary.md
  - Console: warning block (or clean confirmation if no flags)

Exit codes:
  0 → always (this hook never blocks — it runs after the write succeeds)
"""
import json
import sys
import os
import re
import io
from datetime import datetime, timezone

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ── Constants ────────────────────────────────────────────────────────────────

# Section heading that contains cross-agent flags
FLAGS_HEADING = "## Flags from Previous Agents"

# Content patterns that mean "no flags found"
NO_FLAG_MARKERS = frozenset({
    "no flags detected",
    "no flags detected.",
    "none",
    "none.",
    "no flags",
    "none detected",
    "none detected.",
})

# Regex: matches FLAG-ROLE-NNN identifiers (case insensitive)
FLAG_ID_RE = re.compile(r"FLAG-([A-Z]+)-(\d+)", re.IGNORECASE)

# Display order for the flags-summary.md sections
AGENT_SCAN_ORDER = [
    ("techlead", "TechLead Agent (reviewing BA artifacts)",            "team/techlead/architecture.md"),
    ("tester",   "Tester Agent (reviewing all preceding artifacts)",   "team/tester/test-plan.md"),
    ("qa",       "QA/QC Agent (reviewing all artifacts)",             "team/qa/quality-report.md"),
]

# Severity rank for sorting (lower = more severe)
SEVERITY_RANK = {"blocker": 0, "critical": 0, "major": 1, "minor": 2, "unknown": 3}


# ── Path helpers ─────────────────────────────────────────────────────────────

def _norm(path: str) -> str:
    return path.replace("\\", "/")


def extract_slug(file_path: str) -> str:
    m = re.search(r"projects/([^/]+)/team/", _norm(file_path))
    return m.group(1) if m else None


def extract_project_root(file_path: str) -> str:
    """Return absolute path to projects/{slug}/ directory."""
    n = _norm(file_path)
    m = re.search(r"^(.+/projects/[^/]+)/team/", n)
    return m.group(1) if m else None


# ── Flag extraction ──────────────────────────────────────────────────────────

def _read_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def _extract_flags_section(content: str) -> str:
    """Return the text content of the ## Flags from Previous Agents section."""
    idx = content.find(FLAGS_HEADING)
    if idx == -1:
        return ""
    section = content[idx + len(FLAGS_HEADING):]
    # Stop at the next ## heading
    stop = re.search(r"\n## ", section)
    return section[: stop.start()] if stop else section


def _is_empty_flags_section(section: str) -> bool:
    """True if the section says 'no flags' in any form."""
    stripped = section.strip().lower()
    return not stripped or stripped in NO_FLAG_MARKERS or any(
        marker in stripped for marker in NO_FLAG_MARKERS
    )


def _parse_flag_blocks(section: str, source_file: str) -> list[dict]:
    """
    Parse individual FLAG-{ROLE}-{NNN} entries from a flags section.
    Returns a list of dicts with keys: id, role, severity, source, issue, suggestion.
    """
    flags: list[dict] = []

    # Split on ### headings (each flag is a ### block)
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

        # Extract structured fields
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
    """Read one artifact file and return all flags it contains."""
    content = _read_file(artifact_path)
    if not content:
        return []
    section = _extract_flags_section(content)
    if _is_empty_flags_section(section):
        return []
    return _parse_flag_blocks(section, artifact_path)


def collect_all_flags(project_root: str) -> dict[str, list[dict]]:
    """
    Scan all flagging-capable artifact files.
    Returns ordered dict: { agent_key: [flag_dict, ...] }
    """
    result: dict[str, list[dict]] = {}
    for agent_key, _label, rel_path in AGENT_SCAN_ORDER:
        artifact_path = os.path.join(project_root, rel_path)
        flags = extract_flags_from_artifact(artifact_path)
        if flags:
            # Sort by severity rank within each agent's flags
            flags.sort(key=lambda f: f["_rank"])
            result[agent_key] = flags
    return result


# ── Summary writing ──────────────────────────────────────────────────────────

def _severity_counts(all_flags: dict[str, list[dict]]) -> tuple[int, int, int]:
    """Returns (critical_count, major_count, minor_count)."""
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
    """Write flags-summary.md and return its path."""
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


# ── Terminal output ──────────────────────────────────────────────────────────

def print_report(all_flags: dict[str, list[dict]], summary_path: str, slug: str) -> None:
    """Print a warning block or a clean confirmation to stdout."""
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


# ── Hook entry point ─────────────────────────────────────────────────────────

def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    # Only respond to Write tool events
    if hook_input.get("tool_name") != "Write":
        sys.exit(0)

    file_path = hook_input.get("tool_input", {}).get("file_path", "")

    # Only trigger when QA/QC writes its sign-off — signals pipeline completion
    if not _norm(file_path).endswith("team/qa/sign-off.md"):
        sys.exit(0)

    slug = extract_slug(file_path)
    project_root = extract_project_root(file_path)

    if not slug or not project_root:
        sys.exit(0)

    all_flags = collect_all_flags(project_root)
    summary_path = write_flags_summary(project_root, slug, all_flags)
    print_report(all_flags, summary_path, slug)

    sys.exit(0)


if __name__ == "__main__":
    main()
