from isabelle_lsp_client.protocol import (
    CaretUpdateRequest,
    ProgressRequest,
    WorkDoneProgressBegin,
    WorkDoneProgressCancelNotification,
    WorkDoneProgressEnd,
    WorkDoneProgressReport,
    parse_work_done_progress,
)


def test_caret_update_request():
    request = CaretUpdateRequest(id=1, uri="file:///path/to/file", line=1, character=2)

    assert request.model_dump() == {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "PIDE/caret_update",
        "params": {
            "uri": "file:///path/to/file",
            "line": 1,
            "character": 2,
        },
    }


def test_progress_request():
    request = ProgressRequest(id=1)

    assert request.model_dump(exclude_none=True) == {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "PIDE/progress_request",
    }


def test_work_done_progress_begin_requires_title():
    begin = WorkDoneProgressBegin(title="Building", cancellable=True, percentage=0)
    assert begin.kind == "begin"
    assert begin.title == "Building"
    assert begin.cancellable is True
    assert begin.percentage == 0


def test_work_done_progress_report_defaults():
    report = WorkDoneProgressReport(message="halfway", percentage=50)
    assert report.kind == "report"
    assert report.message == "halfway"
    assert report.percentage == 50


def test_work_done_progress_end():
    end = WorkDoneProgressEnd(message="done")
    assert end.kind == "end"
    assert end.message == "done"


def test_parse_work_done_progress_dispatches_by_kind():
    assert isinstance(
        parse_work_done_progress({"kind": "begin", "title": "T"}),
        WorkDoneProgressBegin,
    )
    assert isinstance(
        parse_work_done_progress({"kind": "report"}), WorkDoneProgressReport
    )
    assert isinstance(parse_work_done_progress({"kind": "end"}), WorkDoneProgressEnd)


def test_parse_work_done_progress_ignores_unknown_payload():
    assert parse_work_done_progress(None) is None
    assert parse_work_done_progress({}) is None
    assert parse_work_done_progress({"kind": "other"}) is None


def test_work_done_progress_cancel_notification():
    notification = WorkDoneProgressCancelNotification(token="abc")

    assert notification.model_dump(exclude_none=True) == {
        "jsonrpc": "2.0",
        "method": "window/workDoneProgress/cancel",
        "params": {"token": "abc"},
    }
