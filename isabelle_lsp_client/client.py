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
    ClientCapabilities,
    ClientInfo,
    InitializedNotification,
    InitializeParams,
    InitializeRequest,
    LSPClient,
    TextDocumentDidOpenNotification,
    TextDocumentItem,
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

    async def caret_update(self, uri: str, line: int, character: int) -> None:
        logger.info(f"Sending caret update request: {uri}, {line}, {character}")
        await self.lspClient.send_request(CaretUpdateRequest(uri, line, character))

    async def progress_request(self) -> None:
        await self.lspClient.send_notification(ProgressRequest())

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
