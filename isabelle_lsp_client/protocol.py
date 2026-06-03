from typing import Any, Literal, Union

from lsp_client import BaseNotification, BaseRequest
from pydantic import BaseModel

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

ProgressToken = Union[int, str]


class WorkDoneProgressBegin(BaseModel):
    """Signals the start of a work done progress reporting."""

    kind: Literal["begin"] = "begin"
    title: str
    cancellable: bool | None = None
    message: str | None = None
    percentage: int | None = None


class WorkDoneProgressReport(BaseModel):
    """Reports progress of an ongoing work done progress operation."""

    kind: Literal["report"] = "report"
    cancellable: bool | None = None
    message: str | None = None
    percentage: int | None = None


class WorkDoneProgressEnd(BaseModel):
    """Signals the end of a work done progress reporting."""

    kind: Literal["end"] = "end"
    message: str | None = None


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


class WorkDoneProgressCancelNotification(BaseNotification):
    """
    ``window/workDoneProgress/cancel`` — sent by the client to cancel a
    server-initiated work done progress identified by ``token``.
    """

    def __init__(self, token: ProgressToken, **kwargs: Any) -> None:
        super().__init__(
            method=WORK_DONE_PROGRESS_CANCEL, params={"token": token}, **kwargs
        )
