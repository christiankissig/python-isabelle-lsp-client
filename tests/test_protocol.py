from isabelle_lsp_client.protocol import CaretUpdateRequest, ProgressRequest


def test_caret_update_request():
    request = CaretUpdateRequest(id=1, uri="file:///path/to/file", line=1, character=2)

    assert request.model_dump() == {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "PIDE/caret_update",
        "params": {
            "uri": "file:///path/to/file",
            "line": 1,
            "character": 2,
        },
    }


def test_progress_request():
    request = ProgressRequest(id=1)

    assert request.model_dump(exclude_none=True) == {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "PIDE/progress_request",
    }
