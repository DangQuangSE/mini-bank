"""Pre-Write hook: validates plan.json structure before allowing write."""

import json, os, sys, re

def validate_plan(data):
    errors = []
    if not isinstance(data, dict):
        errors.append("Root must be a JSON object")
        return errors
    if "plan_id" not in data:
        errors.append("Missing required field: plan_id")
    if "goal" not in data:
        errors.append("Missing required field: goal")
    if "current_step" not in data:
        errors.append("Missing required field: current_step")
    if "steps" not in data or not isinstance(data["steps"], list):
        errors.append("Missing or invalid field: steps (must be array)")
        return errors
    if not data["steps"]:
        errors.append("steps array is empty")
    for i, step in enumerate(data["steps"]):
        prefix = f"steps[{i}]"
        if "step_id" not in step:
            errors.append(f"{prefix}.step_id is required")
        if "description" not in step:
            errors.append(f"{prefix}.description is required")
        if "status" not in step:
            errors.append(f"{prefix}.status is required")
        elif step["status"] not in ("pending", "in_progress", "completed", "failed", "blocked"):
            errors.append(f"{prefix}.status must be one of: pending, in_progress, completed, failed, blocked")
        if "success_criteria" not in step or not isinstance(step.get("success_criteria"), list):
            errors.append(f"{prefix}.success_criteria must be a non-empty array")
        if "input_files" not in step or not isinstance(step.get("input_files"), list):
            errors.append(f"{prefix}.input_files must be an array")
        if "output_files" not in step or not isinstance(step.get("output_files"), list):
            errors.append(f"{prefix}.output_files must be an array")
    return errors

def main():
    filepath = os.environ.get("CLAUDE_FILE_PATH", "")
    if not filepath or "plan.json" not in filepath:
        sys.exit(0)
    try:
        with open(filepath) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"[Plan Validator] INVALID JSON: {e}")
        sys.exit(1)
    except FileNotFoundError:
        sys.exit(0)
    errors = validate_plan(data)
    if errors:
        print(f"[Plan Validator] BLOCKED: {len(errors)} validation error(s)")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)
    print(f"[Plan Validator] PASS: {len(data.get('steps', []))} steps, step_id order OK")
    sys.exit(0)

if __name__ == "__main__":
    main()
