import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from asyncio.exceptions import CancelledError

# Assuming the IsabelleProcess class is in a module called isabelle_process
from isabelle_lsp_client import IsabelleProcess, ClientHandler


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
        """Test that CancelledError triggers client handler's on_timeout method."""
        # Setup
        isabelle_process.lspClient = mock_lsp_client
        isabelle_process.script_done = False

        # Configure the mock to raise CancelledError on first call, then set script_done
        async def side_effect():
            if mock_lsp_client.read_response.call_count == 1:
                raise CancelledError("Task was cancelled")
            else:
                isabelle_process.script_done = True
                return None

        mock_lsp_client.read_response.side_effect = side_effect

        # Execute
        result = await isabelle_process.read_loop()

        # Verify
        assert result is True
        assert mock_lsp_client.read_response.call_count == 2
        mock_client_handler.on_timeout.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_timeout_when_timeout_disabled(
        self, mock_client_handler, mock_lsp_client
    ):
        """Test that no timeout handling occurs when timeout is disabled (timeout <= 0)."""
        # Setup - Create IsabelleProcess with timeout disabled
        isabelle_process = IsabelleProcess(mock_client_handler, timeout=0)
        isabelle_process.lspClient = mock_lsp_client
        isabelle_process.script_done = False

        # Configure the mock to raise CancelledError on first call, then set script_done
        call_count = 0

        async def side_effect():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise CancelledError("Task was cancelled")
            else:
                isabelle_process.script_done = True
                return None

        mock_lsp_client.read_response.side_effect = side_effect

        # Execute
        result = await isabelle_process.read_loop()

        # Verify
        assert result is True
        assert call_count == 2
        mock_client_handler.on_timeout.assert_called_once()

    @pytest.mark.asyncio
    async def test_normal_operation_without_timeout(
        self, isabelle_process, mock_client_handler, mock_lsp_client
    ):
        """Test normal operation without any timeout or cancellation."""
        # Setup
        isabelle_process.lspClient = mock_lsp_client
        isabelle_process.script_done = False

        # Configure the mock to return normally a few times, then set script_done
        call_count = 0

        async def side_effect():
            nonlocal call_count
            call_count += 1
            if call_count >= 3:
                isabelle_process.script_done = True
            return {"response": "ok"}

        mock_lsp_client.read_response.side_effect = side_effect

        # Execute
        result = await isabelle_process.read_loop()

        # Verify
        assert result is True
        assert call_count >= 3
        mock_client_handler.on_timeout.assert_not_called()

    @pytest.mark.asyncio
    async def test_multiple_timeouts_handled_correctly(
        self, isabelle_process, mock_client_handler, mock_lsp_client
    ):
        """Test that multiple consecutive timeouts are handled correctly."""
        # Setup
        isabelle_process.lspClient = mock_lsp_client
        isabelle_process.script_done = False

        # Configure the mock to raise CancelledError multiple times, then complete
        call_count = 0

        async def side_effect():
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                raise asyncio.exceptions.CancelledError("Timeout occurred")
            else:
                isabelle_process.script_done = True
                return None

        mock_lsp_client.read_response.side_effect = side_effect

        # Execute
        result = await isabelle_process.read_loop()

        # Verify
        assert result is True
        assert call_count == 4
        # on_timeout should be called 3 times (once for each timeout)
        assert mock_client_handler.on_timeout.call_count == 3

    @pytest.mark.asyncio
    async def test_script_done_immediately_exits_loop(
        self, isabelle_process, mock_client_handler, mock_lsp_client
    ):
        """Test that read_loop exits immediately when script_done is True."""
        # Setup
        isabelle_process.lspClient = mock_lsp_client
        isabelle_process.script_done = True  # Set to True immediately

        # Execute
        result = await isabelle_process.read_loop()

        # Verify
        assert result is True
        # read_response should never be called since script_done is already True
        mock_lsp_client.read_response.assert_not_called()
        mock_client_handler.on_timeout.assert_not_called()

    @pytest.mark.asyncio
    async def test_wait_for_called_with_correct_timeout(
        self, isabelle_process, mock_client_handler, mock_lsp_client
    ):
        """Test that asyncio.wait_for is called with the correct timeout value."""
        # Setup
        isabelle_process.lspClient = mock_lsp_client
        isabelle_process.script_done = False

        with patch("asyncio.wait_for") as mock_wait_for:
            # Configure wait_for to set script_done after first call
            async def wait_for_side_effect(coro, timeout):
                isabelle_process.script_done = True
                return await coro

            mock_wait_for.side_effect = wait_for_side_effect
            mock_lsp_client.read_response.return_value = {"response": "ok"}

            # Execute
            result = await isabelle_process.read_loop()

            # Verify
            assert result is True
            mock_wait_for.assert_called_once()
            # Check that wait_for was called with correct timeout
            args, kwargs = mock_wait_for.call_args
            assert len(args) == 2
            assert args[1] == 5  # timeout value from fixture
