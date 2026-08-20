#!/usr/bin/env python3
"""Codex apply_patch adapter for the ck:quality completion receipt gate.

Codex exposes a V4A patch rather than Claude's proposed file content. This
adapter detects only explicit completion additions and verifies the same
plan-local receipt used by the canonical gate. Skills still invoke
`receipt.py verify` directly; this hook is defense in depth.
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "skills" / "ck-quality" / "scripts"))
from receipt import verify_receipt  # noqa: E402

HEADER = re.compile(r"^\*\*\* (Add File|Update File): (.+?)\s*$", re.MULTILINE)
COMPLETED = re.compile(r'^\+\s*"status"\s*:\s*"completed"', re.MULTILINE)
CHECKED = re.compile(r"^\+\s*- \[x\]\s*Phase\s+(\d+)\b.*$", re.MULTILINE | re.IGNORECASE)


def sections(patch: str):
    matches = list(HEADER.finditer(patch))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(patch)
        yield match.group(2).strip(), patch[match.end():end]


def receipt_for_phase_file(path: Path) -> Path:
    return path.parent / "quality" / f"{path.stem}-receipt.json"


def phase_has_confirmed_skip(path: Path) -> bool:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    quality = data.get("quality") if isinstance(data, dict) else None
    return isinstance(quality, dict) and quality.get("status") == "skipped_by_user" and quality.get("decision") == "user_confirmed_skip"


def receipts_for_master(path: Path, body: str) -> list[Path] | None:
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    candidates = []
    for phase in data.get("phases", []):
        if not isinstance(phase, dict) or phase.get("status") == "completed":
            continue
        phase_id, name = phase.get("phase_id"), phase.get("name")
        id_pattern = re.compile(rf'"phase_id"\s*:\s*{re.escape(str(phase_id))}\b')
        mentioned = bool(id_pattern.search(body)) or (isinstance(name, str) and name in body)
        if mentioned:
            candidates.append(phase)
    if not candidates:
        remaining = [p for p in data.get("phases", []) if isinstance(p, dict) and p.get("status") != "completed"]
        if len(remaining) != 1:
            return None
        candidates = remaining
    result = []
    for phase in candidates:
        phase_file = phase.get("file")
        if isinstance(phase_file, str):
            try:
                phase_data = json.loads((path.parent / phase_file).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                phase_data = None
            quality = phase_data.get("quality") if isinstance(phase_data, dict) else None
            if isinstance(quality, dict) and quality.get("status") == "skipped_by_user" and quality.get("decision") == "user_confirmed_skip":
                continue
        raw = phase.get("quality_receipt")
        if isinstance(raw, str) and raw:
            result.append(path.parent / raw if not Path(raw).is_absolute() else Path(raw))
        elif isinstance(phase.get("phase_id"), int) and isinstance(phase.get("name"), str):
            target = f"phase-{phase['phase_id']:02d}-{phase['name']}"
            result.append(path.parent / "quality" / f"{target}-receipt.json")
    return result


def required_receipts(root: Path, patch: str) -> list[Path]:
    required = []
    for raw_path, body in sections(patch):
        path = Path(raw_path)
        path = path if path.is_absolute() else root / path
        path = path.resolve()
        if path.name == "plan.md":
            for raw_num in CHECKED.findall(body):
                line = re.search(rf"^\+\s*- \[x\]\s*Phase\s+{raw_num}\b.*$", body, re.MULTILINE | re.IGNORECASE)
                if line and "quality: skipped_by_user; decision: user_confirmed_skip" in line.group(0).lower():
                    continue
                matches = sorted(path.parent.glob(f"phase-{int(raw_num):02d}-*.md"))
                target = matches[0].stem if matches else f"phase-{int(raw_num):02d}"
                required.append(path.parent / "quality" / f"{target}-receipt.json")
        elif re.fullmatch(r"phase-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*\.json", path.name) and COMPLETED.search(body):
            if phase_has_confirmed_skip(path):
                continue
            required.append(receipt_for_phase_file(path))
        elif path.name == "plan.json" and COMPLETED.search(body):
            resolved = receipts_for_master(path, body)
            if resolved is None:
                raise RuntimeError("cannot resolve the completed master phase receipt from this patch")
            required.extend(resolved)
    return required


def main() -> None:
    data = json.load(sys.stdin)
    tool_input = data.get("tool_input", {})
    patch = tool_input.get("command", "") if isinstance(tool_input, dict) else ""
    if not isinstance(patch, str) or not patch:
        return
    root = Path(data.get("cwd") or Path.cwd()).resolve()
    failures = []
    for receipt in required_receipts(root, patch):
        suffix = "-receipt.json"
        expected_target = receipt.name[:-len(suffix)] if receipt.name.endswith(suffix) else None
        ok, errors = verify_receipt(receipt, repo_root=root, expected_target=expected_target)
        if not ok:
            failures.append((receipt, errors))
    if failures:
        for receipt, errors in failures:
            sys.stderr.write(f"[quality-receipt-gate] invalid receipt: {receipt}\n")
            for error in errors:
                sys.stderr.write(f"  - {error}\n")
        sys.exit(2)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        sys.stderr.write(f"[quality-receipt-gate] blocked: {exc}\n")
        sys.exit(2)
