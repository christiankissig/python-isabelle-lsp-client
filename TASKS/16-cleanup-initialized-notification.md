# Replace `_send_request` workaround with `InitializedNotification`

**Priority:** Medium  
**Blocked on:** `python-lsp-client` task 05 (fix exports)  
**File:** `isabelle_lsp_client/client.py:69`

## Problem

The `initialized` notification is currently sent via a private method and a raw dict:

```python
await self.lspClient._send_request(
    {"jsonrpc": "2.0", "method": "initialized", "params": {}}
)
```

This works but:
- Uses a private API (`_send_request`) that may change without notice.
- Bypasses any type checking or serialisation logic added to `send_notification` in future.
- The intent is obscured — a reader must know the LSP spec to understand why there is no `id`.

Once `python-lsp-client` task 05 exports `InitializedNotification` from the top-level package,
replace the raw dict call with the typed class.

## Fix

```python
from lsp_client import InitializedNotification
...
await self.lspClient.send_notification(InitializedNotification())
```

Remove the raw-dict call entirely.

## Notes

- Depends on `python-lsp-client` task 01 landing first, since that is where
  `BaseNotification` and `send_notification` are introduced. Task 05 just adds the export.
- After this change, task 09 (`test_client.py`) can assert
  `send_notification` is called with an `InitializedNotification` instance.
