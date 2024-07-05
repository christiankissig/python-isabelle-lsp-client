"""
Language Server Protocol client implementation for Isabelle.
"""


import json
import os
import urllib.parse

from lsp_client import STDIOLSPClient, InitializeRequest, OpenTextDocumentRequest
from isabelle_lsp_client.protocol import CaretUpdateRequest, ProgressRequest
from uuid import uuid4


class IsabelleLSPClient(STDIOLSPClient):
    """
    A Language Server Protocol client for Isabelle.
    """

    ENCODING = "utf-8"

    def __init__(
        self,
        executable: str,
        server_args: list[str] = [],
        callbacks: dict[str, callable] = {}
    ):
        server_args = ["vscode_server"] + server_args
        super().__init__(executable, server_args, callbacks)

    def _get_capabilities(self):
        with open("data/capabilities.json", "r") as file:
            text = file.read()
        return json.loads(text)

    def _get_client_info(self):
        return {
            "name": "python-isabelle-lsp-client",
            "version": "0.1.0"
        }

    def initialize(self, params={}, clientCapabilities=None):
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
        self.send_request(InitializeRequest(os.getpid(), params))
        return workDoneToken

    def open_text_document(self, uri: str, text=None):
        parsed_uri = urllib.parse.urlparse(uri)
        if parsed_uri.scheme != 'file':
            raise ValueError(f"Invalid URI scheme: {parsed_uri.scheme}, expected 'file'")
        file_path = urllib.parse.unquote(parsed_uri.path)
        if not text:
            with open(file_path, "r") as file:
                text = file.read()
        self.send_request(OpenTextDocumentRequest(uri, text))

    def caret_update(self, uri: str, line: int, character: int):
        self.send_request(CaretUpdateRequest(uri, line, character))

    def progress_request(self):
        self.send_request(ProgressRequest())
