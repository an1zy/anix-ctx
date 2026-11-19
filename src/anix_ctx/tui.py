"""
TUI module for anix-ctx.
Provides an interactive terminal user interface built with Textual in ANIX dark neon style.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pyperclip
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import Footer, Header, Static, Tree
from textual.widgets.tree import TreeNode

from anix_ctx.formatter import (
    build_ascii_tree,
    estimate_tokens,
    format_context,
    read_file_safe,
)
from anix_ctx.scanner import ScannedFile, scan_directory

TUI_CSS = """
Screen {
    background: #0d1117;
    color: #e6edf3;
}

Header {
    background: #161b22;
    color: #00e5ff;
    dock: top;
    height: 1;
}

Footer {
    background: #161b22;
    color: #8b949e;
    dock: bottom;
}

#main-container {
    layout: horizontal;
    height: 1fr;
    background: #0d1117;
}

#tree-pane {
    width: 52%;
    height: 100%;
    border-right: solid #30363d;
    padding: 0 1;
}

#info-pane {
    width: 48%;
    height: 100%;
    padding: 0 1;
}

Tree {
    background: #0d1117;
    color: #e6edf3;
    padding: 0;
    scrollbar-color: #00e5ff;
}

Tree:focus {
    border: none;
}

.panel-title {
    color: #00e5ff;
    text-style: bold;
    padding: 0 0 1 0;
}

.stats-card {
    background: #161b22;
    border: round #30363d;
    padding: 1;
    margin-bottom: 1;
}

.stat-row {
    margin-bottom: 0;
}

.stat-label {
    color: #8b949e;
}

.stat-value {
    color: #00e5ff;
    text-style: bold;
}

.stat-highlight {
    color: #58a6ff;
    text-style: bold;
}

