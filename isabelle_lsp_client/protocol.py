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
    BaseNotification,
    BaseRequest,
    Diagnostic,
    DiagnosticSeverity,
    Position,
    ProgressToken,
    Range,
    WorkDoneProgressBegin,
    WorkDoneProgressCancelNotification,
    WorkDoneProgressCancelParams,
    WorkDoneProgressEnd,
    WorkDoneProgressReport,
)
from pydantic import BaseModel, ConfigDict, Field, model_validator

# PIDE requests


class CaretUpdateRequest(BaseRequest):
    def __init__(self, uri: str, line: int, character: int, **kwargs: Any) -> None:
        method = "PIDE/caret_update"
        params = {"uri": uri, "line": line, "character": character}
        super().__init__(method=method, params=params, **kwargs)


class ProgressRequest(BaseNotification):
    """
    ``PIDE/progress_request`` — asks Isabelle to start emitting ``PIDE/progress``
    updates.

    Despite the ``_request`` suffix in the method name, this is a JSON-RPC
    notification: the server reacts by pushing ``PIDE/progress`` notifications
    rather than returning a response, so it carries no ``id`` and no params.
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


# Decorations
# https://github.com/m-fleury/isabelle-emacs (VSCode server)
#
# Isabelle reports typed markup as "decorations": groups of same-typed ranges.
# The same element shape — {"type": <class>, "content": [{"range": [...]}, ...]}
# — appears both inside `PIDE/dynamic_output` (over the output-panel text) and as
# `PIDE/decoration` (over a source document). The models below capture that
# shared element; the two notification payloads wrap it differently.
#
# A range is a flat [start_line, start_char, end_line, end_char] array: 0-based,
# half-open. `type` is an Isabelle rendering class (e.g. text_keyword1,
# text_free, background_unprocessed1, dotted_writeln, ...) drawn from a large,
# open set, so it is kept as a plain string rather than an enum.


class DecorationRange(BaseModel):
    """
    A half-open ``[start, end)`` range carried by a decoration.

    On the wire this is a flat
    ``[start_line, start_character, end_line, end_character]`` array; it is
    decoded into named fields here. Lines and characters are 0-based. The frame
    of reference depends on the containing notification: the output-panel
    ``content`` for ``PIDE/dynamic_output``, or the source document identified by
    ``uri`` for ``PIDE/decoration``.
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


class Decoration(BaseModel):
    """
    A group of same-typed markup spans.

    ``type`` is an Isabelle rendering class (e.g. ``text_keyword1``,
    ``text_free``, ``background_unprocessed1``); the set is open, so it is kept
    as a plain string rather than an enum. This element is shared by
    ``PIDE/dynamic_output`` and ``PIDE/decoration``.
    """

    type: str
    content: list[DecorationEntry] = Field(default_factory=list)


# Backwards-compatible alias: the dynamic-output decorations are plain
# :class:`Decoration` groups.
DynamicOutputDecoration = Decoration


# PIDE dynamic output
#
# `PIDE/dynamic_output` is a server -> client notification carrying the proof
# state / output-panel text at the current caret, together with the typed markup
# over that text. The `params` shape observed on the wire is:
#
#   {"content": "<output text>", "decorations": [<Decoration>, ...]}
#
# Decoration ranges are relative to `content` (lines split on "\n"). `content`
# may be empty and `decorations` may be absent/empty.


class DynamicOutput(BaseModel):
    """
    Payload of a ``PIDE/dynamic_output`` notification: the output-panel text at
    the current caret and the typed markup over it.
    """

    content: str = ""
    decorations: list[Decoration] = Field(default_factory=list)

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


# PIDE decoration
#
# `PIDE/decoration` is a server -> client notification carrying the typed markup
# for a source document. The `params` shape observed on the wire is:
#
#   {"uri": "file:///...", "entries": [<Decoration>, ...]}
#
# Decoration ranges are relative to the source document identified by `uri`.
# A single message may carry thousands of ranges across dozens of types.


class DecorationParams(BaseModel):
    """
    Payload of a ``PIDE/decoration`` notification: the typed markup for the
    document identified by ``uri``.
    """

    uri: str
    entries: list[Decoration] = Field(default_factory=list)


