"""
Structured diagnostics logger for Claude Code hooks.

Usage:
    log = HookLogger("session-init")
    log.info("Session state loaded")
    log.warn("No .ck.json found — using defaults")
    log.perf()   # prints "[session-init] done (12ms)"

    clean = strip_ansi(raw_text)
"""
import re
import sys
import time

_ANSI_RE = re.compile(
    r"\x1b(?:\[[0-9;?]*[A-Za-z]|\][^\x07\x1b]*(?:\x07|\x1b\\)|\([A-Z]|[A-Z])"
)


def strip_ansi(s: str) -> str:
    """Remove ANSI escape sequences from a string."""
    return _ANSI_RE.sub("", s) if isinstance(s, str) else ""


class HookLogger:
    """Structured logger that writes to stderr with hook name prefix and timing."""

    def __init__(self, name: str):
        self.name = name
        self._t0 = time.perf_counter()

    def info(self, msg: str) -> None:
        print(f"[{self.name}] {msg}", file=sys.stderr, flush=True)

    def warn(self, msg: str) -> None:
        print(f"[{self.name}] WARN  {msg}", file=sys.stderr, flush=True)

    def error(self, msg: str) -> None:
        print(f"[{self.name}] ERROR {msg}", file=sys.stderr, flush=True)

    def perf(self, label: str = "done") -> None:
        ms = (time.perf_counter() - self._t0) * 1000
        print(f"[{self.name}] {label} ({ms:.0f}ms)", file=sys.stderr, flush=True)

    def __call__(self, msg: str) -> None:
        """Drop-in replacement for utils.log()."""
        self.info(msg)
