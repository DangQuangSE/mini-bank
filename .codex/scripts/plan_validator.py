#!/usr/bin/env python3
"""
plan_validator.py — Validate projects/{slug}/plan/ before SRS generation (Phase 4 gate).

Catches structural errors in plan files BEFORE $sr-generate writes the full
300+ page SRS, so rework happens on cheap plan text instead of expensive
full-document regeneration.

Checks:
  - All 12 required plan files present
  - FR table rows: sequential numbering, valid priority, "shall" stub, GWT stub
  - NFR table rows: sequential numbering, numeric Measure or [TBD]
  - [NEEDS USER INPUT] tags tracked in appendix-b-open-issues.md

Verdict: READY | READY WITH WARNINGS | BLOCKED

Usage:
    python .codex/scripts/plan_validator.py --dir projects/myproject/plan/
    python .codex/scripts/plan_validator.py --dir projects/myproject/plan/ --format json
    python .codex/scripts/plan_validator.py --dir projects/myproject/plan/ --stats
"""

import argparse
import io
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Finding dataclass
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    severity: str   # ERROR | WARN
    rule: str
    message: str
    location: str = ""


REQUIRED_PLAN_FILES = [
    "00-overview.md",
    "01-introduction.md",
    "02-overall-description.md",
    "03-01-external-interfaces.md",
    "03-02-functional-requirements.md",
    "03-03-performance.md",
    "03-04-database.md",
    "03-05-design-constraints.md",
    "03-06-system-attributes.md",
    "03-07-other-requirements.md",
    "appendix-a-glossary.md",
    "appendix-b-open-issues.md",
]

FR_ROW_PATTERN = re.compile(
    r"^\|\s*FR-(\d+)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|",
    re.MULTILINE,
)
NFR_ROW_PATTERN = re.compile(
    r"^\|\s*NFR-(\d+)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|",
    re.MULTILINE,
)
VALID_PRIORITIES = {"essential", "conditional", "optional"}
NUMERIC_PATTERN = re.compile(r"\d", re.IGNORECASE)
NEEDS_INPUT_PATTERN = re.compile(r"\[NEEDS USER INPUT:[^\]]*\]", re.IGNORECASE)
OPEN_ISSUE_ROW_PATTERN = re.compile(r"^\|\s*TBD-\d+\s*\|", re.MULTILINE)


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def check_required_files(dir_path: Path) -> list[Finding]:
    findings = []
    existing = {p.name.lower() for p in dir_path.glob("*.md")}
    for name in REQUIRED_PLAN_FILES:
        if name.lower() not in existing:
            findings.append(Finding(
                severity="ERROR",
                rule="missing-file",
                message=f"Required plan file not found: {name}",
            ))
    return findings


def check_fr_rows(text: str) -> list[Finding]:
    findings = []
    numbers: list[int] = []
    seen_ids: set[int] = set()

    for m in FR_ROW_PATTERN.finditer(text):
        n = int(m.group(1))
        fr_id = f"FR-{n:02d}"
        numbers.append(n)

        if n in seen_ids:
            findings.append(Finding(
                severity="ERROR", rule="fr-duplicate",
                message=f"{fr_id} appears more than once in plan tables",
                location=fr_id,
            ))
        seen_ids.add(n)

        priority, actor, shall_stub, gwt_stub = (g.strip() for g in m.groups()[1:])

        if priority.lower() not in VALID_PRIORITIES:
            findings.append(Finding(
                severity="ERROR", rule="fr-bad-priority",
                message=f'{fr_id}: priority "{priority}" is not Essential/Conditional/Optional',
                location=fr_id,
            ))
        if "shall" not in shall_stub.lower():
            findings.append(Finding(
                severity="ERROR", rule="fr-no-shall",
                message=f"{fr_id}: shall-stub missing \"shall\" — found: \"{shall_stub[:60]}\"",
                location=fr_id,
            ))
        missing_gwt = [kw for kw in ("Given", "When", "Then") if kw.lower() not in gwt_stub.lower()]
        if missing_gwt:
            findings.append(Finding(
                severity="WARN", rule="fr-incomplete-gwt",
                message=f"{fr_id}: GWT stub missing {', '.join(missing_gwt)}",
                location=fr_id,
            ))

    if not numbers:
        findings.append(Finding(
            severity="WARN", rule="no-fr-found",
            message="No FR table rows found across plan files",
        ))
        return findings

    unique = sorted(set(numbers))
    expected = list(range(1, unique[-1] + 1))
    missing = sorted(set(expected) - set(unique))
    if missing:
        findings.append(Finding(
            severity="ERROR", rule="fr-numbering-gap",
            message=f"FR numbering has gaps: missing FR-{', FR-'.join(str(n).zfill(2) for n in missing)}",
        ))
    return findings


