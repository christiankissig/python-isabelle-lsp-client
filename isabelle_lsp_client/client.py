"""
Language Server Protocol client implementation for Isabelle.
"""

import json
import logging
import os
import urllib.parse
from importlib import resources
from typing import Any, Optional
from uuid import uuid4

from lsp_client import (
    BaseNotification,
    ClientCapabilities,
    ClientInfo,
    CompletionList,
    CompletionParams,
    CompletionRequest,
    DefinitionRequest,
    DocumentHighlight,
    DocumentHighlightRequest,
    DocumentSymbol,
    DocumentSymbolParams,
    DocumentSymbolRequest,
    ExitNotification,
    Hover,
    HoverRequest,
    InitializedNotification,
    InitializeParams,
    InitializeRequest,
    Location,
    LocationLink,
    LSPClient,
    Position,
    ShutdownRequest,
    SymbolInformation,
    TextDocumentDidCloseNotification,
    TextDocumentDidOpenNotification,
    TextDocumentIdentifier,
    TextDocumentItem,
    TextDocumentPositionParams,
    parse_completion_result,
    parse_definition_result,
    parse_document_highlight_result,
    parse_document_symbol_result,
    parse_hover_result,
)

from isabelle_lsp_client.protocol import (
    CaretUpdateRequest,
    ProgressRequest,
    ProgressToken,
    WorkDoneProgressCancelNotification,
    WorkDoneProgressCancelParams,
)

from .version import version

logger = logging.getLogger(__name__)

# Default timeout (seconds) for awaited language-feature requests, so a request
# Isabelle never answers (e.g. textDocument/documentSymbol) fails fast instead of
# hanging the caller.
DEFAULT_LANGUAGE_TIMEOUT = 30.0


