# Remove or consolidate dead methods in `ClientHandler`

**Priority:** Medium  
**File:** `isabelle_lsp_client/handler.py:97-122`

## Problem

`ClientHandler` has three methods that duplicate logic already present in `handle()` and are never
called anywhere in the codebase:

- `on_decoration(response)` — mirrors the `PIDE/decoration` branch in `handle()`
- `on_dynamic_output(response)` — mirrors the `PIDE/dynamic_output` branch in `handle()`
- `on_window_logmessage(response)` — mirrors the `window/logMessage` branch in `handle()`

Because `handle()` is the sole entry point (passed as the response handler to `LSPClient`), these
methods are dead code. Their presence is confusing: a reader may think they are part of the
dispatch chain, or that there is a second code path for these methods that has not yet been wired
up.

Crucially, if the dispatch logic in `handle()` is ever updated, the dead methods will silently
diverge, giving future contributors a false impression of how the system works.

## Fix

**Option A (preferred): Delete the three methods.**  
The `handle()` method already performs the full dispatch. There is nothing to consolidate.

**Option B: Route `handle()` through the per-method helpers.**  
Replace the inline dispatch in `handle()` with calls to `on_decoration()`, `on_dynamic_output()`,
and `on_window_logmessage()`. This preserves the named entry points, which may be useful for
subclassing. However, it adds an extra call frame for every notification and makes the flow
slightly less direct.

Option A is recommended unless subclassing is a design goal.

## Notes

- Check git blame / log before deleting; the methods were present before `handle()` centralised
  dispatch. Their removal is a cleanup, not a behaviour change.
- After removal, verify the test suite still passes: `test_process.py` mocks `ClientHandler` as a
  whole, so it will not be affected.
