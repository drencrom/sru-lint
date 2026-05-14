.. _usage:

Usage
=====

SRU Lint is a static analyzer for Ubuntu Stable Release Update (SRU)
patches. Point it at a patch and it runs a suite of plugins that flag
common SRU mistakes — invalid distributions, malformed changelog entries,
missing DEP-3 headers, broken bug targeting, version-ordering problems,
and so on — then prints a report on the terminal or as JSON for CI.

This page assumes you have ``sru-lint`` on ``PATH`` (snap install) or are
prefixing commands with ``poetry run`` (source install). See
:ref:`install` if you have not installed yet.

Synopsis
--------

.. code-block:: text

   sru-lint [GLOBAL OPTIONS] check    [OPTIONS] INPUT
   sru-lint [GLOBAL OPTIONS] plugins
   sru-lint [GLOBAL OPTIONS] login
   sru-lint help [COMMAND]

Global options:

``-v``, ``-vv``
   Increase log verbosity. ``-v`` enables ``INFO``; ``-vv`` enables
   ``DEBUG``. Logs are written to standard error so they do not pollute
   JSON output on standard output.

``-q``, ``--quiet``
   Suppress everything below ``ERROR``-level logs.

The ``check`` command
---------------------

``sru-lint check`` is the primary entry point. The single positional
argument selects what to analyze:

Local file path
   Read a patch from disk. Any file SRU Lint can open and decode as UTF-8.

HTTP or HTTPS URL
   Fetch the patch over the network. A 30-second timeout is applied; there
   are no retries.

``-``
   Read a patch from standard input.

Directory
   Treat the directory as a patches-unapplied git checkout and synthesize
   a debdiff between the previous version recorded in
   ``debian/changelog`` and ``HEAD``.

Examples:

.. code-block:: bash

   # File
   sru-lint check ~/work/foo_1.2-3ubuntu1.debdiff

   # URL (for example a Launchpad merge proposal preview diff)
   sru-lint check https://launchpad.net/.../+files/foo.debdiff

   # Pipe from another tool
   debdiff foo_1.2-3.dsc foo_1.2-3ubuntu1.dsc | sru-lint check -

   # Local git checkout — equivalent to running `debdiff` against the
   # previous version recorded in debian/changelog
   sru-lint check ~/work/foo

Selecting plugins
~~~~~~~~~~~~~~~~~

By default every discovered plugin runs. Restrict to a subset with
``-m`` / ``--modules``, accepting both a comma-separated list and
repeated flags:

.. code-block:: bash

   sru-lint check -m changelog-entry .
   sru-lint check -m changelog-entry,dep3-header .
   sru-lint check -m changelog-entry -m dep3-header .

Symbolic names come from the plugin class (``ChangelogEntry`` →
``changelog-entry``). List them with ``sru-lint plugins``.

Output formats
~~~~~~~~~~~~~~

``-f`` / ``--format`` selects the renderer:

``console`` (default)
   Human-readable output rendered with ``rich``: a code snippet for each
   finding, color-coded by severity, and a summary line.

``json``
   A JSON array of findings on standard output — one object per finding
   with ``message``, ``rule_id``, ``severity``, ``span`` (path, start/end
   line and column), and optional ``doc_url``. Logs continue to go to
   standard error.

.. code-block:: bash

   sru-lint check -f json . | jq '.[] | select(.severity == "ERROR")'

Exit codes
~~~~~~~~~~

============  =================================================================
Code          Meaning
============  =================================================================
``0``         No ``ERROR``-level findings. ``WARNING`` and ``INFO`` findings
              may still have been reported.
``1``         At least one ``ERROR``-level finding was produced.
``2``         Input could not be processed — file not found, URL fetch
              failure, unreadable file, or malformed patch.
============  =================================================================

Use ``1`` to gate a CI job on SRU correctness; treat ``2`` as a setup or
infrastructure problem rather than a patch problem.

Listing plugins
---------------

.. code-block:: bash

   sru-lint plugins

Prints each discovered plugin as
``<symbolic-name> : <docstring>``. The list is what ``-m`` accepts. This
command does not parse a patch and does not open a Launchpad connection,
so it is a good smoke test after install.

Authenticating with Launchpad
-----------------------------

``sru-lint login`` runs the Launchpad OAuth flow and caches the resulting
token in the system keyring. Anonymous access is enough for most plugins;
authentication is only required when a plugin needs to read private
Launchpad data — most notably the ESM / Ubuntu Pro PPAs.

.. code-block:: bash

   sru-lint login

The command opens a browser, asks Launchpad to authorize ``sru-lint``,
and reports the resulting account. On success the credentials are
persisted automatically and the next ``sru-lint check`` invocation will
pick them up. Re-run only when the cached credentials expire or are
revoked from the Launchpad UI.

If the keyring cannot persist the credentials (headless CI, snap
confinement blocking the keyring, missing keyring daemon), the command
exits with a warning and ``sru-lint check`` falls back to anonymous
access. On the snap install this almost always means the
``password-manager-service`` plug is not connected — see :ref:`install`.

CI integration
--------------

The intended CI pattern is:

.. code-block:: bash

   sru-lint check -f json . > sru-lint.json
   status=$?
   if [ "$status" -eq 2 ]; then
       echo "::error::sru-lint could not process the patch" >&2
       exit 2
   fi
   exit "$status"

Notes:

- Run from the repository root of a patches-unapplied checkout so the
  directory-input mode can derive the debdiff from
  ``debian/changelog``.
- For air-gapped or pinned environments, pre-fetch the patch and pass
  it as a file or via standard input rather than relying on the URL fetcher.
- Plugins run concurrently in a thread pool. Each finding records the
  plugin's symbolic name as ``rule_id``'s prefix family (for example
  ``CHANGELOG001``), so you can route findings to owners by rule ID.

Troubleshooting
---------------

``Error: File not found: ...``
   The path does not exist or is not readable as the current user.
   Check shell quoting and (if running from the snap) confirm the file
   lives under ``$HOME`` — the snap's ``home`` plug does not grant
   access to ``/tmp``, ``/srv`` or other system locations.

``Error: Failed to fetch content from URL: ...``
   The URL fetcher uses ``urllib`` with a 30-second timeout and no
   retries. Re-run with ``-vv`` to see the underlying exception, or
   download the patch out-of-band and pass it as a file.

``No files found in patch or failed to parse patch``
   The input did not parse as a unified diff. If the patch is wrapped
   in mail or merge-proposal boilerplate, extract the diff body first.

Plugin produces no findings on a patch you expect it to flag
   Check the plugin's file patterns with ``sru-lint plugins`` and the
   plugin source. Patterns are matched with ``fnmatch`` against the
   diff target path, and also as ``*/pattern``, so ``debian/changelog``
   matches both top-level and nested layouts — but a file outside that
   set never reaches the plugin.

ESM / Ubuntu Pro plugins skipping checks
   The plugin needs authenticated Launchpad access. Run
   ``sru-lint login`` and confirm credentials persisted. In headless
   environments without a keyring, authenticated checks are not
   currently supported.
