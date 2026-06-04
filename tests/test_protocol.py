import pytest

from isabelle_lsp_client.protocol import (
    ApplyWorkspaceEditParams,
    CaretUpdateRequest,
    Decoration,
    DecorationParams,
    DecorationRange,
    DiagnosticSeverity,
    DynamicOutput,
    DynamicOutputDecoration,
    NodeStatus,
    ProgressNodes,
    ProgressRequest,
    PublishDiagnosticsParams,
    WorkDoneProgressBegin,
    WorkDoneProgressCancelNotification,
    WorkDoneProgressCancelParams,
    WorkDoneProgressEnd,
    WorkDoneProgressReport,
    parse_apply_edit,
    parse_decoration,
    parse_dynamic_output,
    parse_progress,
    parse_publish_diagnostics,
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
    # PIDE/progress_request is a notification: no id, no params.
    request = ProgressRequest()

    assert request.model_dump(exclude_none=True) == {
        "jsonrpc": "2.0",
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


def test_dynamic_output_decoration_is_decoration_alias():
    # The dynamic-output decoration element is the shared Decoration model.
    assert DynamicOutputDecoration is Decoration


# A real PIDE/decoration payload captured from `isabelle vscode_server`. Ranges
# are [start_line, start_char, end_line, end_char] relative to the source
# document identified by `uri`.
DECORATION_SAMPLE = {
    "uri": "file:///path/to/Theory.thy",
    "entries": [
        {
            "type": "text_keyword1",
            "content": [{"range": [0, 0, 0, 6]}, {"range": [4, 0, 4, 5]}],
        },
        {
            "type": "background_unprocessed1",
            "content": [{"range": [10, 0, 12, 3]}],
        },
    ],
}


def test_parse_decoration_full_payload():
    deco = parse_decoration(DECORATION_SAMPLE)

    assert isinstance(deco, DecorationParams)
    assert deco.uri == "file:///path/to/Theory.thy"
    assert [e.type for e in deco.entries] == [
        "text_keyword1",
        "background_unprocessed1",
    ]
    assert len(deco.entries[0].content) == 2
    # A multi-line range is preserved and converts to an lsp_client.Range.
    span = deco.entries[1].content[0].range.to_range()
    assert (span.start.line, span.end.line) == (10, 12)


def test_parse_decoration_defaults_and_none():
    assert parse_decoration(None) is None
    # `entries` is optional; `uri` is required.
    deco = parse_decoration({"uri": "file:///x.thy"})
    assert deco.entries == []


def test_parse_decoration_requires_uri():
    with pytest.raises(ValueError):
        parse_decoration({"entries": []})


# A PIDE/progress payload following the isabelle-emacs lsp.scala shape. Note the
# hyphenated `nodes-status` key.
PROGRESS_SAMPLE = {
    "nodes-status": [
        {
            "name": "Theory.thy",
            "unprocessed": 2,
            "running": 1,
            "warned": 0,
            "failed": 0,
            "finished": 7,
            "initialized": 1,
            "consolidated": 0,
            "canceled": 0,
            "terminated": 0,
        },
        {
            "name": "Other.thy",
            "unprocessed": 0,
            "running": 0,
            "warned": 1,
            "failed": 0,
            "finished": 4,
            "initialized": 1,
            "consolidated": 1,
            "canceled": 0,
            "terminated": 1,
        },
    ]
}


def test_parse_progress_decodes_hyphenated_key():
    prog = parse_progress(PROGRESS_SAMPLE)

    assert isinstance(prog, ProgressNodes)
    assert [n.name for n in prog.nodes_status] == ["Theory.thy", "Other.thy"]


def test_node_status_derived_metrics():
    prog = parse_progress(PROGRESS_SAMPLE)
    theory, other = prog.nodes_status

    # Theory.thy: total = 2+1+0+0+7 = 10; done = finished+warned+failed = 7.
    assert theory.total == 10
    assert theory.percentage == 70
    assert theory.is_finished is False

    # Other.thy: nothing pending, all done.
    assert other.total == 5
    assert other.percentage == 100
    assert other.is_finished is True


def test_node_status_empty_node():
    node = NodeStatus(name="Empty.thy")
    assert node.total == 0
    assert node.percentage == 0
    assert node.is_finished is True


def test_progress_nodes_populate_by_field_name():
    # The field name (not just the wire alias) is accepted.
    prog = ProgressNodes(nodes_status=[NodeStatus(name="A.thy")])
    assert prog.nodes_status[0].name == "A.thy"


def test_parse_progress_defaults_and_none():
    assert parse_progress(None) is None
    # `nodes-status` is optional; counters default to 0.
    prog = parse_progress({})
    assert prog.nodes_status == []


# The bad-theory-import payload from issue #1 (severity set, two errors).
PUBLISH_DIAGNOSTICS_SAMPLE = {
    "uri": "file:///path/to/Polylog_Library.thy",
    "diagnostics": [
        {
            "range": {
                "start": {"line": 7, "character": 2},
                "end": {"line": 7, "character": 41},
            },
            "message": 'Bad theory import "HOL-Complex_Analysis.Complex_Analysis"',
            "severity": 1,
        },
        {
            "range": {
                "start": {"line": 8, "character": 2},
                "end": {"line": 8, "character": 43},
            },
            "message": 'Bad theory import "Linear_Recurrences.Eulerian_Polynomials"',
            "severity": 1,
        },
    ],
}


def test_parse_publish_diagnostics_message_severity_position():
    published = parse_publish_diagnostics(PUBLISH_DIAGNOSTICS_SAMPLE)

    assert isinstance(published, PublishDiagnosticsParams)
    assert published.uri == "file:///path/to/Polylog_Library.thy"
    first = published.diagnostics[0]
    assert first.message.startswith("Bad theory import")
    assert first.severity == DiagnosticSeverity.Error
    assert (first.range.start.line, first.range.start.character) == (7, 2)


def test_parse_publish_diagnostics_preserves_order():
    published = parse_publish_diagnostics(PUBLISH_DIAGNOSTICS_SAMPLE)
    lines = [d.range.start.line for d in published.diagnostics]
    assert lines == [7, 8]


def test_parse_publish_diagnostics_tolerates_isabelle_quirks():
    # Real Isabelle diagnostics carry a spurious `jsonrpc` key and often omit
    # `severity` even for errors.
    published = parse_publish_diagnostics(
        {
            "uri": "file:///x.thy",
            "diagnostics": [
                {
                    "jsonrpc": "2.0",
                    "range": {
                        "start": {"line": 30, "character": 145},
                        "end": {"line": 30, "character": 167},
                    },
                    "message": 'Undefined fact: "wfs_2_writes_preserved"',
                }
            ],
        }
    )
    diag = published.diagnostics[0]
    assert diag.severity is None
    assert diag.message.startswith("Undefined fact")


def test_parse_publish_diagnostics_defaults_and_none():
    assert parse_publish_diagnostics(None) is None
    # A cleared document publishes an empty diagnostics list.
    published = parse_publish_diagnostics({"uri": "file:///x.thy"})
    assert published.diagnostics == []


# A workspace/applyEdit payload following the isabelle-emacs lsp.scala shape.
APPLY_EDIT_SAMPLE = {
    "edit": {
        "documentChanges": [
            {
                "textDocument": {"uri": "file:///A.thy", "version": 3},
                "edits": [
                    {
                        "range": {
                            "start": {"line": 2, "character": 0},
                            "end": {"line": 2, "character": 5},
                        },
                        "newText": "lemma",
                    },
                    {
                        "range": {
                            "start": {"line": 5, "character": 0},
                            "end": {"line": 5, "character": 0},
                        },
                        "newText": "\ndone",
                    },
                ],
            }
        ]
    }
}


def test_parse_apply_edit_full_payload():
    parsed = parse_apply_edit(APPLY_EDIT_SAMPLE)

    assert isinstance(parsed, ApplyWorkspaceEditParams)
    change = parsed.edit.document_changes[0]
    assert change.uri == "file:///A.thy"
    assert change.textDocument.version == 3
    first = change.edits[0]
    assert first.new_text == "lemma"  # decoded from the camelCase wire key
    assert (first.range.start.line, first.range.end.character) == (2, 5)


def test_parse_apply_edit_preserves_edit_order():
    parsed = parse_apply_edit(APPLY_EDIT_SAMPLE)
    edits = parsed.edit.document_changes[0].edits
    assert [e.range.start.line for e in edits] == [2, 5]


def test_apply_workspace_edit_params_populate_by_field_name():
    from isabelle_lsp_client.protocol import (
        TextDocumentEdit,
        TextEdit,
        VersionedTextDocumentIdentifier,
        WorkspaceEdit,
    )
    from lsp_client import Position, Range

    edit = WorkspaceEdit(
        document_changes=[
            TextDocumentEdit(
                textDocument=VersionedTextDocumentIdentifier(uri="file:///A.thy"),
                edits=[
                    TextEdit(
                        range=Range(
                            start=Position(line=0, character=0),
                            end=Position(line=0, character=1),
                        ),
                        new_text="x",
                    )
                ],
            )
        ]
    )
    assert edit.document_changes[0].edits[0].new_text == "x"


def test_parse_apply_edit_defaults_and_none():
    assert parse_apply_edit(None) is None
    # documentChanges is optional.
    parsed = parse_apply_edit({"edit": {}})
    assert parsed.edit.document_changes == []
