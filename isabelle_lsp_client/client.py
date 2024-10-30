"""
Language Server Protocol client implementation for Isabelle.
"""

import json
import logging
import os
import urllib.parse

from importlib import resources

from .version import version

from lsp_client import (
    LSPClient,
    InitializeRequest,
    TextDocument_DidOpen_Request,
    TextDocumentItem
)
from isabelle_lsp_client.protocol import CaretUpdateRequest, ProgressRequest
from uuid import uuid4


logger = logging.getLogger(__name__)


class IsabelleClient(object):
    """
    A Language Server Protocol client for Isabelle.
    """

    LANGUAGE_ID = "isabelle"
    ENCODING = "utf-8"

    lspClient: LSPClient

    def __init__(self, lspClient):
        self.lspClient = lspClient

    def _get_capabilities(self):
        capabilities_file = resources.files("isabelle_lsp_client.data") / "capabilities.json"
        with capabilities_file.open('r') as file:
            text = file.read()
        return json.loads(text)

    def _get_client_info(self):
        return {
            "name": "python-isabelle-lsp-client",
            "version": version,
        }

    async def initialize(self, params={}, clientCapabilities=None):
        workDoneToken = str(uuid4())
        if clientCapabilities is None:
            params["capabilities"] = self._get_capabilities()
        else:
            params["capabilities"] = clientCapabilities
        params["workDoneToken"] = workDoneToken
        params["trace"] = "off"
        params["clientInfo"] = self._get_client_info()
        params["locale"] = "en_US"
        params["processId"] = os.getpid()
        await self.lspClient.send_request(InitializeRequest(params=params))
        return workDoneToken

    async def open_text_document(self, uri: str, text=None):
        parsed_uri = urllib.parse.urlparse(uri)
        if parsed_uri.scheme != 'file':
            raise ValueError(f"Invalid URI scheme: {parsed_uri.scheme}, expected 'file'")
        file_path = urllib.parse.unquote(parsed_uri.path)
        if not text:
            with open(file_path, "r") as file:
                text = file.read()
        text_document_item = TextDocumentItem(
                uri=uri,
                languageId=self.LANGUAGE_ID,
                version=0,
                text=text)
        didopen_request = TextDocument_DidOpen_Request(
                params={"textDocument": text_document_item})
        await self.lspClient.send_request(didopen_request)

    async def caret_update(self, uri: str, line: int, character: int):
        logger.info(f"Sending caret update request: {uri}, {line}, {character}")
        await self.lspClient.send_request(CaretUpdateRequest(uri, line, character))

    async def progress_request(self):
        await self.lspClient.send_request(ProgressRequest())
