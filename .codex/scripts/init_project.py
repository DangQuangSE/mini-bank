#!/usr/bin/env python3
"""
init_project.py — Initialize project context files for srs-generator.

Creates a _context/ directory under projects/{name}/ with template files
that Codex reads instead of extracting everything from raw text.
This reduces hallucination and speeds up the SRS generation pipeline.

Usage:
    python .codex/scripts/init_project.py <project-name>
    python .codex/scripts/init_project.py <project-name> --path ./custom/output/dir
"""

import argparse
import sys
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------------------
# Template content
# ---------------------------------------------------------------------------

VISION_MD = """\
# Vision — {name}

## Problem Statement
<!-- What problem does this system solve? For whom? -->


## Business Goals
<!-- 2-3 measurable goals this system must achieve -->
- Goal 1:
- Goal 2:

## System Type
<!-- Web app / Mobile app / API / Internal tool / SaaS / Desktop / Other -->


## Success Metrics
<!-- How will we know the system succeeded? Numbers, not adjectives. -->
- Metric 1:
- Metric 2:
"""

FEATURES_MD = """\
# Features — {name}

## In Scope
<!-- List features this system WILL include in v1 -->
- Feature 1:
- Feature 2:

## Out of Scope
<!-- List features explicitly excluded from v1 — prevents scope creep -->
- Out 1:
- Out 2:

## Priority (MoSCoW)
| Feature | Must | Should | Could | Won't |
|---------|------|--------|-------|-------|
|         |      |        |       |       |
"""

TECH_STACK_MD = """\
# Tech Stack — {name}

## Frontend
<!-- Framework, language, target browsers/devices -->


## Backend
<!-- Language, framework, runtime version -->


## Database
<!-- Type, engine, version -->


## Infrastructure
<!-- Cloud provider, hosting, CI/CD -->


## External Integrations
<!-- APIs, SDKs, third-party services -->
| Service | Purpose | Auth method |
|---------|---------|-------------|
|         |         |             |

## Constraints
<!-- Hard technical constraints that requirements must respect -->
- Constraint 1:
"""

GLOSSARY_MD = """\
# Glossary — {name}

<!-- Define domain-specific terms here.
     srs-generator will use this to populate Appendix A and resolve [GLOSSARY-GAP] tags. -->

| Term | Definition |
|------|------------|
|      |            |
"""

QUALITY_STANDARDS_MD = """\
# Quality Standards — {name}

<!-- Numeric thresholds only — no adjectives.
     srs-generator uses these to populate §3.3–§3.6 NFR sections. -->

## Performance
- Response time (p95): < ___ ms under ___ concurrent users
- Throughput: ___ requests/second

## Availability
- Uptime SLA: ___% per month
- Planned maintenance window: ___

## Security
- Authentication: (JWT / OAuth 2.0 / Session / Other)
- Encryption at rest: (AES-256 / Other)
- Encryption in transit: TLS ___

## Reliability
- MTBF target: ___
- Recovery time objective (RTO): ___
- Recovery point objective (RPO): ___
"""

TEMPLATES = {
    "vision.md": VISION_MD,
    "features.md": FEATURES_MD,
    "tech_stack.md": TECH_STACK_MD,
    "glossary.md": GLOSSARY_MD,
    "quality_standards.md": QUALITY_STANDARDS_MD,
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def init_project(name: str, base_path: Path) -> None:
    context_dir = base_path / "projects" / name / "_context"

    if context_dir.exists():
        print(f"[!] Context already exists at {context_dir}")
        choice = input("    Overwrite? [y/N] ").strip().lower()
        if choice != "y":
            print("    Aborted.")
            sys.exit(0)

    context_dir.mkdir(parents=True, exist_ok=True)

    created = []
    for filename, template in TEMPLATES.items():
        file_path = context_dir / filename
        file_path.write_text(
            template.format(name=name, date=date.today().isoformat()),
            encoding="utf-8"
        )
        created.append(file_path)

    print(f"\n✓ Project context initialized: {context_dir}\n")
    for f in created:
        print(f"  {f.relative_to(base_path)}")

    print(f"""
Next steps:
  1. Fill in the context files above
  2. Invoke $srs-generator in Codex — it will read these files automatically
     (or tell Codex: "use context from projects/{name}/_context/")
""")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Initialize srs-generator project context files."
    )
    parser.add_argument("name", help="Project name (used as folder name)")
    parser.add_argument(
        "--path",
        default=".",
        help="Base directory (default: current directory)",
    )
    args = parser.parse_args()

    base_path = Path(args.path).resolve()
    if not base_path.exists():
        print(f"[!] Base path does not exist: {base_path}")
        sys.exit(1)

    init_project(args.name, base_path)


if __name__ == "__main__":
    main()
