#!/usr/bin/env python3
"""Issue and verify ck:quality receipts.

A receipt is the fingerprint proof `quality_receipt_gate.py` checks before
allowing a phase-completion transition. It never claims the semantic review
was correct — only that a specific APPROVED report and the exact file
contents it reviewed have not changed since issuance.

Usage:
    receipt.py issue  <report_path>    # report.verdict must be APPROVED
    receipt.py verify <receipt_path>   # re-checks fingerprint against disk
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

POLICY_VERSION = "1.0.0"
BLOCKING_SEVERITIES = {"BLOCKER", "HIGH"}


class ReceiptError(Exception):
    """A receipt cannot be issued, or a required precondition failed."""


def _repo_root(start: Path) -> Path:
    for parent in [start, *start.parents]:
        if (parent / ".git").exists():
            return parent
    raise ReceiptError(f"no repository root (.git) found above {start}")


def _default_root() -> Path:
    return _repo_root(Path.cwd())


def _resolve_in_repo(root: Path, raw: str, label: str) -> Path:
    """Resolve a path relative to root and reject anything that escapes it."""
    candidate = Path(raw)
    candidate = candidate if candidate.is_absolute() else root / candidate
    candidate = candidate.resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        raise ReceiptError(f"{label} escapes the repository: {raw}")
    return candidate


def _open_blocking_findings(report: dict[str, Any]) -> int:
    """Independently recompute the blocking count from findings, not summary."""
    count = 0
    for finding in report.get("findings", []):
        if not isinstance(finding, dict) or finding.get("status") != "OPEN":
            continue
        severity = finding.get("severity")
        if severity in BLOCKING_SEVERITIES:
            count += 1
        elif severity == "MEDIUM" and finding.get("introduced_by_current_change") is True:
            count += 1
    return count


def _fingerprint(root: Path, report_path: Path, reviewed_files: list[str]) -> str:
    """Hash the report bytes plus every reviewed file's exact current bytes."""
    digest = hashlib.sha256()
    digest.update(report_path.read_bytes())
    for rel in sorted(reviewed_files):
        file_path = _resolve_in_repo(root, rel, "reviewed_files entry")
        digest.update(rel.encode("utf-8"))
        digest.update(file_path.read_bytes())
    return f"sha256:{digest.hexdigest()}"


