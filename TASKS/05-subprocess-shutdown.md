# Graceful shutdown of the Isabelle subprocess

**Priority:** High  
**File:** `isabelle_lsp_client/process.py:108-124`

## Problem

When `on_finished()` sets `_done_event`, the `read_loop` exits on its next iteration. However:

1. The `asyncio.subprocess.Process` object returned by `start_isabelle()` is not stored on `self`.
   After `run()` exits there is no handle to terminate the child process.
2. The Isabelle process keeps running until the OS reclaims it or until the parent process exits.
   For scripts that are invoked repeatedly (e.g. in CI), this leaks processes.
3. Stdin/stdout pipes are not explicitly closed, which can cause the child to block on a write to
   its stdout after the parent has stopped reading.

## Fix

Store the subprocess on `self` and add cleanup in `run()`:

```python
async def run(self, args: dict) -> None:
    ...
    self._process = await self.start_isabelle(args["exec"], options)
    self.lspClient = LSPClient(self._process.stdin, self._process.stdout, response_handler)
    self.isaClient = IsabelleClient(self.lspClient)

    try:
        read_task = asyncio.create_task(self.read_loop())
        write_task = asyncio.create_task(self.write_loop(args))
        await asyncio.gather(read_task, write_task)
    finally:
        await self._shutdown_process()

async def _shutdown_process(self) -> None:
    if self._process.returncode is None:
        self._process.terminate()
        try:
            await asyncio.wait_for(self._process.wait(), timeout=5)
        except asyncio.TimeoutError:
            self._process.kill()
            await self._process.wait()
```

## Notes

- Closing `self._process.stdin` before waiting is good practice: it signals EOF to the child,
  which may cause it to exit cleanly without needing `terminate()`.
- The `LSPClient` may hold a reference to the stream; check whether it needs to be told to stop
  before the streams are closed.