class IsabelleClient(object):
    """
    A Language Server Protocol client for Isabelle.
    """

    LANGUAGE_ID = "isabelle"
    ENCODING = "utf-8"

    lspClient: LSPClient

    def __init__(self, lspClient: LSPClient) -> None:
        self.lspClient = lspClient

    def _get_capabilities(self) -> Any:
        capabilities_file = (
            resources.files("isabelle_lsp_client.data") / "capabilities.json"
        )
        with capabilities_file.open("r") as file:
            text = file.read()
        return json.loads(text)

    def _get_client_info(self) -> Any:
        return {
            "name": "python-isabelle-lsp-client",
            "version": version,
        }

    async def initialize(
        self,
        root_uri: str = "file:///",
        workspace_folders: list[dict] | None = None,
        root_path: str | None = None,
        clientCapabilities: Any = None,
    ) -> str:
        workDoneToken = str(uuid4())
        caps_raw = (
            clientCapabilities
            if clientCapabilities is not None
            else self._get_capabilities()
        )
        params = InitializeParams(
            processId=os.getpid(),
            clientInfo=ClientInfo(**self._get_client_info()),
            rootUri=root_uri,
            rootPath=root_path,
            workspaceFolders=workspace_folders,
            capabilities=ClientCapabilities.model_validate(caps_raw),
            trace="off",
            workDoneToken=workDoneToken,
        )
        # Merge serialised params with locale (not modelled in InitializeParams).
        params_dict = params.model_dump(exclude_none=True)
        params_dict["locale"] = "en_US"
        await self.lspClient.send_request(InitializeRequest(params=params_dict))
        await self.lspClient.send_notification(InitializedNotification())
        return workDoneToken

    async def open_text_document(self, uri: str, text: Optional[str] = None) -> None:
        parsed_uri = urllib.parse.urlparse(uri)
        if parsed_uri.scheme != "file":
            raise ValueError(
                f"Invalid URI scheme: {parsed_uri.scheme}, expected 'file'"
            )
        file_path = urllib.parse.unquote(parsed_uri.path)
        if not text:
            with open(file_path, "r") as file:
                text = file.read()
        text_document_item = TextDocumentItem(
            uri=uri, languageId=self.LANGUAGE_ID, version=0, text=text
        )
        notification = TextDocumentDidOpenNotification(
            params={"textDocument": text_document_item.model_dump()}
        )
        await self.lspClient.send_notification(notification)

    async def close_text_document(self, uri: str) -> None:
        """Notify Isabelle that ``uri`` is closed (``textDocument/didClose``)."""
        notification = TextDocumentDidCloseNotification(
            params={"textDocument": {"uri": uri}}
        )
        await self.lspClient.send_notification(notification)

    async def save_text_document(self, uri: str) -> None:
        """Notify Isabelle that ``uri`` was saved (``textDocument/didSave``)."""
        notification = BaseNotification(
            method="textDocument/didSave", params={"textDocument": {"uri": uri}}
        )
        await self.lspClient.send_notification(notification)

    async def shutdown(self) -> None:
        """
        Send the LSP ``shutdown`` request. Best-effort during teardown: the
        response is not awaited, since the read loop is typically already
        stopping.
        """
        await self.lspClient.send_request(ShutdownRequest())

    async def exit(self) -> None:
        """Send the LSP ``exit`` notification, asking the server to terminate."""
        await self.lspClient.send_notification(ExitNotification())

    async def caret_update(self, uri: str, line: int, character: int) -> None:
        logger.info(f"Sending caret update request: {uri}, {line}, {character}")
        await self.lspClient.send_request(CaretUpdateRequest(uri, line, character))

    async def progress_request(self) -> None:
        await self.lspClient.send_notification(ProgressRequest())

    # Language features
    #
    # These send a request and *await* its result (correlated by id in the
    # LSPClient). They must therefore be called from the write/command side —
    # e.g. an ``on_start`` callback or a command coroutine — and NOT from within
    # a read-loop callback (``PIDE/dynamic_output``, ``PIDE/decoration``, ...):
    # the single read loop processes one message at a time, so awaiting a
    # response from inside a callback would prevent that response from ever being
    # read.
    #
    # Each takes a ``timeout`` (seconds): Isabelle does not answer every request
    # — notably ``textDocument/documentSymbol`` is not implemented by its
    # ``vscode_server`` and never replies — so an unbounded wait would hang the
    # caller. On timeout ``asyncio.TimeoutError`` is raised (and the request is
    # cancelled). Pass ``timeout=None`` to wait indefinitely.

    def _position_params(
        self, uri: str, line: int, character: int
    ) -> TextDocumentPositionParams:
        return TextDocumentPositionParams(
            textDocument=TextDocumentIdentifier(uri=uri),
            position=Position(line=line, character=character),
        )

    async def hover(
        self,
        uri: str,
        line: int,
        character: int,
        timeout: float | None = DEFAULT_LANGUAGE_TIMEOUT,
    ) -> Hover | None:
        """Request ``textDocument/hover`` at a position; ``None`` if no hover."""
        result = await self.lspClient.request(
            HoverRequest(params=self._position_params(uri, line, character)),
            timeout=timeout,
        )
        return parse_hover_result(result)

    async def definition(
        self,
        uri: str,
        line: int,
        character: int,
        timeout: float | None = DEFAULT_LANGUAGE_TIMEOUT,
    ) -> list[Location] | list[LocationLink] | None:
        """Request ``textDocument/definition`` at a position."""
        result = await self.lspClient.request(
            DefinitionRequest(params=self._position_params(uri, line, character)),
            timeout=timeout,
        )
        return parse_definition_result(result)

    async def document_highlight(
        self,
        uri: str,
        line: int,
        character: int,
        timeout: float | None = DEFAULT_LANGUAGE_TIMEOUT,
    ) -> list[DocumentHighlight] | None:
        """Request ``textDocument/documentHighlight`` at a position."""
        result = await self.lspClient.request(
            DocumentHighlightRequest(
                params=self._position_params(uri, line, character)
            ),
            timeout=timeout,
        )
        return parse_document_highlight_result(result)

    async def completion(
        self,
        uri: str,
        line: int,
        character: int,
        timeout: float | None = DEFAULT_LANGUAGE_TIMEOUT,
    ) -> CompletionList | None:
        """
        Request ``textDocument/completion`` at a position. A bare item array is
        normalised to a :class:`CompletionList`.
        """
        params = CompletionParams(
            textDocument=TextDocumentIdentifier(uri=uri),
            position=Position(line=line, character=character),
        )
        result = await self.lspClient.request(
            CompletionRequest(params=params), timeout=timeout
        )
        return parse_completion_result(result)

    async def document_symbol(
        self, uri: str, timeout: float | None = DEFAULT_LANGUAGE_TIMEOUT
    ) -> list[DocumentSymbol] | list[SymbolInformation] | None:
        """
        Request ``textDocument/documentSymbol`` for a document (theory outline).

        Note: Isabelle's ``vscode_server`` does not currently answer this
        request, so it will raise ``asyncio.TimeoutError`` after ``timeout``.
        """
        params = DocumentSymbolParams(textDocument=TextDocumentIdentifier(uri=uri))
        result = await self.lspClient.request(
            DocumentSymbolRequest(params=params), timeout=timeout
        )
        return parse_document_symbol_result(result)

    async def acknowledge_work_done_progress_create(self, request_id: int) -> None:
        """
        Respond to a server-initiated ``window/workDoneProgress/create`` request.

        The request requires a response before the server starts reporting
        progress against the created token; a ``null`` result acknowledges it.
        """
        logger.info(f"Acknowledging workDoneProgress/create request {request_id}")
        await self.lspClient._send_request(
            {"jsonrpc": "2.0", "id": request_id, "result": None}
        )

    async def cancel_work_done_progress(self, token: ProgressToken) -> None:
        """
        Send ``window/workDoneProgress/cancel`` to cancel a server-initiated,
        cancellable work done progress identified by ``token``.
        """
        logger.info(f"Cancelling workDoneProgress for token {token}")
        await self.lspClient.send_notification(
            WorkDoneProgressCancelNotification(
                params=WorkDoneProgressCancelParams(token=token)
            )
        )
