import logging

from lsp_client import ContentChange, TextDocument_DidChange_Request

from isabelle_lsp_client import IsabelleClient

logger = logging.getLogger(__name__)


class Document:
    lines: list[str]

    """
    Document model.
    """

    def __init__(
        self, isabelle: IsabelleClient, uri: str, text: str | None = None
    ) -> None:
        """
        Constructor.

        For the moment expects uri to be of "file://" scheme.
        """
        if text:
            self.lines = text.split("\n")
        else:
            self.isabelle = isabelle
            self.uri = uri
            if uri.startswith("file://"):
                self.file_path = uri[len("file://") :]
            else:
                raise ValueError("Invalid URI scheme: " + uri)
            self.lines = []
            self.version = 0
            self.caret_position = (0, 0)

    def read_file(self) -> None:
        """
        Reads file at uri and stores lines in memory.
        """
        with open(self.file_path, "r") as file:
            text = file.read()
        self.lines = text.split("\n")
        logging.debug(f"read {len(self.lines)} lines from {self.file_path}")

    async def open_file(self) -> None:
        """
        Has Isabelle open the file at uri, reads the file locally, and sets
        caret position to the beginning of the file.
        """
        await self.isabelle.open_text_document(self.uri)
        self.read_file()
        await self.isabelle.caret_update(
            self.uri, self.caret_position[0], self.caret_position[1]
        )

    def write_file(self, suffix: str = "_new") -> None:
        """
        Writes the file locally to disk.
        """
        new_file_path = self.file_path + suffix
        logger.info(f"writing file {new_file_path}")
        with open(new_file_path, "w") as file:
            file.write("\n".join(self.lines))

    def local_apply_change(self, change: ContentChange) -> None:
        """
        Applies a single content change locally in memory.
        """
        start_line = self.lines[change.range.start.line]
        end_line = self.lines[change.range.end.line]
        text_before = start_line[: change.range.start.character]
        text_after = end_line[change.range.end.character :]
        new_line = text_before + change.text + text_after
        logger.debug(f"replacing line {start_line} with {new_line}")
        self.lines = "\n".join(
            self.lines[: change.range.start.line]
            + [new_line]
            + self.lines[change.range.end.line + 1 :]
        ).split("\n")

    def local_apply_changes(self, changes: list[ContentChange]) -> None:
        """
        Applies a list of content changes locally in memory.
        """
        for change in changes:
            self.local_apply_change(change)

    async def isabelle_apply_changes(self, changes: list[ContentChange]) -> None:
        """
        Applies a list of content changes in Isabelle.
        """
        self.version += 1
        request = TextDocument_DidChange_Request(
            uri=self.uri, version=str(self.version), contentChanges=changes
        )
        await self.isabelle.lspClient.send_request(request)

    async def apply_changes(self, changes: list[ContentChange]) -> None:
        """
        Applies a list of content changes locally in memory and in Isabelle.
        """
        self.local_apply_changes(changes)
        await self.isabelle_apply_changes(changes)

    def get_progress(self, line: int) -> float:
        """
        Calculates progress based on line number.
        """
        return line / len(self.lines)

    async def move_caret(self, line: int = 0, character: int = 0) -> None:
        """
        Moves caret position locally and in Isabelle.
        """
        self.caret_position = (line, character)
        await self.isabelle.caret_update(self.uri, line, character)

    async def move_caret_to_end(self) -> None:
        """
        Moves caret to the end of the document.
        """
        if self.lines:
            await self.move_caret(len(self.lines) - 1, len(self.lines[-1]))
        else:
            raise ValueError("No lines in document")

    def find_next(
        self, pattern: str, start_line: int = -1, start_character: int = -1
    ) -> tuple[int, int]:
        """
        Finds string starting from a position, i.e. line number and character.
        """
        if start_line < 0:
            start_line = self.caret_position[0]
        if start_character < 0:
            start_character = self.caret_position[1]

        for line_number in range(start_line, len(self.lines)):
            line = self.lines[line_number]
            if line_number == start_line:
                line = line[start_character:]
            if line_number == start_line:
                pos = line.find(pattern, start_character)
            else:
                pos = line.find(pattern)
            if pos >= 0:
                return (line_number, pos)
        return (-1, -1)

    def theory_until_caret(self, separator: str = "\n") -> str:
        """
        Returns the theory file until the caret position as a string.
        """
        return separator.join(self.lines[: self.caret_position[0]])
