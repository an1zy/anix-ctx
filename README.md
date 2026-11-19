# ANIX CTX

![python](https://img.shields.io/badge/python-3.10%2B-blue) ![license](https://img.shields.io/badge/license-MIT-green) [![PyPI](https://img.shields.io/pypi/v/anix-ctx)](https://pypi.org/project/anix-ctx/) ![status](https://img.shields.io/badge/status-active-success)

🇬🇧 English · 🇷🇺 [Русский](README.ru.md)

Interactive terminal context packager for LLMs. Select project files in a dark neon TUI, track estimated token usage in real time, and copy a Markdown document with an ASCII directory tree directly to the clipboard.

<p align="center">
  <img src="assets/demo.svg" alt="ANIX CTX Demo" width="900">
</p>

```
$ anix-ctx . --copy
[ANIX CTX] Copied 8 files (~8,690 tokens, 34,770 chars) to clipboard!
```

---

## Features

- **TUI File Selector:** Interactive tree navigation with keyboard toggles (`Space` on files or entire folders).
- **Gitignore & Filter Engine:** Automatically excludes `.git`, `node_modules`, `__pycache__`, virtual environments, lockfiles (`package-lock.json`, `poetry.lock`, `uv.lock`), minified assets, and custom `.gitignore` patterns.
- **Binary & Size Guards:** Drops binary files and skips files larger than 500 KB to prevent token waste.
- **In-Memory Cache:** File sizes and token estimations are cached on load; toggling files recomputes metrics without disk I/O.
- **Dynamic Markdown Fencing:** Adaptive backtick fencing prevents nested code blocks from breaking Markdown formatting.
- **Headless Mode:** CLI flags (`--copy`, `-o context.md`) for instant context generation in scripts and pipelines.
- **Safe Encoding:** Reads all text files with UTF-8 replacement to avoid decoding crashes on non-standard Windows encodings.

---

## Install

Requires Python 3.10+.

```bash
pip install anix-ctx
```

Or install in editable mode for local development:

```bash
git clone https://github.com/an1zy/anix-ctx.git
cd anix-ctx
pip install -e .
```

---

## Usage

### Interactive TUI

Launch the TUI in the current directory:

```bash
anix-ctx
```

Or specify a target folder:

```bash
anix-ctx /path/to/project
```

### Headless CLI Mode

Package files without launching the interface:

```bash
# Copy directly to system clipboard
anix-ctx --copy
anix-ctx -c

# Save context to a file
anix-ctx -o context.md

# Package a specific subdirectory into clipboard
anix-ctx src/ --copy
```

---

## Keybindings

| Key | Action |
| :--- | :--- |
| `Space` | Toggle selected state of current file or folder |
| `Enter` / Click | Expand or collapse folder / toggle file |
| `a` | Select all / Deselect all |
| `c` | Copy Markdown context to clipboard |
| `s` | Save context to `context.md` |
| `q` | Exit application |

---

## Output Format

The copied context contains an ASCII directory tree followed by fenced code blocks with detected language identifiers:

````markdown
# Project Context

## File Tree
````
anix-ctx
├── src/
│   └── anix_ctx/
│       ├── __init__.py
│       ├── cli.py
│       ├── formatter.py
│       ├── scanner.py
│       └── tui.py
├── .gitignore
├── LICENSE
├── pyproject.toml
└── README.md
````

## Files

### `pyproject.toml`
````toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
...
````

### `src/anix_ctx/cli.py`
````python
...
````
````

---

## Part of ANIX

- **[anixcode](https://github.com/an1zy/anixcode)** — terminal AI coding agent.
- **[anix-type](https://github.com/an1zy/anix-type)** — context-aware shell autocompletion daemon.
- **[anix-vault](https://github.com/an1zy/anix-vault)** — local secrets and environment manager.
- **[anix-snap](https://github.com/an1zy/anix-snap)** — terminal code screenshots.

---

## License

MIT License. Copyright (c) 2026 ANIX.
