import logging
import time
from collections import defaultdict
from typing import Any, Callable

from isabelle_lsp_client.document import Document

logger = logging.getLogger(__name__)


PIDE_DECORATION = "PIDE/decoration"
PIDE_DYNAMIC_OUTPUT = "PIDE/dynamic_output"
WINDOW_LOGMESSAGE = "window/logMessage"
WINDOW_SHOWMESSAGE = "window/showMessage"


class ClientHandler:
    # other documents in unfinished heap
    documents: dict[str, Document]
    # main document
    document: Document | None

    on_start_callbacks: list[Callable]
    on_timeout_callbacks: list[Callable]
    callbacks: dict[str, list[Callable[..., Any]]]

    def __init__(self) -> None:
        self.document = None
        self.documents = {}
        self.on_start_callbacks = []
        self.on_timeout_callbacks = []
        self.callbacks = defaultdict(list)

    def add_document(self, document: Document) -> None:
        self.documents[document.uri] = document

    def set_document(self, document: Document) -> None:
        self.document = document

    def register_on_start(self, handler_method: Callable) -> None:
        self.on_start_callbacks.append(handler_method)

    def register_on_timeout(self, handler_method: Callable) -> None:
        self.on_timeout_callbacks.append(handler_method)

    def register_on_decoration(self, handler_method: Callable) -> None:
        self.callbacks[PIDE_DECORATION].append(handler_method)

    def register_on_dynamic_output(self, handler_method: Callable) -> None:
        self.callbacks[PIDE_DYNAMIC_OUTPUT].append(handler_method)

    def register_on_window_logmessage(self, handler_method: Callable) -> None:
        self.callbacks[WINDOW_LOGMESSAGE].append(handler_method)

    def register(self, method: str, handler_method: Callable) -> None:
        self.callbacks[method].append(handler_method)

    async def on_timeout(self, **kwargs: Any) -> None:
        logger.warning("Timeout occurred while waiting for response")
        for callback in self.on_timeout_callbacks:
            await callback(self.document, **kwargs)

    async def on_start(self, **kwargs: Any) -> None:
        for callback in self.on_start_callbacks:
            await callback(self.document, **kwargs)

    async def handle(self, response: dict[Any, Any]) -> None:
        DOCUMENT_REQUIRED = {PIDE_DECORATION, PIDE_DYNAMIC_OUTPUT}
        DOCUMENT_EXACT = {PIDE_DECORATION}

        if "method" in response:
            method = response["method"]
        elif "id" in response:
            # Server response to a client request (result or error).
            if "error" in response:
                logger.error(
                    "Server returned error for id=%s: %s",
                    response["id"],
                    response["error"],
                )
            else:
                logger.debug(
                    "Server response for id=%s: %s",
                    response["id"],
                    response.get("result"),
                )
            return
        else:
            logger.warning("Unrecognised message shape: %s", response)
            return

        if method in DOCUMENT_REQUIRED and not self.document:
            raise Exception("document not set")

        timestamp = time.time_ns() // 1_000_000

        if (
            method in DOCUMENT_EXACT
            and self.document is not None
            and response["params"]["uri"] != self.document.uri
        ):
            logger.error(f"updating wrong file {response['params']['uri']}")
            return

        if method in self.callbacks:
            logger.info(f"Handling response for method {method}")
            for callback in self.callbacks[method]:
                await callback(self.document, response, timestamp)
        else:
            logger.warning(f"Unhandled response for method {method}")
