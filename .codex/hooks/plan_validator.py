"""Codex PreToolUse hook for validating plan.json writes.

Codex sends apply_patch hooks a JSON event on stdin. The previous version of
this hook only read CLAUDE_FILE_PATH, so it silently skipped every Codex
patch. Add-file content is fully available; update-file content is only
best-effort because apply_patch does not include the old file in the event.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _patch_utils import FileOp, parse_apply_patch


def validate_plan(data: object) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["Root must be a JSON object"]

    for field in ("plan_id", "goal", "current_step"):
        if field not in data:
            errors.append(f"Missing required field: {field}")

    steps = data.get("steps")
    if not isinstance(steps, list):
        errors.append("Missing or invalid field: steps (must be array)")
        return errors
    if not steps:
        errors.append("steps array is empty")

    for i, step in enumerate(steps):
        prefix = f"steps[{i}]"
        if not isinstance(step, dict):
            errors.append(f"{prefix} must be an object")
            continue
        if "step_id" not in step:
            errors.append(f"{prefix}.step_id is required")
        if "description" not in step:
            errors.append(f"{prefix}.description is required")
        if "status" not in step:
            errors.append(f"{prefix}.status is required")
        elif step["status"] not in (
            "pending",
            "in_progress",
            "completed",
            "failed",
            "blocked",
        ):
            errors.append(
                f"{prefix}.status must be one of: pending, in_progress, "
                "completed, failed, blocked"
            )
        if "success_criteria" not in step or not isinstance(
            step.get("success_criteria"), list
        ):
            errors.append(f"{prefix}.success_criteria must be a non-empty array")
        if "input_files" not in step or not isinstance(step.get("input_files"), list):
            errors.append(f"{prefix}.input_files must be an array")
        if "output_files" not in step or not isinstance(step.get("output_files"), list):
            errors.append(f"{prefix}.output_files must be an array")

    return errors


def _resolve_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path

    current = Path.cwd()
    direct = current / path
    if direct.exists():
        return direct

    # Codex may start the command in a repository subdirectory.
    for parent in (current, *current.parents):
        candidate = parent / path
        if candidate.exists():
            return candidate
    return direct


def _validate_json(text: str, source: str) -> list[str]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return [f"{source}: INVALID JSON: {exc}"]
    return [f"{source}: {error}" for error in validate_plan(data)]


def _validate_operation(operation: FileOp) -> list[str]:
    if Path(operation.path).name.lower() != "plan.json":
        return []

    if operation.action == "add":
        return _validate_json(operation.content, operation.path)

    if operation.action != "update":
        return []

    # A complete JSON replacement is sometimes recoverable from the added
    # lines. Otherwise validate the current file as a safe best-effort check;
    # the raw Codex event does not contain unchanged lines from an update.
    candidate = operation.content.strip()
    if candidate.startswith("{") and candidate.endswith("}"):
        return _validate_json(candidate, operation.path)

    path = _resolve_path(operation.path)
    if not path.is_file():
        return []
    try:
        current = path.read_text(encoding="utf-8")
    except OSError:
        return []
    return _validate_json(current, str(path))


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return 0

    if not isinstance(event, dict) or event.get("tool_name") != "apply_patch":
        return 0

    tool_input = event.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0
    command = tool_input.get("command", "")
    if not isinstance(command, str) or not command:
        return 0

    errors: list[str] = []
    for operation in parse_apply_patch(command):
        errors.extend(_validate_operation(operation))

    if errors:
        print(
            f"[Plan Validator] BLOCKED: {len(errors)} validation error(s)",
            file=sys.stderr,
        )
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
