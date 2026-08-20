#!/usr/bin/env python3
"""
srs_validator.py — Validate a generated SRS.md against IEEE 830-1998.

Checks:
  - All required sections present (§1–§3 + Appendix A/B)
  - FR numbering sequential, no gaps
  - Each FR has "shall" clause and Given/When/Then stubs
  - No unresolved tags: [CONTEXT-GAP], [GLOSSARY-GAP], [VERIFIABILITY-FAIL], [TBD]
  - NFR Response Measure is numeric (not adjective-only)

Verdict: COMPLIANT | PARTIALLY COMPLIANT | NON-COMPLIANT

Usage:
    python .codex/scripts/srs_validator.py docs/srs-myproject-20260614.md
    python .codex/scripts/srs_validator.py docs/srs-myproject-20260614.md --format json
    python .codex/scripts/srs_validator.py docs/srs-myproject-20260614.md --strict
"""

import argparse
import io
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Finding dataclass
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    severity: str   # ERROR | WARN | INFO
    rule: str
    message: str
    location: str = ""  # section or line reference


# ---------------------------------------------------------------------------
# Required section patterns (headings to look for)
# ---------------------------------------------------------------------------

REQUIRED_SECTIONS = {
    "§1 Introduction":          r"^#{1,3}\s+1[\.\s]+Introduction",
    "§1.1 Purpose":             r"^#{1,4}\s+1\.1",
    "§1.2 Scope":               r"^#{1,4}\s+1\.2",
    "§1.3 Definitions":         r"^#{1,4}\s+1\.3",
    "§1.4 References":          r"^#{1,4}\s+1\.4",
    "§1.5 Overview":            r"^#{1,4}\s+1\.5",
    "§2 Overall Description":   r"^#{1,3}\s+2[\.\s]+Overall",
    "§2.1 Product Perspective": r"^#{1,4}\s+2\.1",
    "§2.3 User Characteristics":r"^#{1,4}\s+2\.3",
    "§2.4 Constraints":         r"^#{1,4}\s+2\.4",
    "§3 Specific Requirements": r"^#{1,3}\s+3[\.\s]+Specific",
    "§3.1 External Interfaces": r"^#{1,4}\s+3\.1",
    "§3.2 Functions/FR":        r"^#{1,4}\s+3\.2",
    "§3.3 Performance":         r"^#{1,4}\s+3\.3",
    "Appendix A Glossary":      r"^#{1,3}\s+Appendix\s+A",
    "Appendix B Open Issues":   r"^#{1,3}\s+Appendix\s+B",
}

UNRESOLVED_TAGS = {
    "[CONTEXT-GAP]":       r"\[CONTEXT-GAP:[^\]]*\]",
    "[GLOSSARY-GAP]":      r"\[GLOSSARY-GAP:[^\]]*\]",
    "[VERIFIABILITY-FAIL]":r"\[VERIFIABILITY-FAIL:[^\]]*\]",
    "[TBD]":               r"\[TBD:[^\]]*\]",
}

