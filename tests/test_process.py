import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from isabelle_lsp_client import ClientHandler, IsabelleProcess


def _mock_document(uri, calls):
    doc = MagicMock()
    doc.uri = uri
    doc.close_file = AsyncMock(side_effect=lambda: calls.append(f"close:{uri}"))
    return doc


class TestGracefulShutdown:
    @pytest.fixture
    def process(self):
        return IsabelleProcess(ClientHandler())

    def _isa_client(self, calls):
        isa = MagicMock()
        isa.shutdown = AsyncMock(side_effect=lambda: calls.append("shutdown"))
        isa.exit = AsyncMock(side_effect=lambda: calls.append("exit"))
        return isa

    @pytest.mark.asyncio
    async def test_closes_documents_then_shutdown_then_exit(self, process):
        calls = []
        process.isaClient = self._isa_client(calls)
        process.clientHandler.add_document(_mock_document("file:///B.thy", calls))
        process.clientHandler.set_document(_mock_document("file:///A.thy", calls))

        await process._graceful_lsp_shutdown()

        # Documents are closed first, then the shutdown/exit handshake in order.
        assert calls[-2:] == ["shutdown", "exit"]
        assert set(calls[:-2]) == {"close:file:///B.thy", "close:file:///A.thy"}

    @pytest.mark.asyncio
    async def test_each_uri_closed_once(self, process):
        calls = []
        process.isaClient = self._isa_client(calls)
        doc = _mock_document("file:///A.thy", calls)
        process.clientHandler.add_document(doc)
        process.clientHandler.set_document(doc)

        await process._graceful_lsp_shutdown()

        assert calls.count("close:file:///A.thy") == 1

    @pytest.mark.asyncio
    async def test_errors_are_swallowed(self, process):
        process.isaClient = MagicMock()
        process.isaClient.shutdown = AsyncMock(side_effect=RuntimeError("gone"))
        process.isaClient.exit = AsyncMock()

        # Must not raise even though shutdown fails.
        await process._graceful_lsp_shutdown()
        process.isaClient.exit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_noop_without_isa_client(self, process):
        # No isaClient assigned (e.g. startup failed early) — must be a no-op.
        await process._graceful_lsp_shutdown()

    @pytest.mark.asyncio
    async def test_shutdown_process_runs_graceful_then_terminates(self, process):
        process._graceful_lsp_shutdown = AsyncMock()
        proc = MagicMock()
        proc.returncode = None
        proc.stdin = MagicMock()
        proc.stdin.wait_closed = AsyncMock()
        proc.wait = AsyncMock()
        process._process = proc

        await process._shutdown_process()

        process._graceful_lsp_shutdown.assert_awaited_once()
        proc.terminate.assert_called_once()


