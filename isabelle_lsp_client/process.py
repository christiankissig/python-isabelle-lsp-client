import asyncio
import logging
import os
from typing import Any, Literal

from lsp_client import LSPClient

from .client import IsabelleClient
from .document import Document
from .handler import WINDOW_LOGMESSAGE, WINDOW_SHOWMESSAGE, ClientHandler
from .isabelle import is_isabelle_ready

logger = logging.getLogger(__name__)


class IsabelleProcess(object):
    isabelle_ready = False
    script_done = False
    command: Any | None = None

    def __init__(self, clientHandler: ClientHandler, timeout: int = -1) -> None:
        self.clientHandler = clientHandler
        self.clientHandler.register(WINDOW_LOGMESSAGE, self.update_status)
        self.clientHandler.register(WINDOW_SHOWMESSAGE, self.update_status)
        self.timeout = timeout
        self._done_event = asyncio.Event()

    async def start_isabelle(
        self, isabelle_exec: str, isabelle_options: list
    ) -> asyncio.subprocess.Process:
        isabelle_args = [
            "vscode_server",
            "-o",
            "vscode_pide_extensions",
            "-v",
            "-L",
            "/tmp/python-lsp-isa",
            "-o",
            "vscode_html_output=false",
        ]
        isabelle_args.extend(isabelle_options)
        logger.info(f"Starting Isabelle with {isabelle_exec} {' '.join(isabelle_args)}")
        process = await asyncio.create_subprocess_exec(
            isabelle_exec,
            *isabelle_args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            bufsize=0,
        )
        return process

    async def read_loop(self) -> Literal[True]:
        while not self._done_event.is_set():
            try:
                if self.timeout > 0:
                    await asyncio.wait_for(self.lspClient.read_response(), self.timeout)
                else:
                    await self.lspClient.read_response()
            except TimeoutError:
                await self.clientHandler.on_timeout()
        return True

    async def write_loop(self, args: dict) -> Literal[True]:
        self.isabelle_ready = False

        relative_filename = args["theory"]
        file_path = os.path.abspath(relative_filename)
        root_path = os.path.dirname(file_path)

        workspace_name = root_path.split("/")[-1]
        file_uri = "file://" + file_path

        await self.isaClient.initialize(
            {
                "workspaceFolders": [
                    {"uri": "file://" + root_path, "name": workspace_name}
                ],
                "rootUri": "file://" + root_path,
                "rootPath": root_path,
            }
        )

        while True:
            await asyncio.sleep(10)
            if self.isabelle_ready:
                break

        output_suffix = args.get("output_suffix", "_new")

        if "theories" in args:
            for theory in args["theories"]:
                theory_uri = "file://" + os.path.abspath(theory)
                document = Document(
                    self.isaClient, theory_uri, output_suffix=output_suffix
                )
                self.clientHandler.add_document(document)
                logger.info(f"Opening file {theory_uri}")
                await document.open_file()

        document = Document(self.isaClient, file_uri, output_suffix=output_suffix)
        self.clientHandler.set_document(document)
        await document.open_file()

        await self.clientHandler.on_start()

        return True

    async def run(self, args: dict) -> None:
        if "exec" not in args:
            raise ValueError("Isabelle executable not specified in args")

        if "options" in args:
            options = args["options"]
        else:
            options = []

        process = await self.start_isabelle(args["exec"], options)
        response_handler = self.clientHandler.handle
        self.lspClient = LSPClient(process.stdin, process.stdout, response_handler)
        self.isaClient = IsabelleClient(self.lspClient)

        read_task = asyncio.create_task(self.read_loop())
        write_task = asyncio.create_task(self.write_loop(args))
        await asyncio.gather(read_task, write_task)

    async def update_status(
        self, _document: Document, response: dict, _timestamp: str
    ) -> None:
        logger.debug(f"Updating status for message : {response}")
        if (
            "params" in response
            and "message" in response["params"]
            and is_isabelle_ready(response["params"]["message"])
        ):
            logger.debug("Isabelle is ready")
            self.isabelle_ready = True

    def on_finished(self, **kwargs: Any) -> None:
        logger.info("Finished")
        self.script_done = True
        self._done_event.set()
