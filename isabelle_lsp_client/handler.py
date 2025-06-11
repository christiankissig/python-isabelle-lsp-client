import logging
import time
from typing import Any, Callable, List

from isabelle_lsp_client.document import Document

logger = logging.getLogger(__name__)


class ClientHandler:
    document: Document | None = None

    on_start_callbacks: List[Callable] = []
    on_update_decoration: List[Callable] = []
    on_update_dynamic_output: List[Callable] = []
    on_update_window_logmessage: List[Callable] = []

    def __init__(self) -> None:
        pass

    def set_document(self, document: Document) -> None:
        self.document = document

    def register_on_start(self, handler_method: Callable) -> None:
        self.on_start_callbacks.append(handler_method)

    def register_on_decoration(self, handler_method: Callable) -> None:
        self.on_update_decoration.append(handler_method)

    def register_on_dynamic_output(self, handler_method: Callable) -> None:
        self.on_update_dynamic_output.append(handler_method)

    def register_on_window_logmessage(self, handler_method: Callable) -> None:
        self.on_update_window_logmessage.append(handler_method)

    async def on_start(self, **kwargs: Any) -> None:
        for callback in self.on_start_callbacks:
            await callback(self.document, **kwargs)

    async def on_decoration(self, response: dict) -> None:
        if not self.document:
            raise Exception("document not set")

        timestamp = time.time_ns() // 1_000_000

        if response["params"]["uri"] != self.document.uri:
            logger.error(f"updating wrong file {response['params']['uri']}")
            return

        for callback in self.on_update_decoration:
            await callback(self.document, response, timestamp)

    async def on_dynamic_output(self, response: dict) -> None:
        if not self.document:
            raise Exception("document not set")

        timestamp = time.time_ns() // 1_000_000
        logger.info("updating dynamic output")
        for callback in self.on_update_dynamic_output:
            await callback(self.document, response, timestamp)

    async def on_window_logmessage(self, response: dict) -> None:
        timestamp = time.time_ns() // 1_000_000
        if "params" in response and "message" in response["params"]:
            logger.info(f"logging {response['params']['message']}")
        for callback in self.on_update_window_logmessage:
            await callback(self.document, response, timestamp)

    def callbacks(self) -> dict:
        return {
            "PIDE/decoration": self.on_decoration,
            "PIDE/dynamic_output": self.on_dynamic_output,
            "window/logMessage": self.on_window_logmessage,
        }
