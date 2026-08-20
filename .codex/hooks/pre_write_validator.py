#!/usr/bin/env python3
"""
Virtual Team Skill — Pre-Write Validator Hook (Codex CLI port)

Intercepts every apply_patch call touching team artifact files.
Blocks writes that have missing required sections or hardcoded credentials.

Ported from .claude/hooks/pre_write_validator.py. Differences:
  - tool_name is "apply_patch" (matcher alias "Write"), not "Write".
  - tool_input has a single `command` field (raw patch text) instead of
    file_path/content. _patch_utils.parse_apply_patch() splits it into
    one (path, content) pair per file touched by the patch, and every
    file is validated independently.
  - For "Update File" patches, `content` only contains the lines being
    added by the diff hunks (no original-file context is available
    before the patch is applied) — heading/credential checks therefore
    run against the added lines only in that case. "Add File" patches
    (the common case for this repo's artifact-generation skills) get the
    full new content.
  - Block reason goes to stderr, not stdout (Codex's PreToolUse contract).

Exit codes:
  0 -> allow the write
  2 -> block the write, show error message to the agent (agent MUST fix and retry)
"""
import json
import sys
import os
import re
import io

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import retry_controller
from _patch_utils import parse_apply_patch

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ============================================================
# VALIDATION SCHEMAS
# Maps file path suffix -> required Markdown headings (exact match)
# ============================================================
HEADING_SCHEMA = {
    "team/ba/requirements.md": [
        "## Executive Summary",
        "## Requirements",
        "## Assumptions",
        "## Flags from Previous Agents",
    ],
    "team/ba/user-stories.md": [
        "## User Stories",
        "## Story ID Index",
    ],
    "team/ba/acceptance-criteria.md": [
        "## Acceptance Criteria",
    ],
    "team/ba/business-rules.md": [
        "## Business Rules",
    ],
    "team/techlead/architecture.md": [
        "## Overview",
        "## Component Architecture",
        "## Deployment Model",
        "## Gate 1: Design Freeze",
        "## Flags from Previous Agents",
    ],
    "team/techlead/tech-stack.md": [
        "## Frontend",
        "## Backend",
        "## Database",
        "## Infrastructure",
        "## Rejected Alternatives",
    ],
    "team/techlead/ERD.md": [
        "## Entity Relationship Diagram",
        "## Entity Descriptions",
    ],
    "team/techlead/sequence-diagrams.md": [
        "## Sequence Diagrams",
    ],
    "team/pm/sprint-plan.md": [
        "## Sprint Overview",
        "## Sprint 1",
    ],
    "team/pm/task-breakdown.md": [
        "## Tasks",
    ],
    "team/pm/story-points.md": [
        "## Velocity Estimate",
        "## Story Points Summary",
    ],
    "team/be/pr-description.md": [
        "## Summary",
        "## Changes",
        "## Testing Notes",
    ],
    "team/fe/pr-description.md": [
        "## Summary",
        "## Changes",
        "## Testing Notes",
    ],
    "team/tester/test-plan.md": [
        "## Scope",
        "## Approach",
        "## Test Environments",
        "## Entry Criteria",
        "## Exit Criteria",
        "## Gate 2: UAT Readiness",
        "## Flags from Previous Agents",
    ],
    "team/tester/test-cases-unit.md": [
        "## Unit Test Cases",
    ],
    "team/tester/test-cases-integration.md": [
        "## Integration Test Cases",
    ],
    "team/tester/test-cases-e2e.md": [
        "## End-to-End Test Cases",
    ],
    "team/tester/bug-report-template.md": [
        "## Bug Report Template",
    ],
    "team/qa/quality-report.md": [
        "## Completeness Check",
        "## Cross-artifact Consistency",
        "## Security Review",
        "## Process Compliance",
        "## Summary of Findings",
    ],
    "team/qa/compliance-check.md": [
        "## Milestone Gates",
        "## ADR Coverage",
        "## Security Scan",
        "## Overall Status",
    ],
    "team/qa/sign-off.md": [
        "## Verdict",
        "## Date",
        "## Findings",
        "## Conditions",
    ],
    "team/.project-config.md": [
        "## Project",
        "## Level Profile",
    ],
}

