"""
Isabelle-specific LSP protocol types.

The ``PIDE/*`` request types are Isabelle extensions and are defined here. The
work done progress payloads and the cancel notification are part of the LSP base
protocol and are re-exported from :mod:`lsp_client`; only the ``WorkDoneProgress``
union and the ``parse_work_done_progress`` helper are Isabelle-side conveniences
layered on top of those spec types.

The ``PIDE/dynamic_output`` payload (proof state / output-panel text plus typed
markup) has no published specification; it is defined by the isabelle-emacs
fork's VSCode server. The models here mirror the observed wire format.
"""

from typing import Any, Union

from lsp_client import (
    BaseRequest,
    Position,
    ProgressToken,
    Range,
    WorkDoneProgressBegin,
    WorkDoneProgressCancelNotification,
    WorkDoneProgressCancelParams,
    WorkDoneProgressEnd,
    WorkDoneProgressReport,
)
from pydantic import BaseModel, Field, model_validator

# PIDE requests


class CaretUpdateRequest(BaseRequest):
    def __init__(self, uri: str, line: int, character: int, **kwargs: Any) -> None:
        method = "PIDE/caret_update"
        params = {"uri": uri, "line": line, "character": character}
        super().__init__(method=method, params=params, **kwargs)


class ProgressRequest(BaseRequest):
    """
    Request to update progress of a task.
    """

    def __init__(self, **kwargs: Any) -> None:
        method = "PIDE/progress_request"
        super().__init__(method=method, params=None, **kwargs)


# Work Done Progress
# https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/#workDoneProgress

PROGRESS = "$/progress"
WORK_DONE_PROGRESS_CREATE = "window/workDoneProgress/create"
WORK_DONE_PROGRESS_CANCEL = "window/workDoneProgress/cancel"


WorkDoneProgress = Union[
    WorkDoneProgressBegin, WorkDoneProgressReport, WorkDoneProgressEnd
]


def parse_work_done_progress(value: dict | None) -> WorkDoneProgress | None:
    """
    Parse the ``value`` of a ``$/progress`` notification into a typed work done
    progress object, or ``None`` if it is not a work done progress payload.
    """
    if not value:
        return None
    kind = value.get("kind")
    if kind == "begin":
        return WorkDoneProgressBegin(**value)
    if kind == "report":
        return WorkDoneProgressReport(**value)
    if kind == "end":
        return WorkDoneProgressEnd(**value)
    return None


# PIDE dynamic output
# https://github.com/m-fleury/isabelle-emacs (VSCode server: Dynamic_Output)
#
# `PIDE/dynamic_output` is a server -> client notification carrying the proof
# state / output-panel text at the current caret, together with typed markup
# ranges over that text. The `params` shape observed on the wire is:
#
#   {"content": "<output text>",
#    "decorations": [
#       {"type": "text_keyword1",
#        "content": [{"range": [start_line, start_char, end_line, end_char]},
#                    ...]},
#       ...]}
#
# Ranges are 0-based, half-open, and relative to `content` (NOT the source
# document); lines are split on "\n". `content` may be empty and `decorations`
# may be absent/empty.


class DecorationRange(BaseModel):
    """
    A half-open ``[start, end)`` range over the dynamic-output ``content`` text.

    On the wire this is a flat
    ``[start_line, start_character, end_line, end_character]`` array; it is
    decoded into named fields here. Lines and characters are 0-based and
    relative to the ``content`` string.
    """

    start_line: int
    start_character: int
    end_line: int
    end_character: int

    @model_validator(mode="before")
    @classmethod
    def _coerce_array(cls, data: Any) -> Any:
        if isinstance(data, (list, tuple)):
            if len(data) != 4:
                raise ValueError(
                    f"decoration range must have 4 elements, got {len(data)}"
                )
            start_line, start_character, end_line, end_character = data
            return {
                "start_line": start_line,
                "start_character": start_character,
                "end_line": end_line,
                "end_character": end_character,
            }
        return data

    def to_range(self) -> Range:
        """Convert to an :class:`lsp_client.Range`."""
        return Range(
            start=Position(line=self.start_line, character=self.start_character),
            end=Position(line=self.end_line, character=self.end_character),
        )


class DecorationEntry(BaseModel):
    """A single markup span; one entry of a decoration's ``content`` list."""

    range: DecorationRange


class DynamicOutputDecoration(BaseModel):
    """
    A group of same-typed markup spans within the dynamic-output text.

    ``type`` is an Isabelle rendering class (e.g. ``text_keyword1``,
    ``text_free``, ``text_bound``, ``text_var``, ``text_main``). The set is open,
    so it is kept as a plain string rather than an enum.
    """

    type: str
    content: list[DecorationEntry] = Field(default_factory=list)


class DynamicOutput(BaseModel):
    """
    Payload of a ``PIDE/dynamic_output`` notification: the output-panel text at
    the current caret and the typed markup over it.
    """

    content: str = ""
    decorations: list[DynamicOutputDecoration] = Field(default_factory=list)

    @property
    def lines(self) -> list[str]:
        """The ``content`` split into lines, matching the decoration indexing."""
        return self.content.split("\n")


def parse_dynamic_output(params: dict | None) -> DynamicOutput | None:
    """
    Parse the ``params`` of a ``PIDE/dynamic_output`` notification into a typed
    :class:`DynamicOutput`, or ``None`` if there is no payload.
    """
    if params is None:
        return None
    return DynamicOutput.model_validate(params)


__all__ = [
    "CaretUpdateRequest",
    "ProgressRequest",
    "PROGRESS",
    "WORK_DONE_PROGRESS_CREATE",
    "WORK_DONE_PROGRESS_CANCEL",
    "ProgressToken",
    "WorkDoneProgress",
    "WorkDoneProgressBegin",
    "WorkDoneProgressReport",
    "WorkDoneProgressEnd",
    "WorkDoneProgressCancelNotification",
    "WorkDoneProgressCancelParams",
    "parse_work_done_progress",
    "DecorationRange",
    "DecorationEntry",
    "DynamicOutputDecoration",
    "DynamicOutput",
    "parse_dynamic_output",
]
