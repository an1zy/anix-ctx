"""
CLI entry point for anix-ctx.
Handles command line arguments, headless packaging (--copy, -o), and TUI launching.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pyperclip

from anix_ctx import __version__
from anix_ctx.formatter import calculate_stats, format_context
from anix_ctx.scanner import scan_directory


def create_parser() -> argparse.ArgumentParser:
    """Create command line arguments parser."""
    parser = argparse.ArgumentParser(
        prog="anix-ctx",
        description="Interactive context packager for LLMs with dark neon TUI (ANIX ecosystem).",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Path to project directory (default: current directory).",
    )
    parser.add_argument(
        "-c",
        "--copy",
        action="store_true",
        help="Headless mode: pack project context and copy directly to clipboard without opening TUI.",
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="FILE",
        help="Headless mode: pack project context and save directly to file without opening TUI.",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show program version and exit.",
    )
    return parser


def run_headless(target_dir: Path, copy_to_clipboard: bool, output_file: str | None) -> int:
    """Run non-interactive context generation and copy or write output."""
    files = scan_directory(target_dir)
    if not files:
        print(f"⚡ [ANIX CTX] No matching files found in: {target_dir}", file=sys.stderr)
        return 1

    stats = calculate_stats(files)
    formatted = format_context(files, root_name=target_dir.name)

    if copy_to_clipboard:
        try:
            pyperclip.copy(formatted)
            print(
                f"⚡ [ANIX CTX] Copied {stats.file_count} files "
                f"(~{stats.approx_tokens:,} tokens, {stats.char_count:,} chars) to clipboard!"
            )
        except Exception as exc:
            print(f"⚡ [ANIX CTX] Clipboard error: {exc}", file=sys.stderr)
            return 1

    if output_file:
        out_path = Path(output_file).resolve()
        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w", encoding="utf-8", errors="replace") as f:
                f.write(formatted)
            print(
                f"⚡ [ANIX CTX] Saved {stats.file_count} files "
                f"(~{stats.approx_tokens:,} tokens) to: {out_path.name}"
            )
        except Exception as exc:
            print(f"⚡ [ANIX CTX] File write error: {exc}", file=sys.stderr)
            return 1

    return 0


def main() -> None:
    """Main CLI entry point."""
    parser = create_parser()
    args = parser.parse_args()

    target_dir = Path(args.path).resolve()
    if not target_dir.exists():
        print(f"⚡ [ANIX CTX] Error: Directory does not exist: {target_dir}", file=sys.stderr)
        sys.exit(1)

    if not target_dir.is_dir():
        print(f"⚡ [ANIX CTX] Error: Path is not a directory: {target_dir}", file=sys.stderr)
        sys.exit(1)

    # Check for headless execution
    if args.copy or args.output:
        code = run_headless(target_dir, copy_to_clipboard=args.copy, output_file=args.output)
        sys.exit(code)

    # Interactive TUI mode
    from anix_ctx.tui import AnixCtxApp

    app = AnixCtxApp(target_dir)
    app.run()


if __name__ == "__main__":
    main()
