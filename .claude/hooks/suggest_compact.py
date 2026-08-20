#!/usr/bin/env python3
"""
Strategic Compact Suggester — cross-platform Python replacement for suggest-compact.sh

Tracks tool call count per session and emits suggestions at thresholds
via stderr (shown to Claude as context).

Environment:
  CLAUDE_SESSION_ID   Session identifier (used to isolate counter per session)
  COMPACT_THRESHOLD   Tool call count at which to first suggest compact (default 50)
"""

import sys
import os
from pathlib import Path

session_id = os.environ.get("CLAUDE_SESSION_ID") or os.environ.get("PPID", "default")
threshold = int(os.environ.get("COMPACT_THRESHOLD", "50"))

tmp_dir = Path(os.environ.get("TEMP", os.environ.get("TMPDIR", "/tmp")))
counter_file = tmp_dir / f"claude-tool-count-{session_id}"

try:
    count = int(counter_file.read_text().strip()) + 1 if counter_file.exists() else 1
    counter_file.write_text(str(count))
except Exception:
    sys.exit(0)

if count == threshold:
    print(
        f"[StrategicCompact] {threshold} tool calls reached — consider /compact if transitioning phases",
        file=sys.stderr,
    )
elif count > threshold and count % 25 == 0:
    print(
        f"[StrategicCompact] {count} tool calls — good checkpoint for /compact if context is stale",
        file=sys.stderr,
    )
