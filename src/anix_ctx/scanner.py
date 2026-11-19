"""
Scanner module for anix-ctx.
Handles file discovery, .gitignore matching, ignore rules, and binary file filtering.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import pathspec

# Max file size: 500 KB to avoid wasting LLM context tokens
MAX_FILE_SIZE = 500 * 1024

# Default ignore patterns (directories, caches, lockfiles, minified assets)
DEFAULT_IGNORE_PATTERNS: list[str] = [
    # VCS & IDEs
    ".git",
    ".git/**",
    ".hg",
    ".svn",
    ".idea",
    ".vscode",
    # Build & Virtual Environments
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    ".env",
    "dist",
    "build",
    "out",
    "target",
    "*.egg-info",
    ".next",
    ".nuxt",
    ".cache",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    # Lockfiles & Minified Assets
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "uv.lock",
    "Cargo.lock",
    "composer.lock",
    "*.min.js",
    "*.min.css",
    "*.map",
    # Temporary & OS files
    ".DS_Store",
    "Thumbs.db",
    "desktop.ini",
]

# Common binary file extensions for fast short-circuit check
BINARY_EXTENSIONS: set[str] = {
    # Images
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp", ".bmp", ".tiff", ".psd", ".raw",
    # Binaries & Libraries
    ".exe", ".dll", ".so", ".dylib", ".bin", ".pyc", ".pyd", ".class", ".o", ".obj",
    # Archives & Compressed
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar", ".iso", ".dmg",
    # Documents & Media
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".mp3", ".mp4", ".wav", ".avi", ".mov", ".mkv", ".flac", ".ogg",
    # Fonts
    ".woff", ".woff2", ".ttf", ".otf", ".eot",
    # Databases
    ".sqlite", ".sqlite3", ".db",
}


@dataclass(frozen=True)
class ScannedFile:
    """Represents a discovered project file."""
    path: Path
    rel_path: str
    size: int
    is_text: bool = True

    def __lt__(self, other: ScannedFile) -> bool:
        return self.rel_path.lower() < other.rel_path.lower()


def is_binary_file(file_path: Path) -> bool:
    """
    Check if a file is binary using extension lookup and null-byte heuristic.
    """
    if file_path.suffix.lower() in BINARY_EXTENSIONS:
        return True

    try:
        with open(file_path, "rb") as f:
            chunk = f.read(1024)
            if b"\x00" in chunk:
                return True
    except (OSError, PermissionError):
        return True

    return False


def load_ignore_spec(root_path: Path, extra_patterns: Sequence[str] | None = None) -> pathspec.PathSpec:
    """
    Compile a PathSpec matcher from default patterns and local .gitignore/.ignore files.
    """
    patterns: list[str] = list(DEFAULT_IGNORE_PATTERNS)

    if extra_patterns:
        patterns.extend(extra_patterns)

    # Read .gitignore if present in root
    gitignore_path = root_path / ".gitignore"
    if gitignore_path.is_file():
        try:
            with open(gitignore_path, "r", encoding="utf-8", errors="replace") as f:
                patterns.extend(f.read().splitlines())
        except (OSError, PermissionError):
            pass

    # Read .ignore if present in root
    ignore_path = root_path / ".ignore"
    if ignore_path.is_file():
        try:
            with open(ignore_path, "r", encoding="utf-8", errors="replace") as f:
                patterns.extend(f.read().splitlines())
        except (OSError, PermissionError):
            pass

    return pathspec.PathSpec.from_lines("gitwildmatch", patterns)


def scan_directory(
    root_path: Path,
    extra_patterns: Sequence[str] | None = None,
    max_file_size: int = MAX_FILE_SIZE,
) -> list[ScannedFile]:
    """
    Scan the target directory recursively, filtering out ignored, binary,
    and oversized files. Early-prunes ignored directories for high performance.
    """
    root_path = root_path.resolve()
    if not root_path.exists() or not root_path.is_dir():
        return []

    spec = load_ignore_spec(root_path, extra_patterns=extra_patterns)
    scanned_files: list[ScannedFile] = []

    for dirpath, dirnames, filenames in os.walk(root_path, topdown=True):
        current_dir = Path(dirpath)
        rel_dir = current_dir.relative_to(root_path).as_posix()

        # Prune ignored directories in-place to skip descending into them
        pruned_dirs: list[str] = []
        for d in dirnames:
            rel_subdir = f"{rel_dir}/{d}" if rel_dir != "." else d
            # Match both as directory and generic pattern
            if spec.match_file(rel_subdir) or spec.match_file(f"{rel_subdir}/"):
                continue
            pruned_dirs.append(d)
        dirnames[:] = pruned_dirs

        # Process files in current directory
        for filename in filenames:
            file_path = current_dir / filename
            rel_file = f"{rel_dir}/{filename}" if rel_dir != "." else filename

            # Check ignore rules
            if spec.match_file(rel_file):
                continue

            try:
                stat = file_path.stat()
                file_size = stat.st_size
            except (OSError, PermissionError):
                continue

            # Skip oversized files
            if file_size > max_file_size:
                continue

            # Skip binary files
            if is_binary_file(file_path):
                continue

            scanned_files.append(
                ScannedFile(
                    path=file_path,
                    rel_path=rel_file,
                    size=file_size,
                    is_text=True,
                )
            )

    scanned_files.sort()
    return scanned_files
