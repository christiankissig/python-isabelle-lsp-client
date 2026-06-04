import pytest

from isabelle_lsp_client.protocol import (
    CaretUpdateRequest,
    DecorationRange,
    DynamicOutput,
    ProgressRequest,
    WorkDoneProgressBegin,
    WorkDoneProgressCancelNotification,
    WorkDoneProgressCancelParams,
    WorkDoneProgressEnd,
    WorkDoneProgressReport,
    parse_dynamic_output,
    parse_work_done_progress,
)

# A real PIDE/dynamic_output payload captured from `isabelle vscode_server`
# (isabelle-emacs fork). Ranges are [start_line, start_char, end_line, end_char]
# relative to `content`.
DYNAMIC_OUTPUT_SAMPLE = {
    "content": (
        "proof (prove)\n"
        "goal (1 subgoal):\n"
        " 1. \\<forall>x. \\<exists>b. (x, b) \\<in> writes"
    ),
    "decorations": [
        {
            "type": "text_keyword1",
            "content": [{"range": [1, 0, 1, 4]}],
        },
        {
            "type": "text_bound",
            "content": [{"range": [2, 13, 2, 14]}, {"range": [2, 25, 2, 26]}],
        },
    ],
}


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
    notification = WorkDoneProgressCancelNotification(
        params=WorkDoneProgressCancelParams(token="abc")
    )

    assert notification.model_dump(exclude_none=True) == {
        "jsonrpc": "2.0",
        "method": "window/workDoneProgress/cancel",
        "params": {"token": "abc"},
    }


def test_decoration_range_decodes_flat_array():
    r = DecorationRange.model_validate([2, 13, 2, 14])
    assert (r.start_line, r.start_character, r.end_line, r.end_character) == (
        2,
        13,
        2,
        14,
    )


def test_decoration_range_to_lsp_range():
    lsp_range = DecorationRange.model_validate([1, 0, 1, 4]).to_range()
    assert lsp_range.start.line == 1
    assert lsp_range.start.character == 0
    assert lsp_range.end.line == 1
    assert lsp_range.end.character == 4


def test_decoration_range_rejects_wrong_arity():
    with pytest.raises(ValueError):
        DecorationRange.model_validate([1, 2, 3])


def test_parse_dynamic_output_full_payload():
    out = parse_dynamic_output(DYNAMIC_OUTPUT_SAMPLE)

    assert isinstance(out, DynamicOutput)
    assert out.content.startswith("proof (prove)")
    assert out.lines[1] == "goal (1 subgoal):"
    assert [d.type for d in out.decorations] == ["text_keyword1", "text_bound"]
    # The keyword decoration covers "goal" on line 1.
    kw = out.decorations[0].content[0].range
    assert out.lines[kw.start_line][kw.start_character : kw.end_character] == "goal"
    # The bound-variable group carries two spans.
    assert len(out.decorations[1].content) == 2


def test_parse_dynamic_output_empty_payload():
    out = parse_dynamic_output({"content": "", "decorations": []})
    assert out.content == ""
    assert out.decorations == []
    assert out.lines == [""]


def test_parse_dynamic_output_defaults_and_none():
    assert parse_dynamic_output(None) is None
    # Both fields are optional on the wire.
    out = parse_dynamic_output({})
    assert out.content == ""
    assert out.decorations == []
