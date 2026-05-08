# Fix typo: `documnts` → `documents`

**Priority:** Low  
**File:** `isabelle_lsp_client/handler.py:19, 29, 34`

## Problem

The field storing additional (non-primary) documents is misspelled:

```python
documnts: dict[str, Document]   # line 19
self.documnts = {}               # line 29
self.documnts[document.uri] = document  # line 34
```

The misspelling is not caught by mypy or ruff because the name is internally consistent. It will
confuse anyone reading the code or trying to access the field from outside the class.

## Fix

Rename all occurrences to `documents`:

```python
documents: dict[str, Document]
self.documents = {}
self.documents[document.uri] = document
```

Run a project-wide search for `documnts` to confirm no other files reference the field by the
misspelled name before committing.

## Notes

- This is a pure rename with no behaviour change.
- If `documents` is accessed externally (it currently is not), callers will need updating too.