def parse_decoration(params: dict | None) -> DecorationParams | None:
    """
    Parse the ``params`` of a ``PIDE/decoration`` notification into a typed
    :class:`DecorationParams`, or ``None`` if there is no payload.
    """
    if params is None:
        return None
    return DecorationParams.model_validate(params)


# PIDE progress
# https://github.com/m-fleury/isabelle-emacs (VSCode server: lsp.scala
# Progress_Node / Progress_Nodes)
#
# `PIDE/progress` is a server -> client notification carrying a full snapshot of
# per-theory-node processing status. The `params` shape is:
#
#   {"nodes-status": [
#       {"name": "<node>", "unprocessed": int, "running": int, "warned": int,
#        "failed": int, "finished": int, "initialized": int,
#        "consolidated": int, "canceled": int, "terminated": int},
#       ...]}
#
# The JSON key is "nodes-status" (hyphenated); it is aliased below. Each snapshot
# lists every known node, so the latest message fully replaces prior state.


class NodeStatus(BaseModel):
    """
    Processing status of a single theory node (counters over its commands and
    node-level lifecycle flags), as reported by ``PIDE/progress``.
    """

    name: str
    unprocessed: int = 0
    running: int = 0
    warned: int = 0
    failed: int = 0
    finished: int = 0
    initialized: int = 0
    consolidated: int = 0
    canceled: int = 0
    terminated: int = 0

    @property
    def total(self) -> int:
        """Number of commands in the node (the five per-command counters)."""
        return (
            self.unprocessed + self.running + self.warned + self.failed + self.finished
        )

    @property
    def is_finished(self) -> bool:
        """True when nothing is pending (no unprocessed or running commands)."""
        return self.unprocessed == 0 and self.running == 0

    @property
    def percentage(self) -> int:
        """
        Percent of commands no longer pending (``finished`` + ``warned`` +
        ``failed``) over :attr:`total`; ``0`` for an empty node.
        """
        if self.total == 0:
            return 0
        done = self.finished + self.warned + self.failed
        return round(100 * done / self.total)


class ProgressNodes(BaseModel):
    """
    Payload of a ``PIDE/progress`` notification: the processing status of every
    known theory node.
    """

    model_config = ConfigDict(populate_by_name=True)

    nodes_status: list[NodeStatus] = Field(default_factory=list, alias="nodes-status")


def parse_progress(params: dict | None) -> ProgressNodes | None:
    """
    Parse the ``params`` of a ``PIDE/progress`` notification into a typed
    :class:`ProgressNodes`, or ``None`` if there is no payload.
    """
    if params is None:
        return None
    return ProgressNodes.model_validate(params)


# Publish diagnostics
# https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/#textDocument_publishDiagnostics
#
# `textDocument/publishDiagnostics` is a standard LSP server -> client
# notification. Isabelle uses it to report theory errors (bad imports, undefined
# facts, ...). The `Diagnostic` / `DiagnosticSeverity` element types are reused
# from :mod:`lsp_client`; only the notification params are modelled here.
#
# Isabelle quirks tolerated by the model: each diagnostic may carry a spurious
# `jsonrpc` key (ignored), and `severity` is frequently absent even for errors.


class PublishDiagnosticsParams(BaseModel):
    """
    Payload of a ``textDocument/publishDiagnostics`` notification: the full set
    of diagnostics for the document identified by ``uri``. Each notification
    replaces any previously published diagnostics for that ``uri``.
    """

    uri: str
    version: int | None = None
    diagnostics: list[Diagnostic] = Field(default_factory=list)


def parse_publish_diagnostics(params: dict | None) -> PublishDiagnosticsParams | None:
    """
    Parse the ``params`` of a ``textDocument/publishDiagnostics`` notification
    into a typed :class:`PublishDiagnosticsParams`, or ``None`` if there is no
    payload. Diagnostic order is preserved.
    """
    if params is None:
        return None
    return PublishDiagnosticsParams.model_validate(params)


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
    "Decoration",
    "DynamicOutputDecoration",
    "DynamicOutput",
    "parse_dynamic_output",
    "DecorationParams",
    "parse_decoration",
    "NodeStatus",
    "ProgressNodes",
    "parse_progress",
    "Diagnostic",
    "DiagnosticSeverity",
    "PublishDiagnosticsParams",
    "parse_publish_diagnostics",
]
