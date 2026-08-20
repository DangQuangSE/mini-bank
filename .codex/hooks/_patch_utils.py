#!/usr/bin/env python3
"""
Shared helper for Codex apply_patch hooks.

Claude Code's Write tool gives hooks a clean (file_path, content) pair.
Codex's apply_patch tool instead gives hooks a single `command` string
containing the raw V4A patch text, e.g.:

    *** Begin Patch
    *** Add File: projects/foo/team/ba/requirements.md
    +# Requirements
    +...
    *** Update File: projects/foo/team/ba/notes.md
    @@
    -old line
    +new line
    *** End Patch

A single apply_patch call can touch multiple files in one patch, so every
hook that used to assume "one Write = one file" must instead iterate over
all file ops contained in the patch.

For "Add File" sections the full new content is recoverable (every body
line is prefixed with `+`). For "Update File" sections only the *added*
lines are recoverable from the diff hunks — there is no original-file
content available to a PreToolUse hook, since the patch has not been
applied yet. Heading/credential checks below are run against this
best-effort content, which is sufficient for the common case in this repo
(agents create brand-new artifact files rather than editing existing ones).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_FILE_HEADER_RE = re.compile(
    r"^\*\*\* (Add File|Update File|Delete File): (.+?)\s*$"
)


@dataclass
class FileOp:
    action: str   # "add" | "update" | "delete"
    path: str     # repo-relative (or absolute) path as written in the patch
    content: str  # best-effort new content ("" for delete)


def parse_apply_patch(command: str) -> list[FileOp]:
    """Split an apply_patch `command` string into per-file operations."""
    if not command or "*** " not in command:
        return []

    lines = command.splitlines()
    ops: list[FileOp] = []

    current_action = None
    current_path = None
    body: list[str] = []

    def flush():
        if current_path is None:
            return
        if current_action in ("add", "update"):
            content = "\n".join(l[1:] for l in body if l.startswith("+"))
        else:
            content = ""
        ops.append(FileOp(action=current_action, path=current_path, content=content))

    for line in lines:
        m = _FILE_HEADER_RE.match(line)
        if m:
            flush()
            kind, path = m.groups()
            current_action = {"Add File": "add", "Update File": "update", "Delete File": "delete"}[kind]
            current_path = path.strip()
            body = []
            continue
        if line.strip() in ("*** Begin Patch", "*** End Patch"):
            continue
        if current_path is not None:
            body.append(line)

    flush()
    return ops


def all_paths(command: str) -> list[str]:
    """Convenience: just the file paths touched by this patch."""
    return [op.path for op in parse_apply_patch(command)]
