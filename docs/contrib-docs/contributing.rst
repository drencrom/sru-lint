.. _contributing:

Contributing to SRU Lint
========================

SRU Lint is written using the Python language.

The code is maintained by the `SE org <https://docs.google.com/document/d/1RIZ2or6GiTwHSZDLmREErEyo6rkzgBOBghg1GMaAHeE/edit?tab=t.0>`_ and hosted on `github <https://github.com/canonical/sru-lint>`_ and all development is organised in Jira using the `Kanban board <https://warthogs.atlassian.net/jira/software/c/projects/SET/boards/6454>`_ and the `current active pulse <https://warthogs.atlassian.net/jira/software/c/projects/SET/boards/1490>`_.

Development setup
-----------------

Dependency management uses `Poetry <https://python-poetry.org/>`_. The project
targets Python 3.12.

.. code-block:: bash

   git clone https://github.com/canonical/sru-lint.git
   cd sru-lint
   poetry install                                  # installs runtime + dev deps

Common development commands, all run from the repository root:

.. code-block:: bash

   poetry run sru-lint check path/to/patch.debdiff       # run on a debdiff file
   poetry run sru-lint check .                           # run on a patches-unapplied git repo
   poetry run sru-lint -vv check .                       # -v INFO, -vv DEBUG; -q for errors only
   poetry run sru-lint check -m changelog-entry .        # restrict to a single plugin
   poetry run sru-lint plugins                           # list discovered plugins

   # Tests
   poetry run python -m unittest discover -s tests       # unit tests
   poetry run pytest tests/functional_tests              # functional tests (need `poetry install` first)

   # Lint / format / type check
   poetry run ruff check .
   poetry run ruff format .
   poetry run mypy sru_lint/

Run all checks at once
~~~~~~~~~~~~~~~~~~~~~~

A single Poetry script runs the full local check suite (ruff lint + format
check, mypy, unit tests, and functional tests):

.. code-block:: bash

   poetry run check-all

It runs every step even if an earlier one fails, prints a PASS/FAIL summary
at the end, and exits non-zero if anything failed. Use it before opening a
pull request.

Code style and conventions
--------------------------

- Python 3.12, line length 100, double quotes (enforced by ``ruff format``).
- Ruff lint rules: ``E,W,F,I,B,C4,UP`` (see ``pyproject.toml``).
- Type checking via ``mypy`` with ``--ignore-missing-imports``.
- A ``.pre-commit-config.yaml`` is provided; install hooks with
  ``poetry run pre-commit install`` to run ruff/mypy on each commit.
- Tests use ``unittest`` (from the standard library) for plugin/unit tests. The
  ``tests/functional_tests/`` suite uses ``pytest`` and shells out to the
  installed ``sru-lint`` binary, so it requires a prior ``poetry install``.

Architecture overview
---------------------

A ``check`` run is a single pipeline wired in ``sru_lint/cli.py``:

1. **Input resolution.** ``read_input_content`` accepts a file path, URL,
   ``-`` (standard input), or a directory. A directory is treated as a git
   repository and ``git_debdiff()`` synthesizes a debdiff by walking
   ``git log debian/changelog`` to find the previous version's commit and
   diffing ``<that>..HEAD``.
2. **Patch parsing.** ``sru_lint/common/patch_processor.py`` converts the
   raw patch text into a ``unidiff.PatchSet`` and then into a list of
   ``ProcessedFile`` objects. Each ``ProcessedFile`` carries a
   ``SourceSpan`` whose ``content`` is the added lines only and
   ``content_with_context`` is added + context lines (each line keeping the
   target line number from the diff).
3. **Plugin discovery.** ``PluginManager.load_plugins()`` walks
   ``sru_lint.plugins`` recursively with ``pkgutil.iter_modules``, imports
   every submodule (including nested packages), and instantiates every
   concrete ``Plugin`` subclass it finds. There is no manual registration
   list — see :ref:`plugin-autoloading`.
