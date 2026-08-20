#!/usr/bin/env python3
"""
Virtual Team Skill — Retry Controller (Codex CLI port)

Module imported by pre_write_validator.py.

Responsibilities:
  - Count prior validation attempts for an agent (by scanning validation-errors/)
  - Write a structured attempt log on each failure (FR-36)
  - Return a hard-stop message when MAX_ATTEMPTS is reached (FR-35)
  - Return a retry message with remaining-attempts count for earlier failures

NOT a hook — does not read from stdin. Called as a library by the validator hook.

Ported from .claude/hooks/retry_controller.py: recovery commands use
Codex's `$skill-name` invocation syntax instead of Claude's `/skill-name`
slash commands.
"""
import os
import glob
import re
from datetime import datetime, timezone

MAX_ATTEMPTS = 3

AGENT_META: dict[str, tuple[str, str]] = {
    "ba":       ("BA",       "$team-ba"),
    "techlead": ("TechLead", "$team-techlead"),
    "pm":       ("PM",       "$team-pm"),
    "be":       ("BE Dev",   "$team-dev"),
    "fe":       ("FE Dev",   "$team-fe"),
    "tester":   ("Tester",   "$team-test"),
    "qa":       ("QA/QC",    "$team-qa"),
}


def _norm(path: str) -> str:
    return path.replace("\\", "/")


def extract_slug(file_path: str) -> str:
    m = re.search(r"projects/([^/]+)/team/", _norm(file_path))
    return m.group(1) if m else "unknown-project"


def extract_agent_key(file_path: str) -> str:
    m = re.search(r"team/([^/]+)/", _norm(file_path))
    return m.group(1) if m else "unknown"


def extract_errors_dir(file_path: str) -> str:
    n = _norm(file_path)
    # Match both absolute paths (Claude's Write) and repo-relative paths
    # (Codex's apply_patch, which has no leading prefix before "projects/").
    m = re.search(r"^(.*projects/[^/]+)/team/", n)
    project_root = m.group(1) if m else "projects/unknown-project"
    return os.path.join(project_root, "validation-errors")


def count_prior_attempts(errors_dir: str, agent_key: str) -> int:
    if not os.path.isdir(errors_dir):
        return 0
    pattern = os.path.join(errors_dir, f"{agent_key}-attempt-*.md")
    return len(glob.glob(pattern))


def _sections_md(missing_sections: list[str]) -> str:
    if not missing_sections:
        return ""
    lines = "\n".join(f"- `{s}`" for s in missing_sections)
    return f"### Missing Required Sections\n{lines}"


def _violations_md(cred_violations: list[tuple[str, str]]) -> str:
    if not cred_violations:
        return ""
    lines = "\n".join(f"- {desc}: `{snippet[:80]}`" for desc, snippet in cred_violations)
    return f"### Security Violations (Hardcoded Credentials)\n{lines}"


def write_attempt_log(
    errors_dir: str,
    agent_key: str,
    attempt_n: int,
    file_path: str,
    slug: str,
    missing_sections: list[str],
    cred_violations: list[tuple[str, str]],
) -> str:
    os.makedirs(errors_dir, exist_ok=True)

    display_name, command = AGENT_META.get(agent_key, (agent_key.upper(), f"$team-{agent_key}"))
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    is_hard_stop = attempt_n >= MAX_ATTEMPTS
    result_str = "HARD STOP" if is_hard_stop else f"RETRY ({attempt_n}/{MAX_ATTEMPTS})"

    issues_blocks = list(filter(None, [
        _sections_md(missing_sections),
        _violations_md(cred_violations),
    ]))
    issues_md = "\n\n".join(issues_blocks) or "_No structured details captured._"

    content = (
        f"# Validation Error Log — {display_name} Agent\n"
        f"agent: {display_name}\n"
        f"attempt: {attempt_n}/{MAX_ATTEMPTS}\n"
        f"timestamp: {timestamp}\n"
        f"file: {os.path.basename(file_path)}\n"
        f"result: **{result_str}**\n"
        f"\n"
        f"## Issues Found\n"
        f"\n"
        f"{issues_md}\n"
        f"\n"
        f"## Recovery\n"
        f"```\n"
        f"{command} --project {slug}\n"
        f"```\n"
    )

    log_path = os.path.join(errors_dir, f"{agent_key}-attempt-{attempt_n}.md")
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(content)

    return log_path


def _console_issues(missing_sections: list[str], cred_violations: list[tuple[str, str]]) -> str:
    parts = []
    if missing_sections:
        lines = "\n".join(f"    - {s}" for s in missing_sections)
        parts.append(f"  Missing sections:\n{lines}")
    if cred_violations:
        lines = "\n".join(
            f"    - {desc}: {snippet[:60]}" for desc, snippet in cred_violations
        )
        parts.append(f"  Security violations:\n{lines}")
    return "\n".join(parts)


def handle_failure(
    file_path: str,
    missing_sections: list[str],
    cred_violations: list[tuple[str, str]],
) -> tuple[str, bool]:
    """
    Called by pre_write_validator.py when validation fails.

    Returns:
      (message: str, is_hard_stop: bool)
      message      -> written to stderr so Codex shows it to the agent
      is_hard_stop -> True if the agent must stop entirely
    """
    slug = extract_slug(file_path)
    agent_key = extract_agent_key(file_path)
    errors_dir = extract_errors_dir(file_path)
    display_name, command = AGENT_META.get(agent_key, (agent_key.upper(), f"$team-{agent_key}"))

    prior = count_prior_attempts(errors_dir, agent_key)
    attempt_n = prior + 1
    is_hard_stop = attempt_n >= MAX_ATTEMPTS

    log_path = write_attempt_log(
        errors_dir=errors_dir,
        agent_key=agent_key,
        attempt_n=attempt_n,
        file_path=file_path,
        slug=slug,
        missing_sections=missing_sections,
        cred_violations=cred_violations,
    )

    issues_str = _console_issues(missing_sections, cred_violations)

    if is_hard_stop:
        message = (
            f"[{display_name}] VALIDATION FAILED — attempt {attempt_n}/{MAX_ATTEMPTS} — HARD STOP\n"
            f"\n"
            f"{issues_str}\n"
            f"\n"
            f"Error log : {log_path}\n"
            f"Action    : run `{command} --project {slug}` to retry manually\n"
            f"\n"
            f"PIPELINE HALTED. The file was NOT saved. Resolve all issues before retrying."
        )
    else:
        remaining = MAX_ATTEMPTS - attempt_n
        message = (
            f"[{display_name}] Validation failed — attempt {attempt_n}/{MAX_ATTEMPTS} — RETRY REQUIRED\n"
            f"\n"
            f"{issues_str}\n"
            f"\n"
            f"Attempt log      : {log_path}\n"
            f"Remaining tries  : {remaining}/{MAX_ATTEMPTS}\n"
            f"\n"
            f"The file was NOT saved. Rewrite it addressing ALL issues above, then try the patch again."
        )

    return message, is_hard_stop
