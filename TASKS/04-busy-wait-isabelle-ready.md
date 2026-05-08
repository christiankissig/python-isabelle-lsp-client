# Replace busy-wait loop in `write_loop` with `asyncio.Event`

**Priority:** High  
**File:** `isabelle_lsp_client/process.py:83-86`

## Problem

After sending the `initialize` request, `write_loop` polls `self.isabelle_ready` in a tight loop
with a 10-second sleep:

```python
while True:
    await asyncio.sleep(10)
    if self.isabelle_ready:
        break
```

This has two problems:

1. **Unnecessary latency.** If Isabelle becomes ready 1 second after the loop starts, the client
   still waits up to 10 more seconds before proceeding. On slow machines this compounds with
   Isabelle's own startup time.

2. **No upper bound.** If Isabelle never sends the welcome message (e.g. wrong executable, missing
   heap), the loop runs forever. There is no timeout and no error.

## Fix

Replace the boolean flag and polling loop with an `asyncio.Event`:

```python
# __init__
self._isabelle_ready_event = asyncio.Event()

# update_status — called when welcome message arrives
self._isabelle_ready_event.set()

# write_loop — replaces the while/sleep loop
await asyncio.wait_for(self._isabelle_ready_event.wait(), timeout=120)
```

The `timeout` value (120 s here) should be configurable, either via the constructor or the `args`
dict (e.g. `args.get("startup_timeout", 120)`). On timeout, raise a descriptive exception rather
than hanging.

## Notes

- `self.isabelle_ready` (the bool) can be removed once the event replaces it, unless something
  else reads the flag externally (nothing currently does).
- The `asyncio.Event` must be created inside an async context or after the loop is running;
  creating it in `__init__` is fine from Python 3.10+ since there is no longer a running-loop
  check on construction.
