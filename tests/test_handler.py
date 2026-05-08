from unittest.mock import AsyncMock, MagicMock

import pytest

from isabelle_lsp_client.handler import (
    PIDE_DECORATION,
    PIDE_DYNAMIC_OUTPUT,
    WINDOW_LOGMESSAGE,
    ClientHandler,
)


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
    async def test_on_start_calls_all_registered_callbacks(self, handler, mock_document):
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


class TestDocuments:
    def test_add_document_stores_by_uri(self, handler, mock_document):
        handler.add_document(mock_document)
        assert handler.documents[mock_document.uri] is mock_document

    def test_set_document_sets_main_document(self, handler, mock_document):
        handler.set_document(mock_document)
        assert handler.document is mock_document
