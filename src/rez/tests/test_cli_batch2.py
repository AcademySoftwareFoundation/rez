# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
In-process unit tests for rez CLI subcommands (batch 2).
"""
from __future__ import annotations

import argparse
import contextlib
import io
import logging
import os
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from rez.cli import (
    bind as cli_bind,
    depends as cli_depends,
    diff as cli_diff,
    help as cli_help,
    interpret as cli_interpret,
    mv as cli_mv,
    pip as cli_pip,
    plugins as cli_plugins,
    search as cli_search,
    view as cli_view,
)
from rez.cli._complete_util import FilesCompleter, PackageCompleter, PackageFamilyCompleter
from rez.config import config
from rez.serialise import FileFormat
from rez.tests.util import TempdirMixin, TestBase
from rez.vendor.argcomplete.completers import EnvironCompleter


def _make_parser(module, completions: bool = False) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rez-test")
    parser.add_argument("-v", "--verbose", action="count", default=0)
    module.setup_parser(parser, completions=completions)
    return parser


def _actions_by_dest(parser: argparse.ArgumentParser) -> dict[str, argparse.Action]:
    return {action.dest: action for action in parser._actions}


class TestCliBind(TestBase):
    def test_list(self) -> None:
        parser = _make_parser(cli_bind)
        opts = parser.parse_args(["--list"])
        buf = io.StringIO()
        with patch("rez.package_bind.get_bind_modules", return_value={"foo": "/a/foo.py", "bar": "/b/bar.py"}):
            with contextlib.redirect_stdout(buf):
                cli_bind.command(opts, parser)
        out = buf.getvalue()
        self.assertIn("PACKAGE", out)
        self.assertIn("bar", out)
        self.assertIn("foo", out)
        self.assertLess(out.index("bar"), out.index("foo"))

    def test_quickstart_with_and_without_variants(self) -> None:
        parser = _make_parser(cli_bind)
        opts = parser.parse_args(["--quickstart", "--release"])
        self.update_settings({"release_packages_path": "/tmp/rel_pkgs"})

        buf = io.StringIO()
        with patch("rez.package_bind.bind_package", return_value=["v1"]) as mock_bind:
            with patch("rez.package_bind._print_package_list") as mock_print:
                with contextlib.redirect_stdout(buf):
                    cli_bind.command(opts, parser)
        self.assertEqual(mock_bind.call_count, 8)
        self.assertEqual(mock_bind.call_args.kwargs["path"], "/tmp/rel_pkgs")
        self.assertTrue(mock_bind.call_args.kwargs["no_deps"])
        mock_print.assert_called_once()
        self.assertIn("Successfully converted", buf.getvalue())

        buf2 = io.StringIO()
        with patch("rez.package_bind.bind_package", return_value=[]):
            with patch("rez.package_bind._print_package_list") as mock_print2:
                with contextlib.redirect_stdout(buf2):
                    cli_bind.command(opts, parser)
        mock_print2.assert_not_called()
        self.assertNotIn("Successfully converted", buf2.getvalue())
        self.assertIn("To bind other software", buf2.getvalue())

    def test_missing_pkg_errors(self) -> None:
        parser = _make_parser(cli_bind)
        opts = parser.parse_args([])
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as cm:
                cli_bind.command(opts, parser)
        self.assertEqual(cm.exception.code, 2)

    def test_search_and_bind_package(self) -> None:
        parser = _make_parser(cli_bind)
        opts_search = parser.parse_args(["--search", "python"])
        with patch("rez.package_bind.find_bind_module") as mock_find:
            cli_bind.command(opts_search, parser)
        mock_find.assert_called_once_with("python", verbose=True)

        opts_bind = parser.parse_args(["-i", "/custom/path", "--no-deps", "python-3.10+", "--extra"])
        with patch("rez.package_bind.bind_package") as mock_bind:
            cli_bind.command(opts_bind, parser)
        mock_bind.assert_called_once()
        kwargs = mock_bind.call_args.kwargs
        self.assertEqual(mock_bind.call_args.args[0], "python")
        self.assertEqual(kwargs["path"], "/custom/path")
        self.assertIsNotNone(kwargs["version_range"])
        self.assertTrue(kwargs["no_deps"])
        self.assertEqual(kwargs["bind_args"], ["--extra"])

        opts_local = parser.parse_args(["python"])
        self.update_settings({"local_packages_path": "/local/pkgs"})
        with patch("rez.package_bind.bind_package") as mock_bind2:
            cli_bind.command(opts_local, parser)
        self.assertEqual(mock_bind2.call_args.kwargs["path"], "/local/pkgs")
        self.assertIsNone(mock_bind2.call_args.kwargs["version_range"])


class TestCliInterpret(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        TempdirMixin.setUpClass()

    @classmethod
    def tearDownClass(cls) -> None:
        TempdirMixin.tearDownClass()
        super().tearDownClass()

    def test_setup_parser_completions(self) -> None:
        parser_on = _make_parser(cli_interpret, completions=True)
        actions_on = _actions_by_dest(parser_on)
        self.assertIs(getattr(actions_on["parent_vars"], "completer", None), EnvironCompleter)
        self.assertIsInstance(getattr(actions_on["FILE"], "completer", None), FilesCompleter)

        parser_off = _make_parser(cli_interpret, completions=False)
        actions_off = _actions_by_dest(parser_off)
        self.assertIsNone(getattr(actions_off["parent_vars"], "completer", None))
        self.assertIsNone(getattr(actions_off["FILE"], "completer", None))

        opts = parser_on.parse_args(["-c", "env.FOO = 'bar'"])
        self.assertTrue(opts.command)

    def test_command_dict_and_table_and_no_env(self) -> None:
        parser = _make_parser(cli_interpret)
        with patch.dict(os.environ, {"REZ_TEST_HOST_SENTINEL": "1"}):
            opts_dict = parser.parse_args([
                "-c", "-f", "dict", "--no-env",
                "env.FOO = '1'\nenv.BAR = '2'\nenv.REZ_TEST_HOST_SENTINEL.append('2')",
                "--pv", "REZ_TEST_HOST_SENTINEL",
            ])
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                cli_interpret.command(opts_dict, parser)
            self.assertIn("'BAR': '2'", buf.getvalue())
            self.assertIn("'FOO': '1'", buf.getvalue())
            self.assertIn(f"'REZ_TEST_HOST_SENTINEL': '{os.pathsep}2'", buf.getvalue())

        with patch.dict(os.environ, {"REZ_TEST_HOST_SENTINEL": "1"}):
            opts_env = parser.parse_args([
                "-c", "-f", "dict",
                "env.FOO = '1'\nenv.REZ_TEST_HOST_SENTINEL.append('2')",
                "--pv", "REZ_TEST_HOST_SENTINEL",
            ])
            buf_env = io.StringIO()
            with contextlib.redirect_stdout(buf_env):
                cli_interpret.command(opts_env, parser)
            self.assertIn(f"'REZ_TEST_HOST_SENTINEL': '1{os.pathsep}2'", buf_env.getvalue())

        opts_table = parser.parse_args(["-c", "-f", "table", "--no-env", "env.FOO = '1'\nenv.BAR = '2'"])
        buf_table = io.StringIO()
        with contextlib.redirect_stdout(buf_table):
            cli_interpret.command(opts_table, parser)
        self.assertIn("BAR", buf_table.getvalue())
        self.assertIn("FOO", buf_table.getvalue())

    def test_command_file_and_shell_formats(self) -> None:
        from rez.shells import create_shell
        from rez.utils.platform_ import platform_

        shell_name = "cmd" if platform_.name == "windows" else "sh"
        rex_file = os.path.join(self.root, "script.rex")
        with open(rex_file, "w") as f:
            f.write("env.MY_VAR = 'hello'\n")

        target_shell = create_shell(shell_name)
        parser = _make_parser(cli_interpret)
        opts_default = parser.parse_args([rex_file, "--pv", "MY_VAR"])
        buf = io.StringIO()
        with patch("rez.shells.create_shell", return_value=target_shell) as mock_shell:
            with contextlib.redirect_stdout(buf):
                cli_interpret.command(opts_default, parser)
        mock_shell.assert_called_once_with()
        self.assertIn("MY_VAR", buf.getvalue())

        opts_explicit = parser.parse_args(["-c", "-f", shell_name, "env.X = '1'"])
        buf2 = io.StringIO()
        with patch("rez.shells.create_shell", wraps=create_shell) as mock_shell2:
            with contextlib.redirect_stdout(buf2):
                cli_interpret.command(opts_explicit, parser)
        mock_shell2.assert_called_once_with(shell_name)
        self.assertIn("X", buf2.getvalue())

    @unittest.expectedFailure
    def test_parent_vars_all_cli_arg(self) -> None:
        # Bug in src/rez/cli/interpret.py:69: --pv has nargs='+', so "--pv all"
        # parses as ["all"] rather than "all", making `opts.parent_vars == "all"`
        # unreachable via the CLI parser and passing ["all"] instead of True.
        parser = _make_parser(cli_interpret)
        opts = parser.parse_args(["-c", "-f", "sh", "env.X.append('1')", "--pv", "all"])
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cli_interpret.command(opts, parser)
        self.assertIn("${X}:1", buf.getvalue())


class TestCliView(TestBase):
    def test_setup_parser_completions(self) -> None:
        parser_on = _make_parser(cli_view, completions=True)
        actions_on = _actions_by_dest(parser_on)
        self.assertIs(getattr(actions_on["PKG"], "completer", None), PackageCompleter)

        parser_off = _make_parser(cli_view, completions=False)
        actions_off = _actions_by_dest(parser_off)
        self.assertIsNone(getattr(actions_off["PKG"], "completer", None))

        opts = parser_on.parse_args(["foo"])
        self.assertEqual(opts.PKG, "foo")

    def test_current_context_errors_and_success(self) -> None:
        parser = _make_parser(cli_view)
        opts = parser.parse_args(["-c", "foo"])

        with patch("rez.status.status", SimpleNamespace(context=None)):
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as cm:
                    cli_view.command(opts, parser)
        self.assertEqual(cm.exception.code, 1)

        ctx_missing = MagicMock()
        ctx_missing.get_resolved_package.return_value = None
        with patch("rez.status.status", SimpleNamespace(context=ctx_missing)):
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as cm2:
                    cli_view.command(opts, parser)
        self.assertEqual(cm2.exception.code, 1)

        pkg = MagicMock()
        pkg.uri = "/repo/foo/1.0/package.py"
        variant = SimpleNamespace(parent=pkg)
        ctx_ok = MagicMock()
        ctx_ok.get_resolved_package.return_value = variant
        opts_py = parser.parse_args(["-c", "-f", "py", "-a", "-b", "foo"])
        buf = io.StringIO()
        with patch("rez.status.status", SimpleNamespace(context=ctx_ok)):
            with contextlib.redirect_stdout(buf):
                cli_view.command(opts_py, parser)
        self.assertNotIn("URI:", buf.getvalue())
        self.assertNotIn("CONTENTS:", buf.getvalue())
        pkg.print_info.assert_called_once_with(format_=FileFormat.py, include_release=True)

    def test_iter_packages_not_found_and_found(self) -> None:
        parser = _make_parser(cli_view)
        opts = parser.parse_args(["foo"])

        with patch("rez.packages.iter_packages", return_value=[]):
            with contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as cm:
                    cli_view.command(opts, parser)
        self.assertEqual(cm.exception.code, 1)

        pkg1 = MagicMock(version="1.0", uri="/repo/foo/1.0/package.py")
        pkg2 = MagicMock(version="2.0", uri="/repo/foo/2.0/package.py")
        buf = io.StringIO()
        with patch("rez.packages.iter_packages", return_value=[pkg2, pkg1]):
            with contextlib.redirect_stdout(buf):
                cli_view.command(opts, parser)
        self.assertIn("URI:\n/repo/foo/2.0/package.py", buf.getvalue())
        self.assertIn("CONTENTS:", buf.getvalue())
        pkg2.print_info.assert_called_once_with(format_=FileFormat.yaml, include_release=False)


class TestCliHelp(TestBase):
    def test_setup_parser_completions(self) -> None:
        parser_on = _make_parser(cli_help, completions=True)
        actions_on = _actions_by_dest(parser_on)
        self.assertIs(getattr(actions_on["PKG"], "completer", None), PackageCompleter)

        parser_off = _make_parser(cli_help, completions=False)
        actions_off = _actions_by_dest(parser_off)
        self.assertIsNone(getattr(actions_off["PKG"], "completer", None))

        opts = parser_on.parse_args(["foo", "2"])
        self.assertEqual(opts.PKG, "foo")
        self.assertEqual(opts.SECTION, 2)

    def test_manual_or_no_pkg(self) -> None:
        parser = _make_parser(cli_help)
        for args in (["-m"], []):
            opts = parser.parse_args(args)
            with patch("rez.package_help.PackageHelp.open_rez_manual") as mock_open:
                with self.assertRaises(SystemExit) as cm:
                    cli_help.command(opts, parser)
            self.assertEqual(cm.exception.code, 0)
            mock_open.assert_called_once()

    def test_conflict_and_not_found(self) -> None:
        parser = _make_parser(cli_help)
        opts_conflict = parser.parse_args(["!foo"])
        with self.assertRaises(ValueError):
            cli_help.command(opts_conflict, parser)

        opts_missing = parser.parse_args(["foo"])
        fake_help = MagicMock(success=False)
        with patch("rez.package_help.PackageHelp", return_value=fake_help):
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as cm:
                    cli_help.command(opts_missing, parser)
        self.assertEqual(cm.exception.code, 1)

    def test_entries_open_and_index_error(self) -> None:
        parser = _make_parser(cli_help)
        pkg = SimpleNamespace(uri="/repo/foo/1.0", description="  A test package  ")
        fake_help = MagicMock(success=True, package=pkg)

        opts_entries = parser.parse_args(["-e", "foo"])
        buf = io.StringIO()
        with patch("rez.package_help.PackageHelp", return_value=fake_help):
            with contextlib.redirect_stdout(buf):
                cli_help.command(opts_entries, parser)
        self.assertIn("Description:\nA test package", buf.getvalue())
        fake_help.print_info.assert_called_once()

        pkg_nodesc = SimpleNamespace(uri="/repo/foo/1.0", description="")
        fake_help2 = MagicMock(success=True, package=pkg_nodesc)
        opts_open = parser.parse_args(["foo", "2"])
        with patch("rez.package_help.PackageHelp", return_value=fake_help2):
            with contextlib.redirect_stdout(io.StringIO()):
                cli_help.command(opts_open, parser)
        fake_help2.open.assert_called_once_with(1)

        fake_help2.open.side_effect = IndexError("out of range")
        with patch("rez.package_help.PackageHelp", return_value=fake_help2):
            with contextlib.redirect_stdout(io.StringIO()):
                with contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as cm:
                        cli_help.command(opts_open, parser)
        self.assertEqual(cm.exception.code, 2)


class TestCliSearch(TestBase):
    def test_setup_parser_completions(self) -> None:
        parser_on = _make_parser(cli_search, completions=True)
        actions_on = _actions_by_dest(parser_on)
        self.assertIs(getattr(actions_on["PKG"], "completer", None), PackageCompleter)

        parser_off = _make_parser(cli_search, completions=False)
        actions_off = _actions_by_dest(parser_off)
        self.assertIsNone(getattr(actions_off["PKG"], "completer", None))

        opts = parser_on.parse_args(["foo*"])
        self.assertEqual(opts.PKG, "foo*")

    def test_invalid_time_range(self) -> None:
        parser = _make_parser(cli_search)
        opts = parser.parse_args(["--after", "200", "--before", "100"])
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as cm:
                cli_search.command(opts, parser)
        self.assertEqual(cm.exception.code, 2)

    def test_search_results_and_empty_branches(self) -> None:
        parser = _make_parser(cli_search)
        opts = parser.parse_args(["--nw", "--no-local", "--paths", "/p1" + os.pathsep, "-t", "package", "foo"])

        searcher_inst = MagicMock()
        searcher_inst.search.return_value = ("package", [SimpleNamespace(validation_error=None)])
        formatter_inst = MagicMock()
        with patch("rez.package_search.ResourceSearcher", return_value=searcher_inst) as mock_cls:
            with patch("rez.package_search.ResourceSearchResultFormatter", return_value=formatter_inst):
                cli_search.command(opts, parser)
        self.assertEqual(mock_cls.call_args.kwargs["package_paths"], ["/p1"])
        self.assertEqual(mock_cls.call_args.kwargs["resource_type"], "package")
        self.assertTrue(mock_cls.call_args.kwargs["no_local"])
        formatter_inst.print_search_results.assert_called_once()

        # Empty results without --errors
        searcher_inst.search.return_value = ("package", [])
        opts_plain = parser.parse_args(["foo"])
        with patch("rez.package_search.ResourceSearcher", return_value=searcher_inst):
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as cm:
                    cli_search.command(opts_plain, parser)
        self.assertEqual(cm.exception.code, 1)

        # --errors with no erroneous results
        searcher_inst.search.return_value = ("package", [SimpleNamespace(validation_error=None)])
        opts_err = parser.parse_args(["-e", "foo"])
        with patch("rez.package_search.ResourceSearcher", return_value=searcher_inst):
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as cm2:
                    cli_search.command(opts_err, parser)
        self.assertEqual(cm2.exception.code, 1)

        # --errors with erroneous result
        err_res = SimpleNamespace(validation_error="bad")
        searcher_inst.search.return_value = ("package", [err_res])
        with patch("rez.package_search.ResourceSearcher", return_value=searcher_inst):
            with patch("rez.package_search.ResourceSearchResultFormatter", return_value=formatter_inst):
                cli_search.command(opts_err, parser)
        formatter_inst.print_search_results.assert_called_with([err_res])


class TestCliDepends(TestBase):
    def test_setup_parser_completions(self) -> None:
        parser_on = _make_parser(cli_depends, completions=True)
        actions_on = _actions_by_dest(parser_on)
        self.assertIs(getattr(actions_on["PKG"], "completer", None), PackageFamilyCompleter)

        parser_off = _make_parser(cli_depends, completions=False)
        actions_off = _actions_by_dest(parser_off)
        self.assertIsNone(getattr(actions_off["PKG"], "completer", None))

        opts = parser_on.parse_args(["foo"])
        self.assertEqual(opts.PKG, "foo")

    def test_text_output_normal_and_quiet(self) -> None:
        parser = _make_parser(cli_depends)
        opts = parser.parse_args(["--paths", "~/pkgs" + os.pathsep, "foo"])
        buf = io.StringIO()
        with patch(
            "rez.package_search.get_reverse_dependency_tree",
            return_value=([["foo"], ["bar"]], "g"),
        ) as mock_dep:
            with contextlib.redirect_stdout(buf):
                res = cli_depends.command(opts, parser)
        self.assertIsNone(res)
        self.assertTrue(config.show_progress)
        self.assertEqual(mock_dep.call_args.kwargs["paths"], [os.path.expanduser("~/pkgs")])
        self.assertFalse(mock_dep.call_args.kwargs["build_requires"])
        self.assertEqual(buf.getvalue().splitlines(), ["#0: foo", "#1: bar"])

        opts_q = parser.parse_args(["-q", "foo"])
        buf_q = io.StringIO()
        with patch("rez.package_search.get_reverse_dependency_tree", return_value=([["foo"], ["bar"]], "g")):
            with contextlib.redirect_stdout(buf_q):
                cli_depends.command(opts_q, parser)
        self.assertFalse(config.show_progress)
        self.assertEqual(buf_q.getvalue().splitlines(), ["foo", "bar"])

        opts_b = parser.parse_args(["-b", "foo"])
        with patch("rez.package_search.get_reverse_dependency_tree", return_value=([["foo"]], "g")) as mock_dep_b:
            with contextlib.redirect_stdout(io.StringIO()):
                cli_depends.command(opts_b, parser)
        self.assertTrue(mock_dep_b.call_args.kwargs["build_requires"])

    def test_graph_modes(self) -> None:
        parser = _make_parser(cli_depends)
        with patch("rez.package_search.get_reverse_dependency_tree", return_value=([], "g")):
            with patch("rez.vendor.pygraph.readwrite.dot.write", return_value="digraph {}"):
                opts_pg = parser.parse_args(["--pg", "foo"])
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    self.assertEqual(cli_depends.command(opts_pg, parser), 0)
                self.assertIn("digraph {}", buf.getvalue())

                opts_wg = parser.parse_args(["--wg", "/tmp/out.dot", "foo"])
                with patch("rez.utils.graph_utils.save_graph") as mock_save:
                    self.assertEqual(cli_depends.command(opts_wg, parser), 0)
                mock_save.assert_called_once_with("digraph {}", dest_file="/tmp/out.dot")

                opts_g = parser.parse_args(["-g", "foo"])
                with patch("rez.utils.graph_utils.view_graph") as mock_view:
                    self.assertEqual(cli_depends.command(opts_g, parser), 0)
                mock_view.assert_called_once_with("digraph {}")


class TestCliMv(TestBase):
    def test_setup_parser_completions(self) -> None:
        parser_on = _make_parser(cli_mv, completions=True)
        actions_on = _actions_by_dest(parser_on)
        self.assertIs(getattr(actions_on["PKG"], "completer", None), PackageCompleter)

        parser_off = _make_parser(cli_mv, completions=False)
        actions_off = _actions_by_dest(parser_off)
        self.assertIsNone(getattr(actions_off["PKG"], "completer", None))

        opts = parser_on.parse_args(["-d", "/dest", "foo-1.0"])
        self.assertEqual(opts.PKG, "foo-1.0")

    def test_list_repos_when_path_omitted(self) -> None:
        parser = _make_parser(cli_mv)
        opts = parser.parse_args(["-d", "/dest", "foo-1.0"])
        self.update_settings({"packages_path": ["/repo1", "/repo2"]})

        repo1 = MagicMock()
        repo1.get_package.return_value = MagicMock()
        repo1.__str__.return_value = "filesystem@/repo1"
        repo2 = MagicMock()
        repo2.get_package.return_value = None

        buf = io.StringIO()
        with patch("rez.package_repository.package_repository_manager.get_repository", side_effect=[repo1, repo2]):
            with contextlib.redirect_stdout(buf):
                with self.assertRaises(SystemExit) as cm:
                    cli_mv.command(opts, parser)
        self.assertEqual(cm.exception.code, 0)
        self.assertIn("filesystem@/repo1", buf.getvalue())

        repo_none = MagicMock()
        repo_none.get_package.return_value = None
        with patch("rez.package_repository.package_repository_manager.get_repository", return_value=repo_none):
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as cm2:
                    cli_mv.command(opts, parser)
        self.assertEqual(cm2.exception.code, 1)

    def test_move_package_and_not_found(self) -> None:
        parser = _make_parser(cli_mv)
        opts = parser.parse_args(["-d", "/dest", "-k", "-f", "foo-1.0", "/src"])

        with patch("rez.packages.get_package_from_repository", return_value=None):
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as cm:
                    cli_mv.command(opts, parser)
        self.assertEqual(cm.exception.code, 1)

        src_pkg = MagicMock()
        with patch("rez.packages.get_package_from_repository", return_value=src_pkg):
            with patch("rez.package_move.move_package") as mock_move:
                cli_mv.command(opts, parser)
        mock_move.assert_called_once_with(
            package=src_pkg,
            dest_repository="/dest",
            keep_timestamp=True,
            force=True,
            verbose=0,
        )


class TestCliDiff(TestBase):
    def test_setup_parser_completions(self) -> None:
        parser_on = _make_parser(cli_diff, completions=True)
        actions_on = _actions_by_dest(parser_on)
        self.assertIs(getattr(actions_on["PKG1"], "completer", None), PackageCompleter)
        self.assertIs(getattr(actions_on["PKG2"], "completer", None), PackageCompleter)

        parser_off = _make_parser(cli_diff, completions=False)
        actions_off = _actions_by_dest(parser_off)
        self.assertIsNone(getattr(actions_off["PKG1"], "completer", None))
        self.assertIsNone(getattr(actions_off["PKG2"], "completer", None))

        opts = parser_on.parse_args(["foo-1.0", "foo-2.0"])
        self.assertEqual(opts.PKG1, "foo-1.0")
        self.assertEqual(opts.PKG2, "foo-2.0")

    def test_diff_one_and_two_packages(self) -> None:
        parser = _make_parser(cli_diff)
        pkg1 = MagicMock()
        pkg2 = MagicMock()

        opts_one = parser.parse_args(["foo-1.0"])
        with patch("rez.packages.get_package_from_string", return_value=pkg1):
            with patch("rez.utils.diff_packages.diff_packages") as mock_diff:
                cli_diff.command(opts_one, parser)
        mock_diff.assert_called_once_with(pkg1, None)

        opts_two = parser.parse_args(["foo-1.0", "foo-2.0"])
        with patch("rez.packages.get_package_from_string", side_effect=[pkg1, pkg2]):
            with patch("rez.utils.diff_packages.diff_packages") as mock_diff2:
                cli_diff.command(opts_two, parser)
        mock_diff2.assert_called_once_with(pkg1, pkg2)


class TestCliPip(TestBase):
    def test_missing_install_flag_errors(self) -> None:
        parser = _make_parser(cli_pip)
        opts = parser.parse_args(["requests"])
        rez_logger = logging.getLogger("rez")
        orig_level = rez_logger.level
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as cm:
                    cli_pip.command(opts, parser)
            self.assertEqual(cm.exception.code, 2)
            self.assertEqual(rez_logger.level, logging.INFO)
        finally:
            rez_logger.setLevel(orig_level)

    def test_install_invokes_pip_install_package(self) -> None:
        parser = _make_parser(cli_pip)
        opts = parser.parse_args([
            "-v", "-i", "-r", "--python-version", "3.11", "-p", "/custom", "requests", "-e", "--no-deps",
        ])
        rez_logger = logging.getLogger("rez")
        orig_level = rez_logger.level
        try:
            with patch("rez.pip.pip_install_package") as mock_pip:
                cli_pip.command(opts, parser)
            mock_pip.assert_called_once_with(
                "requests",
                python_version="3.11",
                release=True,
                prefix="/custom",
                extra_args=["--no-deps"],
            )
            self.assertTrue(config.debug_package_release)
        finally:
            rez_logger.setLevel(orig_level)


class TestCliPlugins(TestBase):
    def test_setup_parser_completions(self) -> None:
        parser_on = _make_parser(cli_plugins, completions=True)
        actions_on = _actions_by_dest(parser_on)
        self.assertIs(getattr(actions_on["PKG"], "completer", None), PackageFamilyCompleter)

        parser_off = _make_parser(cli_plugins, completions=False)
        actions_off = _actions_by_dest(parser_off)
        self.assertIsNone(getattr(actions_off["PKG"], "completer", None))

        opts = parser_on.parse_args(["foo"])
        self.assertEqual(opts.PKG, "foo")

    def test_plugins_found_and_none_found(self) -> None:
        parser = _make_parser(cli_plugins)
        opts = parser.parse_args(["--paths", "~/p1" + os.pathsep, "foo"])
        buf = io.StringIO()
        with patch("rez.package_search.get_plugins", return_value=["plug_a", "plug_b"]) as mock_get:
            with contextlib.redirect_stdout(buf):
                cli_plugins.command(opts, parser)
        self.assertEqual(mock_get.call_args.kwargs["paths"], [os.path.expanduser("~/p1")])
        self.assertEqual(buf.getvalue().splitlines(), ["plug_a", "plug_b"])

        opts_none = parser.parse_args(["foo"])
        err = io.StringIO()
        with patch("rez.package_search.get_plugins", return_value=[]):
            with contextlib.redirect_stderr(err):
                cli_plugins.command(opts_none, parser)
        self.assertIn("package 'foo' has no plugins.", err.getvalue())
