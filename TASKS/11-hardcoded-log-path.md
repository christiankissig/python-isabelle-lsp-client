# Hardcoded Isabelle log path should be configurable

**Priority:** Low  
**File:** `isabelle_lsp_client/process.py:37`

## Problem

The path `/tmp/python-lsp-isa` is hardcoded as the `-L` argument to `isabelle vscode_server`:

```python
isabelle_args = [
    "vscode_server",
    "-o", "vscode_pide_extensions",
    "-v",
    "-L", "/tmp/python-lsp-isa",
    "-o", "vscode_html_output=false",
]
```

This causes problems in several situations:

- Multiple concurrent Isabelle processes (e.g. in parallel test runs or CI matrix jobs) will
  write to the same log file and corrupt or overwrite each other's output.
- The `/tmp` directory may not be writable or appropriate on all platforms (e.g. some container
  environments, macOS with strict sandboxing).
- Users have no way to redirect the log to a more visible location during debugging without
  modifying the library source.

## Fix

Accept a log path via `args` in `run()`, with a sensible default:

```python
log_path = args.get("log_path", "/tmp/python-lsp-isa")
isabelle_args = [
    "vscode_server",
    "-o", "vscode_pide_extensions",
    "-v",
    "-L", log_path,
    "-o", "vscode_html_output=false",
]
```

Alternatively, accept it in the `IsabelleProcess` constructor so it can be set once per process
instance rather than per `run()` call.

For CI or test scenarios, consider generating a unique path automatically when no path is given:

```python
import tempfile
log_path = args.get("log_path") or tempfile.mktemp(prefix="isabelle-lsp-")
```

## Notes

- The `-v` (verbose) flag also contributes to log volume. Consider whether it should be
  configurable too, or whether it should only be enabled when a log path is explicitly provided.
