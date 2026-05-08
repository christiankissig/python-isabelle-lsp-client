# Bug: `Document.__init__` text branch skips attribute initialization

**Priority:** High  
**File:** `isabelle_lsp_client/document.py:17-41`

## Problem

The `Document` constructor has two branches. When `text` is provided, the branch returns early
after splitting the text into lines, and never initialises the following attributes:

- `self.isabelle`
- `self.uri`
- `self.output_suffix`
- `self.file_path`
- `self.version`
- `self.caret_position`

Any subsequent call to `open_file()`, `write_file()`, `apply_changes()`, `move_caret()`,
`isabelle_apply_changes()`, or `find_next()` will raise `AttributeError`.

The `text` parameter was likely introduced to support constructing a `Document` from an in-memory
string (e.g. in tests), but the implementation was never completed.

## Current code

```python
def __init__(self, isabelle, uri, text=None, output_suffix=""):
    if text:
        self.lines = text.split("\n")
    else:
        self.isabelle = isabelle
        self.uri = uri
        self.output_suffix = output_suffix
        if uri.startswith("file://"):
            self.file_path = uri[len("file://"):]
        else:
            raise ValueError("Invalid URI scheme: " + uri)
        self.lines = []
        self.version = 1
        self.caret_position = (0, 0)
```

## Fix

Move all attribute assignments before the `if text:` branch. When text is provided, skip
`read_file()` (the file-read step) rather than skipping attribute setup. The `uri` and `isabelle`
arguments should remain required; the text branch should only short-circuit the file read.

```python
def __init__(self, isabelle, uri, text=None, output_suffix=""):
    self.isabelle = isabelle
    self.uri = uri
    self.output_suffix = output_suffix
    if uri.startswith("file://"):
        self.file_path = uri[len("file://"):]
    else:
        raise ValueError("Invalid URI scheme: " + uri)
    self.version = 1
    self.caret_position = (0, 0)

    if text is not None:
        self.lines = text.split("\n")
    else:
        self.lines = []
```

## Tests to add

- Construct `Document` with `text=` and assert all attributes are accessible.
- Call `move_caret` and `find_next` on a text-constructed document without error.