def issue_receipt(report_path: str | Path, repo_root: str | Path | None = None) -> dict[str, Any]:
    root = Path(repo_root).resolve() if repo_root else _default_root()
    resolved_report = _resolve_in_repo(root, str(report_path), "report_path")
    if not resolved_report.is_file():
        raise ReceiptError(f"report not found: {resolved_report}")
    try:
        report = json.loads(resolved_report.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ReceiptError(f"report is not valid JSON: {exc}")
    if not isinstance(report, dict):
        raise ReceiptError("report must be a JSON object")

    if report.get("verdict") != "APPROVED":
        raise ReceiptError(
            f"cannot issue a receipt for verdict {report.get('verdict')!r}; only APPROVED reports qualify"
        )
    open_blocking = _open_blocking_findings(report)
    if open_blocking != 0:
        raise ReceiptError(f"cannot issue a receipt: {open_blocking} open blocking finding(s) remain")

    reviewed_files = report.get("reviewed_files")
    if not isinstance(reviewed_files, list) or not reviewed_files or not all(
        isinstance(f, str) and f for f in reviewed_files
    ):
        raise ReceiptError("report.reviewed_files must be a non-empty array of strings")
    for rel in reviewed_files:
        path = _resolve_in_repo(root, rel, "reviewed_files entry")
        if not path.is_file():
            raise ReceiptError(f"reviewed file missing: {rel}")

    target = report.get("target")
    if not isinstance(target, str) or not target:
        raise ReceiptError("report.target must be a non-empty string")

    fingerprint = _fingerprint(root, resolved_report, reviewed_files)
    receipt = {
        "target": target,
        "verdict": "APPROVED",
        "policy_version": POLICY_VERSION,
        "report_path": str(resolved_report.relative_to(root)).replace("\\", "/"),
        "reviewed_files": sorted(reviewed_files),
        "source_fingerprint": fingerprint,
        "reviewed_at": report.get("reviewed_at"),
        "open_blocking_findings": 0,
    }
    receipt_path = resolved_report.parent / f"{target}-receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    receipt["issued_path"] = str(receipt_path.relative_to(root)).replace("\\", "/")
    return receipt


def verify_receipt(
    receipt_path: str | Path,
    repo_root: str | Path | None = None,
    expected_target: str | None = None,
) -> tuple[bool, list[str]]:
    root = Path(repo_root).resolve() if repo_root else _default_root()
    try:
        resolved_receipt = _resolve_in_repo(root, str(receipt_path), "receipt_path")
    except ReceiptError as exc:
        return False, [str(exc)]

    if not resolved_receipt.is_file():
        return False, [f"receipt not found: {resolved_receipt}"]
    try:
        receipt = json.loads(resolved_receipt.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return False, [f"receipt is not valid JSON: {exc}"]
    if not isinstance(receipt, dict):
        return False, ["receipt must be a JSON object"]

    errors: list[str] = []
    receipt_target = receipt.get("target")
    if not isinstance(receipt_target, str) or not receipt_target:
        errors.append("receipt.target is missing or malformed")
    else:
        expected_name = f"{receipt_target}-receipt.json"
        if resolved_receipt.name != expected_name:
            errors.append(
                f"receipt filename {resolved_receipt.name!r} does not match target {receipt_target!r}"
            )
        if expected_target is not None and receipt_target != expected_target:
            errors.append(
                f"receipt target {receipt_target!r} does not match expected phase {expected_target!r}"
            )
    if receipt.get("verdict") != "APPROVED":
        errors.append(f"receipt verdict is {receipt.get('verdict')!r}, not APPROVED")
    if receipt.get("policy_version") != POLICY_VERSION:
        errors.append(
            f"receipt policy_version {receipt.get('policy_version')!r} does not match current {POLICY_VERSION!r}"
        )
    if receipt.get("open_blocking_findings") != 0:
        errors.append("receipt records open_blocking_findings != 0")

    report_rel = receipt.get("report_path")
    reviewed_files = receipt.get("reviewed_files")
    if not isinstance(report_rel, str) or not report_rel:
        errors.append("receipt.report_path is missing")
        return False, errors
    if not isinstance(reviewed_files, list) or not all(isinstance(f, str) for f in reviewed_files):
        errors.append("receipt.reviewed_files is missing or malformed")
        return False, errors

    try:
        report_path = _resolve_in_repo(root, report_rel, "receipt.report_path")
        resolved_reviewed = [
            _resolve_in_repo(root, rel, "receipt.reviewed_files entry") for rel in reviewed_files
        ]
    except ReceiptError as exc:
        return False, [str(exc)]

    if not report_path.is_file():
        errors.append(f"reviewed report no longer exists: {report_rel}")
    for rel, resolved in zip(reviewed_files, resolved_reviewed):
        if not resolved.is_file():
            errors.append(f"reviewed file no longer exists: {rel}")
    if errors:
        return False, errors

    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return False, [f"reviewed report is not valid JSON: {exc}"]
    if not isinstance(report, dict) or report.get("target") != receipt_target:
        errors.append("reviewed report target does not match receipt.target")
        return False, errors

    try:
        current_fingerprint = _fingerprint(root, report_path, reviewed_files)
    except ReceiptError as exc:
        return False, [str(exc)]
    if current_fingerprint != receipt.get("source_fingerprint"):
        errors.append("source_fingerprint mismatch: the report or a reviewed file changed since the receipt was issued")

    return (not errors), errors


def main(argv: list[str]) -> int:
    if len(argv) < 3 or argv[1] not in {"issue", "verify"}:
        print("usage: receipt.py issue <report_path> | receipt.py verify <receipt_path>", file=sys.stderr)
        return 2
    action, target = argv[1], argv[2]
    try:
        if action == "issue":
            receipt = issue_receipt(target)
            print(json.dumps(receipt, indent=2))
            return 0
        ok, errors = verify_receipt(target)
        if ok:
            print(f"[ck:quality receipt] VALID: {target}")
            return 0
        print(f"[ck:quality receipt] INVALID: {target}", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    except ReceiptError as exc:
        print(f"[ck:quality receipt] ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
