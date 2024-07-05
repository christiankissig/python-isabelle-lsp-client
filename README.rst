Summary
=======

This repository contains an unofficial LSP client for Isabelle vscode\_server.
The client is written to be used with Isabelle2023, guarantees of correctness
are not provided. Use at your own risk.

Contrary to 
[https://github.com/inpefess/isabelle-client/tree/master](isabelle-client), the
client in this repository talks to Isabelle through the language server 
protocol allowing for more granular interaction, such as retrieving the
proof state in a specific part of the proof script. The language server
protocol is based on JSON-RPC.

Requirements
============

The client implementation requires the 
[https://github.com/m-fleury/isabelle-emacs](emacs fork of Isabelle), which
supports non-HTML output. The client implementation supports Isabelle2023 and
Isabelle2024.

Until lsp_client is available through PyPI, the client implementation requires
a virtual Python environment with 
[https://github.com/christiankissig/python-lsp-client](python-lsp-client) 
manually installed:

```bash
source /path/to/venv/bin/activate
cd python-lsp-client
pip install .
```

How to use
==========

Communication with the Isabelle language server is asynchronous, so that any
implementation needs to follow a pattern of callback functions. 

As Isabelle acts as an LSP server, actions are triggered by setting a caret to 
a specific position. In order to process a theory whole, the caret needs to be
set to the bottom of the file. In order to retrieve the proof state after a
specific command, the caret needs to be set to the end position of the command
in the theory file.

If a theory file depends on other theories, corresponding files will be
processed first. Isabelle may send status updates for these files. Appropriate
filtering needs to be implemented.
