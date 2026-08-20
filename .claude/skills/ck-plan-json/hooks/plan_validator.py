#!/usr/bin/env python3
"""Validate phased ck:plan-json documents and PreToolUse payloads."""

from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path
from typing import Any


PLAN_STATUSES = {"pending", "in_progress", "completed", "blocked"}
PHASE_STATUSES = PLAN_STATUSES
STEP_STATUSES = {"pending", "in_progress", "completed", "failed", "blocked"}
QUALITY_STATUSES = {"not_evaluated", "changes_required", "approved", "skipped_by_user"}
TESTING_STATUSES = {"not_started", "blocked_on_quality", "in_progress", "passed", "failed"}
PHASE_FILE_RE = re.compile(r"^phase-(\d{2})-([a-z0-9]+(?:-[a-z0-9]+)*)\.json$")
KEBAB_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _enum_error(value: Any, allowed: set[str], label: str) -> str | None:
    if not isinstance(value, str) or value not in allowed:
        return f"{label} must be one of: {', '.join(sorted(allowed))}"
    return None


def _validate_quality_state(data: dict[str, Any], prefix: str) -> list[str]:
    """Validate optional design_constraints/quality_profile/quality/testing fields.

    All four fields are optional so plans written before this schema addition
    remain valid; a present field must still have the correct shape.
    """
    errors: list[str] = []
    if "design_constraints" in data:
        constraints = data["design_constraints"]
        if not isinstance(constraints, list) or any(
            not isinstance(item, str) or not item.strip() for item in constraints
        ):
            errors.append(f"{prefix}.design_constraints must be an array of non-empty strings")
    if "quality_profile" in data and not isinstance(data["quality_profile"], dict):
        errors.append(f"{prefix}.quality_profile must be an object")
    if "quality" in data:
        quality = data["quality"]
        if not isinstance(quality, dict):
            errors.append(f"{prefix}.quality must be an object")
        else:
            error = _enum_error(quality.get("status"), QUALITY_STATUSES, f"{prefix}.quality.status")
            if error:
                errors.append(error)
            for field in ("report", "receipt"):
                if field in quality and not isinstance(quality[field], str):
                    errors.append(f"{prefix}.quality.{field} must be a string")
            if quality.get("status") == "skipped_by_user" and quality.get("decision") != "user_confirmed_skip":
                errors.append(f"{prefix}.quality.decision must be user_confirmed_skip when quality is skipped")
            if "remediation_cycles" in quality and (
                not _is_int(quality["remediation_cycles"]) or quality["remediation_cycles"] < 0
            ):
                errors.append(f"{prefix}.quality.remediation_cycles must be a non-negative integer")
    if "testing" in data:
        testing = data["testing"]
        if not isinstance(testing, dict):
            errors.append(f"{prefix}.testing must be an object")
        else:
            error = _enum_error(testing.get("status"), TESTING_STATUSES, f"{prefix}.testing.status")
            if error:
                errors.append(error)
            if "report" in testing and not isinstance(testing["report"], str):
                errors.append(f"{prefix}.testing.report must be a string")
    return errors


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _required(data: dict[str, Any], fields: tuple[str, ...], prefix: str) -> list[str]:
    return [f"{prefix}.{field} is required" for field in fields if field not in data]


def _read_json(path: Path, label: str) -> tuple[Any | None, list[str]]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except FileNotFoundError:
        return None, [f"{label} is missing: {path.name}"]
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return None, [f"{label} contains invalid JSON: {exc}"]
    except OSError as exc:
        return None, [f"{label} cannot be read: {exc}"]


def _parse_proposed(content: Any, label: str) -> tuple[Any | None, list[str]]:
    if not isinstance(content, str):
        return None, [f"{label} proposed content must be a JSON string"]
    try:
        return json.loads(content), []
    except json.JSONDecodeError as exc:
        return None, [f"{label} contains invalid JSON: {exc}"]


