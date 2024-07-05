from lsp_client import BaseRequest

# PIDE requests


class CaretUpdateRequest(BaseRequest):
    """
    Request to move caret to position in the text document.

    :param uri: The URI of the text document.
    :param line: The line number of the caret.
    :param character: The character number of the caret.
    """
    def __init__(self, uri: str, line: int, character: int):
        method = "PIDE/caret_update"
        params = {
            "uri": uri,
            "line": line,
            "character": character
        }
        super().__init__(method, params)


class ProgressRequest(BaseRequest):
    """
    Request to update progress of a task.
    """
    def __init__(self):
        method = "PIDE/progress_request"
        super().__init__(method, {})
