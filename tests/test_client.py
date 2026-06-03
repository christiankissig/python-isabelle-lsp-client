from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest

from isabelle_lsp_client.client import IsabelleClient

URI = "file:///path/to/Theory.thy"


@pytest.fixture
def mock_lsp():
    lsp = MagicMock()
    lsp.send_request = AsyncMock()
    lsp.send_notification = AsyncMock()
    lsp._send_request = AsyncMock()
    return lsp


@pytest.fixture
def client(mock_lsp):
    return IsabelleClient(mock_lsp)


class TestInitialize:
    @pytest.mark.asyncio
    async def test_send_request_called_with_initialize_request(self, client, mock_lsp):
        from lsp_client import InitializeRequest

        await client.initialize(root_uri="file:///workspace")

        mock_lsp.send_request.assert_awaited_once()
        req = mock_lsp.send_request.call_args[0][0]
        assert isinstance(req, InitializeRequest)

    @pytest.mark.asyncio
    async def test_initialized_notification_sent(self, client, mock_lsp):
        from lsp_client import InitializedNotification

        await client.initialize(root_uri="file:///workspace")

        mock_lsp.send_notification.assert_awaited_once()
        notif = mock_lsp.send_notification.call_args[0][0]
        assert isinstance(notif, InitializedNotification)

    @pytest.mark.asyncio
    async def test_params_contain_expected_keys(self, client, mock_lsp):
        await client.initialize(
            root_uri="file:///workspace",
            root_path="/workspace",
        )

        req = mock_lsp.send_request.call_args[0][0]
        params = req.params
        assert "processId" in params
        assert "clientInfo" in params
        assert "capabilities" in params
        assert params["rootUri"] == "file:///workspace"
        assert params["locale"] == "en_US"

    @pytest.mark.asyncio
    async def test_returns_work_done_token(self, client, mock_lsp):
        token = await client.initialize(root_uri="file:///workspace")
        assert isinstance(token, str) and len(token) > 0


class TestOpenTextDocument:
    @pytest.mark.asyncio
    async def test_send_notification_called_for_valid_uri(self, client, mock_lsp):
        from lsp_client import TextDocumentDidOpenNotification

        with patch("builtins.open", mock_open(read_data="theory content")):
            await client.open_text_document(URI)

        mock_lsp.send_notification.assert_awaited_once()
        notif = mock_lsp.send_notification.call_args[0][0]
        assert isinstance(notif, TextDocumentDidOpenNotification)

    @pytest.mark.asyncio
    async def test_notification_contains_correct_language_id(self, client, mock_lsp):
        with patch("builtins.open", mock_open(read_data="content")):
            await client.open_text_document(URI)

        notif = mock_lsp.send_notification.call_args[0][0]
        assert notif.params["textDocument"]["languageId"] == "isabelle"

    @pytest.mark.asyncio
    async def test_raises_for_non_file_uri(self, client, mock_lsp):
        with pytest.raises(ValueError, match="Invalid URI scheme"):
            await client.open_text_document("https://example.com/Theory.thy")

    @pytest.mark.asyncio
    async def test_uses_provided_text_without_reading_file(self, client, mock_lsp):
        await client.open_text_document(URI, text="provided text")

        notif = mock_lsp.send_notification.call_args[0][0]
        assert notif.params["textDocument"]["text"] == "provided text"


class TestCaretUpdate:
    @pytest.mark.asyncio
    async def test_send_request_called_with_caret_update_request(
        self, client, mock_lsp
    ):
        from isabelle_lsp_client.protocol import CaretUpdateRequest

        await client.caret_update(URI, line=3, character=7)

        mock_lsp.send_request.assert_awaited_once()
        req = mock_lsp.send_request.call_args[0][0]
        assert isinstance(req, CaretUpdateRequest)
        assert req.params["uri"] == URI
        assert req.params["line"] == 3
        assert req.params["character"] == 7


class TestWorkDoneProgress:
    @pytest.mark.asyncio
    async def test_acknowledge_create_sends_null_result_response(
        self, client, mock_lsp
    ):
        await client.acknowledge_work_done_progress_create(request_id=7)

        mock_lsp._send_request.assert_awaited_once_with(
            {"jsonrpc": "2.0", "id": 7, "result": None}
        )

    @pytest.mark.asyncio
    async def test_cancel_sends_cancel_notification(self, client, mock_lsp):
        from isabelle_lsp_client.protocol import WorkDoneProgressCancelNotification

        await client.cancel_work_done_progress(token="t1")

        mock_lsp.send_notification.assert_awaited_once()
        notif = mock_lsp.send_notification.call_args[0][0]
        assert isinstance(notif, WorkDoneProgressCancelNotification)
        assert notif.params == {"token": "t1"}
