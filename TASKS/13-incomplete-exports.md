# Incomplete `__init__.py` exports

**Priority:** Low  
**File:** `isabelle_lsp_client/__init__.py`

## Problem

Two public utility functions from `isabelle.py` are not exported from the package's top-level
`__init__.py`:

- `is_isabelle_ready` — used internally in `process.py`; useful to consumers who want to detect
  the ready state from their own log-message callbacks.
- `get_command_from_document` — parses a tactic command from a document at a given position;
  directly useful for any script that inspects proof structure.

Because they are not in `__all__`, users who do `from isabelle_lsp_client import ...` cannot
discover or import them without knowing to import from the submodule directly.

## Fix

Add both to `__init__.py`:

```python
from isabelle_lsp_client.isabelle import (
    command_finishes_subgoal,
    get_command_from_document,       # add
    get_command_from_sledgehammer,
    is_isabelle_ready,               # add
    is_sledgehammer_done,
    is_sledgehammer_noproof,
)
```

And extend `__all__`:

```python
__all__ = [
    ...
    "get_command_from_document",
    "is_isabelle_ready",
    ...
]
```

## Notes

- Review `protocol.py` exports too: `CaretUpdateRequest` and `ProgressRequest` are not exported.
  They are only needed for advanced users building custom request types, but if the library is
  meant to be extended, they should be accessible.