4. **Filtering and execution.** Plugins run *concurrently* in a
   ``ThreadPoolExecutor``. Each plugin's ``Plugin.process()`` filters
   ``processed_files`` against patterns registered via
   ``add_file_pattern()`` (matched with ``fnmatch``, also tried as
   ``*/pattern`` so ``debian/changelog`` matches both top-level and nested
   paths) and calls ``process_file()`` per matching file.
5. **Feedback.** Plugins append ``FeedbackItem`` objects (message,
   ``SourceSpan``, ``ErrorCode`` rule_id, ``Severity``, optional
   ``doc_url``). Console output uses ``rich`` to render code snippets; JSON
   output uses ``ErrorEnumEncoder``.
6. **Exit code.** ``1`` if any ``Severity.ERROR`` feedback was produced,
   ``2`` for input errors (file not found, URL fetch failure, malformed
   patch), ``0`` otherwise.

Writing a new plugin
--------------------

Plugins live anywhere under ``sru_lint/plugins/`` (top-level modules or
nested packages — both are discovered). A plugin is a class that inherits
from ``Plugin`` and implements ``process_file``.

Minimal example
~~~~~~~~~~~~~~~

.. code-block:: python

   # sru_lint/plugins/no_tabs.py
   from sru_lint.common.errors import ErrorCode
   from sru_lint.common.feedback import Severity
   from sru_lint.plugins.plugin_base import Plugin


   class NoTabs(Plugin):
       """Flag tab characters in added lines of debian/rules."""

       def register_file_patterns(self):
           self.add_file_pattern("debian/rules")

       def process_file(self, processed_file):
           for line in processed_file.source_span.content:
               if "\t" not in line.content:
                   continue
               self.create_feedback(
                   message="Tab character found",
                   rule_id=ErrorCode.PATCH002,
                   severity=Severity.WARNING,
                   source_span=processed_file.source_span,
                   line_number=line.line_number,
               )

Drop the file under ``sru_lint/plugins/`` and the plugin manager will pick
it up automatically — no registration list to edit.

The ``Plugin`` contract
~~~~~~~~~~~~~~~~~~~~~~~

Defined in ``sru_lint/plugins/plugin_base.py``:

- ``__symbolic_name__`` is **auto-derived** from the class name (PascalCase
  → kebab-case), e.g. ``NoTabs`` → ``no-tabs``. The symbolic name is what
  ``sru-lint check -m <name>`` and ``sru-lint plugins`` use. Set the
  attribute explicitly only to override the default.
- ``register_file_patterns(self)`` — override to call ``self.add_file_pattern("...")``
  for every path glob the plugin wants to see. Patterns are matched both as
  given and as ``*/pattern`` so ``debian/changelog`` matches whether the
  diff is rooted at the repository or one level down.
- ``process_file(self, processed_file)`` — **abstract**. Called once per
  matching file. Append findings via ``self.add_feedback(...)`` or use the
  ``create_feedback(...)`` / ``create_line_feedback(...)`` helpers, which
  build the ``SourceSpan`` and log at the right severity.
- ``post_process(self)`` — optional end-of-run hook. Runs from ``__exit__``
  (the CLI wraps each plugin with ``with plugin:``).
- ``self.logger`` is a child logger under ``plugins.<symbolic-name>``.
- ``self.lp_helper`` is a ready-to-use Launchpad helper — see
  :ref:`launchpad-integration` below.

.. _plugin-autoloading:

Plugin auto-loading
~~~~~~~~~~~~~~~~~~~

``PluginManager.load_plugins()`` (in ``sru_lint/plugin_manager.py``) does
the discovery:

1. ``pkgutil.iter_modules`` walks ``sru_lint.plugins`` recursively,
   importing every submodule and nested package. Files that fail to import are
   logged at warning level and skipped — they will not silently disappear.
2. ``inspect.getmembers`` then enumerates every class in those modules.
   Every concrete subclass of ``Plugin`` (other than ``Plugin`` itself) is
   instantiated and added to the returned list.

