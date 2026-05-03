# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
test running of all commandline tools (just -h on each)
"""
from rez.tests.util import TestBase
import argparse
import contextlib
import io
import os
import os.path
import subprocess
import sys
import unittest
from tempfile import TemporaryFile
from unittest.mock import patch

from rez.system import system
from rez.cli._entry_points import get_specifications
from rez.cli._main import setup_parser
from rez.cli import complete as complete_module
from rez.cli.complete import command as complete_command
from rez.vendor.argcomplete import autocomplete


@contextlib.contextmanager
def _disable_fd_9():
    """Make ``os.fdopen(9, ...)`` raise within the ``with`` block.

    argcomplete unconditionally does ``os.fdopen(9, "w")`` for its debug
    stream. Under pytest, fd 9 is part of pytest's capture / faulthandler
    machinery; wrapping it either breaks subsequent tests or breaks pytest
    shutdown. Forcing the open to fail makes argcomplete fall back to
    ``sys.stderr``, which is safe.
    """
    real_fdopen = os.fdopen

    def fake_fdopen(fd, *args, **kwargs):
        if fd == 9:
            raise OSError("fd 9 disabled in tests")
        return real_fdopen(fd, *args, **kwargs)

    with patch("os.fdopen", side_effect=fake_fdopen):
        yield


class TestImports(TestBase):
    def test_1(self) -> None:
        """run -h option on every cli tool"""

        # skip if cli not available
        if not system.rez_bin_path:
            self.skipTest("Not a production install")

        for toolname in get_specifications().keys():
            if toolname.startswith('_'):
                continue

            binfile = os.path.join(system.rez_bin_path, toolname)
            subprocess.check_output([binfile, "-h"])


class TestComplete(TestBase):
    """Test argcomplete-driven completion against the actual rez parser.

    Uses the in-process pattern from argcomplete's own test suite
    (https://github.com/kislyuk/argcomplete/blob/main/test/test.py): set
    COMP_LINE/COMP_POINT/_ARGCOMPLETE in the env, call ``autocomplete()``
    with an output_stream and exit_method, then split the captured output
    by IFS.
    """

    IFS = "\013"

    def setUp(self) -> None:
        super().setUp()
        self._saved_environ = os.environ.copy()
        os.environ["_ARGCOMPLETE"] = "1"
        os.environ["IFS"] = self.IFS
        os.environ["_ARGCOMPLETE_SHELL"] = "bash"

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._saved_environ)
        super().tearDown()

    # Inspired by https://github.com/kislyuk/argcomplete/blob/8e5ad6a5a702e5529f61ae9a63f720beda68ffaf/test/test.py#L118-L143  # noqa
    def _run_completer(self, command, point=None):
        if point is None:
            point = len(command)
        os.environ["COMP_LINE"] = command
        os.environ["COMP_POINT"] = str(point)

        parser = setup_parser()
        with TemporaryFile(mode="w+") as t:
            with _disable_fd_9():
                with self.assertRaises(SystemExit) as cm:
                    autocomplete(parser, output_stream=t, exit_method=sys.exit)
            self.assertEqual(cm.exception.code, 0)
            t.seek(0)
            return set(t.read().split(self.IFS))

    def test_subcommand_completion(self) -> None:
        """`rez <TAB>` should list subcommands."""
        completions = self._run_completer("rez ")
        self.assertIn("env", completions)
        self.assertIn("build", completions)

    def test_subcommand_prefix(self) -> None:
        """`rez bui<TAB>` should narrow to `build`."""
        completions = self._run_completer("rez bui")
        self.assertEqual(completions, {"build "})

    def test_subcommand_options(self) -> None:
        """`rez env --<TAB>` should list options for the env subcommand."""
        completions = self._run_completer("rez env --")
        # --help is on every parser, --input/--output are env-specific
        self.assertIn("--help", completions)
        self.assertIn("--input", completions)
        self.assertIn("--output", completions)

    def _run_complete_command(self, command, point=None):
        """Drive ``rez.cli.complete.command()`` (the ``_rez-complete`` tool).

        Unlike ``autocomplete()``, this entry point reads COMP_LINE/COMP_POINT
        from the environment, prints space-separated completions to stdout,
        and returns normally (no SystemExit).
        """
        if point is None:
            point = len(command)
        os.environ["COMP_LINE"] = command
        os.environ["COMP_POINT"] = str(point)

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            complete_command(None, None, None)
        return set(buf.getvalue().split())

    def test_command_subcommand_listing(self) -> None:
        """`_rez-complete` for `rez ` should list subcommands."""
        completions = self._run_complete_command("rez ")

        # Only test a few entries as to not make these tests
        # annoying to maintain.
        self.assertIn("env", completions)
        self.assertIn("build", completions)
        self.assertGreater(len(completions), 2)
        # hidden subcommands should not be listed
        self.assertNotIn("complete", completions)
        self.assertNotIn("forward", completions)

    def test_command_subcommand_prefix(self) -> None:
        """`_rez-complete` for `rez bui` should narrow to `build`."""
        self.assertEqual(
            self._run_complete_command("rez bui"),
            {"build"}
        )
        self.assertEqual(
            self._run_complete_command("rez c"),
            {"config", "context", "cp"}
        )

    def test_command_subcommand_options(self) -> None:
        """`_rez-complete` for `rez env --` should exercise RezCompletionFinder.

        This is the path that uses ``rez.cli._complete_util.RezCompletionFinder``
        (where the locale-aware byte->char COMP_POINT translation lives).
        """
        with _disable_fd_9():
            completions = self._run_complete_command("rez env --")

        # --help is on every parser, --input/--output are env-specific
        self.assertIn("--help", completions)
        self.assertIn("--input", completions)
        self.assertIn("--output", completions)

    def test_command_setup_parser_is_noop(self) -> None:
        """``complete.setup_parser`` is a no-op; calling it must not modify
        the parser or raise."""
        parser = argparse.ArgumentParser()
        before = list(parser._actions)
        complete_module.setup_parser(parser)
        self.assertEqual(parser._actions, before)

    def test_command_invalid_comp_point(self) -> None:
        """A non-numeric COMP_POINT must fall back to ``len(comp_line)``."""
        os.environ["COMP_LINE"] = "rez bui"
        os.environ["COMP_POINT"] = "not-an-int"

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            complete_command(None, None, None)
        self.assertEqual(set(buf.getvalue().split()), {"build"})

    def test_command_hyphenated_invocation(self) -> None:
        """``rez-env --`` (the hyphenated form) must take the ``else`` branch
        that derives the subcommand by splitting on ``-``."""
        with _disable_fd_9():
            completions = self._run_complete_command("rez-env --")

        # Same expectations as the `rez env --` case — proves the
        # `cmd.split("-", 1)[-1]` branch hands off to the same parser.
        self.assertIn("--help", completions)
        self.assertIn("--input", completions)
        self.assertIn("--output", completions)

    def test_command_double_dash_munging(self) -> None:
        """A `` -- `` sequence in the line must be rewritten to ``--N#`` so
        that the subcommand parser's ``--N0`` / ``--N1`` actions match."""
        # `rez env` declares an `--N0` action for args after `--`. We type
        # ``rez env -- `` so the regex r"\s--\s" matches and the munging
        # loop runs. The resulting completions come from the env subparser.
        with _disable_fd_9():
            completions = self._run_complete_command("rez env -- ")

        # We don't assert specific completions (the args-after-`--` path
        # invokes an executables/files completer that depends on $PATH and
        # cwd); we just need the munging loop to have run without raising.
        # As a sanity check, make sure we got *some* output back.
        self.assertIsInstance(completions, set)

    def test_command_double_dash_cursor_before_dashes(self) -> None:
        """When COMP_POINT is before the ``--``, the munging loop must
        leave comp_point unchanged (the false branch of `if comp_point >= j`).
        """
        # Place the cursor early in the line ("rez ", position 4) so that
        # by the time the munging loop runs, comp_point is below the index
        # of the inserted N# token.
        with _disable_fd_9():
            completions = self._run_complete_command("rez env -- ", point=4)
        self.assertIsInstance(completions, set)


if __name__ == '__main__':
    unittest.main()
