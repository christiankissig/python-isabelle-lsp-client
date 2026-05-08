# Expand test coverage across all modules

**Priority:** Medium  
**File:** `tests/`

## Problem

Current test coverage is sparse:

| Module | What is tested |
|---|---|
| `process.py` | Read loop timeout/event behaviour only |
| `protocol.py` | Request serialisation (2 tests) |
| `handler.py` | Nothing |
| `document.py` | Nothing |
| `client.py` | Nothing |
| `isabelle.py` | Nothing |

The three bugs identified in tasks 01–03 all exist in untested code paths. New contributions have
no safety net.

## Tests to add

### `tests/test_document.py`

- **`Document.__init__` with `text=`** — assert all attributes are set (covers bug in task 01).
- **`Document.__init__` with file URI** — assert `file_path` strips `file://` correctly.
- **`Document.__init__` with invalid URI scheme** — assert `ValueError` is raised.
- **`read_file`** — mock `open`, assert `self.lines` is populated.
- **`write_file`** — mock `open`, assert content is `"\n".join(self.lines)`.
- **`write_file` with `output_suffix`** — assert the suffix is appended to the path.
- **`local_apply_change`** — single-line replacement within a line.
- **`local_apply_change`** — multi-line replacement spanning two lines.
- **`local_apply_changes`** — two sequential changes applied in order.
- **`get_progress`** — returns `line / len(lines)`.
- **`find_next`** — pattern at column 0 (covers bug in task 03).
- **`find_next`** — pattern starting exactly at `start_character`.
- **`find_next`** — pattern before `start_character` on start line (should not find).
- **`find_next`** — pattern on a later line.
- **`find_next`** — no match returns `(-1, -1)`.
- **`theory_until_caret`** — returns lines up to but not including the caret line.

### `tests/test_handler.py`

- **`handle` dispatches to registered callback** for a known method.
- **`handle` logs warning** for an unrecognised method (no callback registered).
- **`handle` logs warning** for a message without `"method"`.
- **`handle` raises** when `PIDE/decoration` or `PIDE/dynamic_output` arrives and `document` is
  `None`.
- **`handle` skips** `PIDE/decoration` notification when URI does not match the document URI.
- **`on_start`** calls all registered `on_start_callbacks` with the document.
- **`on_timeout`** calls all registered `on_timeout_callbacks` with the document.
- **`register`** — multiple callbacks for the same method are all called.

### `tests/test_isabelle.py`

- **`is_isabelle_ready`** — returns `True` for strings starting with `"Welcome to Isabelle/"`.
- **`is_isabelle_ready`** — returns `False` for unrelated strings.
- **`is_sledgehammer_done`** — returns `True` for content ending with `"Done"`.
- **`is_sledgehammer_noproof`** — returns `True` when `"No proof found"` is present.
- **`get_command_from_sledgehammer`** — extracts command from a well-formed response string.
- **`get_command_from_sledgehammer`** — returns `None` when no match.
- **`command_finishes_subgoal`** — returns `True` for `"by ..."`, `"done"`, `"qed"`.

### `tests/test_client.py`

> **Blocked on `python-lsp-client` tasks 01 and 05.** `send_notification` and
> `InitializedNotification` do not yet exist in `lsp-client`; write these tests after those
> tasks land and task 16 (cleanup `InitializedNotification` workaround) is complete.

Use `AsyncMock` for `LSPClient`. Focus on the shape of the requests sent, not on the transport.

- **`initialize`** — assert `send_request` is called with an `InitializeRequest` containing the
  expected capability keys, `processId`, `clientInfo`, and `workDoneToken`.
- **`initialize`** — assert `send_notification` is called with `InitializedNotification`.
- **`open_text_document`** — assert `send_notification` is called with `TextDocumentDidOpenNotification`
  containing the file contents and correct `languageId`.
- **`open_text_document`** — assert `ValueError` for non-`file://` URIs.
- **`caret_update`** — assert `send_request` is called with a `CaretUpdateRequest` with correct
  `uri`, `line`, and `character`.

## Notes

- `pytest-asyncio` is already a dependency; use `@pytest.mark.asyncio` for async tests.
- `Document` tests that exercise file I/O should use `tmp_path` (built-in pytest fixture) or
  `unittest.mock.mock_open` rather than touching real files.
- The `asyncio_mode` in `pytest.ini` is currently `STRICT`; each async test needs the decorator.
