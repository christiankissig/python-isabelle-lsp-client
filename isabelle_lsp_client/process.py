import asyncio
import logging
import os

from lsp_client import LSPClient

from .client import IsabelleClient
from .document import Document
from .handler import ClientHandler

logger = logging.getLogger(__name__)

class IsabelleProcess(object):

    isabelle_ready = False
    script_done = False

    def __init__(self, clientHandler:ClientHandler):
        self.clientHandler = clientHandler

    async def start_isabelle(self, isabelle_exec):
        isabelle_args = [
                "vscode_server",
                "-o", "vscode_pide_extensions",
                "-v",
                "-L", "/tmp/python-lsp-isa",
                "-o", "vscode_html_output=false",
                ]
        logger.info(f"Starting Isabelle with {isabelle_exec} {' '.join(isabelle_args)}")
        process = await asyncio.create_subprocess_exec(
            isabelle_exec,
            *isabelle_args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            bufsize=0
        )
        return process


    async def read_loop(self):
        while True:
            await self.lspClient.read_response()
            if self.script_done:
                break
        return True


    async def write_loop(self, args):

        self.isabelle_ready = False

        print("Initializing Isabelle")
        relative_filename = args.theory
        file_path = os.path.abspath(relative_filename)
        root_path = os.path.dirname(file_path)

        workspace_name = root_path.split("/")[-1]
        file_uri = "file://" + file_path

        await self.isaClient.initialize({
            "workspaceFolders": [
                {
                    "uri": "file://" + root_path,
                    "name": workspace_name
                }],
            "rootUri": "file://" + root_path,
            "rootPath": root_path,
        })

        print("Waiting for Isabelle to start")

        while True:
            await asyncio.sleep(10)
            if self.isabelle_ready:
                break

        document = Document(self.isaClient, file_uri)
        self.clientHandler.set_document(document)
        await document.open_file()

        await self.clientHandler.on_start()

        return True


    async def run(self, args:dict, commands=[]):
        process = await self.start_isabelle(args['exec'])
        self.lspClient = LSPClient(
                process.stdin,
                process.stdout,
                self.clientHandler.callbacks())
        self.isaClient = IsabelleClient(self.lspClient)

        if args is not None and args['command'] in commands:
            commands[args['command']].set_isabelle(self.isaClient)

        write_task = asyncio.create_task(self.write_loop(args))
        read_task = asyncio.create_task(self.read_loop())
        result = await asyncio.gather(read_task, write_task)
        print(result)

