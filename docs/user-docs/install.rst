.. _install:

Installation
============

SRU Lint runs on Linux and requires Python 3.12 or newer. It can be installed
either as a snap (recommended for day-to-day use) or directly from source
(recommended for development and unreleased features).

From the snap store
-------------------

The snap is published to the ``edge`` channel:

.. code-block:: bash

   sudo snap install --edge sru-lint

The snap is ``strict``-confined. It declares four plugs:

- ``home`` (auto-connected) — lets ``sru-lint check`` read patches from
  your home directory and walk a local git checkout.
- ``network`` (auto-connected) — used for URL inputs and Launchpad
  queries.
- ``desktop`` (auto-connected) — used by ``sru-lint login`` to open the
  default browser for the Launchpad OAuth flow.
- ``password-manager-service`` (**manual**) — required by
  ``sru-lint login`` to cache the OAuth token in the system keyring.
  This interface does not auto-connect on install; connect it before
  running ``sru-lint login``:

  .. code-block:: bash

     sudo snap connect sru-lint:password-manager-service

  Verify the connection with ``snap connections sru-lint``. See
  :ref:`usage` for the full ``sru-lint login`` workflow.

Patches outside ``$HOME`` are not reachable through the ``home`` plug —
pass them via standard input or copy them under ``$HOME`` first.

Upgrade with ``sudo snap refresh sru-lint``; remove with
``sudo snap remove sru-lint``.

From source (Poetry)
--------------------

Use this path if you are developing plugins, tracking unreleased fixes, or
running SRU Lint in a CI image that already has Python tooling.

Prerequisites:

- Python 3.12 or newer
- `Poetry <https://python-poetry.org/>`_ 1.8 or newer
- ``git``

.. code-block:: bash

   git clone https://github.com/canonical/sru-lint.git
   cd sru-lint
   poetry install        # installs runtime + dev dependency groups

This produces an isolated virtual environment under ``.venv/`` (or wherever
Poetry is configured to place it). Run the tool with ``poetry run sru-lint
...`` or enter ``poetry shell`` once and drop the prefix.

To install only the runtime dependencies (e.g. for a container image), pass
``--only main``:

.. code-block:: bash

   poetry install --only main

Verifying the installation
--------------------------

Run ``sru-lint plugins`` (or ``poetry run sru-lint plugins``) — it lists
the discovered plugins without touching the network. An empty list or an
import error indicates the install did not complete successfully.

For day-to-day use see :ref:`usage`.

Uninstalling
------------

.. code-block:: bash

   sudo snap remove sru-lint                              # snap install
   rm -rf /path/to/sru-lint                               # source install

Removing the snap also removes any cached Launchpad credentials it stored
under its confined data directory. A source install stores credentials in
the host keyring; remove them through your keyring management tool
(``seahorse``, ``kwalletmanager``, ``secret-tool``) if you want a clean
slate.
