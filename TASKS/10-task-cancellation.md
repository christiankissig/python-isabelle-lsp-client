# Task failure should cancel sibling task in `run()`

**Priority:** Low  
**File:** `isabelle_lsp_client/process.py:122-124`

## Problem

`run()` launches `read_loop` and `write_loop` as concurrent tasks and awaits both:

```python
read_task = asyncio.create_task(self.read_loop())
write_task = asyncio.create_task(self.write_loop(args))
await asyncio.gather(read_task, write_task)
```

`asyncio.gather` with `return_exceptions=False` (the default) will re-raise the first exception
from any task, but it does not automatically cancel the other task. The surviving task keeps
running in the background even after `run()` has returned with an exception.

Concrete failure scenarios:

- `write_loop` raises `FileNotFoundError` (theory file not found) → `read_loop` keeps running,
  consuming responses from a connection that will never advance.
- `read_loop` raises an unexpected exception → `write_loop` is mid-sleep in the ready-wait loop
  and never terminates.

In both cases, the Isabelle subprocess is also not terminated (see task 05).

## Fix

Cancel the sibling task explicitly when one fails:

```python
read_task = asyncio.create_task(self.read_loop())
write_task = asyncio.create_task(self.write_loop(args))
try:
    await asyncio.gather(read_task, write_task)
except Exception:
    read_task.cancel()
    write_task.cancel()
    await asyncio.gather(read_task, write_task, return_exceptions=True)
    raise
```

Alternatively, use `asyncio.TaskGroup` (Python 3.11+), which provides this behaviour by default:

```python
async with asyncio.TaskGroup() as tg:
    tg.create_task(self.read_loop())
    tg.create_task(self.write_loop(args))
```

`TaskGroup` cancels all sibling tasks when any one raises, then re-raises all exceptions as an
`ExceptionGroup`. If Python 3.10 support must be maintained, use the explicit `cancel()` approach.

## Notes

- This task pairs with task 05 (subprocess shutdown): the `finally` block in `run()` should
  handle both task cancellation and process cleanup together.
- `CancelledError` is a subclass of `BaseException`, not `Exception`, so ensure the cleanup
  handler catches `BaseException` or re-raises `CancelledError` explicitly.