ADR_REQUIRED_HEADINGS = ["## Context", "## Decision", "## Consequences"]

# ============================================================
# CREDENTIAL DETECTION
# ============================================================
CREDENTIAL_PATTERNS = [
    (
        r"""(?ix)
        \b(password|passwd|secret|api_key|apikey|auth_token|access_token|private_key)\s*
        [=:]\s*
        ['"]
        (?!
          process\.env\.|
          os\.environ|
          os\.getenv|
          import\.meta\.env\.|
          \$\{|
          \$[A-Z_]
        )
        (?!
          your_|<|placeholder|changeme|xxx|dummy|example|test123|fake|todo
        )
        [^'"]{5,}
        ['"]
        """,
        "hardcoded secret or password",
    ),
    (
        r"""(?i)(mysql|postgresql|postgres|mongodb|redis|mariadb)://[^:\s]+:[^@\s$\{]{4,}@""",
        "hardcoded database URL with embedded credentials",
    ),
    (
        r"""(?i)aws_access_key_id\s*[=:]\s*['"]AKIA[A-Z0-9]{16}['"]""",
        "hardcoded AWS access key ID",
    ),
    (
        r"""(?i)(gh[ps]_[A-Za-z0-9]{36}|glpat-[A-Za-z0-9\-_]{20})""",
        "hardcoded GitHub/GitLab personal access token",
    ),
]


def normalize(path: str) -> str:
    return path.replace("\\", "/")


def is_team_artifact(path: str) -> bool:
    return "/team/" in normalize(path)


def find_schema_key(path: str):
    n = normalize(path)
    for key in HEADING_SCHEMA:
        if n.endswith(key):
            return key
    if re.search(r"/team/techlead/ADR-\d+\.md$", n):
        return "__ADR__"
    return None


def missing_headings(schema_key: str, content: str) -> list:
    required = ADR_REQUIRED_HEADINGS if schema_key == "__ADR__" else HEADING_SCHEMA.get(schema_key, [])
    found = set(re.findall(r"^##[^\n]+", content, re.MULTILINE))
    return [h for h in required if h not in found]


def is_source_file(path: str) -> bool:
    n = normalize(path)
    if "/team/be/" not in n and "/team/fe/" not in n:
        return False
    ext = os.path.splitext(n)[1].lower()
    return ext not in (".md", ".example", ".txt", ".json", ".yaml", ".yml", ".toml", ".lock", "")


def credential_violations(path: str, content: str) -> list:
    if not is_source_file(path):
        return []
    violations = []
    for pattern, description in CREDENTIAL_PATTERNS:
        matches = re.findall(pattern, content)
        for m in matches[:2]:
            snippet = str(m)[:80]
            violations.append((description, snippet))
    return violations


def check_env_example(path: str, content: str):
    if normalize(path).endswith(".env.example") and not content.strip():
        return ".env.example is empty. It must list all required environment variables with placeholder values."
    return None


def validate_file(file_path: str, content: str):
    """Returns (missing_sections, cred_violations) for one file."""
    if not is_team_artifact(file_path):
        return [], []

    missing_sections: list = []

    schema_key = find_schema_key(file_path)
    if schema_key:
        missing_sections = missing_headings(schema_key, content)

    env_error = check_env_example(file_path, content)
    if env_error:
        missing_sections.append(f"[.env.example] {env_error}")

    cred_violations = credential_violations(file_path, content)
    return missing_sections, cred_violations


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

    for op in parse_apply_patch(command):
        if op.action == "delete":
            continue

        missing_sections, cred_violations = validate_file(op.path, op.content)

        if missing_sections or cred_violations:
            message, _is_hard_stop = retry_controller.handle_failure(
                op.path, missing_sections, cred_violations
            )
            print(message, file=sys.stderr)
            sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
