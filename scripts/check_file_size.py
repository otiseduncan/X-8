from __future__ import annotations

import argparse
from pathlib import Path

IGNORED_DIRS = {
    ".git",
    ".pytest_cache",
    "node_modules",
    "dist",
    "build",
    "coverage",
    "playwright-report",
    "test-results",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    "runtime",
}
GENERATED_SUFFIXES = {".lock", ".png", ".jpg", ".jpeg", ".gif", ".mp4", ".zip"}
DOC_DIRS = {"docs", "knowledge"}
NORMAL_HARD_MAX = 1000
DOC_HARD_MAX = 1500
WARN_AT = 500


def is_ignored(path: Path) -> bool:
    return any(part in IGNORED_DIRS for part in path.parts) or path.suffix in GENERATED_SUFFIXES


def line_count(path: Path) -> int:
    try:
        return len(path.read_text(encoding="utf-8").splitlines())
    except UnicodeDecodeError:
        return 0


def limit_for(path: Path) -> int:
    return DOC_HARD_MAX if path.parts and path.parts[0] in DOC_DIRS else NORMAL_HARD_MAX


def scan(root: Path) -> int:
    failures: list[str] = []
    warnings: list[str] = []
    for path in root.rglob("*"):
        rel = path.relative_to(root)
        if not path.is_file() or is_ignored(rel):
            continue
        count = line_count(path)
        if count == 0:
            continue
        limit = limit_for(rel)
        if count > limit:
            failures.append(f"{rel}: {count} lines exceeds hard max {limit}")
        elif count > WARN_AT:
            warnings.append(f"{rel}: {count} lines exceeds preferred warning {WARN_AT}")
    for warning in warnings:
        print(f"warning: {warning}")
    for failure in failures:
        print(f"error: {failure}")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args()
    return scan(Path(args.root).resolve())


if __name__ == "__main__":
    raise SystemExit(main())
