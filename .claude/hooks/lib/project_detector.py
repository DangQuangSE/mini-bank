"""
Detect project type and package manager from the working directory.

Reads .ck.json for overrides where applicable. Falls back to file-system
heuristics (lock files, config markers, extensions).

Usage:
    from project_detector import detect_project_type, get_package_manager

    info = detect_project_type()
    # {"languages": ["typescript"], "primary": "typescript", "projectDir": "..."}

    pm = get_package_manager()
    # {"name": "pnpm", "source": "lock-file"}
"""
import json
import os
from pathlib import Path


_LANGUAGE_MARKERS: list[tuple[str, list[str], set[str]]] = [
    ("python",     ["requirements.txt", "pyproject.toml", "setup.py", "setup.cfg", "Pipfile"], {".py"}),
    ("typescript", ["tsconfig.json", "tsconfig.build.json"],                                   {".ts", ".tsx"}),
    ("javascript", ["package.json", "jsconfig.json"],                                          {".js", ".jsx", ".mjs"}),
    ("golang",     ["go.mod", "go.sum"],                                                       {".go"}),
    ("rust",       ["Cargo.toml"],                                                             {".rs"}),
    ("ruby",       ["Gemfile", "Rakefile"],                                                    {".rb"}),
    ("java",       ["pom.xml", "build.gradle"],                                                {".java"}),
    ("csharp",     [],                                                                         {".cs", ".csproj", ".sln"}),
    ("elixir",     ["mix.exs"],                                                                {".ex", ".exs"}),
    ("php",        ["composer.json"],                                                          {".php"}),
]

_LOCK_TO_PM = [
    ("pnpm-lock.yaml", "pnpm"),
    ("bun.lockb",      "bun"),
    ("yarn.lock",      "yarn"),
    ("package-lock.json", "npm"),
]


def detect_project_type(project_dir: Path | None = None) -> dict:
    """Return detected languages, frameworks, and primary language."""
    d = project_dir or Path(os.getcwd())
    try:
        entries = list(d.iterdir())
        root_files = {e.name for e in entries if e.is_file()}
        root_exts = {Path(n).suffix for n in root_files}
    except Exception:
        return {"languages": [], "frameworks": [], "primary": "unknown", "projectDir": str(d)}

    languages: list[str] = []
    for lang, markers, exts in _LANGUAGE_MARKERS:
        if any(m in root_files for m in markers) or bool(exts & root_exts):
            languages.append(lang)

    if "typescript" in languages and "javascript" in languages:
        languages.remove("javascript")

    return {
        "languages": languages,
        "frameworks": [],
        "primary": languages[0] if languages else "unknown",
        "projectDir": str(d),
    }


def get_package_manager(project_dir: Path | None = None) -> dict:
    """Return detected package manager and how it was discovered."""
    d = project_dir or Path(os.getcwd())

    env_pm = os.environ.get("CLAUDE_PACKAGE_MANAGER")
    if env_pm in ("npm", "pnpm", "yarn", "bun"):
        return {"name": env_pm, "source": "environment"}

    for lock, name in _LOCK_TO_PM:
        if (d / lock).exists():
            return {"name": name, "source": "lock-file"}

    global_cfg = Path(os.environ.get("HOME") or os.environ.get("USERPROFILE", "")) / ".claude" / "package-manager.json"
    if global_cfg.exists():
        try:
            cfg = json.loads(global_cfg.read_text(encoding="utf-8"))
            if cfg.get("packageManager") in ("npm", "pnpm", "yarn", "bun"):
                return {"name": cfg["packageManager"], "source": "global-config"}
        except Exception:
            pass

    return {"name": "npm", "source": "default"}
