# Bug: `auto_sledge.py` callback missing `timestamp` parameter

**Priority:** High  
**File:** `isabelle_lsp_client/examples/auto_sledge.py:34`

## Problem

All callbacks registered with `ClientHandler` are called with three positional arguments:

```python
await callback(self.document, response, timestamp)  # handler.py:93
```

The `on_update_dynamic_output` function in `auto_sledge.py` only declares two:

```python
async def on_update_dynamic_output(document: Document, response: dict) -> None:
```

This will raise `TypeError: on_update_dynamic_output() takes 2 positional arguments but 3 were
given` the first time a `PIDE/dynamic_output` notification arrives — i.e. as soon as Isabelle
elaborates any proof. The script silently fails at the point it is most needed.

The same issue would affect any user who copies the example as a template for their own callbacks.

## Fix

Add `timestamp: int` as the third parameter to match the contract expected by `ClientHandler`:

```python
async def on_update_dynamic_output(
    document: Document, response: dict, timestamp: int
) -> None:
```

The `on_start` callback is called as `await callback(self.document)` (one argument), so it is
correct and does not need changing.

## Notes

- The callback contract (`(document, response, timestamp)`) is not documented anywhere. Consider
  adding a type alias or protocol class to `handler.py` so that the expected signature is
  machine-checkable by mypy.
