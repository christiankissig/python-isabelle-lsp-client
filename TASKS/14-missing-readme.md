# Missing README and installation instructions

**Priority:** Low  
**File:** `README.rst` (does not exist), `pyproject.toml:8`

## Problem

`pyproject.toml` declares `readme = "README.rst"` but the file does not exist in the repository.
Any attempt to build or publish the package with Poetry will fail. PyPI (if the package is ever
published) would show no description.

More importantly, there is no user-facing document explaining:

1. What the library does and what Isabelle version it supports.
2. The non-obvious installation prerequisite: `lsp_client` is not on PyPI and must be installed
   from GitHub manually before `poetry install` will succeed.
3. The requirement for the `isabelle-emacs` fork (not upstream Isabelle) and the
   `vscode_html_output=false` option dependency.
4. The `ISABELLE_EXEC` environment variable expected by the example.
5. A minimal usage example showing how to subclass or compose `ClientHandler` and
   `IsabelleProcess` for a custom script.

## Fix

Create `README.rst` (or switch to `README.md` and update `pyproject.toml`) with at minimum:

- **What it is** — one paragraph.
- **Prerequisites** — Python version, `isabelle-emacs` fork link, `lsp_client` install command.
- **Installation** — `pip install git+...` for `lsp_client`, then `poetry install`.
- **Quick start** — minimal working example (can reference `auto_sledge.py`).
- **Environment variables** — `ISABELLE_EXEC`.
- **Supported Isabelle versions** — 2023 and 2024 (as noted in CLAUDE.md).

## Notes

- If Markdown is preferred over reStructuredText, change `pyproject.toml`:
  ```toml
  readme = "README.md"
  ```
- The `lsp_client` package being absent from PyPI is the single highest friction point for new
  users. The README should address this in the very first installation step.
