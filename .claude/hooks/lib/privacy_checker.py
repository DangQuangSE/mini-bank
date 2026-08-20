"""
Sensitive file detection for the privacy-block hook.

Usage:
    from privacy_checker import check_file, check_bash, load_allow_list

    match = check_file("/project/.env", allow_list=load_allow_list())
    if match:
        # block — match is the pattern that triggered, e.g. ".env"
        ...

    match = check_bash("cat secrets/db.key")
    if match:
        # block
        ...
"""
import fnmatch
import json
import os
import re
from pathlib import Path

SENSITIVE_FILENAME_PATTERNS: list[str] = [
    ".env",
    ".env.*",
    "*.key",
    "*.pem",
    "*.pfx",
    "*.p12",
    "*.keystore",
    "*.jks",
    "*credentials*",
    "*credential*",
    "*secrets*",
    "*secret*",
    "*password*",
    "*passwd*",
    "*.cert",
    "id_rsa",
    "id_ecdsa",
    "id_ed25519",
    "id_dsa",
]

SENSITIVE_PATH_PARTS: list[str] = [".ssh/", "secrets/", "credentials/", ".gnupg/"]

_BASH_RE = re.compile(
    r"(\.env\b|credentials|\.key\b|\.pem\b|secret[^s\w]|password|passwd|id_rsa)",
    re.IGNORECASE,
)


def load_allow_list(cwd: str | None = None) -> set[str]:
    """Load privacyBlock.allowList from .ck.json, lowercased."""
    try:
        root = _find_root(cwd)
        if not root:
            return set()
        ck = root / ".ck.json"
        if not ck.exists():
            return set()
        cfg = json.loads(ck.read_text(encoding="utf-8-sig"))
        return {p.lower() for p in cfg.get("privacyBlock", {}).get("allowList", [])}
    except Exception:
        return set()


def check_file(path_str: str, allow_list: set[str] | None = None) -> str | None:
    """Return matched pattern string if the file is sensitive, else None."""
    if not path_str:
        return None

    p = Path(path_str)
    name = p.name.lower()
    path_lower = str(p).lower().replace("\\", "/")

    if allow_list and (path_str.lower() in allow_list or name in allow_list):
        return None

    for pattern in SENSITIVE_FILENAME_PATTERNS:
        if fnmatch.fnmatch(name, pattern):
            return pattern

    for part in SENSITIVE_PATH_PARTS:
        if part in path_lower:
            return part

    return None


def check_bash(cmd: str, allow_list: set[str] | None = None) -> str | None:
    """Return match description if the Bash command touches sensitive files, else None."""
    if not cmd:
        return None
    m = _BASH_RE.search(cmd)
    if not m:
        return None
    matched = m.group(0)
    if allow_list and matched.lower() in allow_list:
        return None
    return matched


def _find_root(cwd: str | None = None) -> Path | None:
    start = Path(cwd or os.getcwd())
    for p in [start, *start.parents]:
        if (p / ".git").exists():
            return p
    return None
