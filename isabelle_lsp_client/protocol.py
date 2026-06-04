"""
Isabelle-specific LSP protocol types.

The ``PIDE/*`` request types are Isabelle extensions and are defined here. The
work done progress payloads and the cancel notification are part of the LSP base
protocol and are re-exported from :mod:`lsp_client`; only the ``WorkDoneProgress``
union and the ``parse_work_done_progress`` helper are Isabelle-side conveniences
layered on top of those spec types.
"""

from typing import Any, Union

from lsp_client import (
    BaseRequest,
    ProgressToken,
    WorkDoneProgressBegin,
    WorkDoneProgressCancelNotification,
    WorkDoneProgressCancelParams,
    WorkDoneProgressEnd,
    WorkDoneProgressReport,
)

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
]
