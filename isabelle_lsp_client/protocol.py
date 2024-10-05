from lsp_client import BaseRequest


# PIDE requests

class CaretUpdateRequest(BaseRequest):

    def __init__(self, uri: str, line: int, character: int, **kwargs):
        method = "PIDE/caret_update"
        params = {
            "uri": uri,
            "line": line,
            "character": character
        }
        super().__init__(method=method, params=params, **kwargs)


class ProgressRequest(BaseRequest):
    """
    Request to update progress of a task.
    """
    def __init__(self, **kwargs):
        method = "PIDE/progress_request"
        super().__init__(method=method, params=None, **kwargs)