def validate_phase(data: Any, prefix: str = "phase") -> list[str]:
    """Validate one phase document without consulting its master manifest."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return [f"{prefix} must be a JSON object"]

    required = ("plan_id", "phase_id", "name", "goal", "status", "current_step", "steps")
    errors.extend(_required(data, required, prefix))
    if errors:
        return errors

    if not isinstance(data["plan_id"], str) or not data["plan_id"].strip():
        errors.append(f"{prefix}.plan_id must be a non-empty string")
    if not _is_int(data["phase_id"]) or data["phase_id"] < 1:
        errors.append(f"{prefix}.phase_id must be a positive integer")
    if not isinstance(data["name"], str) or not KEBAB_RE.fullmatch(data["name"]):
        errors.append(f"{prefix}.name must be kebab-case")
    if not isinstance(data["goal"], str) or not data["goal"].strip():
        errors.append(f"{prefix}.goal must be a non-empty string")

    status = data["status"]
    if not isinstance(status, str) or status not in PHASE_STATUSES:
        errors.append(f"{prefix}.status must be one of: {', '.join(sorted(PHASE_STATUSES))}")

    errors.extend(_validate_quality_state(data, prefix))

    steps = data["steps"]
    if not isinstance(steps, list) or not steps:
        errors.append(f"{prefix}.steps must be a non-empty array")
        return errors
    if len(steps) > 15:
        errors.append(f"{prefix}.steps must contain at most 15 steps")

    for index, step in enumerate(steps, start=1):
        step_prefix = f"{prefix}.steps[{index - 1}]"
        if not isinstance(step, dict):
            errors.append(f"{step_prefix} must be an object")
            continue
        step_required = (
            "step_id", "description", "status", "input_files", "output_files",
            "ai_generated_code", "debug_logs", "success_criteria",
        )
        missing = _required(step, step_required, step_prefix)
        errors.extend(missing)
        if missing:
            continue
        if step["step_id"] != index or not _is_int(step["step_id"]):
            errors.append(f"{step_prefix}.step_id must equal {index}")
        if not isinstance(step["description"], str) or not step["description"].strip():
            errors.append(f"{step_prefix}.description must be a non-empty string")
        if not isinstance(step["status"], str) or step["status"] not in STEP_STATUSES:
            errors.append(f"{step_prefix}.status is invalid")
        for field in ("input_files", "output_files", "debug_logs", "success_criteria"):
            if not isinstance(step[field], list):
                errors.append(f"{step_prefix}.{field} must be an array")
        for field in ("input_files", "output_files"):
            values = step[field]
            if isinstance(values, list) and any(
                not isinstance(item, str) or not item.strip() for item in values
            ):
                errors.append(f"{step_prefix}.{field} must contain non-empty strings only")
        logs = step["debug_logs"]
        if isinstance(logs, list):
            if len(logs) > 3:
                errors.append(f"{step_prefix}.debug_logs must contain at most 3 entries")
            for log_index, log in enumerate(logs):
                if not isinstance(log, dict) or any(
                    not isinstance(log.get(field), str) or not log[field].strip()
                    for field in ("timestamp", "error", "attempted_fix")
                ):
                    errors.append(
                        f"{step_prefix}.debug_logs[{log_index}] must contain non-empty "
                        "timestamp, error, and attempted_fix strings"
                    )
        if not isinstance(step["ai_generated_code"], str):
            errors.append(f"{step_prefix}.ai_generated_code must be a string")
        criteria = step["success_criteria"]
        if isinstance(criteria, list) and (
            not criteria or any(not isinstance(item, str) or not item.strip() for item in criteria)
        ):
            errors.append(f"{step_prefix}.success_criteria must be a non-empty string array")
        if step["status"] == "failed" and isinstance(step["debug_logs"], list) and not step["debug_logs"]:
            errors.append(f"{step_prefix}.debug_logs must record a failed attempt")

    cursor = data["current_step"]
    if not _is_int(cursor):
        errors.append(f"{prefix}.current_step must be an integer")
        return errors

    statuses = [step.get("status") if isinstance(step, dict) else None for step in steps]
    count = len(steps)
    if status == "pending":
        if cursor != 1 or any(item != "pending" for item in statuses):
            errors.append(f"{prefix} pending state requires current_step 1 and all steps pending")
    elif status == "in_progress":
        if not 1 <= cursor <= count:
            errors.append(f"{prefix}.current_step is out of range for in_progress state")
        else:
            before, active, after = statuses[: cursor - 1], statuses[cursor - 1], statuses[cursor:]
            if any(item != "completed" for item in before) or active not in {"in_progress", "failed"} or any(item != "pending" for item in after):
                errors.append(f"{prefix} in_progress state is inconsistent with current_step")
    elif status == "completed":
        if cursor != count + 1 or any(item != "completed" for item in statuses):
            errors.append(f"{prefix} completed state requires current_step = step_count + 1 and all steps completed")
        quality = data.get("quality")
        if not isinstance(quality, dict) or quality.get("status") not in {"approved", "skipped_by_user"}:
            errors.append(f"{prefix} completed state requires quality.status = approved or skipped_by_user")
    elif status == "blocked":
        if not 1 <= cursor <= count:
            errors.append(f"{prefix}.current_step is out of range for blocked state")
        else:
            before, active, after = statuses[: cursor - 1], statuses[cursor - 1], statuses[cursor:]
            if any(item != "completed" for item in before) or active != "blocked" or any(item != "pending" for item in after):
                errors.append(f"{prefix} blocked state is inconsistent with current_step")
    return errors


def _validate_master_state(master: dict[str, Any], errors: list[str]) -> None:
    phases = master.get("phases")
    if not isinstance(phases, list) or not phases:
        return
    status = master.get("status")
    cursor = master.get("current_phase")
    statuses = [entry.get("status") if isinstance(entry, dict) else None for entry in phases]
    count = len(phases)
    if not _is_int(cursor):
        errors.append("plan.current_phase must be an integer")
        return
    if status == "pending":
        if cursor != 1 or any(item != "pending" for item in statuses):
            errors.append("plan pending state requires current_phase 1 and all phases pending")
    elif status == "in_progress":
        if not 1 <= cursor <= count:
            errors.append("plan.current_phase is out of range for in_progress state")
        else:
            before, active, after = statuses[: cursor - 1], statuses[cursor - 1], statuses[cursor:]
            if any(item != "completed" for item in before) or active not in {"pending", "in_progress"} or any(item != "pending" for item in after):
                errors.append("plan in_progress state is inconsistent with current_phase")
    elif status == "completed":
        if cursor != count + 1 or any(item != "completed" for item in statuses):
            errors.append("plan completed state requires current_phase = phase_count + 1 and all phases completed")
    elif status == "blocked":
        if not 1 <= cursor <= count:
            errors.append("plan.current_phase is out of range for blocked state")
        else:
            before, active, after = statuses[: cursor - 1], statuses[cursor - 1], statuses[cursor:]
            if any(item != "completed" for item in before) or active != "blocked" or any(item != "pending" for item in after):
                errors.append("plan blocked state is inconsistent with current_phase")


def validate_bundle(master_path: str | Path, master_override: Any | None = None) -> tuple[list[str], dict[str, int]]:
    """Validate a master manifest and every phase file it references."""
    path = Path(master_path).expanduser().resolve()
    stats = {"phase_count": 0, "step_count": 0}
    if master_override is None:
        master, errors = _read_json(path, "plan")
    elif isinstance(master_override, str):
        master, errors = _parse_proposed(master_override, "plan")
    else:
        master, errors = master_override, []
    if errors:
        return errors, stats
    if not isinstance(master, dict):
        return ["plan must be a JSON object"], stats

    errors = _required(
        master,
        ("plan_id", "goal", "status", "current_phase", "global_context", "phases"),
        "plan",
    )
    if "steps" in master:
        errors.append("plan.steps is forbidden; steps belong in phase files")
    if not isinstance(master.get("plan_id"), str) or not master.get("plan_id", "").strip():
        errors.append("plan.plan_id must be a non-empty string")
    if not isinstance(master.get("goal"), str) or not master.get("goal", "").strip():
        errors.append("plan.goal must be a non-empty string")
    if not isinstance(master.get("status"), str) or master.get("status") not in PLAN_STATUSES:
        errors.append("plan.status is invalid")
    if not isinstance(master.get("global_context"), dict):
        errors.append("plan.global_context must be an object")
    phases = master.get("phases")
    if not isinstance(phases, list) or not phases:
        errors.append("plan.phases must be a non-empty array")
        return errors, stats

    stats["phase_count"] = len(phases)
    base = path.parent.resolve()
    seen_files: set[str] = set()
    seen_ids: set[int] = set()
    for index, entry in enumerate(phases, start=1):
        prefix = f"phases[{index - 1}]"
        if not isinstance(entry, dict):
            errors.append(f"{prefix} must be an object")
            continue
        missing = _required(entry, ("phase_id", "name", "description", "file", "status", "depends_on"), prefix)
        errors.extend(missing)
        if missing:
            continue

        phase_id = entry["phase_id"]
        name = entry["name"]
        filename = entry["file"]
        if not _is_int(phase_id) or phase_id != index or phase_id in seen_ids:
            errors.append(f"{prefix}.phase_id must be unique, sequential, and equal {index}")
        if _is_int(phase_id):
            seen_ids.add(phase_id)
        if not isinstance(name, str) or not KEBAB_RE.fullmatch(name):
            errors.append(f"{prefix}.name must be kebab-case")
        if not isinstance(entry["description"], str) or not entry["description"].strip():
            errors.append(f"{prefix}.description must be a non-empty string")
        if not isinstance(entry["status"], str) or entry["status"] not in PHASE_STATUSES:
            errors.append(f"{prefix}.status is invalid")
        if "steps" in entry:
            errors.append(f"{prefix}.steps is forbidden; step detail belongs in the phase file")
        if "quality_status" in entry:
            error = _enum_error(entry["quality_status"], QUALITY_STATUSES, f"{prefix}.quality_status")
            if error:
                errors.append(error)
        if "testing_status" in entry:
            error = _enum_error(entry["testing_status"], TESTING_STATUSES, f"{prefix}.testing_status")
            if error:
                errors.append(error)
        if entry.get("status") == "completed" and entry.get("quality_status") not in {"approved", "skipped_by_user"}:
            errors.append(f"{prefix} completed state requires quality_status = approved or skipped_by_user")

        dependencies = entry["depends_on"]
        if not isinstance(dependencies, list):
            errors.append(f"{prefix}.depends_on must be an array")
        elif (
            any(not _is_int(item) for item in dependencies)
            or len(set(dependencies)) != len(dependencies)
            or any(item < 1 or not _is_int(phase_id) or item >= phase_id for item in dependencies)
        ):
            errors.append(f"{prefix}.depends_on may contain unique earlier phase IDs only")

        if not isinstance(filename, str):
            errors.append(f"{prefix}.file must be a string")
            continue
        normalized = filename.replace("\\", "/").casefold()
        if normalized in seen_files:
            errors.append(f"{prefix}.file is a duplicate phase reference")
        seen_files.add(normalized)
        expected = f"phase-{phase_id:02d}-{name}.json" if _is_int(phase_id) and isinstance(name, str) else ""
        candidate = Path(filename)
        if candidate.is_absolute() or candidate.name != filename or "/" in filename or "\\" in filename:
            errors.append(f"{prefix}.file must be a basename-only sibling of plan.json")
            continue
        if not PHASE_FILE_RE.fullmatch(filename) or filename != expected:
            errors.append(f"{prefix}.file must match phase-{{phase_id:02d}}-{{kebab-name}}.json")
            continue
        phase_path = (base / filename).resolve()
        if phase_path.parent != base:
            errors.append(f"{prefix}.file escapes plan directory")
            continue

        phase, phase_read_errors = _read_json(phase_path, prefix)
        errors.extend(phase_read_errors)
        if phase_read_errors:
            continue
        phase_errors = validate_phase(phase, prefix=f"phase-{phase_id:02d}")
        errors.extend(phase_errors)
        if isinstance(phase, dict):
            steps = phase.get("steps")
            if isinstance(steps, list):
                stats["step_count"] += len(steps)
            for field, expected_value in (
                ("plan_id", master.get("plan_id")),
                ("phase_id", phase_id),
                ("name", name),
                ("status", entry["status"]),
            ):
                if phase.get(field) != expected_value:
                    errors.append(f"phase-{phase_id:02d}.{field} does not match master")
            if "quality_status" in entry:
                phase_quality = phase.get("quality")
                if not isinstance(phase_quality, dict) or phase_quality.get("status") != entry["quality_status"]:
                    errors.append(f"phase-{phase_id:02d}.quality.status does not match master.quality_status")
            if "testing_status" in entry:
                phase_testing = phase.get("testing")
                if not isinstance(phase_testing, dict) or phase_testing.get("status") != entry["testing_status"]:
                    errors.append(f"phase-{phase_id:02d}.testing.status does not match master.testing_status")

    _validate_master_state(master, errors)
    return errors, stats


def _validate_recovery_master(master: Any, phase_id: Any) -> list[str]:
    """Validate master-only invariants before applying a recovery transition."""
    if not isinstance(master, dict):
        return ["master must be an object"]
    errors = _required(
        master,
        ("plan_id", "goal", "status", "current_phase", "global_context", "phases"),
        "master",
    )
    if "steps" in master:
        errors.append("master.steps is forbidden")
    if not isinstance(master.get("plan_id"), str) or not master.get("plan_id", "").strip():
        errors.append("master.plan_id must be a non-empty string")
    if not isinstance(master.get("status"), str) or master.get("status") not in PLAN_STATUSES:
        errors.append("master.status is invalid")
    if not _is_int(master.get("current_phase")):
        errors.append("master.current_phase must be an integer")
    if not isinstance(master.get("global_context"), dict):
        errors.append("master.global_context must be an object")
    phases = master.get("phases")
    if not isinstance(phases, list) or not phases:
        errors.append("master.phases must be a non-empty array")
        return errors

    for index, entry in enumerate(phases, start=1):
        prefix = f"master.phases[{index - 1}]"
        if not isinstance(entry, dict):
            errors.append(f"{prefix} must be an object")
            continue
        missing = _required(
            entry,
            ("phase_id", "name", "description", "file", "status", "depends_on"),
            prefix,
        )
        errors.extend(missing)
        if missing:
            continue
        if entry["phase_id"] != index or not _is_int(entry["phase_id"]):
            errors.append(f"{prefix}.phase_id must equal {index}")
        if not isinstance(entry["name"], str) or not KEBAB_RE.fullmatch(entry["name"]):
            errors.append(f"{prefix}.name must be kebab-case")
        expected = f"phase-{index:02d}-{entry['name']}.json" if isinstance(entry["name"], str) else ""
        if not isinstance(entry["file"], str) or entry["file"] != expected or Path(entry["file"]).name != entry["file"]:
            errors.append(f"{prefix}.file is invalid")
        if not isinstance(entry["status"], str) or entry["status"] not in PHASE_STATUSES:
            errors.append(f"{prefix}.status is invalid")
        if "steps" in entry:
            errors.append(f"{prefix}.steps is forbidden")
        dependencies = entry["depends_on"]
        if not isinstance(dependencies, list) or (
            any(not _is_int(item) for item in dependencies)
            or len(set(dependencies)) != len(dependencies)
            or any(item < 1 or item >= index for item in dependencies)
        ):
            errors.append(f"{prefix}.depends_on may contain unique earlier phase IDs only")

    _validate_master_state(master, errors)
    if not _is_int(phase_id) or not 1 <= phase_id <= len(phases):
        errors.append("phase.phase_id is outside master phases")
        return errors
    if master.get("current_phase") != phase_id:
        errors.append("phase is not the master's current_phase")
        return errors

    for prior in phases[: phase_id - 1]:
        if not isinstance(prior, dict) or prior.get("status") != "completed":
            errors.append("all prior phases must be completed before recovery")
            break
    for later in phases[phase_id:]:
        if not isinstance(later, dict) or later.get("status") != "pending":
            errors.append("all later phases must remain pending during recovery")
            break
    active = phases[phase_id - 1]
    if isinstance(active, dict) and isinstance(active.get("depends_on"), list):
        for dependency in active["depends_on"]:
            if _is_int(dependency) and 1 <= dependency <= len(phases):
                target = phases[dependency - 1]
                if not isinstance(target, dict) or target.get("status") != "completed":
                    errors.append(f"dependency phase {dependency} is incomplete")
    return errors


def reconcile_master(master: Any, phase: Any) -> tuple[Any, list[str]]:
    """Repair one legal phase-first transition without mutating caller data."""
    updated = copy.deepcopy(master)
    if not isinstance(master, dict) or not isinstance(phase, dict):
        return updated, ["master and phase must be objects"]
    if phase.get("plan_id") != master.get("plan_id"):
        return updated, ["phase.plan_id does not match master"]
    phase_id = phase.get("phase_id")
    master_errors = _validate_recovery_master(master, phase_id)
    if master_errors:
        return updated, master_errors
    entry = master["phases"][phase_id - 1]
    if not isinstance(entry, dict) or entry.get("phase_id") != phase_id:
        return updated, ["phase.phase_id does not match master ordering"]
    if phase.get("name") != entry.get("name"):
        return updated, ["phase.name does not match master"]
    if master.get("current_phase") != phase_id:
        return updated, ["phase is not the master's current_phase"]

    phase_errors = validate_phase(phase, prefix=f"phase-{phase_id:02d}")
    if phase_errors:
        return updated, phase_errors
    master_status = entry.get("status")
    phase_status = phase.get("status")
    if not isinstance(master_status, str) or not isinstance(phase_status, str):
        return updated, ["master and phase status values must be strings"]
    if master_status == phase_status:
        return updated, []
    if master_status == "in_progress" and phase_status == "pending":
        return updated, ["master is ahead of phase; automatic recovery is unsafe"]

    transition = (master_status, phase_status)
    allowed = {("pending", "in_progress"), ("in_progress", "completed"), ("in_progress", "blocked")}
    if transition not in allowed:
        return updated, [f"status transition {master_status!r} -> {phase_status!r} is not one legal recovery step"]

    updated_entry = updated["phases"][phase_id - 1]
    updated_entry["status"] = phase_status
    if phase_status == "in_progress":
        updated["status"] = "in_progress"
    elif phase_status == "blocked":
        updated["status"] = "blocked"
    else:
        if phase_id == len(updated["phases"]):
            updated["status"] = "completed"
            updated["current_phase"] = len(updated["phases"]) + 1
        else:
            updated["status"] = "in_progress"
            updated["current_phase"] = phase_id + 1
    return updated, []


def apply_edit(
    existing: str,
    old_string: str,
    new_string: str,
    replace_all: bool = False,
) -> str:
    """Reconstruct an Edit tool's proposed file content."""
    if not isinstance(old_string, str) or not old_string:
        raise ValueError("old_string must be non-empty")
    if not isinstance(new_string, str):
        raise ValueError("new_string must be a string")
    occurrences = existing.count(old_string)
    if replace_all:
        if occurrences < 1:
            raise ValueError("old_string must occur at least once")
        return existing.replace(old_string, new_string)
    if occurrences != 1:
        raise ValueError("old_string must occur exactly once")
    return existing.replace(old_string, new_string, 1)