class TestIsabelleProcessTimeout:
    """Test suite for IsabelleProcess timeout handling in read_loop."""

    @pytest.fixture
    def mock_client_handler(self):
        """Create a mock ClientHandler with necessary methods."""
        handler = MagicMock(spec=ClientHandler)
        handler.register = MagicMock()
        handler.on_timeout = AsyncMock()
        return handler

    @pytest.fixture
    def isabelle_process(self, mock_client_handler):
        """Create an IsabelleProcess instance with mocked dependencies."""
        return IsabelleProcess(mock_client_handler, timeout=5)

    @pytest.fixture
    def mock_lsp_client(self):
        """Create a mock LSPClient."""
        client = MagicMock()
        client.read_response = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_cancelled_error_triggers_client_handler_on_timeout(
        self, isabelle_process, mock_client_handler, mock_lsp_client
    ):
        """Test that TimeoutError triggers client handler's on_timeout method."""
        isabelle_process.lspClient = mock_lsp_client

        async def side_effect():
            if mock_lsp_client.read_response.call_count == 1:
                raise TimeoutError("Task timed out")
            else:
                isabelle_process.on_finished()
                return None

        mock_lsp_client.read_response.side_effect = side_effect

        result = await isabelle_process.read_loop()

        assert result is True
        assert mock_lsp_client.read_response.call_count == 2
        mock_client_handler.on_timeout.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_timeout_when_timeout_disabled(
        self, mock_client_handler, mock_lsp_client
    ):
        """Test that no timeout handling occurs when timeout is disabled (timeout <= 0)."""
        isabelle_process = IsabelleProcess(mock_client_handler, timeout=0)
        isabelle_process.lspClient = mock_lsp_client

        call_count = 0

        async def side_effect():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise TimeoutError("Task was cancelled")
            else:
                isabelle_process.on_finished()
                return None

        mock_lsp_client.read_response.side_effect = side_effect

        result = await isabelle_process.read_loop()

        assert result is True
        assert call_count == 2
        # With timeout=0 the loop calls read_response directly (no wait_for wrapper),
        # so a raw TimeoutError from read_response is still caught and on_timeout fires.
        mock_client_handler.on_timeout.assert_called_once()

    @pytest.mark.asyncio
    async def test_normal_operation_without_timeout(
        self, isabelle_process, mock_client_handler, mock_lsp_client
    ):
        """Test normal operation without any timeout or cancellation."""
        isabelle_process.lspClient = mock_lsp_client

        call_count = 0

        async def side_effect():
            nonlocal call_count
            call_count += 1
            if call_count >= 3:
                isabelle_process.on_finished()
            return {"response": "ok"}

        mock_lsp_client.read_response.side_effect = side_effect

        result = await isabelle_process.read_loop()

        assert result is True
        assert call_count >= 3
        mock_client_handler.on_timeout.assert_not_called()

    @pytest.mark.asyncio
    async def test_multiple_timeouts_handled_correctly(
        self, isabelle_process, mock_client_handler, mock_lsp_client
    ):
        """Test that multiple consecutive timeouts are handled correctly."""
        isabelle_process.lspClient = mock_lsp_client

        call_count = 0

        async def side_effect():
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                raise asyncio.TimeoutError("Timeout occurred")
            else:
                isabelle_process.on_finished()
                return None

        mock_lsp_client.read_response.side_effect = side_effect

        result = await isabelle_process.read_loop()

        assert result is True
        assert call_count == 4
        assert mock_client_handler.on_timeout.call_count == 3

    @pytest.mark.asyncio
    async def test_script_done_immediately_exits_loop(
        self, isabelle_process, mock_client_handler, mock_lsp_client
    ):
        """Test that read_loop exits immediately when already finished before entry."""
        isabelle_process.lspClient = mock_lsp_client
        isabelle_process.on_finished()  # set the done event before entering the loop

        result = await isabelle_process.read_loop()

        assert result is True
        mock_lsp_client.read_response.assert_not_called()
        mock_client_handler.on_timeout.assert_not_called()

    @pytest.mark.asyncio
    async def test_acknowledge_work_done_progress_create_responds(
        self, isabelle_process
    ):
        """The create request is acknowledged via the Isabelle client."""
        isabelle_process.isaClient = MagicMock()
        isabelle_process.isaClient.acknowledge_work_done_progress_create = AsyncMock()

        await isabelle_process.acknowledge_work_done_progress_create(
            None,
            {"id": 9, "method": "window/workDoneProgress/create", "params": {}},
            "ts",
        )

        isabelle_process.isaClient.acknowledge_work_done_progress_create.assert_awaited_once_with(
            9
        )

    @pytest.mark.asyncio
    async def test_acknowledge_work_done_progress_create_without_id_noop(
        self, isabelle_process
    ):
        """A malformed create request without an id is ignored."""
        isabelle_process.isaClient = MagicMock()
        isabelle_process.isaClient.acknowledge_work_done_progress_create = AsyncMock()

        await isabelle_process.acknowledge_work_done_progress_create(
            None, {"method": "window/workDoneProgress/create"}, "ts"
        )

        isabelle_process.isaClient.acknowledge_work_done_progress_create.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_wait_for_called_with_correct_timeout(
        self, isabelle_process, mock_client_handler, mock_lsp_client
    ):
        """Test that asyncio.wait_for is called with the correct timeout value."""
        isabelle_process.lspClient = mock_lsp_client

        with patch("asyncio.wait_for") as mock_wait_for:

            async def wait_for_side_effect(coro, timeout):
                isabelle_process.on_finished()
                return await coro

            mock_wait_for.side_effect = wait_for_side_effect
            mock_lsp_client.read_response.return_value = {"response": "ok"}

            result = await isabelle_process.read_loop()

            assert result is True
            mock_wait_for.assert_called_once()
            args, kwargs = mock_wait_for.call_args
            assert len(args) == 2
            assert args[1] == 5  # timeout value from fixture