#tree-preview {
    background: #161b22;
    border: round #30363d;
    padding: 1;
    height: 1fr;
    color: #8b949e;
    overflow-y: auto;
}
"""


def format_bytes(size: int) -> str:
    """Format file size into human-readable string."""
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


class AnixCtxApp(App[None]):
    """Main Textual application for interactive context packaging."""

    TITLE = "ANIX // CTX"
    SUB_TITLE = "Context Packager"
    CSS = TUI_CSS

    BINDINGS = [
        Binding("space", "toggle_node", "Toggle", priority=True),
        Binding("a", "toggle_all", "Select/Deselect All"),
        Binding("c", "copy_context", "Copy Clipboard"),
        Binding("s", "save_context", "Save context.md"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, target_dir: Path) -> None:
        super().__init__()
        self.target_dir = target_dir.resolve()
        self.scanned_files: list[ScannedFile] = []
        # Pre-cached character counts to avoid disk reads on every toggle
        self.char_cache: dict[Path, int] = {}
        # Selection state: mapping from ScannedFile to bool
        self.selection_map: dict[ScannedFile, bool] = {}
        # Mapping from Tree node ID to node data
        self.node_file_map: dict[int, ScannedFile] = {}

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main-container"):
            with Vertical(id="tree-pane"):
                yield Static("📁 PROJECT FILES", classes="panel-title")
                yield Tree(self.target_dir.name, id="file-tree")
            with Vertical(id="info-pane"):
                yield Static("⚡ LIVE STATS", classes="panel-title")
                with Vertical(classes="stats-card", id="stats-widget"):
                    yield Static("", id="stat-files")
                    yield Static("", id="stat-chars")
                    yield Static("", id="stat-tokens")
                    yield Static("", id="stat-top5")
                yield Static("🌳 ASCII TREE PREVIEW", classes="panel-title")
                yield VerticalScroll(Static("", id="preview-content"), id="tree-preview")
        yield Footer()

    def on_mount(self) -> None:
        """Scan directory, cache sizes, build tree, and compute initial stats."""
        self.scanned_files = scan_directory(self.target_dir)

        # Pre-cache characters for fast, zero-I/O live stat calculations
        for f in self.scanned_files:
            content = read_file_safe(f.path)
            self.char_cache[f.path] = len(content)
            self.selection_map[f] = True  # Selected by default

        self._populate_tree()
        self._refresh_stats()

    def _populate_tree(self) -> None:
        """Construct the hierarchical file tree with checkbox states."""
        tree: Tree[Any] = self.query_one("#file-tree", Tree)
        tree.root.expand()

        dir_nodes: dict[str, TreeNode[Any]] = {"": tree.root}

        for f in self.scanned_files:
            parts = f.rel_path.split("/")
            # Create directory nodes along the path
            curr_dir = ""
            for part in parts[:-1]:
                parent_dir = curr_dir
                curr_dir = f"{curr_dir}/{part}" if curr_dir else part
                if curr_dir not in dir_nodes:
                    parent_node = dir_nodes[parent_dir]
                    dir_nodes[curr_dir] = parent_node.add(
                        f"📁 [bold]{part}/[/]",
                        expand=True,
                        data={"type": "dir", "path": curr_dir},
                    )

            # Add file leaf
            file_name = parts[-1]
            parent_node = dir_nodes[curr_dir]
            is_selected = self.selection_map.get(f, True)
            chars = self.char_cache.get(f.path, f.size)

            checkbox = "[bold #00e5ff]\[x][/]" if is_selected else "[dim #8b949e]\[ ][/]"
            label = f"{checkbox} {file_name} [dim #8b949e]({format_bytes(f.size)} / ~{chars // 4} tok)[/]"

            leaf = parent_node.add_leaf(
                label,
                data={"type": "file", "file": f},
            )
            self.node_file_map[leaf.id] = f

        self._update_all_dir_labels(tree.root)

    def _update_file_label(self, node: TreeNode[Any], scanned_file: ScannedFile) -> None:
        """Update checkbox label for a single file node."""
        is_selected = self.selection_map.get(scanned_file, True)
        file_name = scanned_file.path.name
        chars = self.char_cache.get(scanned_file.path, scanned_file.size)

        checkbox = "[bold #00e5ff]\[x][/]" if is_selected else "[dim #8b949e]\[ ][/]"
        node.set_label(
            f"{checkbox} {file_name} [dim #8b949e]({format_bytes(scanned_file.size)} / ~{chars // 4} tok)[/]"
        )

    def _get_files_under_node(self, node: TreeNode[Any]) -> list[ScannedFile]:
        """Collect all ScannedFile instances under a tree branch."""
        files: list[ScannedFile] = []
        if node.data and node.data.get("type") == "file":
            files.append(node.data["file"])
        for child in node.children:
            files.extend(self._get_files_under_node(child))
        return files

    def _update_all_dir_labels(self, node: TreeNode[Any]) -> tuple[int, int]:
        """
        Recursively update directory labels with child selection ratios.
        Returns (selected_count, total_count).
        """
        if node.data and node.data.get("type") == "file":
            f = node.data["file"]
            is_sel = 1 if self.selection_map.get(f, False) else 0
            return is_sel, 1

        selected_sub = 0
        total_sub = 0

        for child in node.children:
            sel, tot = self._update_all_dir_labels(child)
            selected_sub += sel
            total_sub += tot

        if node != self.query_one("#file-tree", Tree).root and node.data and node.data.get("type") == "dir":
            dir_name = node.data["path"].split("/")[-1]
            if selected_sub == total_sub and total_sub > 0:
                box = "[bold #00e5ff]\[x][/]"
            elif selected_sub == 0:
                box = "[dim #8b949e]\[ ][/]"
            else:
                box = "[bold #00e5ff]\[-][/]"
            node.set_label(f"{box} 📁 [bold]{dir_name}/[/] [dim #8b949e]({selected_sub}/{total_sub})[/]")

        return selected_sub, total_sub

    def _refresh_stats(self) -> None:
        """Update the live statistics and ASCII tree preview using in-memory cache."""
        selected_files = [f for f, sel in self.selection_map.items() if sel]
        total_files = len(self.scanned_files)
        total_selected = len(selected_files)

        total_chars = sum(self.char_cache.get(f.path, 0) for f in selected_files)
        total_tokens = estimate_tokens(total_chars)

        # Update stats widgets
        self.query_one("#stat-files", Static).update(
            f"[#8b949e]Selected Files:[/] [bold #00e5ff]{total_selected}[/] / {total_files}"
        )
        self.query_one("#stat-chars", Static).update(
            f"[#8b949e]Total Characters:[/] [bold #58a6ff]{total_chars:,}[/]"
        )
        self.query_one("#stat-tokens", Static).update(
            f"[#8b949e]Estimated Tokens:[/] [bold #00e5ff]~{total_tokens:,}[/] [dim](chars // 4)[/]"
        )

        # Top 5 heaviest files
        file_weights = [(f.rel_path, self.char_cache.get(f.path, 0)) for f in selected_files]
        file_weights.sort(key=lambda x: x[1], reverse=True)
        top5 = file_weights[:5]

        if top5:
            top5_lines = ["[#8b949e]Top Heaviest Files:[/][dim]"]
            for path, chars in top5:
                top5_lines.append(f" • [white]{path}[/] (~{chars // 4:,} tok)")
            top5_lines.append("[/dim]")
            self.query_one("#stat-top5", Static).update("\n".join(top5_lines))
        else:
            self.query_one("#stat-top5", Static).update("[dim #8b949e]No files selected[/]")

        # ASCII tree preview
        rel_paths = [f.rel_path for f in selected_files]
        tree_text = build_ascii_tree(rel_paths, root_name=self.target_dir.name)
        self.query_one("#preview-content", Static).update(tree_text)

    def action_toggle_node(self) -> None:
        """Toggle checkbox of the currently highlighted node (file or directory)."""
        tree: Tree[Any] = self.query_one("#file-tree", Tree)
        node = tree.cursor_node
        if not node or not node.data:
            return

        node_data = node.data
        if node_data.get("type") == "file":
            f = node_data["file"]
            self.selection_map[f] = not self.selection_map.get(f, True)
            self._update_file_label(node, f)
        elif node_data.get("type") == "dir" or node == tree.root:
            sub_files = self._get_files_under_node(node)
            all_selected = all(self.selection_map.get(f, False) for f in sub_files)
            new_state = not all_selected
            for f in sub_files:
                self.selection_map[f] = new_state

            # Refresh labels of all descendants
            def _refresh_sub(n: TreeNode[Any]) -> None:
                if n.data and n.data.get("type") == "file":
                    self._update_file_label(n, n.data["file"])
                for ch in n.children:
                    _refresh_sub(ch)

            _refresh_sub(node)

        self._update_all_dir_labels(tree.root)
        self._refresh_stats()

    def on_tree_node_selected(self, event: Tree.NodeSelected[Any]) -> None:
        """Handle Enter key or click on tree node."""
        node = event.node
        if node.data and node.data.get("type") == "file":
            self.action_toggle_node()
        else:
            node.toggle()

    def action_toggle_all(self) -> None:
        """Toggle all files: select all if any deselected, otherwise deselect all."""
        tree: Tree[Any] = self.query_one("#file-tree", Tree)
        any_unselected = any(not sel for sel in self.selection_map.values())
        new_state = any_unselected

        for f in self.scanned_files:
            self.selection_map[f] = new_state

        def _refresh_all(node: TreeNode[Any]) -> None:
            if node.data and node.data.get("type") == "file":
                self._update_file_label(node, node.data["file"])
            for ch in node.children:
                _refresh_all(ch)

        _refresh_all(tree.root)
        self._update_all_dir_labels(tree.root)
        self._refresh_stats()

        msg = "All files selected" if new_state else "All files deselected"
        self.notify(msg, title="ANIX CTX")

    def action_copy_context(self) -> None:
        """Pack selected files and copy to clipboard."""
        selected_files = [f for f, sel in self.selection_map.items() if sel]
        if not selected_files:
            self.notify("No files selected to copy!", title="ANIX CTX", severity="warning")
            return

        formatted = format_context(selected_files, root_name=self.target_dir.name)
        try:
            pyperclip.copy(formatted)
            tokens = estimate_tokens(sum(self.char_cache.get(f.path, 0) for f in selected_files))
            self.notify(
                f"Copied {len(selected_files)} files (~{tokens:,} tokens) to clipboard!",
                title="ANIX CTX",
            )
        except Exception as exc:
            self.notify(f"Clipboard error: {exc}", title="ANIX CTX", severity="error")

    def action_save_context(self) -> None:
        """Pack selected files and save to context.md in target directory."""
        selected_files = [f for f, sel in self.selection_map.items() if sel]
        if not selected_files:
            self.notify("No files selected to save!", title="ANIX CTX", severity="warning")
            return

        out_path = self.target_dir / "context.md"
        formatted = format_context(selected_files, root_name=self.target_dir.name)
        try:
            with open(out_path, "w", encoding="utf-8", errors="replace") as f:
                f.write(formatted)
            tokens = estimate_tokens(sum(self.char_cache.get(f.path, 0) for f in selected_files))
            self.notify(
                f"Saved {len(selected_files)} files (~{tokens:,} tokens) to context.md",
                title="ANIX CTX",
            )
        except Exception as exc:
            self.notify(f"File save error: {exc}", title="ANIX CTX", severity="error")

