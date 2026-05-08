# Update `initialize()` to use typed `InitializeParams`

**Priority:** Medium  
**Blocked on:** `python-lsp-client` task 08 (wire `InitializeParams` to `InitializeRequest`)  
**File:** `isabelle_lsp_client/client.py:55–69`

## Problem

`IsabelleClient.initialize()` builds the `initialize` request params as a plain `dict` with no
validation:

```python
async def initialize(self, params: dict = {}, clientCapabilities: Any = None) -> str:
    workDoneToken = str(uuid4())
    if clientCapabilities is None:
        params["capabilities"] = self._get_capabilities()
    else:
        params["capabilities"] = clientCapabilities
    params["workDoneToken"] = workDoneToken
    params["trace"] = "off"
    params["clientInfo"] = self._get_client_info()
    params["locale"] = "en_US"
    params["processId"] = os.getpid()
    await self.lspClient.send_request(InitializeRequest(params=params))
```

Once `python-lsp-client` task 08 makes `InitializeRequest` accept a typed `InitializeParams`
object, passing a plain dict may break. More importantly, using `InitializeParams` exposes
the structure to mypy and removes the mutable-default-argument bug (`params: dict = {}`).

## Fix

```python
from lsp_client import InitializeParams, ClientInfo

async def initialize(self, clientCapabilities: Any = None) -> str:
    workDoneToken = str(uuid4())
    capabilities = clientCapabilities if clientCapabilities is not None else self._get_capabilities()
    params = InitializeParams(
        processId=os.getpid(),
        clientInfo=ClientInfo(**self._get_client_info()),
        locale="en_US",
        capabilities=capabilities,
        workDoneToken=workDoneToken,
        trace="off",
    )
    await self.lspClient.send_request(InitializeRequest(params=params))
    ...
```

Drop the `params: dict = {}` argument — it was never part of the public API and the mutable
default is a latent bug.

## Notes

- Verify the field names in `InitializeParams` once `python-lsp-client` task 08 lands, as the
  exact defaults and optional fields may differ from the sketch above.
- `_get_client_info()` returns a plain dict; either update it to return a `ClientInfo` directly
  or keep the `ClientInfo(**self._get_client_info())` expansion.
