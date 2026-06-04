import logging
import time
from collections import defaultdict
from typing import Any, Callable

from lsp_client import InitializeResult
from pydantic import ValidationError

from isabelle_lsp_client.document import Document
from isabelle_lsp_client.protocol import (
    PROGRESS,
    WORK_DONE_PROGRESS_CREATE,
    DecorationParams,
    DynamicOutput,
    ProgressToken,
    WorkDoneProgress,
    WorkDoneProgressBegin,
    WorkDoneProgressEnd,
    parse_decoration,
    parse_dynamic_output,
    parse_work_done_progress,
)

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
    # Latest work done progress state, keyed by progress token. Entries are
    # added on a `begin` notification and removed on `end`.
    progress: dict[ProgressToken, WorkDoneProgress]
    # Server capabilities advertised in the `initialize` response, captured the
    # first time a response carrying an `InitializeResult` payload arrives.
    initialize_result: InitializeResult | None
    # Latest PIDE/dynamic_output payload (proof state / output-panel text at the
    # caret), parsed on each notification.
    dynamic_output: DynamicOutput | None
    # Latest PIDE/decoration payload (typed markup for the main document), parsed
    # on each notification that targets the main document.
    decorations: DecorationParams | None

    def __init__(self) -> None:
        self.document = None
        self.documents = {}
        self.on_start_callbacks = []
        self.on_timeout_callbacks = []
        self.callbacks = defaultdict(list)
        self.progress = {}
        self.initialize_result = None
        self.dynamic_output = None
        self.decorations = None

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

    def register_on_progress(self, handler_method: Callable) -> None:
        """Register a callback for ``$/progress`` notifications."""
        self.callbacks[PROGRESS].append(handler_method)

    def register_on_work_done_progress_create(self, handler_method: Callable) -> None:
        """Register a callback for ``window/workDoneProgress/create`` requests."""
        self.callbacks[WORK_DONE_PROGRESS_CREATE].append(handler_method)

    def register(self, method: str, handler_method: Callable) -> None:
        self.callbacks[method].append(handler_method)

    async def on_timeout(self, **kwargs: Any) -> None:
        logger.warning("Timeout occurred while waiting for response")
        for callback in self.on_timeout_callbacks:
            await callback(self.document, **kwargs)

    async def on_start(self, **kwargs: Any) -> None:
        for callback in self.on_start_callbacks:
            await callback(self.document, **kwargs)

    def _capture_initialize_result(self, result: Any) -> None:
        """
        Store the server's ``InitializeResult`` the first time the response to
        the ``initialize`` request arrives. Responses are dispatched here
        asynchronously, so the result is recognised by its ``capabilities``
        field rather than by correlating the request id. Other request results
        and malformed payloads are ignored.
        """
        if self.initialize_result is not None:
            return
        if not isinstance(result, dict) or "capabilities" not in result:
            return
        try:
            self.initialize_result = InitializeResult.model_validate(result)
        except ValidationError as e:
            logger.warning("Could not parse initialize result: %s", e)

    def _track_progress(self, response: dict[Any, Any]) -> None:
        """
        Maintain the per-token work done progress state from a ``$/progress``
        notification. Non work done progress payloads are ignored.
        """
        params = response.get("params") or {}
        token = params.get("token")
        if token is None:
            return
        progress = parse_work_done_progress(params.get("value"))
        if progress is None:
            return
        if isinstance(progress, WorkDoneProgressBegin):
            self.progress[token] = progress
        elif isinstance(progress, WorkDoneProgressEnd):
            # The token is no longer valid once the operation ends.
            self.progress.pop(token, None)
        else:
            # A report only updates the in-flight state if a begin was seen.
            if token in self.progress:
                self.progress[token] = progress

    def _track_dynamic_output(self, response: dict[Any, Any]) -> None:
        """
        Parse and store the latest ``PIDE/dynamic_output`` payload. A malformed
        payload leaves the previous value in place.
        """
        try:
            self.dynamic_output = parse_dynamic_output(response.get("params"))
        except ValidationError as e:
            logger.warning("Could not parse dynamic output: %s", e)

    def _track_decoration(self, response: dict[Any, Any]) -> None:
        """
        Parse and store the latest ``PIDE/decoration`` payload for the main
        document. A malformed payload leaves the previous value in place.
        """
        try:
            self.decorations = parse_decoration(response.get("params"))
        except ValidationError as e:
            logger.warning("Could not parse decoration: %s", e)

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
                self._capture_initialize_result(response.get("result"))
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

        if method == PROGRESS:
            self._track_progress(response)
        elif method == PIDE_DYNAMIC_OUTPUT:
            self._track_dynamic_output(response)
        elif method == PIDE_DECORATION:
            # Reached only after the DOCUMENT_EXACT uri check above, so this
            # decoration targets the main document.
            self._track_decoration(response)

        if self.callbacks.get(method):
            logger.info(f"Handling response for method {method}")
            for callback in self.callbacks[method]:
                await callback(self.document, response, timestamp)
        elif method in (PROGRESS, WORK_DONE_PROGRESS_CREATE):
            # Known work done progress methods are handled internally even
            # without a consumer callback registered.
            logger.debug(f"No consumer callback for method {method}")
        else:
            logger.warning(f"Unhandled response for method {method}")
