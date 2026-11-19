"""
Formatter module for anix-ctx.
Builds ASCII directory trees, estimates tokens, handles dynamic Markdown fences,
and formats the final LLM prompt context.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from anix_ctx.scanner import ScannedFile

# Extension to Markdown syntax highlighting identifier
LANGUAGE_MAP: dict[str, str] = {
    # Python
    ".py": "python",
    ".pyw": "python",
    ".pyi": "python",
    # Web / JS / TS
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "jsx",
    ".ts": "typescript",
    ".mts": "typescript",
    ".cts": "typescript",
    ".tsx": "tsx",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "scss",
    ".sass": "sass",
    ".less": "less",
    ".vue": "vue",
    ".svelte": "svelte",
    # Systems & Compiled
    ".rs": "rust",
    ".go": "go",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".hh": "cpp",
    ".cs": "csharp",
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".swift": "swift",
    ".dart": "dart",
    # Scripting & Shell
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "bash",
    ".ps1": "powershell",
    ".psm1": "powershell",
    ".bat": "bat",
    ".cmd": "cmd",
    ".rb": "ruby",
    ".php": "php",
    ".lua": "lua",
    # Config & Data
    ".json": "json",
    ".json5": "json5",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".ini": "ini",
    ".cfg": "ini",
    ".env": "ini",
    ".xml": "xml",
    ".sql": "sql",
    ".graphql": "graphql",
    ".gql": "graphql",
    # Markup & Docs
    ".md": "markdown",
    ".markdown": "markdown",
    ".rst": "rst",
    ".tex": "latex",
    ".txt": "text",
}

# Special filename mappings
FILENAME_LANGUAGE_MAP: dict[str, str] = {
    "dockerfile": "dockerfile",
    "containerfile": "dockerfile",
    "makefile": "makefile",
    "gemfile": "ruby",
    "rakefile": "ruby",
    ".gitignore": "gitignore",
    ".ignore": "gitignore",
    ".dockerignore": "dockerignore",
    "cmakelists.txt": "cmake",
}


@dataclass
class ContextStats:
    """Statistics for the selected context files."""
    file_count: int
    char_count: int
    approx_tokens: int
    top_files: list[tuple[str, int]]  # (rel_path, char_count)


class TreeNode:
    """Node representing a directory or file in the ASCII tree."""

    def __init__(self, name: str, is_dir: bool = False):
        self.name = name
        self.is_dir = is_dir
        self.children: dict[str, TreeNode] = {}


def get_language(path: Path) -> str:
    """Detect language identifier for Markdown code block."""
    lower_name = path.name.lower()
    if lower_name in FILENAME_LANGUAGE_MAP:
        return FILENAME_LANGUAGE_MAP[lower_name]
    return LANGUAGE_MAP.get(path.suffix.lower(), "")


def get_dynamic_fence(content: str) -> str:
    """
    Generate a dynamic backtick fence to prevent nested code blocks
    from breaking the Markdown output. Minimum 4 backticks.
    """
    count = 4
    while ("`" * count) in content:
        count += 1
    return "`" * count


def read_file_safe(path: Path) -> str:
    """
    Safely read text file contents with UTF-8 encoding and character replacement.
    """
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception as exc:
        return f"[Error reading file: {exc}]"


def estimate_tokens(char_count: int) -> int:
    """Estimate token count from character count (approx 4 chars per token)."""
    return char_count // 4


def build_ascii_tree(rel_paths: Sequence[str], root_name: str = ".") -> str:
    """
    Build a clean ASCII hierarchy tree for the given relative paths.
    """
    if not rel_paths:
        return f"{root_name}\n(no files selected)"

    root = TreeNode(root_name, is_dir=True)

    for rel_path in sorted(rel_paths):
        parts = [p for p in Path(rel_path).as_posix().split("/") if p and p != "."]
        curr = root
        for i, part in enumerate(parts):
            is_file = (i == len(parts) - 1)
            if part not in curr.children:
                curr.children[part] = TreeNode(part, is_dir=not is_file)
            curr = curr.children[part]

    lines: list[str] = [root.name]

    def _render(node: TreeNode, prefix: str = "") -> None:
        # Directories first, then alphabetical by name
        sorted_keys = sorted(
            node.children.keys(),
            key=lambda k: (not node.children[k].is_dir, k.lower()),
        )
        for i, key in enumerate(sorted_keys):
            child = node.children[key]
            is_last = (i == len(sorted_keys) - 1)
            connector = "└── " if is_last else "├── "
            display_name = f"{child.name}/" if child.is_dir else child.name
            lines.append(f"{prefix}{connector}{display_name}")

            next_prefix = prefix + ("    " if is_last else "│   ")
            _render(child, next_prefix)

    _render(root)
    return "\n".join(lines)


def calculate_stats(files: Sequence[ScannedFile]) -> ContextStats:
    """
    Calculate file count, total characters, estimated tokens, and top-5 heaviest files.
    """
    total_chars = 0
    file_weights: list[tuple[str, int]] = []

    for f in files:
        content = read_file_safe(f.path)
        c_len = len(content)
        total_chars += c_len
        file_weights.append((f.rel_path, c_len))

    file_weights.sort(key=lambda item: item[1], reverse=True)
    top_5 = file_weights[:5]

    return ContextStats(
        file_count=len(files),
        char_count=total_chars,
        approx_tokens=estimate_tokens(total_chars),
        top_files=top_5,
    )


def format_context(files: Sequence[ScannedFile], root_name: str = ".") -> str:
    """
    Format selected files into an LLM-ready Markdown string with ASCII tree and safe code blocks.
    """
    if not files:
        return "# Project Context\n\n*(No files selected)*\n"

    rel_paths = [f.rel_path for f in files]
    tree_text = build_ascii_tree(rel_paths, root_name=root_name)
    tree_fence = get_dynamic_fence(tree_text)

    sections: list[str] = [
        "# Project Context",
        "",
        "## File Tree",
        f"{tree_fence}",
        tree_text,
        f"{tree_fence}",
        "",
        "## Files",
    ]

    for f in sorted(files, key=lambda x: x.rel_path.lower()):
        content = read_file_safe(f.path)
        lang = get_language(f.path)
        fence = get_dynamic_fence(content)

        sections.append("")
        sections.append(f"### `{f.rel_path}`")
        sections.append(f"{fence}{lang}")
        sections.append(content)
        sections.append(f"{fence}")

    sections.append("")
    return "\n".join(sections)
