from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest
from lsp_client import ContentChange, Position, Range

from isabelle_lsp_client.document import Document


@pytest.fixture
def mock_isabelle():
    isabelle = MagicMock()
    isabelle.caret_update = AsyncMock()
    isabelle.lspClient = MagicMock()
    isabelle.lspClient.send_notification = AsyncMock()
    return isabelle


URI = "file:///some/path/Theory.thy"


def make_doc(isabelle, text="line one\nline two\nline three"):
    return Document(isabelle, URI, text=text)


class TestDocumentTextConstructor:
    def test_all_attributes_initialized_with_text(self, mock_isabelle):
        doc = Document(mock_isabelle, URI, text="line one\nline two\nline three")
        assert doc.isabelle is mock_isabelle
        assert doc.uri == URI
        assert doc.file_path == "/some/path/Theory.thy"
        assert doc.output_suffix == ""
        assert doc.version == 1
        assert doc.caret_position == (0, 0)
        assert doc.lines == ["line one", "line two", "line three"]

    def test_output_suffix_passed_through(self, mock_isabelle):
        doc = Document(mock_isabelle, URI, text="content", output_suffix=".out")
        assert doc.output_suffix == ".out"

    def test_empty_text_gives_one_empty_line(self, mock_isabelle):
        doc = Document(mock_isabelle, URI, text="")
        assert doc.lines == [""]

    def test_invalid_uri_raises(self, mock_isabelle):
        with pytest.raises(ValueError, match="Invalid URI scheme"):
            Document(mock_isabelle, "https://example.com/Theory.thy")

    def test_no_text_gives_empty_lines(self, mock_isabelle):
        doc = Document(mock_isabelle, URI)
        assert doc.lines == []

    def test_file_path_strips_scheme(self, mock_isabelle):
        doc = Document(mock_isabelle, URI, text="x")
        assert doc.file_path == "/some/path/Theory.thy"


class TestReadFile:
    def test_read_file_populates_lines(self, mock_isabelle):
        doc = Document(mock_isabelle, URI)
        with patch("builtins.open", mock_open(read_data="line one\nline two")):
            doc.read_file()
        assert doc.lines == ["line one", "line two"]


class TestWriteFile:
    def test_write_file_writes_joined_lines(self, mock_isabelle):
        doc = make_doc(mock_isabelle, text="line one\nline two")
        m = mock_open()
        with patch("builtins.open", m):
            doc.write_file()
        m().write.assert_called_once_with("line one\nline two")

    def test_write_file_with_suffix_appends_to_path(self, mock_isabelle):
        doc = Document(mock_isabelle, URI, text="x", output_suffix=".new")
        m = mock_open()
        with patch("builtins.open", m) as mocked:
            doc.write_file()
        mocked.assert_called_once_with("/some/path/Theory.thy.new", "w")


class TestLocalApplyChange:
    def _range(self, sl, sc, el, ec):
        return Range(
            start=Position(line=sl, character=sc),
            end=Position(line=el, character=ec),
        )

    def test_single_line_replacement(self, mock_isabelle):
        doc = make_doc(mock_isabelle, text="apply sledge\napply blast")
        change = ContentChange(text="simp", range=self._range(0, 6, 0, 12))
        doc.local_apply_change(change)
        assert doc.lines[0] == "apply simp"

    def test_multi_line_replacement(self, mock_isabelle):
        # Range (0,1)→(1,3) replaces "aa\nbbb" with "X"; text_after="" from end of "bbb"
        doc = make_doc(mock_isabelle, text="aaa\nbbb\nccc")
        change = ContentChange(text="X", range=self._range(0, 1, 1, 3))
        doc.local_apply_change(change)
        assert doc.lines == ["aX", "ccc"]

    def test_full_document_sync_no_range(self, mock_isabelle):
        doc = make_doc(mock_isabelle, text="old content")
        change = ContentChange(text="new\ncontent")
        doc.local_apply_change(change)
        assert doc.lines == ["new", "content"]

    def test_local_apply_changes_applies_in_order(self, mock_isabelle):
        doc = make_doc(mock_isabelle, text="abc\ndef")
        changes = [
            ContentChange(text="X", range=self._range(0, 0, 0, 1)),
            ContentChange(text="Y", range=self._range(1, 0, 1, 1)),
        ]
        doc.local_apply_changes(changes)
        assert doc.lines[0] == "Xbc"
        assert doc.lines[1] == "Yef"


