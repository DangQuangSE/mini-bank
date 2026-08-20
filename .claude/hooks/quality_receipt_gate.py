#!/usr/bin/env python3
"""
PreToolUse Write|Edit hook — block a phase-completion transition without a
fresh, valid ck:quality receipt.

Fires only on the transition itself (old on-disk state != completed, proposed
state == completed). Ordinary edits that leave completion status unchanged —
including files that already had a phase checked off before this hook
existed — are never blocked. Detects three completion surfaces:

  - a JSON phase file (phase-NN-name.json): status becomes "completed"
  - the JSON master (plan.json): any phases[] entry status becomes "completed"
  - a Markdown plan.md: a "- [ ] Phase N: ..." box becomes "- [x] Phase N: ..."

Verification logic (fingerprint, policy version, open-blocker count) lives in
skills/ck-quality/scripts/receipt.py — this hook only resolves *which*
receipt(s) a proposed write requires and calls that shared verifier.
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
try:
    from ck_config_utils import is_enabled  # noqa: E402
except ImportError:
    # Standalone Antigravity/Codex adapters may not install the Claude hook
    # utility package. Receipt enforcement stays enabled by default.
    def is_enabled(_name: str) -> bool:
        return True

sys.path.insert(0, str(Path(__file__).parent.parent / "skills" / "ck-quality" / "scripts"))
from receipt import verify_receipt  # noqa: E402

PHASE_JSON_RE = re.compile(r"^phase-(\d{2})-([a-z0-9]+(?:-[a-z0-9]+)*)\.json$")
MD_CHECKBOX_RE = re.compile(r"^- \[( |x|X)\]\s*Phase\s+(\d+)\b", re.MULTILINE)


def _repo_root(start: Path) -> Path | None:
    for parent in [start, *start.parents]:
        if (parent / ".git").exists():
            return parent
    return None


def _apply_edit(existing: str, old_string: str, new_string: str, replace_all: bool) -> str | None:
    if not old_string:
        return None
    occurrences = existing.count(old_string)
    if replace_all:
        if occurrences < 1:
            return None
        return existing.replace(old_string, new_string)
    if occurrences != 1:
        return None
    return existing.replace(old_string, new_string, 1)


def _proposed_and_existing(tool_name: str, tool_input: dict, path: Path) -> tuple[str | None, str | None]:
    """Return (existing_content_or_None, proposed_content) for a Write/Edit call."""
    existing = None
    if path.is_file():
        try:
            existing = path.read_text(encoding="utf-8")
        except OSError:
            existing = None

    if tool_name == "Write":
        proposed = tool_input.get("content")
        return existing, proposed if isinstance(proposed, str) else None

    if existing is None:
        return None, None
    proposed = _apply_edit(
        existing,
        tool_input.get("old_string", ""),
        tool_input.get("new_string", ""),
        replace_all=tool_input.get("replace_all") is True,
    )
    return existing, proposed


def _receipt_dir_and_target_for(root: Path, phase_path: Path) -> tuple[Path, str]:
    return phase_path.parent / "quality", phase_path.stem


def _required_receipts_for_json_phase(root: Path, path: Path, existing: str | None, proposed: str) -> list[tuple[str, Path]]:
    old_status = None
    if existing is not None:
        try:
            old_status = json.loads(existing).get("status")
        except json.JSONDecodeError:
            old_status = None
    try:
        new_data = json.loads(proposed)
        new_status = new_data.get("status")
    except json.JSONDecodeError:
        return []
    if old_status == "completed" or new_status != "completed":
        return []
    quality = new_data.get("quality")
    if isinstance(quality, dict) and quality.get("status") == "skipped_by_user" and quality.get("decision") == "user_confirmed_skip":
        return []
    quality_dir, target = _receipt_dir_and_target_for(root, path)
    return [(target, quality_dir / f"{target}-receipt.json")]


def _required_receipts_for_master(root: Path, path: Path, existing: str | None, proposed: str) -> list[tuple[str, Path]]:
    try:
        new_data = json.loads(proposed)
    except json.JSONDecodeError:
        return []
    if not isinstance(new_data, dict):
        return []
    old_status_by_id: dict[int, str] = {}
    if existing is not None:
        try:
            old_data = json.loads(existing)
            for entry in old_data.get("phases", []) if isinstance(old_data, dict) else []:
                if isinstance(entry, dict) and isinstance(entry.get("phase_id"), int):
                    old_status_by_id[entry["phase_id"]] = entry.get("status")
        except json.JSONDecodeError:
            pass

    required = []
    quality_dir = path.parent / "quality"
    for entry in new_data.get("phases", []):
        if not isinstance(entry, dict):
            continue
        phase_id = entry.get("phase_id")
        name = entry.get("name")
        if not isinstance(phase_id, int) or not isinstance(name, str):
            continue
        if entry.get("status") != "completed":
            continue
        if old_status_by_id.get(phase_id) == "completed":
            continue
        if entry.get("quality_status") == "skipped_by_user":
            phase_file = entry.get("file")
            try:
                phase_data = json.loads((path.parent / phase_file).read_text(encoding="utf-8")) if isinstance(phase_file, str) else None
            except (OSError, json.JSONDecodeError):
                phase_data = None
            quality = phase_data.get("quality") if isinstance(phase_data, dict) else None
            if isinstance(quality, dict) and quality.get("status") == "skipped_by_user" and quality.get("decision") == "user_confirmed_skip":
                continue
        target = f"phase-{phase_id:02d}-{name}"
        required.append((target, quality_dir / f"{target}-receipt.json"))
    return required


def _checked_phase_numbers(content: str) -> set[int]:
    return {int(num) for mark, num in MD_CHECKBOX_RE.findall(content) if mark.lower() == "x"}


def _required_receipts_for_plan_md(root: Path, path: Path, existing: str | None, proposed: str) -> list[tuple[str, Path]]:
    old_checked = _checked_phase_numbers(existing) if existing is not None else set()
    new_checked = _checked_phase_numbers(proposed)
    newly_checked = new_checked - old_checked
    if not newly_checked:
        return []

    quality_dir = path.parent / "quality"
    required = []
    for num in sorted(newly_checked):
        phase_line = re.search(rf"^- \[[xX]\]\s*Phase\s+{num}\b.*$", proposed, re.MULTILINE)
        if phase_line and "quality: skipped_by_user; decision: user_confirmed_skip" in phase_line.group(0).lower():
            continue
        matches = sorted(path.parent.glob(f"phase-{num:02d}-*.md"))
        if not matches:
            # No phase file to resolve a target from; still require a receipt
            # under the plain phase-NN target so the transition fails closed.
            target = f"phase-{num:02d}"
        else:
            target = matches[0].stem
        required.append((target, quality_dir / f"{target}-receipt.json"))
    return required


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    if not is_enabled("qualityReceiptGate"):
        sys.exit(0)

    tool_name = data.get("tool_name")
    tool_input = data.get("tool_input", {})
    if tool_name not in {"Write", "Edit"} or not isinstance(tool_input, dict):
        sys.exit(0)

    raw_path = tool_input.get("file_path", "")
    if not isinstance(raw_path, str) or not raw_path:
        sys.exit(0)
    path = Path(raw_path)
    if not path.is_absolute():
        path = Path(data.get("cwd", ".")) / path
    path = path.resolve()

    root = _repo_root(path.parent)
    if root is None:
        sys.exit(0)

    is_master = path.name == "plan.json"
    is_json_phase = bool(PHASE_JSON_RE.fullmatch(path.name))
    is_plan_md = path.name == "plan.md"
    if not (is_master or is_json_phase or is_plan_md):
        sys.exit(0)

    existing, proposed = _proposed_and_existing(tool_name, tool_input, path)
    if proposed is None:
        sys.exit(0)

    if is_json_phase:
        required = _required_receipts_for_json_phase(root, path, existing, proposed)
    elif is_master:
        required = _required_receipts_for_master(root, path, existing, proposed)
    else:
        required = _required_receipts_for_plan_md(root, path, existing, proposed)

    if not required:
        sys.exit(0)

    failures = []
    for target, receipt_path in required:
        ok, errors = verify_receipt(receipt_path, repo_root=root, expected_target=target)
        if not ok:
            try:
                rel = receipt_path.relative_to(root)
            except ValueError:
                rel = receipt_path
            failures.append((target, rel, errors))

    if not failures:
        sys.exit(0)

    sys.stderr.write("[quality-receipt-gate] BLOCKED: phase-completion transition without a valid receipt.\n")
    for target, rel, errors in failures:
        sys.stderr.write(f"  - {target}: expected valid receipt at {rel}\n")
        for error in errors:
            sys.stderr.write(f"      {error}\n")
    sys.stderr.write(
        "Run `/ck:quality --gate <phase-file>` until APPROVED (it issues the receipt automatically), "
        "then retry this completion write.\n"
    )
    sys.exit(2)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        sys.stderr.write(f"[quality-receipt-gate] internal error: {exc}\n")
        sys.exit(2)