def check_nfr_rows(text: str) -> list[Finding]:
    findings = []
    numbers: list[int] = []

    for m in NFR_ROW_PATTERN.finditer(text):
        n = int(m.group(1))
        nfr_id = f"NFR-{n:02d}"
        numbers.append(n)
        scenario = m.group(3)

        if "[TBD" in scenario:
            continue
        if "measure" not in scenario.lower():
            findings.append(Finding(
                severity="WARN", rule="nfr-no-measure-label",
                message=f'{nfr_id}: scenario has no "Measure:" field',
                location=nfr_id,
            ))
        elif not NUMERIC_PATTERN.search(scenario.split("easure", 1)[-1]):
            findings.append(Finding(
                severity="WARN", rule="nfr-no-numeric",
                message=f"{nfr_id}: Measure has no numeric threshold",
                location=nfr_id,
            ))

    if not numbers:
        findings.append(Finding(
            severity="WARN", rule="no-nfr-found",
            message="No NFR table rows found across plan files",
        ))
        return findings

    unique = sorted(set(numbers))
    expected = list(range(1, unique[-1] + 1))
    missing = sorted(set(expected) - set(unique))
    if missing:
        findings.append(Finding(
            severity="ERROR", rule="nfr-numbering-gap",
            message=f"NFR numbering has gaps: missing NFR-{', NFR-'.join(str(n).zfill(2) for n in missing)}",
        ))
    return findings


def check_open_items_tracked(text: str) -> list[Finding]:
    needs_input = len(NEEDS_INPUT_PATTERN.findall(text))
    tracked = len(OPEN_ISSUE_ROW_PATTERN.findall(text))
    if needs_input > tracked:
        return [Finding(
            severity="WARN", rule="needs-input-untracked",
            message=(
                f"{needs_input} [NEEDS USER INPUT] tag(s) found but only {tracked} row(s) "
                "in appendix-b-open-issues.md — every tag must be logged with owner + resolve-by"
            ),
        )]
    return []


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def compute_stats(text: str) -> dict:
    fr_rows = list(FR_ROW_PATTERN.finditer(text))
    priority_counts = {"essential": 0, "conditional": 0, "optional": 0}
    for m in fr_rows:
        p = m.group(2).strip().lower()
        if p in priority_counts:
            priority_counts[p] += 1

    nfr_rows = list(NFR_ROW_PATTERN.finditer(text))
    nfr_tbd = sum(1 for m in nfr_rows if "[TBD" in m.group(3))

    return {
        "fr_total": len({int(m.group(1)) for m in fr_rows}),
        "fr_essential": priority_counts["essential"],
        "fr_conditional": priority_counts["conditional"],
        "fr_optional": priority_counts["optional"],
        "nfr_total": len({int(m.group(1)) for m in nfr_rows}),
        "nfr_confirmed": len(nfr_rows) - nfr_tbd,
        "nfr_tbd": nfr_tbd,
        "needs_input_open": len(NEEDS_INPUT_PATTERN.findall(text)),
        "needs_input_tracked": len(OPEN_ISSUE_ROW_PATTERN.findall(text)),
    }


