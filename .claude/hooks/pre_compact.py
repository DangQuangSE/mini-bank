#!/usr/bin/env python3
"""
PreCompact Hook — save state before context compaction.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from ck_config_utils import get_sessions_dir, load_ck_config
from hook_logger import HookLogger
from session_utils import append_file, ensure_dir, find_files, get_datetime_string, get_time_string



def purge_outdated(sessions_dir: Path, compact_day: int) -> None:
    """Remove all session files older than compact_day days."""
    now = __import__("time").time()
    cutoff = compact_day * 86400
    removed = 0
    try:
        for entry in sessions_dir.iterdir():
            if not entry.is_file():
                continue
            try:
                age = now - entry.stat().st_mtime
            except OSError:
                continue
            if age > cutoff:
                entry.unlink(missing_ok=True)
                removed += 1
    except Exception:
        pass
    if removed:
        log.info(f"Purged {removed} session file(s) older than {compact_day}d")


def main() -> None:
    log = HookLogger("pre-compact")
    sessions_dir = get_sessions_dir()
    ensure_dir(sessions_dir)

    config = load_ck_config()
    compact_day: int = int(config.get("compactDay", 3))

    timestamp = get_datetime_string()
    append_file(sessions_dir / "compaction-log.txt", f"[{timestamp}] Context compaction triggered\n")

    purge_outdated(sessions_dir, compact_day)

    active = find_files(sessions_dir, "*-session.tmp")
    if active:
        time_str = get_time_string()
        append_file(
            active[0]["path"],
            f"\n---\n**[Compaction occurred at {time_str}]** - Context was summarized\n",
        )

    log.info("State saved before compaction")

    # Reset caveman state so threshold recalculates from 0 after /compact
    import os, tempfile
    session_id = os.environ.get("CLAUDE_SESSION_ID")
    if session_id:
        caveman_state = sessions_dir / f"caveman-{session_id}.json"
        if caveman_state.exists():
            caveman_state.write_text('{"active": false}', encoding="utf-8")
        tmp_dir = Path(os.environ.get("TEMP", os.environ.get("TMPDIR", tempfile.gettempdir())))
        counter = tmp_dir / f"claude-tool-count-{session_id}"
        if counter.exists():
            counter.write_text("0", encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        HookLogger("pre-compact").error(str(e))
        sys.exit(1)
