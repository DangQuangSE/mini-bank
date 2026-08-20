"""
Count installed hooks, skills, and agents in a .claude/ directory.

Usage:
    from config_counter import get_summary

    summary = get_summary(Path(".claude"))
    # {"hooks": 8, "skills": 5, "agents": 3}
"""
import json
from pathlib import Path


def count_hooks(settings_path: Path) -> int:
    """Count total hook entries registered in settings.json."""
    if not settings_path.exists():
        return 0
    try:
        cfg = json.loads(settings_path.read_text(encoding="utf-8-sig"))
        hooks_map = cfg.get("hooks", {})
        total = 0
        for event_entries in hooks_map.values():
            for matcher_block in event_entries:
                total += len(matcher_block.get("hooks", []))
        return total
    except Exception:
        return 0


def count_skills(claude_dir: Path) -> int:
    """Count skill directories under .claude/skills/."""
    skills_dir = claude_dir / "skills"
    if not skills_dir.exists():
        return 0
    return sum(1 for p in skills_dir.iterdir() if p.is_dir() and not p.name.startswith("."))


def count_agents(claude_dir: Path) -> int:
    """Count agent .md files under .claude/agents/."""
    agents_dir = claude_dir / "agents"
    if not agents_dir.exists():
        return 0
    return sum(1 for p in agents_dir.iterdir() if p.is_file() and p.suffix == ".md")


def get_summary(claude_dir: Path) -> dict:
    """Return {hooks, skills, agents} counts for a .claude/ directory."""
    return {
        "hooks": count_hooks(claude_dir / "settings.json"),
        "skills": count_skills(claude_dir),
        "agents": count_agents(claude_dir),
    }