class TestApplyTextEdits:
    @staticmethod
    def _edit(sl, sc, el, ec, new_text):
        from isabelle_lsp_client.protocol import TextEdit

        return TextEdit(
            range=Range(
                start=Position(line=sl, character=sc),
                end=Position(line=el, character=ec),
            ),
            new_text=new_text,
        )

    @pytest.mark.asyncio
    async def test_applies_edits_and_notifies(self, mock_isabelle):
        doc = make_doc(mock_isabelle, text="aaa\nbbb\nccc")
        edits = [self._edit(0, 0, 0, 3, "XXX"), self._edit(2, 0, 2, 3, "ZZZ")]

        await doc.apply_text_edits(edits)

        assert doc.lines == ["XXX", "bbb", "ZZZ"]
        mock_isabelle.lspClient.send_notification.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_edits_are_applied_bottom_up(self, mock_isabelle):
        doc = make_doc(mock_isabelle, text="aaa\nbbb\nccc")
        # Provide edits in top-down order; they should be applied bottom-up.
        await doc.apply_text_edits(
            [self._edit(0, 0, 0, 1, "x"), self._edit(2, 0, 2, 1, "z")]
        )

        notif = mock_isabelle.lspClient.send_notification.call_args[0][0]
        lines = [c.range.start.line for c in notif.params["contentChanges"]]
        assert lines == [2, 0]

    @pytest.mark.asyncio
    async def test_empty_edits_is_noop(self, mock_isabelle):
        doc = make_doc(mock_isabelle, text="aaa")

        await doc.apply_text_edits([])

        assert doc.lines == ["aaa"]
        mock_isabelle.lspClient.send_notification.assert_not_awaited()


class TestGetProgress:
    def test_progress_fraction(self, mock_isabelle):
        doc = make_doc(mock_isabelle, text="a\nb\nc\nd")
        assert doc.get_progress(2) == 0.5


class TestFindNext:
    def test_pattern_at_column_zero(self, mock_isabelle):
        doc = make_doc(mock_isabelle, text="apply auto\napply simp\napply blast")
        assert doc.find_next("apply simp") == (1, 0)

    def test_pattern_at_exact_start_character(self, mock_isabelle):
        doc = make_doc(mock_isabelle, text="xx apply simp")
        assert doc.find_next("apply", start_line=0, start_character=3) == (0, 3)

    def test_pattern_before_start_character_not_found_on_start_line(
        self, mock_isabelle
    ):
        doc = make_doc(mock_isabelle, text="apply simp\napply blast")
        # start_character=6 skips "apply " — "simp" is at col 6, which is exactly at boundary
        line, char = doc.find_next("apply", start_line=0, start_character=1)
        # "apply" at col 0 is before start_character=1, so it should not be found on line 0
        assert line != 0

    def test_pattern_on_later_line(self, mock_isabelle):
        doc = make_doc(mock_isabelle, text="foo\nbar\nbaz")
        assert doc.find_next("baz", start_line=0, start_character=0) == (2, 0)

    def test_no_match_returns_minus_one(self, mock_isabelle):
        doc = make_doc(mock_isabelle, text="apply auto")
        assert doc.find_next("sledgehammer") == (-1, -1)

    def test_uses_caret_position_as_default(self, mock_isabelle):
        doc = make_doc(mock_isabelle, text="apply auto\napply simp")
        doc.caret_position = (1, 0)
        assert doc.find_next("apply simp") == (1, 0)


class TestTheoryUntilCaret:
    def test_returns_lines_before_caret(self, mock_isabelle):
        doc = make_doc(mock_isabelle, text="line0\nline1\nline2")
        doc.caret_position = (2, 0)
        assert doc.theory_until_caret() == "line0\nline1"

    def test_custom_separator(self, mock_isabelle):
        doc = make_doc(mock_isabelle, text="a\nb\nc")
        doc.caret_position = (2, 0)
        assert doc.theory_until_caret(separator="|") == "a|b"


class TestMoveCaret:
    @pytest.mark.asyncio
    async def test_move_caret_on_text_document(self, mock_isabelle):
        doc = Document(mock_isabelle, URI, text="line one\nline two")
        await doc.move_caret(1, 4)
        assert doc.caret_position == (1, 4)
        mock_isabelle.caret_update.assert_awaited_once_with(URI, 1, 4)
