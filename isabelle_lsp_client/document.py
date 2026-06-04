import logging

from lsp_client import ContentChange, TextDocumentDidChangeNotification

from .client import IsabelleClient

logger = logging.getLogger(__name__)


class Document:
    lines: list[str]

    """
    Document model.
    """

    def __init__(
        self,
        isabelle: IsabelleClient,
        uri: str,
        text: str | None = None,
        output_suffix: str = "",
    ) -> None:
        """
        Constructor.

        For the moment expects uri to be of "file://" scheme.
        output_suffix: appended to filename on write. Empty string means in-place.
        """
        self.isabelle = isabelle
        self.uri = uri
        self.output_suffix = output_suffix
        if uri.startswith("file://"):
            self.file_path = uri[len("file://") :]
        else:
            raise ValueError("Invalid URI scheme: " + uri)
        self.version = 1
        self.caret_position = (0, 0)

        if text is not None:
            self.lines = text.split("\n")
        else:
            self.lines = []

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

    async def close_file(self) -> None:
        """
        Notify Isabelle that this document is closed (``textDocument/didClose``).
        """
        await self.isabelle.close_text_document(self.uri)

    def write_file(self) -> None:
        """
        Writes the file to disk. Uses output_suffix set at construction time:
        empty string means in-place, any other value is appended to the filename.
        """
        output_path = self.file_path + self.output_suffix
        logger.info(f"writing file {output_path}")
        with open(output_path, "w") as file:
            file.write("\n".join(self.lines))

    def local_apply_change(self, change: ContentChange) -> None:
        """
        Applies a single content change locally in memory.
        """
        if change.range is None:
            # Full-document sync: replace all content.
            self.lines = change.text.split("\n")
            return
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
        notification = TextDocumentDidChangeNotification(
            uri=self.uri, version=self.version, contentChanges=changes
        )
        await self.isabelle.lspClient.send_notification(notification)

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