def format_stats(stats: dict, fmt: str) -> str:
    if fmt == "json":
        return json.dumps(stats, indent=2, ensure_ascii=False)
    return (
        f"FRs:  {stats['fr_total']} total "
        f"({stats['fr_essential']} Essential / {stats['fr_conditional']} Conditional / {stats['fr_optional']} Optional)\n"
        f"NFRs: {stats['nfr_total']} total "
        f"({stats['nfr_confirmed']} confirmed / {stats['nfr_tbd']} [TBD])\n"
        f"Open items: {stats['needs_input_open']} flagged / {stats['needs_input_tracked']} tracked in appendix-b"
    )


# ---------------------------------------------------------------------------
# Verdict + output
# ---------------------------------------------------------------------------

def verdict(findings: list[Finding]) -> str:
    if any(f.severity == "ERROR" for f in findings):
        return "BLOCKED"
    if any(f.severity == "WARN" for f in findings):
        return "READY WITH WARNINGS"
    return "READY"


def validate(dir_path: Path) -> tuple[list[Finding], str]:
    findings: list[Finding] = check_required_files(dir_path)

    md_files = sorted(dir_path.glob("*.md"))
    text = "\n\n".join(f.read_text(encoding="utf-8") for f in md_files)

    findings += check_fr_rows(text)
    findings += check_nfr_rows(text)
    findings += check_open_items_tracked(text)
    findings.sort(key=lambda f: (0 if f.severity == "ERROR" else 1, f.rule))
    return findings, verdict(findings)


def format_markdown(findings: list[Finding], v: str, path: str) -> str:
    emoji = {"READY": "✓", "READY WITH WARNINGS": "!", "BLOCKED": "✗"}
    lines = [
        f"## Plan Validation: {emoji.get(v, '?')} {v}",
        f"Dir: `{path}`",
        f"Issues: {len(findings)} ({sum(1 for f in findings if f.severity=='ERROR')} errors, "
        f"{sum(1 for f in findings if f.severity=='WARN')} warnings)\n",
    ]
    if not findings:
        lines.append("All checks passed.")
    else:
        lines.append("| Severity | Rule | Message | Location |")
        lines.append("|----------|------|---------|----------|")
        for f in findings:
            lines.append(f"| **{f.severity}** | {f.rule} | {f.message} | {f.location or '—'} |")
    return "\n".join(lines)


def format_json(findings: list[Finding], v: str, path: str) -> str:
    return json.dumps({
        "verdict": v,
        "dir": path,
        "issue_count": len(findings),
        "findings": [
            {"severity": f.severity, "rule": f.rule, "message": f.message, "location": f.location}
            for f in findings
        ],
    }, indent=2, ensure_ascii=False)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate plan/ files before SRS generation (Phase 4 gate)."
    )
    parser.add_argument("--dir", required=True, metavar="DIR", help="Path to projects/{slug}/plan/")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    parser.add_argument("--stats", action="store_true", help="Print FR/NFR/open-item counts instead of findings")
    args = parser.parse_args()

    dir_path = Path(args.dir)
    if not dir_path.is_dir():
        print(f"[!] Directory not found: {dir_path}", file=sys.stderr)
        sys.exit(1)

    if args.stats:
        md_files = sorted(dir_path.glob("*.md"))
        if not md_files:
            print(f"[!] No .md files found in: {dir_path}", file=sys.stderr)
            sys.exit(1)
        text = "\n\n".join(f.read_text(encoding="utf-8") for f in md_files)
        print(format_stats(compute_stats(text), args.format))
        sys.exit(0)

    findings, v = validate(dir_path)

    if args.format == "json":
        print(format_json(findings, v, str(dir_path)))
    else:
        print(format_markdown(findings, v, str(dir_path)))

    sys.exit(0 if v != "BLOCKED" else 1)


if __name__ == "__main__":
    main()
