# `IsabelleProcess.command` field is declared but never used

**Priority:** Medium  
**File:** `isabelle_lsp_client/process.py:19, 108-124`

## Problem

`IsabelleProcess` declares a class-level attribute:

```python
command: Any | None = None
```

The CLAUDE.md documents the intended behaviour:

> Optionally pass a `command` object to `run()` — if it has `set_isabelle(client)` or
> `register(handler)` methods, they are called during setup.

Neither `run()` nor any other method reads or calls `self.command`. The field is therefore dead.
Users who follow the CLAUDE.md and pass a `command` object will see it silently ignored.

## Fix

Wire up the `command` object inside `run()`, after `lspClient` and `isaClient` are created and
before the tasks are started:

```python
async def run(self, args: dict) -> None:
    ...
    self.lspClient = LSPClient(...)
    self.isaClient = IsabelleClient(self.lspClient)

    if self.command is not None:
        if hasattr(self.command, "set_isabelle"):
            self.command.set_isabelle(self.isaClient)
        if hasattr(self.command, "register"):
            self.command.register(self.clientHandler)

    read_task = asyncio.create_task(self.read_loop())
    write_task = asyncio.create_task(self.write_loop(args))
    await asyncio.gather(read_task, write_task)
```

Also expose a way to set the command, either via the constructor or as a parameter to `run()`.
Accepting it in the constructor is simpler and keeps `run()` focused on I/O:

```python
def __init__(self, clientHandler, timeout=-1, command=None):
    ...
    self.command = command
```

## Notes

- Consider replacing `Any | None` with a `Protocol` that declares `set_isabelle` and `register`
  so mypy can verify that passed objects satisfy the interface.
