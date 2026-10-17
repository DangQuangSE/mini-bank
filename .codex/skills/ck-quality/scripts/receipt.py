#!/usr/bin/env python3
"""Issue and verify ck:quality receipts.

A receipt is the fingerprint proof `quality_receipt_gate.py` checks before
allowing a phase-completion transition. It never claims the semantic review
was correct — only that a specific APPROVED report and the exact file
contents it reviewed have not changed since issuance.

The report and its reviewed files do not need to share one git repository
(a polyrepo project may keep `plans/{slug}` in a docs repo while the
reviewed code lives in sibling repos). The root used to store relative
paths is the filesystem common ancestor of the report and every reviewed
file, computed at issue time and recorded in the receipt itself — verify
never has to re-derive or be told where that root is.

Usage:
    receipt.py issue  <report_path>    # report.verdict must be APPROVED
    receipt.py verify <receipt_path>   # re-checks fingerprint against disk
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

POLICY_VERSION = "1.1.0"
BLOCKING_SEVERITIES = {"BLOCKER", "HIGH"}


class ReceiptError(Exception):
    """A receipt cannot be issued, or a required precondition failed."""


def _resolve_path(base: Path, raw: str) -> Path:
    candidate = Path(raw)
    candidate = candidate if candidate.is_absolute() else base / candidate
    return candidate.resolve()


def _compute_root(paths: list[Path]) -> Path | None:
    """Deepest common ancestor directory of every given path, or None if they
    share no filesystem root at all (e.g. different Windows drives).

    Raises if the only thing paths have in common is a filesystem root
    (e.g. `C:\\` or `/`) — that means reviewed_files almost certainly
    contains a stray, unrelated path rather than a legitimate polyrepo
    layout, and issuing a receipt over it would rubber-stamp the mistake.
    """
    try:
        common = Path(os.path.commonpath([str(p) for p in paths]))
    except ValueError:
        return None
    root = common if common.is_dir() else common.parent
    if root.parent == root:
        raise ReceiptError(
            f"report and reviewed_files share no meaningful common directory "
            f"(computed root is filesystem root {root}); check reviewed_files for a stray path"
        )
    return root


def _to_stored_path(root: Path | None, path: Path) -> str:
    if root is None:
        return str(path)
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path)


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


def _fingerprint(report_path: Path, labeled_reviewed: list[tuple[str, Path]]) -> str:
    """Hash the report bytes plus every reviewed file's exact current bytes.

    Callers must pass labeled_reviewed already sorted by label — both
    issue_receipt and verify_receipt do, since the receipt stores
    reviewed_files pre-sorted.
    """
    digest = hashlib.sha256()
    digest.update(report_path.read_bytes())
    for label, file_path in labeled_reviewed:
        digest.update(label.encode("utf-8"))
        digest.update(file_path.read_bytes())
    return f"sha256:{digest.hexdigest()}"


def issue_receipt(report_path: str | Path, repo_root: str | Path | None = None) -> dict[str, Any]:
    base = Path.cwd()
    resolved_report = _resolve_path(base, str(report_path))
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

    resolved_reviewed: list[Path] = []
    for rel in reviewed_files:
        path = _resolve_path(base, rel)
        if not path.is_file():
            raise ReceiptError(f"reviewed file missing: {rel}")
        resolved_reviewed.append(path)

    target = report.get("target")
    if not isinstance(target, str) or not target:
        raise ReceiptError("report.target must be a non-empty string")

    root = Path(repo_root).resolve() if repo_root else _compute_root([resolved_report, *resolved_reviewed])

    labeled_reviewed = sorted(
        ((_to_stored_path(root, p), p) for p in resolved_reviewed),
        key=lambda item: item[0],
    )
    fingerprint = _fingerprint(resolved_report, labeled_reviewed)
    receipt = {
        "target": target,
        "verdict": "APPROVED",
        "policy_version": POLICY_VERSION,
        "root": str(root) if root else None,
        "report_path": _to_stored_path(root, resolved_report),
        "reviewed_files": [label for label, _ in labeled_reviewed],
        "source_fingerprint": fingerprint,
        "reviewed_at": report.get("reviewed_at"),
        "open_blocking_findings": 0,
    }
    receipt_path = resolved_report.parent / f"{target}-receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    receipt["issued_path"] = str(receipt_path)
    return receipt


def verify_receipt(
    receipt_path: str | Path,
    repo_root: str | Path | None = None,
    expected_target: str | None = None,
) -> tuple[bool, list[str]]:
    resolved_receipt = _resolve_path(Path.cwd(), str(receipt_path))
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

    stored_root = receipt.get("root")
    if isinstance(stored_root, str) and stored_root:
        root: Path | None = Path(stored_root)
    elif repo_root is not None:
        root = Path(repo_root).resolve()
    else:
        root = None

    def _resolve_stored(label: str) -> Path:
        if root is None and not Path(label).is_absolute():
            raise ReceiptError(f"cannot resolve path without a known root: {label}")
        return _resolve_path(root if root is not None else Path.cwd(), label)

    try:
        report_path = _resolve_stored(report_rel)
        resolved_reviewed = [_resolve_stored(rel) for rel in reviewed_files]
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

    current_fingerprint = _fingerprint(report_path, list(zip(reviewed_files, resolved_reviewed)))
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
