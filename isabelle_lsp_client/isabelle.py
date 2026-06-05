import functools
import json
import re
from importlib import resources

from .document import Document

# Isabelle symbol notation token, e.g. ``\<Rightarrow>`` or ``\<^sub>``.
_ISABELLE_SYMBOL = re.compile(r"\\<[^>\s]+>")


@functools.lru_cache(maxsize=1)
def _symbol_table() -> dict[str, str]:
    """Load the bundled Isabelle symbol table (token -> Unicode character)."""
    raw = (
        resources.files("isabelle_lsp_client.data")
        .joinpath("symbols.json")
        .read_text(encoding="utf-8")
    )
    return {token: chr(code) for token, code in json.loads(raw).items()}


def decode_symbols(text: str) -> str:
    """
    Decode Isabelle symbol notation in ``text`` to Unicode.

    Replaces ``\\<name>`` tokens (e.g. ``\\<Rightarrow>``) with the corresponding
    Unicode character (``⇒``) from the bundled symbol table. Tokens not in the
    table are left unchanged. Useful on text Isabelle surfaces with raw notation
    — hover contents, ``PIDE/dynamic_output`` proof state, decoration content.
    """
    table = _symbol_table()
    return _ISABELLE_SYMBOL.sub(lambda m: table.get(m.group(0), m.group(0)), text)


def get_command_from_sledgehammer(content: str) -> str | None:
    lines = content.split("\\n")
    pattern = r"Try this: (.*?) \([\.0-9]+ m?s\)"
    for line in lines:
        match = re.search(pattern, line)
        if match:
            return match.group(1)
    return None


def get_command_from_document(document: Document, pos: tuple[int, int]) -> str | None:
    current_line = pos[0]
    if not document.lines[current_line][pos[1] :].lstrip().startswith("apply"):
        return None
    line = document.lines[current_line][pos[1] :].lstrip()[len("apply") :].lstrip()
    while line == "":
        current_line += 1
        line = document.lines[current_line].strip()
    if not line.startswith("("):
        command = line.split(" ")[0]
        return command

    command = "("
    line = line[1:]
    parens = 1
    while parens > 0:
        until = 0
        # TODO handle strings etc
        for character in line:
            if character == "(":
                parens += 1
            elif character == ")":
                parens -= 1
            until += 1
            if parens == 0:
                break
        if until > 0:
            command += line[:until]
        if parens > 0:
            command += " "
        current_line += 1
        if current_line < len(document.lines):
            line = document.lines[current_line].strip()
    return command


def command_finishes_subgoal(command: str) -> bool:
    return (
        command.startswith("by")
        or command.startswith("done")
        or command.startswith("qed")
    )


def is_sledgehammer_done(content: str) -> bool:
    return content.strip().endswith("Done")


def is_sledgehammer_noproof(content: str) -> bool:
    return "No proof found" in content


def is_isabelle_ready(content: str) -> bool:
    return content.startswith("Welcome to Isabelle/")
