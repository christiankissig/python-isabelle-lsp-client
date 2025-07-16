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
    document: Document | None = None

    on_start_callbacks: list[Callable] = []
    on_timeout_callbacks: list[Callable] = []
    callbacks: dict[str, list[Callable[..., Any]]] = defaultdict(list)

    def __init__(self) -> None:
        self.document = None

    def set_document(self, document: Document) -> None:
        self.document = document

    def register_on_start(self, handler_method: Callable) -> None:
        self.on_start_callbacks.append(handler_method)

    def register_on_timeout(self, handler_method: Callable) -> None:
        self.on_timeout_callbacks.append(handler_method)

    def register(self, method: str, handler_method: Callable) -> None:
        self.callbacks[method].append(handler_method)

    async def on_timeout(self, **kwargs: Any) -> None:
        logger.warn("Timeout occurred while waiting for response")
        for callback in self.on_timeout_callbacks:
            await callback(self.document, **kwargs)

    async def on_start(self, **kwargs: Any) -> None:
        for callback in self.on_start_callbacks:
            await callback(self.document, **kwargs)

    async def handle(self, response: dict) -> None:
        DOCUMENT_REQUIRED = {PIDE_DECORATION, PIDE_DYNAMIC_OUTPUT}
        DOCUMENT_EXACT = {PIDE_DECORATION}

        if "method" in response:
            method = response["method"]
        else:
            logger.warn(f"Unhandled response: {response}")
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
            logger.warn(f"Unhandled response for method {method}")

    async def on_decoration(self, response: dict) -> None:
        if not self.document:
            raise Exception("document not set")

        timestamp = time.time_ns() // 1_000_000

        if response["params"]["uri"] != self.document.uri:
            logger.error(f"updating wrong file {response['params']['uri']}")
            return

        for callback in self.callbacks[PIDE_DECORATION]:
            await callback(self.document, response, timestamp)

    async def on_dynamic_output(self, response: dict) -> None:
        if not self.document:
            raise Exception("document not set")

        timestamp = time.time_ns() // 1_000_000
        logger.info("updating dynamic output")
        for callback in self.callbacks[PIDE_DYNAMIC_OUTPUT]:
            await callback(self.document, response, timestamp)

    async def on_window_logmessage(self, response: dict) -> None:
        timestamp = time.time_ns() // 1_000_000
        if "params" in response and "message" in response["params"]:
            logger.info(f"logging {response['params']['message']}")
        for callback in self.callbacks[WINDOW_LOGMESSAGE]:
            await callback(self.document, response, timestamp)
