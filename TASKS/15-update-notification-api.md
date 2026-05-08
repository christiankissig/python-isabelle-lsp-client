# Switch `didOpen` and `didChange` from `send_request` to `send_notification`

**Priority:** High  
**Blocked on:** `python-lsp-client` task 01 (notifications not requests)  
**Files:** `isabelle_lsp_client/client.py`, `isabelle_lsp_client/document.py`

## Problem

`textDocument/didOpen` and `textDocument/didChange` are LSP notifications — they must not carry
an `id` field. Once `python-lsp-client` task 01 introduces `BaseNotification`,
`TextDocumentDidOpenNotification`, `TextDocumentDidChangeNotification`, and `send_notification()`,
this client must be updated to use them. Continuing to call `send_request()` for these messages
violates the LSP spec and may cause Isabelle's server to behave incorrectly.

## Current code

`client.py:85`:
```python
didopen_request = TextDocument_DidOpen_Request(
    params={"textDocument": text_document_item}
)
await self.lspClient.send_request(didopen_request)
```

`document.py:103–106`:
```python
request = TextDocument_DidChange_Request(
    uri=self.uri, version=str(self.version), contentChanges=changes
)
await self.isabelle.lspClient.send_request(request)
```

## Fix

`client.py` — replace import and call:
```python
from lsp_client import TextDocumentDidOpenNotification  # new name
...
notification = TextDocumentDidOpenNotification(
    params={"textDocument": text_document_item}
)
await self.lspClient.send_notification(notification)
```

`document.py` — replace import and call:
```python
from lsp_client import TextDocumentDidChangeNotification  # new name
...
notification = TextDocumentDidChangeNotification(
    uri=self.uri, version=str(self.version), contentChanges=changes
)
await self.isabelle.lspClient.send_notification(notification)
```

If `lsp-client` keeps the old names as deprecated aliases, the rename can be done in a single
commit that also switches `send_request` → `send_notification`.

## Notes

- `python-lsp-client` task 01 says deprecated aliases will be kept for the old names. Confirm
  this before deciding whether to rename immediately or just switch the send method.
- After this task, task 09 (`test_client.py`) can assert `send_notification` is called for
  `open_text_document`.
