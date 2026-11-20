# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Unit tests for the `rez suite` CLI module (`rez.cli.suite`).
"""
from __future__ import annotations

import argparse
import contextlib
import io
import unittest
from unittest.mock import MagicMock, patch

from rez.cli.suite import command, setup_parser
from rez.exceptions import SuiteError
from rez.tests.util import TestBase


def _make_parser(completions: bool = False) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rez-suite")
    parser.add_argument("-v", "--verbose", action="count", default=0)
    setup_parser(parser, completions=completions)
    return parser


class TestSuiteCLI(TestBase):
    """Tests for `rez.cli.suite.setup_parser` and `rez.cli.suite.command`."""

    def _run_command(self, args: list[str], parser: argparse.ArgumentParser | None = None):
        if parser is None:
            parser = _make_parser()
        opts = parser.parse_args(args)
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            with contextlib.redirect_stderr(stderr):
                command(opts, parser)
        return stdout.getvalue(), stderr.getvalue()

    def test_setup_parser_defaults(self) -> None:
        parser = _make_parser(completions=False)
        opts = parser.parse_args(["/tmp/mysuite"])
        self.assertEqual(opts.DIR, "/tmp/mysuite")
        self.assertFalse(opts.list)
        self.assertFalse(opts.create)
        self.assertIsNone(opts.context)

    def test_setup_parser_with_completions(self) -> None:
        from rez.cli._complete_util import (
            FilesCompleter,
            PackageCompleter,
            PackageFamilyCompleter,
        )

        parser = _make_parser(completions=True)
        actions = {a.dest: a for a in parser._actions}
        self.assertIsInstance(actions["DIR"].completer, FilesCompleter)
        self.assertIs(actions["find_request"].completer, PackageFamilyCompleter)
        self.assertIs(actions["find_resolve"].completer, PackageCompleter)

    @unittest.expectedFailure
    def test_setup_parser_add_completer(self) -> None:
        # Bug in src/rez/cli/suite.py:34-37,84: `add_action` for `--add` is
        # overwritten by `--prefix-char`, attaching the *.rxt FilesCompleter
        # to `prefix_char` instead of `add`.
        from rez.cli._complete_util import FilesCompleter

        parser = _make_parser(completions=True)
        actions = {a.dest: a for a in parser._actions}
        self.assertIsInstance(
            getattr(actions["add"], "completer", None), FilesCompleter
        )
        self.assertIsNone(getattr(actions["prefix_char"], "completer", None))

    def test_missing_dir_errors(self) -> None:
        with self.assertRaises(SystemExit) as cm:
            self._run_command([])
        self.assertEqual(cm.exception.code, 2)

    def test_list_with_suites(self) -> None:
        s1 = MagicMock(load_path="/suites/one")
        s2 = MagicMock(load_path="/suites/two")
        fake_status = MagicMock(suites=[s1, s2])
        parser = _make_parser()
        opts = parser.parse_args(["--list"])
        stdout = io.StringIO()
        with patch("rez.status.status", fake_status):
            with contextlib.redirect_stdout(stdout):
                with self.assertRaises(SystemExit) as cm:
                    command(opts, parser)
        self.assertEqual(cm.exception.code, 0)
        self.assertEqual(stdout.getvalue(), "/suites/one\n/suites/two\n")

    def test_list_empty(self) -> None:
        fake_status = MagicMock(suites=[])
        parser = _make_parser()
        opts = parser.parse_args(["--list"])
        stdout = io.StringIO()
        with patch("rez.status.status", fake_status):
            with contextlib.redirect_stdout(stdout):
                with self.assertRaises(SystemExit) as cm:
                    command(opts, parser)
        self.assertEqual(cm.exception.code, 0)
        self.assertEqual(stdout.getvalue(), "No visible suites.\n")

    def test_create_suite(self) -> None:
        mock_suite_cls = MagicMock()
        mock_suite = mock_suite_cls.return_value
        parser = _make_parser()
        opts = parser.parse_args(["-v", "--create", "/suites/new"])
        stdout = io.StringIO()
        with patch("rez.suite.Suite", mock_suite_cls):
            with contextlib.redirect_stdout(stdout):
                with self.assertRaises(SystemExit) as cm:
                    command(opts, parser)
        self.assertEqual(cm.exception.code, 0)
        mock_suite.save.assert_called_once_with("/suites/new")
        self.assertIn("create empty suite at '/suites/new'...", stdout.getvalue())

    def test_context_required_options(self) -> None:
        mock_suite_cls = MagicMock()
        cases = [
            ["--add", "ctx.rxt", "/suites/s"],
            ["--prefix", "pre_", "/suites/s"],
            ["--suffix", "_suf", "/suites/s"],
            ["--hide", "tool1", "/suites/s"],
            ["--unhide", "tool1", "/suites/s"],
            ["--alias", "tool1", "t1", "/suites/s"],
            ["--unalias", "t1", "/suites/s"],
            ["--interactive", "/suites/s"],
        ]
        for args in cases:
            with self.subTest(args=args):
                with patch("rez.suite.Suite", mock_suite_cls):
                    with self.assertRaises(SystemExit) as cm:
                        self._run_command(args)
                self.assertEqual(cm.exception.code, 2)

    def test_interactive(self) -> None:
        mock_suite_cls = MagicMock()
        mock_suite = mock_suite_cls.load.return_value
        mock_ctx = mock_suite.context.return_value
        mock_ctx.execute_shell.return_value = (7, None, None)

        parser = _make_parser()
        opts = parser.parse_args(["--interactive", "--context", "myctx", "/suites/s"])
        with patch("rez.suite.Suite", mock_suite_cls):
            with self.assertRaises(SystemExit) as cm:
                command(opts, parser)

        self.assertEqual(cm.exception.code, 7)
        mock_suite.context.assert_called_once_with("myctx")
        mock_ctx.execute_shell.assert_called_once_with(block=True)

    def test_validate_valid(self) -> None:
        mock_suite_cls = MagicMock()
        mock_suite = mock_suite_cls.load.return_value
        with patch("rez.suite.Suite", mock_suite_cls):
            stdout, stderr = self._run_command(["--validate", "/suites/s"])

        self.assertEqual(stdout, "The suite is valid.\n")
        self.assertEqual(stderr, "")
        mock_suite.validate.assert_called_once_with()
        mock_suite.save.assert_not_called()

    def test_validate_invalid(self) -> None:
        mock_suite_cls = MagicMock()
        mock_suite = mock_suite_cls.load.return_value
        mock_suite.validate.side_effect = SuiteError("broken tool")

        parser = _make_parser()
        opts = parser.parse_args(["--validate", "/suites/s"])
        stderr = io.StringIO()
        with patch("rez.suite.Suite", mock_suite_cls):
            with contextlib.redirect_stderr(stderr):
                with self.assertRaises(SystemExit) as cm:
                    command(opts, parser)

        self.assertEqual(cm.exception.code, 1)
        self.assertIn("The suite is invalid:\nbroken tool", stderr.getvalue())

    def test_find_request_and_resolve(self) -> None:
        mock_suite_cls = MagicMock()
        mock_suite = mock_suite_cls.load.return_value
        mock_suite.find_contexts.return_value = ["ctx_a", "ctx_b"]

        with patch("rez.suite.Suite", mock_suite_cls):
            stdout, _ = self._run_command(["--find-request", "foo", "/suites/s"])

        self.assertEqual(stdout, "ctx_a\nctx_b\n")
        mock_suite.find_contexts.assert_called_once_with(
            in_request="foo", in_resolve=None
        )
        mock_suite.save.assert_not_called()

    def test_find_resolve_empty(self) -> None:
        mock_suite_cls = MagicMock()
        mock_suite = mock_suite_cls.load.return_value
        mock_suite.find_contexts.return_value = []

        with patch("rez.suite.Suite", mock_suite_cls):
            stdout, _ = self._run_command(["--find-resolve", "bar-1.0", "/suites/s"])

        self.assertEqual(stdout, "")
        mock_suite.find_contexts.assert_called_once_with(
            in_request=None, in_resolve="bar-1.0"
        )

    def test_print_tools(self) -> None:
        mock_suite_cls = MagicMock()
        mock_suite = mock_suite_cls.load.return_value

        with patch("rez.suite.Suite", mock_suite_cls):
            self._run_command(["-v", "--tools", "--context", "ctx1", "/suites/s"])

        mock_suite.print_tools.assert_called_once_with(
            verbose=1, context_name="ctx1"
        )
        mock_suite.save.assert_not_called()

    def test_add_context_and_save_verbose(self) -> None:
        mock_suite_cls = MagicMock()
        mock_suite = mock_suite_cls.load.return_value
        mock_rxt_cls = MagicMock()
        mock_rxt = mock_rxt_cls.load.return_value

        with patch("rez.suite.Suite", mock_suite_cls):
            with patch("rez.resolved_context.ResolvedContext", mock_rxt_cls):
                stdout, _ = self._run_command(
                    [
                        "-v",
                        "--add",
                        "/tmp/ctx.rxt",
                        "--context",
                        "myctx",
                        "--prefix-char",
                        "%",
                        "/suites/s",
                    ]
                )

        mock_rxt_cls.load.assert_called_once_with("/tmp/ctx.rxt")
        mock_suite.add_context.assert_called_once_with(
            name="myctx", context=mock_rxt, prefix_char="%"
        )
        mock_suite.save.assert_called_once_with("/suites/s")
        self.assertIn("loading context at '/tmp/ctx.rxt'...", stdout)
        self.assertIn("adding context 'myctx'...", stdout)
        self.assertIn("saving suite to '/suites/s'...", stdout)

    def test_remove_context(self) -> None:
        mock_suite_cls = MagicMock()
        mock_suite = mock_suite_cls.load.return_value

        with patch("rez.suite.Suite", mock_suite_cls):
            stdout, _ = self._run_command(["--remove", "oldctx", "/suites/s"])

        self.assertEqual(stdout, "")
        mock_suite.remove_context.assert_called_once_with(name="oldctx")
        mock_suite.save.assert_called_once_with("/suites/s")

    def test_bump_context(self) -> None:
        mock_suite_cls = MagicMock()
        mock_suite = mock_suite_cls.load.return_value

        with patch("rez.suite.Suite", mock_suite_cls):
            self._run_command(["--bump", "myctx", "/suites/s"])

        mock_suite.bump_context.assert_called_once_with(name="myctx")
        mock_suite.save.assert_called_once_with("/suites/s")

    def test_prefix_and_suffix(self) -> None:
        mock_suite_cls = MagicMock()
        mock_suite = mock_suite_cls.load.return_value

        with patch("rez.suite.Suite", mock_suite_cls):
            self._run_command(
                ["--prefix", "pre_", "--context", "c1", "/suites/s"]
            )
            mock_suite.set_context_prefix.assert_called_once_with(
                name="c1", prefix="pre_"
            )
            mock_suite.save.assert_called_once_with("/suites/s")

            mock_suite.reset_mock()
            self._run_command(
                ["--suffix", "_suf", "--context", "c1", "/suites/s"]
            )
            mock_suite.set_context_suffix.assert_called_once_with(
                name="c1", suffix="_suf"
            )
            mock_suite.save.assert_called_once_with("/suites/s")

    def test_hide_and_unhide_tool(self) -> None:
        mock_suite_cls = MagicMock()
        mock_suite = mock_suite_cls.load.return_value

        with patch("rez.suite.Suite", mock_suite_cls):
            self._run_command(["--hide", "maya", "--context", "c1", "/suites/s"])
            mock_suite.hide_tool.assert_called_once_with(
                context_name="c1", tool_name="maya"
            )
            mock_suite.save.assert_called_once_with("/suites/s")

            mock_suite.reset_mock()
            self._run_command(
                ["--unhide", "maya", "--context", "c1", "/suites/s"]
            )
            mock_suite.unhide_tool.assert_called_once_with(
                context_name="c1", tool_name="maya"
            )
            mock_suite.save.assert_called_once_with("/suites/s")

    def test_alias_and_unalias_tool(self) -> None:
        mock_suite_cls = MagicMock()
        mock_suite = mock_suite_cls.load.return_value

        with patch("rez.suite.Suite", mock_suite_cls):
            self._run_command(
                ["--alias", "python", "py", "--context", "c1", "/suites/s"]
            )
            mock_suite.alias_tool.assert_called_once_with(
                context_name="c1", tool_name="python", tool_alias="py"
            )
            mock_suite.save.assert_called_once_with("/suites/s")

            mock_suite.reset_mock()
            self._run_command(
                ["--unalias", "py", "--context", "c1", "/suites/s"]
            )
            mock_suite.unalias_tool.assert_called_once_with(
                context_name="c1", tool_name="py"
            )
            mock_suite.save.assert_called_once_with("/suites/s")

    def test_which_found(self) -> None:
        mock_suite_cls = MagicMock()
        mock_suite = mock_suite_cls.load.return_value
        mock_suite.get_tool_filepath.return_value = "/suites/s/bin/python"

        parser = _make_parser()
        opts = parser.parse_args(["--which", "python", "/suites/s"])
        stdout = io.StringIO()
        with patch("rez.suite.Suite", mock_suite_cls):
            with contextlib.redirect_stdout(stdout):
                with self.assertRaises(SystemExit) as cm:
                    command(opts, parser)

        self.assertEqual(cm.exception.code, 0)
        self.assertEqual(stdout.getvalue(), "/suites/s/bin/python\n")
        mock_suite.get_tool_filepath.assert_called_once_with("python")

    def test_which_not_found(self) -> None:
        mock_suite_cls = MagicMock()
        mock_suite = mock_suite_cls.load.return_value
        mock_suite.get_tool_filepath.return_value = None

        parser = _make_parser()
        opts = parser.parse_args(["--which", "missing", "/suites/s"])
        with patch("rez.suite.Suite", mock_suite_cls):
            with self.assertRaises(SystemExit) as cm:
                command(opts, parser)

        self.assertEqual(cm.exception.code, 1)

    def test_context_info(self) -> None:
        mock_suite_cls = MagicMock()
        mock_suite = mock_suite_cls.load.return_value
        mock_ctx = mock_suite.context.return_value

        with patch("rez.suite.Suite", mock_suite_cls):
            self._run_command(["-vv", "--context", "c1", "/suites/s"])

        mock_suite.context.assert_called_once_with("c1")
        mock_ctx.print_info.assert_called_once_with(verbosity=2)
        mock_suite.save.assert_not_called()

    def test_suite_info_default(self) -> None:
        mock_suite_cls = MagicMock()
        mock_suite = mock_suite_cls.load.return_value

        parser = _make_parser()
        opts = parser.parse_args(["-v", "/suites/s"])
        with patch("rez.suite.Suite", mock_suite_cls):
            with self.assertRaises(SystemExit) as cm:
                command(opts, parser)

        self.assertEqual(cm.exception.code, 0)
        mock_suite.print_info.assert_called_once_with(verbose=1)
        mock_suite.save.assert_not_called()
