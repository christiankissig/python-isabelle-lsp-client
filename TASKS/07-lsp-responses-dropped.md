# LSP server responses are silently dropped

**Priority:** Medium  
**File:** `isabelle_lsp_client/handler.py:67-95`

## Problem

The LSP protocol has two kinds of server-to-client messages:

1. **Notifications** — no `"id"`, always have `"method"`.
2. **Responses** — have `"id"`, no `"method"`, carry `"result"` or `"error"`.

`ClientHandler.handle()` checks for `"method"` and logs a warning when it is absent:

```python
if "method" in response:
    method = response["method"]
else:
    logger.warn(f"Unhandled response: {response}")
    return
```

Every response the server sends to a client request (e.g. the result of `initialize`,
`textDocument/didOpen`, `PIDE/caret_update`) hits this branch and is dropped. This means:

- The `initialize` response (which carries server capabilities) is never inspected.
- Any error returned by the server for a malformed request is silently discarded.
- If `LSPClient` relies on `handle()` to correlate request IDs, responses are lost.

## Investigation result

`LSPClient._handle_response` unconditionally calls `self.response_handler(response)` — it passes
every message (notifications and responses alike) straight through without filtering. The handler
therefore receives server responses to `initialize`, `textDocument/didOpen`, `PIDE/caret_update`,
etc., and currently drops all of them with a misleading warning.

The handler needs a response dispatch path:

```python
if "method" in response:
    # notification path (existing)
    ...
elif "id" in response:
    # response path (new)
    if "error" in response:
        logger.error(f"Server returned error for id={response['id']}: {response['error']}")
    else:
        logger.debug(f"Server response for id={response['id']}: {response.get('result')}")
else:
    logger.warn(f"Unrecognised message shape: {response}")
```

## Notes

- Isabelle's `initialize` response may contain server-side capability information that could be
  useful (e.g. supported PIDE extensions). Logging it at DEBUG level would at minimum aid
  diagnostics.
