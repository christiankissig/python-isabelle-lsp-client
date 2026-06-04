from unittest.mock import AsyncMock, MagicMock

import pytest

from isabelle_lsp_client.handler import (
    PIDE_DECORATION,
    PIDE_DYNAMIC_OUTPUT,
    PIDE_PROGRESS,
    TEXTDOCUMENT_PUBLISHDIAGNOSTICS,
    WINDOW_LOGMESSAGE,
    WORKSPACE_APPLYEDIT,
    ClientHandler,
)
from isabelle_lsp_client.protocol import (
    PROGRESS,
    WORK_DONE_PROGRESS_CREATE,
    ApplyWorkspaceEditParams,
    DecorationParams,
    DynamicOutput,
    ProgressNodes,
    WorkDoneProgressBegin,
    WorkDoneProgressReport,
    parse_apply_edit,
)


def _progress(token, value):
    return {"method": PROGRESS, "params": {"token": token, "value": value}}


@pytest.fixture
def handler():
    return ClientHandler()


@pytest.fixture
def mock_document():
    doc = MagicMock()
    doc.uri = "file:///path/to/Theory.thy"
    return doc


class TestHandleDispatch:
    @pytest.mark.asyncio
    async def test_registered_callback_is_called(self, handler, mock_document):
        handler.set_document(mock_document)
        cb = AsyncMock()
        handler.register(WINDOW_LOGMESSAGE, cb)

        await handler.handle({"method": WINDOW_LOGMESSAGE, "params": {"message": "hi"}})

        cb.assert_awaited_once()
        args = cb.call_args[0]
        assert args[0] is mock_document
        assert args[1]["method"] == WINDOW_LOGMESSAGE

    @pytest.mark.asyncio
    async def test_multiple_callbacks_for_same_method_all_called(self, handler):
        cb1, cb2 = AsyncMock(), AsyncMock()
        handler.register(WINDOW_LOGMESSAGE, cb1)
        handler.register(WINDOW_LOGMESSAGE, cb2)

        await handler.handle({"method": WINDOW_LOGMESSAGE, "params": {}})

        cb1.assert_awaited_once()
        cb2.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_unrecognised_method_logs_warning(self, handler, caplog):
        import logging

        with caplog.at_level(logging.WARNING):
            await handler.handle({"method": "unknown/method"})

        assert any("Unhandled" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_server_response_with_result_logs_debug(self, handler, caplog):
        import logging

        with caplog.at_level(logging.DEBUG):
            await handler.handle({"id": 1, "result": {"capabilities": {}}})

        # Should not raise and should not log a warning
        assert not any("Unhandled" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_server_error_response_logs_error(self, handler, caplog):
        import logging

        with caplog.at_level(logging.ERROR):
            await handler.handle(
                {"id": 1, "error": {"code": -32600, "message": "Invalid Request"}}
            )

        assert any("error" in r.message.lower() for r in caplog.records)

    @pytest.mark.asyncio
    async def test_unrecognised_message_shape_logs_warning(self, handler, caplog):
        import logging

        with caplog.at_level(logging.WARNING):
            await handler.handle({"jsonrpc": "2.0"})

        assert any("Unrecognised" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_pide_decoration_raises_without_document(self, handler):
        with pytest.raises(Exception, match="document not set"):
            await handler.handle(
                {
                    "method": PIDE_DECORATION,
                    "params": {"uri": "file:///x.thy"},
                }
            )

    @pytest.mark.asyncio
    async def test_pide_decoration_skips_wrong_uri(self, handler, mock_document):
        handler.set_document(mock_document)
        cb = AsyncMock()
        handler.register(PIDE_DECORATION, cb)

        await handler.handle(
            {
                "method": PIDE_DECORATION,
                "params": {"uri": "file:///other.thy"},
            }
        )

        cb.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_pide_decoration_calls_callback_for_matching_uri(
        self, handler, mock_document
    ):
        handler.set_document(mock_document)
        cb = AsyncMock()
        handler.register(PIDE_DECORATION, cb)

        await handler.handle(
            {
                "method": PIDE_DECORATION,
                "params": {"uri": mock_document.uri},
            }
        )

        cb.assert_awaited_once()


class TestOnStartOnTimeout:
    @pytest.mark.asyncio
    async def test_on_start_calls_all_registered_callbacks(
        self, handler, mock_document
    ):
        handler.set_document(mock_document)
        cb1, cb2 = AsyncMock(), AsyncMock()
        handler.register_on_start(cb1)
        handler.register_on_start(cb2)

        await handler.on_start()

        cb1.assert_awaited_once_with(mock_document)
        cb2.assert_awaited_once_with(mock_document)

    @pytest.mark.asyncio
    async def test_on_timeout_calls_all_registered_callbacks(self, handler):
        cb = AsyncMock()
        handler.register_on_timeout(cb)

        await handler.on_timeout()

        cb.assert_awaited_once_with(handler.document)


class TestWorkDoneProgress:
    @pytest.mark.asyncio
    async def test_progress_callback_is_called(self, handler):
        cb = AsyncMock()
        handler.register_on_progress(cb)

        await handler.handle(_progress("t1", {"kind": "begin", "title": "Build"}))

        cb.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_begin_tracked_by_token(self, handler):
        await handler.handle(
            _progress("t1", {"kind": "begin", "title": "Build", "percentage": 0})
        )

        assert isinstance(handler.progress["t1"], WorkDoneProgressBegin)
        assert handler.progress["t1"].title == "Build"

    @pytest.mark.asyncio
    async def test_report_updates_tracked_state(self, handler):
        await handler.handle(_progress("t1", {"kind": "begin", "title": "Build"}))
        await handler.handle(
            _progress("t1", {"kind": "report", "percentage": 42, "message": "x"})
        )

        assert isinstance(handler.progress["t1"], WorkDoneProgressReport)
        assert handler.progress["t1"].percentage == 42

    @pytest.mark.asyncio
    async def test_report_without_begin_is_not_tracked(self, handler):
        await handler.handle(_progress("t1", {"kind": "report", "percentage": 10}))

        assert "t1" not in handler.progress

    @pytest.mark.asyncio
    async def test_end_clears_tracked_state(self, handler):
        await handler.handle(_progress("t1", {"kind": "begin", "title": "Build"}))
        await handler.handle(_progress("t1", {"kind": "end", "message": "done"}))

        assert "t1" not in handler.progress

    @pytest.mark.asyncio
    async def test_progress_without_callback_does_not_warn(self, handler, caplog):
        import logging

        with caplog.at_level(logging.WARNING):
            await handler.handle(_progress("t1", {"kind": "begin", "title": "Build"}))

        assert not any("Unhandled" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_create_request_dispatched_to_callback(self, handler):
        cb = AsyncMock()
        handler.register_on_work_done_progress_create(cb)

        await handler.handle(
            {
                "id": 7,
                "method": WORK_DONE_PROGRESS_CREATE,
                "params": {"token": "t1"},
            }
        )

        cb.assert_awaited_once()
        assert cb.call_args[0][1]["id"] == 7


class TestDynamicOutput:
    @pytest.mark.asyncio
    async def test_dynamic_output_is_parsed_and_tracked(self, handler, mock_document):
        handler.set_document(mock_document)

        await handler.handle(
            {
                "method": PIDE_DYNAMIC_OUTPUT,
                "params": {
                    "content": "goal (1 subgoal):",
                    "decorations": [
                        {"type": "text_keyword1", "content": [{"range": [0, 0, 0, 4]}]}
                    ],
                },
            }
        )

        assert isinstance(handler.dynamic_output, DynamicOutput)
        assert handler.dynamic_output.content == "goal (1 subgoal):"
        assert handler.dynamic_output.decorations[0].type == "text_keyword1"

    @pytest.mark.asyncio
    async def test_dynamic_output_callback_still_receives_raw_response(
        self, handler, mock_document
    ):
        handler.set_document(mock_document)
        cb = AsyncMock()
        handler.register_on_dynamic_output(cb)

        await handler.handle(
            {"method": PIDE_DYNAMIC_OUTPUT, "params": {"content": "x"}}
        )

        cb.assert_awaited_once()
        # The callback contract is unchanged: raw dict, not the parsed model.
        assert cb.call_args[0][1]["params"]["content"] == "x"

    @pytest.mark.asyncio
    async def test_dynamic_output_requires_document(self, handler):
        with pytest.raises(Exception, match="document not set"):
            await handler.handle(
                {"method": PIDE_DYNAMIC_OUTPUT, "params": {"content": "x"}}
            )

    @pytest.mark.asyncio
    async def test_malformed_dynamic_output_keeps_previous(
        self, handler, mock_document
    ):
        handler.set_document(mock_document)
        await handler.handle(
            {"method": PIDE_DYNAMIC_OUTPUT, "params": {"content": "first"}}
        )
        # decorations of the wrong shape must not clobber the tracked value.
        await handler.handle(
            {
                "method": PIDE_DYNAMIC_OUTPUT,
                "params": {"content": "second", "decorations": [{"range": [0, 0]}]},
            }
        )

        assert handler.dynamic_output.content == "first"


class TestDecorationTracking:
    @pytest.mark.asyncio
    async def test_decoration_is_parsed_and_tracked(self, handler, mock_document):
        handler.set_document(mock_document)

        await handler.handle(
            {
                "method": PIDE_DECORATION,
                "params": {
                    "uri": mock_document.uri,
                    "entries": [
                        {"type": "text_keyword1", "content": [{"range": [0, 0, 0, 6]}]}
                    ],
                },
            }
        )

        assert isinstance(handler.decorations, DecorationParams)
        assert handler.decorations.uri == mock_document.uri
        assert handler.decorations.entries[0].type == "text_keyword1"

    @pytest.mark.asyncio
    async def test_decoration_for_other_document_not_tracked(
        self, handler, mock_document
    ):
        handler.set_document(mock_document)

        await handler.handle(
            {
                "method": PIDE_DECORATION,
                "params": {"uri": "file:///other.thy", "entries": []},
            }
        )

        # Decorations for a non-main document are dropped before tracking.
        assert handler.decorations is None

    @pytest.mark.asyncio
    async def test_malformed_decoration_keeps_previous(self, handler, mock_document):
        handler.set_document(mock_document)
        await handler.handle(
            {
                "method": PIDE_DECORATION,
                "params": {
                    "uri": mock_document.uri,
                    "entries": [{"type": "first", "content": []}],
                },
            }
        )
        # An entry missing the required `type` must not clobber the tracked value.
        await handler.handle(
            {
                "method": PIDE_DECORATION,
                "params": {"uri": mock_document.uri, "entries": [{"content": []}]},
            }
        )

        assert handler.decorations.entries[0].type == "first"


class TestProgressNodesTracking:
    PARAMS = {
        "nodes-status": [
            {"name": "Theory.thy", "unprocessed": 1, "running": 0, "finished": 3}
        ]
    }

    @pytest.mark.asyncio
    async def test_progress_is_parsed_and_tracked(self, handler):
        await handler.handle({"method": PIDE_PROGRESS, "params": self.PARAMS})

        assert isinstance(handler.progress_nodes, ProgressNodes)
        assert handler.progress_nodes.nodes_status[0].name == "Theory.thy"
        assert handler.progress_nodes.nodes_status[0].finished == 3

    @pytest.mark.asyncio
    async def test_progress_needs_no_document(self, handler):
        # PIDE/progress is server-wide; it must not require a main document.
        await handler.handle({"method": PIDE_PROGRESS, "params": self.PARAMS})
        assert handler.progress_nodes is not None

    @pytest.mark.asyncio
    async def test_progress_callback_receives_raw_response(self, handler):
        cb = AsyncMock()
        handler.register_on_pide_progress(cb)

        await handler.handle({"method": PIDE_PROGRESS, "params": self.PARAMS})

        cb.assert_awaited_once()
        assert cb.call_args[0][1]["params"] == self.PARAMS

    @pytest.mark.asyncio
    async def test_progress_without_callback_does_not_warn(self, handler, caplog):
        import logging

        with caplog.at_level(logging.WARNING):
            await handler.handle({"method": PIDE_PROGRESS, "params": self.PARAMS})

        assert not any("Unhandled" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_malformed_progress_keeps_previous(self, handler):
        await handler.handle({"method": PIDE_PROGRESS, "params": self.PARAMS})
        # A node entry missing the required `name` must not clobber the snapshot.
        await handler.handle(
            {"method": PIDE_PROGRESS, "params": {"nodes-status": [{"running": 1}]}}
        )

        assert handler.progress_nodes.nodes_status[0].name == "Theory.thy"


def _diagnostics(uri, *lines):
    return {
        "method": TEXTDOCUMENT_PUBLISHDIAGNOSTICS,
        "params": {
            "uri": uri,
            "diagnostics": [
                {
                    "range": {
                        "start": {"line": line, "character": 0},
                        "end": {"line": line, "character": 1},
                    },
                    "message": f"err {line}",
                    "severity": 1,
                }
                for line in lines
            ],
        },
    }


class TestPublishDiagnostics:
    @pytest.mark.asyncio
    async def test_diagnostics_held_per_uri(self, handler):
        await handler.handle(_diagnostics("file:///A.thy", 3, 7))

        held = handler.diagnostics["file:///A.thy"]
        assert [d.range.start.line for d in held] == [3, 7]
        assert held[0].message == "err 3"

    @pytest.mark.asyncio
    async def test_diagnostics_for_imported_theory_needs_no_main_document(
        self, handler
    ):
        # No main document set; diagnostics for an imported theory still land.
        await handler.handle(_diagnostics("file:///Imported.thy", 1))
        assert "file:///Imported.thy" in handler.diagnostics

    @pytest.mark.asyncio
    async def test_republish_replaces_previous_set(self, handler):
        await handler.handle(_diagnostics("file:///A.thy", 3, 7))
        await handler.handle(_diagnostics("file:///A.thy", 5))

        assert [d.range.start.line for d in handler.diagnostics["file:///A.thy"]] == [5]

    @pytest.mark.asyncio
    async def test_cleared_document_stores_empty_list(self, handler):
        await handler.handle(_diagnostics("file:///A.thy", 3))
        await handler.handle(_diagnostics("file:///A.thy"))

        assert handler.diagnostics["file:///A.thy"] == []

    @pytest.mark.asyncio
    async def test_multiple_uris_tracked_independently(self, handler):
        await handler.handle(_diagnostics("file:///A.thy", 1))
        await handler.handle(_diagnostics("file:///B.thy", 2, 3))

        assert set(handler.diagnostics) == {"file:///A.thy", "file:///B.thy"}
        assert len(handler.diagnostics["file:///B.thy"]) == 2

    @pytest.mark.asyncio
    async def test_callback_runs_after_store_in_registration_order(self, handler):
        seen = []

        async def cb1(_doc, response, _ts):
            # The handler store is updated before callbacks fire.
            uri = response["params"]["uri"]
            seen.append(("cb1", len(handler.diagnostics[uri])))

        async def cb2(_doc, response, _ts):
            seen.append(("cb2", None))

        handler.register_on_publish_diagnostics(cb1)
        handler.register_on_publish_diagnostics(cb2)

        await handler.handle(_diagnostics("file:///A.thy", 1, 2))

        assert [name for name, _ in seen] == ["cb1", "cb2"]
        assert seen[0] == ("cb1", 2)

    @pytest.mark.asyncio
    async def test_malformed_diagnostics_keeps_previous(self, handler):
        await handler.handle(_diagnostics("file:///A.thy", 3))
        # A diagnostic missing the required `range` must not clobber the set.
        await handler.handle(
            {
                "method": TEXTDOCUMENT_PUBLISHDIAGNOSTICS,
                "params": {
                    "uri": "file:///A.thy",
                    "diagnostics": [{"message": "no range"}],
                },
            }
        )

        assert [d.range.start.line for d in handler.diagnostics["file:///A.thy"]] == [3]

    @pytest.mark.asyncio
    async def test_diagnostics_without_callback_does_not_warn(self, handler, caplog):
        import logging

        with caplog.at_level(logging.WARNING):
            await handler.handle(_diagnostics("file:///A.thy", 1))

        assert not any("Unhandled" in r.message for r in caplog.records)


_APPLY_EDIT = {
    "edit": {
        "documentChanges": [
            {
                "textDocument": {"uri": "file:///A.thy", "version": 2},
                "edits": [
                    {
                        "range": {
                            "start": {"line": 1, "character": 0},
                            "end": {"line": 1, "character": 3},
                        },
                        "newText": "by",
                    }
                ],
            }
        ]
    }
}


class TestApplyEdit:
    @pytest.mark.asyncio
    async def test_apply_edit_is_parsed_and_tracked(self, handler):
        await handler.handle({"method": WORKSPACE_APPLYEDIT, "params": _APPLY_EDIT})

        assert isinstance(handler.last_apply_edit, ApplyWorkspaceEditParams)
        change = handler.last_apply_edit.edit.document_changes[0]
        assert change.uri == "file:///A.thy"
        assert change.edits[0].new_text == "by"

    @pytest.mark.asyncio
    async def test_apply_edit_callback_receives_raw_response(self, handler):
        cb = AsyncMock()
        handler.register_on_apply_edit(cb)

        await handler.handle({"method": WORKSPACE_APPLYEDIT, "params": _APPLY_EDIT})

        cb.assert_awaited_once()
        assert cb.call_args[0][1]["params"] == _APPLY_EDIT

    @pytest.mark.asyncio
    async def test_apply_edit_without_callback_does_not_warn(self, handler, caplog):
        import logging

        with caplog.at_level(logging.WARNING):
            await handler.handle({"method": WORKSPACE_APPLYEDIT, "params": _APPLY_EDIT})

        assert not any("Unhandled" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_malformed_apply_edit_keeps_previous(self, handler):
        await handler.handle({"method": WORKSPACE_APPLYEDIT, "params": _APPLY_EDIT})
        # `edit` is required; a payload without it must not clobber the value.
        await handler.handle({"method": WORKSPACE_APPLYEDIT, "params": {}})

        assert handler.last_apply_edit is not None

    @pytest.mark.asyncio
    async def test_apply_workspace_edit_routes_to_matching_document(self, handler):
        doc = MagicMock()
        doc.uri = "file:///A.thy"
        doc.apply_text_edits = AsyncMock()
        handler.set_document(doc)

        edit = parse_apply_edit(_APPLY_EDIT).edit
        await handler.apply_workspace_edit(edit)

        doc.apply_text_edits.assert_awaited_once()
        applied = doc.apply_text_edits.call_args[0][0]
        assert applied[0].new_text == "by"

    @pytest.mark.asyncio
    async def test_apply_workspace_edit_routes_to_added_document(self, handler):
        doc = MagicMock()
        doc.uri = "file:///A.thy"
        doc.apply_text_edits = AsyncMock()
        handler.add_document(doc)

        await handler.apply_workspace_edit(parse_apply_edit(_APPLY_EDIT).edit)

        doc.apply_text_edits.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_apply_workspace_edit_skips_unknown_uri(self, handler, caplog):
        import logging

        other = MagicMock()
        other.uri = "file:///Other.thy"
        other.apply_text_edits = AsyncMock()
        handler.set_document(other)

        with caplog.at_level(logging.WARNING):
            await handler.apply_workspace_edit(parse_apply_edit(_APPLY_EDIT).edit)

        other.apply_text_edits.assert_not_awaited()
        assert any("unknown document" in r.message for r in caplog.records)


class TestInitializeResult:
    @pytest.mark.asyncio
    async def test_initialize_response_is_captured(self, handler):
        await handler.handle(
            {
                "id": 1,
                "result": {
                    "capabilities": {"positionEncoding": "utf-16"},
                    "serverInfo": {"name": "Isabelle", "version": "2024"},
                },
            }
        )

        assert handler.initialize_result is not None
        assert handler.initialize_result.serverInfo.name == "Isabelle"
        assert handler.initialize_result.capabilities.positionEncoding == "utf-16"

    @pytest.mark.asyncio
    async def test_non_initialize_response_is_ignored(self, handler):
        await handler.handle({"id": 2, "result": {"some": "other-result"}})

        assert handler.initialize_result is None

    @pytest.mark.asyncio
    async def test_first_initialize_result_wins(self, handler):
        await handler.handle(
            {"id": 1, "result": {"capabilities": {}, "serverInfo": {"name": "first"}}}
        )
        await handler.handle(
            {"id": 9, "result": {"capabilities": {}, "serverInfo": {"name": "second"}}}
        )

        assert handler.initialize_result.serverInfo.name == "first"

    @pytest.mark.asyncio
    async def test_error_response_does_not_capture(self, handler):
        await handler.handle(
            {"id": 1, "error": {"code": -32600, "message": "bad request"}}
        )

        assert handler.initialize_result is None


class TestDocuments:
    def test_add_document_stores_by_uri(self, handler, mock_document):
        handler.add_document(mock_document)
        assert handler.documents[mock_document.uri] is mock_document

    def test_set_document_sets_main_document(self, handler, mock_document):
        handler.set_document(mock_document)
        assert handler.document is mock_document
