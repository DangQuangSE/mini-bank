#!/usr/bin/env python3
"""
Virtual Team Skill — Pre-Write Validator Hook

Intercepts every Write tool call for team artifact files.
Blocks writes that have missing required sections or hardcoded credentials.

Exit codes:
  0 -> allow the write
  2 -> block the write, show error message to agent (agent MUST fix and retry)
"""
import json
import sys
import os
import re
import io

# Force UTF-8 output to avoid encoding errors on Windows (cp1252 default)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Import retry_controller from the same hooks/ directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import retry_controller

# ============================================================
# VALIDATION SCHEMAS
# Maps file path suffix → required Markdown headings (exact match)
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

# ADR files match pattern: team/techlead/ADR-NNN.md
ADR_REQUIRED_HEADINGS = ["## Context", "## Decision", "## Consequences"]

# ============================================================
# CREDENTIAL DETECTION
# Patterns that detect hardcoded secrets in source code.
# Only applied to non-.md, non-.example files under team/be/ or team/fe/
# ============================================================
CREDENTIAL_PATTERNS = [
    # Generic secret/password assignment with a literal value
    (
        r"""(?ix)
        \b(password|passwd|secret|api_key|apikey|auth_token|access_token|private_key)\s*
        [=:]\s*
        ['"]                          # opening quote
        (?!                           # NOT followed by env var patterns:
          process\.env\.|
          os\.environ|
          os\.getenv|
          import\.meta\.env\.|
          \$\{|                       # template literal ${...}
          \$[A-Z_]                    # shell-style $VAR
        )
        (?!                           # NOT a recognisable placeholder:
          your_|<|placeholder|changeme|xxx|dummy|example|test123|fake|todo
        )
        [^'"]{5,}                     # at least 5 real characters
        ['"]                          # closing quote
        """,
        "hardcoded secret or password",
    ),
    # Database/cache URL with embedded credentials (user:pass@host)
    (
        r"""(?i)(mysql|postgresql|postgres|mongodb|redis|mariadb)://[^:\s]+:[^@\s$\{]{4,}@""",
        "hardcoded database URL with embedded credentials",
    ),
    # AWS access key ID
    (
        r"""(?i)aws_access_key_id\s*[=:]\s*['"]AKIA[A-Z0-9]{16}['"]""",
        "hardcoded AWS access key ID",
    ),
    # GitHub/GitLab tokens
    (
        r"""(?i)(gh[ps]_[A-Za-z0-9]{36}|glpat-[A-Za-z0-9\-_]{20})""",
        "hardcoded GitHub/GitLab personal access token",
    ),
]


# ============================================================
# HELPERS
# ============================================================

def normalize(path: str) -> str:
    return path.replace("\\", "/")


def is_team_artifact(path: str) -> bool:
    return "/team/" in normalize(path)


def find_schema_key(path: str):
    """Return matching schema key, '__ADR__', or None."""
    n = normalize(path)
    for key in HEADING_SCHEMA:
        if n.endswith(key):
            return key
    if re.search(r"/team/techlead/ADR-\d+\.md$", n):
        return "__ADR__"
    return None


def missing_headings(schema_key: str, content: str) -> list:
    """Return list of required headings not found in content."""
    required = ADR_REQUIRED_HEADINGS if schema_key == "__ADR__" else HEADING_SCHEMA.get(schema_key, [])
    # Extract all ATX headings starting with ##
    found = set(re.findall(r"^##[^\n]+", content, re.MULTILINE))
    return [h for h in required if h not in found]


def is_source_file(path: str) -> bool:
    """True for BE/FE source code files (not .md, not .example)."""
    n = normalize(path)
    if "/team/be/" not in n and "/team/fe/" not in n:
        return False
    ext = os.path.splitext(n)[1].lower()
    return ext not in (".md", ".example", ".txt", ".json", ".yaml", ".yml", ".toml", ".lock", "")


def credential_violations(path: str, content: str) -> list:
    """Return list of (description, snippet) tuples for detected hardcoded credentials."""
    if not is_source_file(path):
        return []
    violations = []
    for pattern, description in CREDENTIAL_PATTERNS:
        matches = re.findall(pattern, content)
        for m in matches[:2]:  # cap at 2 per pattern to keep output readable
            snippet = str(m)[:80]
            violations.append((description, snippet))
    return violations


def check_env_example(path: str, content: str):
    """Returns error string if .env.example is empty, else None."""
    if normalize(path).endswith(".env.example") and not content.strip():
        return ".env.example is empty. It must list all required environment variables with placeholder values."
    return None


# ============================================================
# MAIN
# ============================================================

def main():
    try:
        hook_input = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # Can't parse → don't block

    if hook_input.get("tool_name") != "Write":
        sys.exit(0)

    tool_input = hook_input.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    content = tool_input.get("content", "")

    if not is_team_artifact(file_path):
        sys.exit(0)  # Not a team artifact

    fname = os.path.basename(file_path)
    missing_sections: list = []
    cred_violations: list = []

    # ── 1. Required headings check ────────────────────────────
    schema_key = find_schema_key(file_path)
    if schema_key:
        missing_sections = missing_headings(schema_key, content)

    # ── 2. .env.example non-empty check ──────────────────────
    env_error = check_env_example(file_path, content)
    if env_error:
        # Treat as a pseudo-section so retry_controller can surface it
        missing_sections.append(f"[.env.example] {env_error}")

    # ── 3. Hardcoded credential check ────────────────────────
    cred_violations = credential_violations(file_path, content)

    if missing_sections or cred_violations:
        # Delegate to retry_controller: counts attempts, writes log, builds message
        message, _is_hard_stop = retry_controller.handle_failure(
            file_path, missing_sections, cred_violations
        )
        print(message, file=sys.stdout)
        sys.exit(2)  # Block the Write call — agent MUST fix and retry

    sys.exit(0)


if __name__ == "__main__":
    main()
