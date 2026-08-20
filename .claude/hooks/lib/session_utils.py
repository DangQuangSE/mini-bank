"""
File system and time utilities shared across session-related hooks.

Usage:
    from session_utils import (
        ensure_dir, find_files, append_file,
        get_time_string, get_datetime_string,
    )
"""
import fnmatch
import os
from datetime import datetime
from pathlib import Path


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_time_string() -> str:
    return datetime.now().strftime("%H:%M")


def get_datetime_string() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def find_files(
    dir_path: Path,
    pattern: str,
    max_age_days: float | None = None,
) -> list[dict]:
    """Return [{path: Path, mtime: float}] sorted newest first."""
    results = []
    try:
        for entry in dir_path.iterdir():
            if not entry.is_file() or not fnmatch.fnmatch(entry.name, pattern):
                continue
            try:
                mtime = entry.stat().st_mtime
            except OSError:
                continue
            if max_age_days is not None:
                age = (datetime.now().timestamp() - mtime) / 86400
                if age > max_age_days:
                    continue
            results.append({"path": entry, "mtime": mtime})
    except Exception:
        pass
    results.sort(key=lambda x: x["mtime"], reverse=True)
    return results


def append_file(path: Path, content: str) -> None:
    ensure_dir(path.parent)
    with open(path, "a", encoding="utf-8") as f:
        f.write(content)