def handle_hook_payload(payload: Any) -> tuple[list[str], dict[str, int]]:
    """Validate proposed Write/Edit content from a Claude Code hook payload."""
    stats = {"phase_count": 0, "step_count": 0}
    if not isinstance(payload, dict):
        return ["hook payload must be an object"], stats
    tool_name = payload.get("tool_name")
    tool_input = payload.get("tool_input", {})
    if tool_name not in {"Write", "Edit"} or not isinstance(tool_input, dict):
        return [], stats
    raw_path = tool_input.get("file_path", "")
    if not isinstance(raw_path, str) or not raw_path:
        return [], stats
    path = Path(raw_path).expanduser().resolve()
    is_master = path.name == "plan.json"
    is_phase = bool(PHASE_FILE_RE.fullmatch(path.name))
    if not is_master and not is_phase:
        return [], stats

    if tool_name == "Write":
        proposed = tool_input.get("content")
    else:
        try:
            existing = path.read_text(encoding="utf-8")
            proposed = apply_edit(
                existing,
                tool_input.get("old_string", ""),
                tool_input.get("new_string", ""),
                replace_all=tool_input.get("replace_all") is True,
            )
        except (OSError, ValueError) as exc:
            return [f"cannot reconstruct proposed edit: {exc}"], stats
    data, parse_errors = _parse_proposed(proposed, path.name)
    if parse_errors:
        return parse_errors, stats
    if is_master:
        return validate_bundle(path, master_override=data)
    phase_errors = validate_phase(data, prefix=path.stem)
    filename_match = PHASE_FILE_RE.fullmatch(path.name)
    if filename_match and isinstance(data, dict):
        expected_id = int(filename_match.group(1))
        expected_name = filename_match.group(2)
        if data.get("phase_id") != expected_id or data.get("name") != expected_name:
            phase_errors.append(
                "phase filename identity does not match proposed phase_id and name"
            )
    if isinstance(data, dict) and isinstance(data.get("steps"), list):
        stats = {"phase_count": 1, "step_count": len(data["steps"])}
    return phase_errors, stats


def _emit(errors: list[str], stats: dict[str, int]) -> int:
    if errors:
        print(f"[Plan Validator] BLOCKED: {len(errors)} validation error(s)", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 2
    print(
        f"[Plan Validator] PASS: {stats['phase_count']} phase(s), "
        f"{stats['step_count']} total step(s)"
    )
    return 0


def main() -> int:
    if len(sys.argv) > 1:
        target = sys.argv[-1]
        return _emit(*validate_bundle(target))
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return 0
    return _emit(*handle_hook_payload(payload))


if __name__ == "__main__":
    sys.exit(main())
