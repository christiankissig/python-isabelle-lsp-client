.. image:: https://github.com/christiankissig/python-isabelle-lsp-client/actions/workflows/ci.yml/badge.svg
   :target: https://github.com/christiankissig/python-isabelle-lsp-client/actions/workflows/ci.yml
   :alt: CI/CD

.. image:: https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue
   :target: https://www.python.org/
   :alt: Python versions

.. image:: https://img.shields.io/badge/license-MIT-green
   :target: https://github.com/christiankissig/python-isabelle-lsp-client/blob/master/LICENSE
   :alt: License: MIT

python-isabelle-lsp-client
==========================

An unofficial Python LSP client for the `Isabelle <https://isabelle.in.tum.de/>`_ theorem prover.
Communicates with ``isabelle vscode_server`` via JSON-RPC (Language Server Protocol).
Supports Isabelle 2023 and Isabelle 2024.

Contrary to `isabelle-client <https://github.com/inpefess/isabelle-client/tree/master>`_, this
client talks to Isabelle through the Language Server Protocol, enabling more granular interaction
such as retrieving the proof state at a specific caret position.

.. warning::

   This library requires the `isabelle-emacs fork <https://github.com/m-fleury/isabelle-emacs>`_
   of Isabelle, **not** upstream Isabelle. The fork supports the non-HTML output mode
   (``vscode_html_output=false``) that this client depends on.


Prerequisites
-------------

* Python 3.10 or later
* The ``isabelle-emacs`` fork built with the ``HOL`` heap
* The ``lsp_client`` companion package (not on PyPI — see below)


Installation
------------

1. Install the ``lsp_client`` package from GitHub (not yet on PyPI)::

       pip install git+https://github.com/christiankissig/python-lsp-client.git

2. Install this package::

       poetry install

   or directly from GitHub::

       pip install git+https://github.com/christiankissig/python-isabelle-lsp-client.git


Quick start
-----------

Communication with Isabelle is fully asynchronous. Register callbacks for the PIDE notifications
you care about, then call ``process.run()``:

.. code-block:: python

   import asyncio
   from isabelle_lsp_client import ClientHandler, IsabelleProcess, PIDE_DYNAMIC_OUTPUT

   async def on_dynamic_output(document, response, timestamp):
       print(response["params"]["content"])

   async def main():
       handler = ClientHandler()
       handler.register(PIDE_DYNAMIC_OUTPUT, on_dynamic_output)

       process = IsabelleProcess(handler)
       await process.run({
           "exec": "/path/to/isabelle-emacs/bin/isabelle",
           "theory": "MyTheory.thy",
       })

   asyncio.run(main())

See ``isabelle_lsp_client/examples/auto_sledge.py`` for a complete working example that
automatically replaces ``sledgehammer`` calls with the proofs Isabelle finds.

Caret-driven elaboration
~~~~~~~~~~~~~~~~~~~~~~~~

Isabelle elaborates the proof state at the current caret position. To process a whole theory,
move the caret to the end of the file. To retrieve the proof state after a specific tactic, move
the caret to the end of that tactic. If a theory depends on others, Isabelle may send status
updates for those files too — filter by URI if needed.


Environment variables
---------------------

``ISABELLE_EXEC``
    Path to the ``isabelle`` executable from the isabelle-emacs fork.
    Used by the ``auto_sledge`` example script.


``run()`` arguments
-------------------

+---------------------+-----------------------------------------------------------+
| Key                 | Description                                               |
+=====================+===========================================================+
| ``exec``            | **Required.** Path to the Isabelle executable.            |
+---------------------+-----------------------------------------------------------+
| ``theory``          | **Required.** Path to the ``.thy`` file to open.         |
+---------------------+-----------------------------------------------------------+
| ``theories``        | Optional list of additional ``.thy`` files to open.      |
+---------------------+-----------------------------------------------------------+
| ``options``         | Extra flags passed to ``isabelle vscode_server``.         |
+---------------------+-----------------------------------------------------------+
| ``output_suffix``   | Suffix appended to the filename on write (default:        |
|                     | ``_new``).                                                |
+---------------------+-----------------------------------------------------------+
| ``log_path``        | Path for the Isabelle server log (default:                |
|                     | ``/tmp/python-lsp-isa``).                                 |
+---------------------+-----------------------------------------------------------+
| ``startup_timeout`` | Seconds to wait for Isabelle to become ready              |
|                     | (default: 120).                                           |
+---------------------+-----------------------------------------------------------+


Development
-----------

Run tests::

    pytest

Type-check::

    mypy isabelle_lsp_client/

Lint (import sorting)::

    ruff check .
