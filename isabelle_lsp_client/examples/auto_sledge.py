"""
Example implementation of the Isabelle LSP client.

This script will search for `sledgehammer` command in a .thy file and replace
`sledgehammer` with commands found by Isabelle.

Please set the environment variable ISABELLE_EXEC to the correct location of the
Isabelle executable from https://github.com/m-fleury/isabelle-emacs .
"""

import asyncio
import os
import re
import sys

from lsp_client import ContentChange, Position, Range

from isabelle_lsp_client import ClientHandler, Document, IsabelleProcess

# configure to correct location of isabelle-emacs Isabelle executable
ISABELLE_EXEC = os.getenv("ISABELLE_EXEC")

COMMAND = "sledgehammer"
WORKING = "Sledgehammering..."
FAILED = "Sledgehammer failed to find a command."
PATTERN = re.compile(r"Try this: (.*?) \([\.0-9]+ m?s\)")


async def on_update_dynamic_output(document: Document, response: dict) -> None:
    """
    Handle PIDE/dynamic_output response:

    If Sledgehammer has a suggestion, replace `sledgehammer` with the command,
    and move on to the next `sledgehammer`.
    """
    content = response["params"]["content"]

    if content == WORKING:
        return

    line = document.lines[document.caret_position[0]]
    if not line[document.caret_position[1] - len(COMMAND) :].startswith(COMMAND):
        return

    command = _get_command_from_sledgehammer(content)
    if command:
        content_change = ContentChange(
            range=Range(
                start=Position(
                    line=document.caret_position[0],
                    character=document.caret_position[1] - len(COMMAND),
                ),
                end=Position(
                    line=document.caret_position[0],
                    character=document.caret_position[1],
                ),
            ),
            text=command,
            rangeLength=len(COMMAND),
        )
        await document.apply_changes([content_change])
        document.write_file()

    await _move_caret_to_next_sledgehammer(document)


async def on_start(document: Document) -> None:
    """
    Load document on start.
    """
    await _move_caret_to_next_sledgehammer(document)


async def _move_caret_to_next_sledgehammer(document: Document) -> None:
    """
    Move caret to next `sledgehammer`.
    """
    pos = document.find_next(COMMAND)
    await document.move_caret(pos[0], pos[1] + len(COMMAND))


def _get_command_from_sledgehammer(content: str) -> str | None:
    """
    Match and extract command from Sledgehammer response.
    """
    lines = content.split("\\n")
    for line in lines:
        match = re.search(PATTERN, line)
        if match:
            return match.group(1)
    return None


async def _run(clientHandler: ClientHandler, args: dict) -> None:
    """
    Create a new Isabelle process, and run with arguments.
    """
    process = IsabelleProcess(clientHandler)
    await process.run(args)


def _main(argv: list[str]) -> None:
    args = {
        "theory": argv[1],
        "exec": ISABELLE_EXEC,
    }

    clientHandler = ClientHandler()
    clientHandler.register_on_start(on_start)
    clientHandler.register_on_dynamic_output(on_update_dynamic_output)

    asyncio.run(_run(clientHandler, args))


if __name__ == "__main__":
    _main(sys.argv)