FR_BLOCK_PATTERN  = re.compile(r"(FR-\d+)", re.IGNORECASE)
FR_SHALL_PATTERN  = re.compile(r"Requirement\s*:\s*.+shall\b", re.IGNORECASE)
FR_GIVEN_PATTERN  = re.compile(r"\*\*Given\*\*|\bGiven\s*:", re.IGNORECASE)
FR_WHEN_PATTERN   = re.compile(r"\*\*When\*\*|\bWhen\s*:", re.IGNORECASE)
FR_THEN_PATTERN   = re.compile(r"\*\*Then\*\*|\bThen\s*:", re.IGNORECASE)
NFR_MEASURE_PATTERN = re.compile(
    r"\|\s*Response\s+Measure\s*\|\s*(.+?)\s*\|", re.IGNORECASE
)
NUMERIC_PATTERN   = re.compile(r"\d+\s*(ms|s|%|rpm|tps|gb|mb|users?|req|uptime|sla|mtbf)", re.IGNORECASE)
FR_PRIORITY_PATTERN = re.compile(r"FR-\d+\s*\[(Essential|Conditional|Optional)\]", re.IGNORECASE)
NFR_ID_PATTERN    = re.compile(r"NFR-(\d+)", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------

def check_sections(text: str) -> list[Finding]:
    findings = []
    for label, pattern in REQUIRED_SECTIONS.items():
        if not re.search(pattern, text, re.MULTILINE | re.IGNORECASE):
            findings.append(Finding(
                severity="ERROR",
                rule="missing-section",
                message=f"Required section not found: {label}",
            ))
    return findings


def check_unresolved_tags(text: str) -> list[Finding]:
    findings = []
    for tag_name, pattern in UNRESOLVED_TAGS.items():
        matches = re.findall(pattern, text)
        if matches:
            findings.append(Finding(
                severity="WARN",
                rule="unresolved-tag",
                message=f"{len(matches)} unresolved {tag_name} tag(s) remain",
                location="; ".join(m[:60] for m in matches[:3]),
            ))
    return findings


def check_fr_numbering(text: str) -> list[Finding]:
    findings = []
    numbers = [int(m.group(1)) for m in re.finditer(r"FR-(\d+)", text, re.IGNORECASE)]
    if not numbers:
        findings.append(Finding(
            severity="WARN",
            rule="no-fr-found",
            message="No FR-NN entries found in document",
        ))
        return findings

    numbers = sorted(set(numbers))
    expected = list(range(1, numbers[-1] + 1))
    missing = sorted(set(expected) - set(numbers))
    if missing:
        findings.append(Finding(
            severity="ERROR",
            rule="fr-numbering-gap",
            message=f"FR numbering has gaps: missing FR-{', FR-'.join(str(n).zfill(2) for n in missing)}",
        ))
    return findings


def check_fr_format(text: str) -> list[Finding]:
    findings = []
    # Split on FR-NN blocks
    blocks = re.split(r"(?=####?\s+FR-\d+)", text, flags=re.IGNORECASE)
    for block in blocks:
        fr_match = re.search(r"FR-(\d+)", block, re.IGNORECASE)
        if not fr_match:
            continue
        fr_id = f"FR-{fr_match.group(1).zfill(2)}"

        if not FR_SHALL_PATTERN.search(block):
            findings.append(Finding(
                severity="ERROR",
                rule="fr-no-shall",
                message=f'{fr_id}: Requirement line missing "shall" clause',
                location=fr_id,
            ))
        for label, pattern in [("Given", FR_GIVEN_PATTERN), ("When", FR_WHEN_PATTERN), ("Then", FR_THEN_PATTERN)]:
            if not pattern.search(block):
                findings.append(Finding(
                    severity="WARN",
                    rule="fr-incomplete-gwt",
                    message=f"{fr_id}: GWT stub missing '{label}:' field",
                    location=fr_id,
                ))
    return findings


def check_nfr_measures(text: str) -> list[Finding]:
    findings = []
    for m in NFR_MEASURE_PATTERN.finditer(text):
        measure = m.group(1).strip()
        if not NUMERIC_PATTERN.search(measure) and "[TBD" not in measure:
            findings.append(Finding(
                severity="WARN",
                rule="nfr-no-numeric",
                message=f'NFR Response Measure has no numeric threshold: "{measure[:80]}"',
            ))
    return findings


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def compute_stats(text: str) -> dict:
    priority_counts = {"essential": 0, "conditional": 0, "optional": 0}
    for m in FR_PRIORITY_PATTERN.finditer(text):
        priority_counts[m.group(1).lower()] += 1
    fr_ids = {int(m.group(1)) for m in re.finditer(r"FR-(\d+)", text, re.IGNORECASE)}

    nfr_ids = {int(m.group(1)) for m in NFR_ID_PATTERN.finditer(text)}
    nfr_tbd = 0
    nfr_confirmed = 0
    for m in NFR_MEASURE_PATTERN.finditer(text):
        measure = m.group(1).strip()
        if "[TBD" in measure:
            nfr_tbd += 1
        else:
            nfr_confirmed += 1

    open_items = sum(len(re.findall(p, text)) for p in UNRESOLVED_TAGS.values())

    return {
        "fr_total": len(fr_ids),
        "fr_essential": priority_counts["essential"],
        "fr_conditional": priority_counts["conditional"],
        "fr_optional": priority_counts["optional"],
        "nfr_total": len(nfr_ids),
        "nfr_confirmed": nfr_confirmed,
        "nfr_tbd": nfr_tbd,
        "open_items": open_items,
    }


def format_stats(stats: dict, fmt: str) -> str:
    if fmt == "json":
        return json.dumps(stats, indent=2, ensure_ascii=False)
    return (
        f"FRs:  {stats['fr_total']} total "
        f"({stats['fr_essential']} Essential / {stats['fr_conditional']} Conditional / {stats['fr_optional']} Optional)\n"
        f"NFRs: {stats['nfr_total']} total "
        f"({stats['nfr_confirmed']} confirmed / {stats['nfr_tbd']} [TBD])\n"
        f"Open items (unresolved tags): {stats['open_items']}"
    )


# ---------------------------------------------------------------------------
# Verdict
# ---------------------------------------------------------------------------

def verdict(findings: list[Finding], strict: bool = False) -> str:
    errors = [f for f in findings if f.severity == "ERROR"]
    warns  = [f for f in findings if f.severity == "WARN"]
    if errors:
        return "NON-COMPLIANT"
    if warns:
        return "PARTIALLY COMPLIANT" if not strict else "NON-COMPLIANT"
    return "COMPLIANT"


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------

def format_markdown(findings: list[Finding], v: str, path: str) -> str:
    emoji = {"COMPLIANT": "✓", "PARTIALLY COMPLIANT": "!", "NON-COMPLIANT": "✗"}
    lines = [
        f"## SRS Validation: {emoji.get(v, '?')} {v}",
        f"File: `{path}`",
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
        "file": path,
        "issue_count": len(findings),
        "findings": [
            {"severity": f.severity, "rule": f.rule,
             "message": f.message, "location": f.location}
            for f in findings
        ],
    }, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def validate(text: str, strict: bool = False) -> tuple[list[Finding], str]:
    findings: list[Finding] = []
    findings += check_sections(text)
    findings += check_unresolved_tags(text)
    findings += check_fr_numbering(text)
    findings += check_fr_format(text)
    findings += check_nfr_measures(text)
    # sort: ERROR first
    findings.sort(key=lambda f: (0 if f.severity == "ERROR" else 1, f.rule))
    return findings, verdict(findings, strict)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate a generated SRS.md against IEEE 830-1998."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("file", nargs="?", help="Path to a single SRS markdown file")
    group.add_argument("--dir", metavar="DIR",
                       help="Directory of per-section SRS files — concatenated before validation")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    parser.add_argument("--strict", action="store_true",
                        help="Treat warnings as errors (stricter verdict)")
    parser.add_argument("--stats", action="store_true",
                        help="Print FR/NFR/open-item counts instead of findings")
    args = parser.parse_args()

    if args.dir:
        dir_path = Path(args.dir)
        if not dir_path.is_dir():
            print(f"[!] Directory not found: {dir_path}", file=sys.stderr)
            sys.exit(1)
        md_files = sorted(dir_path.glob("*.md"))
        if not md_files:
            print(f"[!] No .md files found in: {dir_path}", file=sys.stderr)
            sys.exit(1)
        text = "\n\n".join(f.read_text(encoding="utf-8") for f in md_files)
        label = str(dir_path)
    else:
        path = Path(args.file)
        if not path.exists():
            print(f"[!] File not found: {path}", file=sys.stderr)
            sys.exit(1)
        text = path.read_text(encoding="utf-8")
        label = str(path)

    if args.stats:
        print(format_stats(compute_stats(text), args.format))
        sys.exit(0)

    findings, v = validate(text, strict=args.strict)

    if args.format == "json":
        print(format_json(findings, v, label))
    else:
        print(format_markdown(findings, v, label))

    sys.exit(0 if v == "COMPLIANT" else 1)


if __name__ == "__main__":
    main()
