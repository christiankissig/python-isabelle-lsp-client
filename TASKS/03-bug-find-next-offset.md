# Bug: `Document.find_next` double-applies `start_character` offset

**Priority:** High  
**File:** `isabelle_lsp_client/document.py:148-156`

## Problem

The method slices the starting line by `start_character`, and then passes `start_character` again
as the `str.find` offset into the already-truncated string:

```python
if line_number == start_line:
    line = line[start_character:]          # slice removes first start_character chars
if line_number == start_line:
    pos = line.find(pattern, start_character)  # then skip another start_character chars
else:
    pos = line.find(pattern)
```

For `start_character = 5` on a line `"apply sledgehammer"`, the slice produces
`"sledgehammer"` and then `find` starts searching at character 5 of that string, i.e.
`"hammer"`. Any pattern that begins within the first `start_character` characters of the
sliced string is missed, and the returned position is wrong in the opposite direction too:
`pos` refers to an index in the sliced string, not the original line, so the reported
character offset will be short by `start_character`.

The method is the backbone of the `auto_sledge.py` caret positioning logic, so this bug
causes the caret to be placed incorrectly on every iteration.

## Fix

Remove the slice entirely. Use only the `str.find` offset:

```python
for line_number in range(start_line, len(self.lines)):
    line = self.lines[line_number]
    if line_number == start_line:
        pos = line.find(pattern, start_character)
    else:
        pos = line.find(pattern)
    if pos >= 0:
        return (line_number, pos)
return (-1, -1)
```

This returns positions in terms of the original line, consistent with how callers use the result
(e.g. `move_caret(pos[0], pos[1] + len(COMMAND))`).

## Tests to add

- Pattern at column 0 on the start line: should be found when `start_character=0`.
- Pattern starting exactly at `start_character`: should be found.
- Pattern starting before `start_character`: should not be found on the start line.
- Pattern on a subsequent line: should be found with correct line and character.
- No match anywhere: should return `(-1, -1)`.