There is no manual registration list. Two consequences:

- **Side effects at import time are dangerous.** Any module-level code
  runs during plugin discovery — including for ``sru-lint plugins``, which
  never executes any plugin. Keep import-time work to imports and class
  definitions.
- **Subclasses are discovered everywhere.** If you split a plugin across
  multiple files, only the concrete final class should inherit from
  ``Plugin``; intermediate helpers should be plain classes, otherwise they
  will be discovered too.

Reporting findings
~~~~~~~~~~~~~~~~~~

All rule IDs live in the ``ErrorCode`` enumeration in
``sru_lint/common/errors.py`` (e.g. ``CHANGELOG001``, ``PATCH002``,
``UCA_INVALID_PAIRING``). Use these instead of string literals so JSON
output and downstream consumers stay stable. Add a new value to the
enumeration when introducing a new rule.

The ``Severity`` enumeration (``sru_lint/common/feedback.py``) has ``ERROR``,
``WARNING``, and ``INFO``. Only ``ERROR`` causes a non-zero exit code from
``sru-lint check``.

For convenience the base class offers:

- ``create_feedback(message, rule_id, severity, source_span=..., line_number=..., col_start=..., col_end=..., doc_url=...)``
  — builds a ``FeedbackItem`` with a sensible ``SourceSpan`` and appends
  it to ``self.feedback``.
- ``create_line_feedback(message, rule_id, source_span, target_line_content, severity=..., doc_url=...)``
  — searches the source span for a given literal line, computes column
  offsets, and creates the feedback at the right line number.

If you build a ``FeedbackItem`` manually, pass it to ``self.add_feedback(item)``.

.. _launchpad-integration:

Launchpad integration
~~~~~~~~~~~~~~~~~~~~~

``self.lp_helper`` is a ``LaunchpadHelper`` (see
``sru_lint/common/launchpad_helper.py``). It exposes utilities such as
``get_bug``, ``is_bug_targeted``, ``get_valid_distributions``,
``get_uca_pairings``, ``get_highest_version_in_ppa``, and
``has_sru_template``.

Three things to know:

1. **Connections are lazy.** Constructing the helper (which happens when a
   plugin is instantiated) does not touch the network or the keyring. The
   first method call that needs a connection opens one. Plugins that never
   query Launchpad incur no Launchpad work at all — and ``sru-lint
   plugins`` never opens a connection.
2. **Thread-local connections.** Plugins run concurrently, and
   ``httplib2`` (used by ``launchpadlib``) is not thread-safe. Each worker
   thread gets its own anonymous (or authenticated, if the user ran
   ``sru-lint login``) ``Launchpad`` instance. Do **not** introduce a
   module-level ``Launchpad`` instance — share state only via the helper.
   Shared caches inside the helper (e.g. ``_distributions_cache``,
   ``_uca_pairings_cache``) are guarded by locks.
3. **Authentication is optional.** By default the helper opens an
   anonymous session. If the user has run ``sru-lint login`` and
   credentials are cached in the keyring, the helper picks them up
   automatically — needed for plugins that hit private PPAs
   (e.g. ESM/Pro). Plugins should not assume an authenticated session;
   degrade gracefully when private data is not accessible.

Concurrency notes
-----------------

Plugins are dispatched in a ``ThreadPoolExecutor`` (see
``run_plugins`` in ``sru_lint/cli.py``). Plugin instances are not shared
across threads — each plugin runs from a single thread — but any module-
level or class-level state you introduce **is** shared. Prefer instance
attributes for plugin state, and use ``threading.Lock`` (or the
thread-local pattern in ``launchpad_helper.py``) for anything genuinely
process-global.

Documentation
-------------

User-facing docs live in ``docs/user-docs/``; contributor docs (this file,
releasing, testing) live in ``docs/contrib-docs/``. The docs are built by
Read the Docs from ``docs/`` — see the live site at
https://canonical-sru-lint.readthedocs-hosted.com/.
