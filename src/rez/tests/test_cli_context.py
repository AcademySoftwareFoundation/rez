# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Unit tests for rez.cli.context (rez-context / rez context).
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import os.path
from unittest.mock import MagicMock, patch

from rez.cli import context as cli_context
from rez.cli._main import _add_common_args
from rez.resolved_context import ResolvedContext
from rez.status import status
from rez.system import system
from rez.tests.util import TempdirMixin, TestBase
from rez.utils.filesystem import canonical_path
from rez.utils.platform_ import platform_


def _write_package(pkg_dir, name, version, requires=None, tools=None, env_vars=None):
    os.makedirs(pkg_dir, exist_ok=True)
    lines = [
        f"name = {name!r}",
        f"version = {version!r}",
    ]
    if requires:
        lines.append(f"requires = {requires!r}")
    if tools:
        lines.append(f"tools = {tools!r}")
        bin_dir = os.path.join(pkg_dir, "bin")
        os.makedirs(bin_dir, exist_ok=True)
        for tool in tools:
            if platform_.name == "windows":
                tool_path = os.path.join(bin_dir, f"{tool}.bat")
                with open(tool_path, "w") as f:
                    f.write("@echo off\necho ok\n")
            else:
                tool_path = os.path.join(bin_dir, tool)
                with open(tool_path, "w") as f:
                    f.write("#!/bin/sh\necho ok\n")
                os.chmod(tool_path, 0o755)
    cmd_lines = []
    if tools:
        cmd_lines.append("    env.PATH.append('{root}/bin')")
    if env_vars:
        for k, v in env_vars.items():
            cmd_lines.append(f"    env.{k} = {v!r}")
    if cmd_lines:
        lines.append("def commands():")
        lines.extend(cmd_lines)
    with open(os.path.join(pkg_dir, "package.py"), "w") as f:
        f.write("\n".join(lines) + "\n")


class TestCliContext(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        TempdirMixin.setUpClass()

        cls.packages_path = os.path.join(cls.root, "packages")
        _write_package(
            os.path.join(cls.packages_path, "lib", "1.0.0"),
            "lib",
            "1.0.0",
            env_vars={"LIB_VAR": "1"},
        )
        _write_package(
            os.path.join(cls.packages_path, "lib", "2.0.0"),
            "lib",
            "2.0.0",
            env_vars={"LIB_VAR": "2"},
        )
        _write_package(
            os.path.join(cls.packages_path, "app", "1.0.0"),
            "app",
            "1.0.0",
            requires=["lib-1.0.0"],
            tools=["app_tool"],
            env_vars={"APP_VAR": "one"},
        )
        _write_package(
            os.path.join(cls.packages_path, "app", "2.0.0"),
            "app",
            "2.0.0",
            requires=["lib-2.0.0"],
            tools=["app_tool"],
            env_vars={"APP_VAR": "two"},
        )

        cls.settings = dict(
            packages_path=[cls.packages_path],
            package_filter=None,
            implicit_packages=[],
            warn_untimestamped=False,
            resolve_caching=False,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        TempdirMixin.tearDownClass()
        super().tearDownClass()

    def setUp(self) -> None:
        super().setUp()
        self.rc_v1 = ResolvedContext(["app==1.0.0"])
        self.rxt_v1 = os.path.join(self.root, "v1.rxt")
        self.rc_v1.save(self.rxt_v1)

        self.rc_v2 = ResolvedContext(["app==2.0.0"])
        self.rxt_v2 = os.path.join(self.root, "v2.rxt")
        self.rc_v2.save(self.rxt_v2)

    def _make_parser(self, completions: bool = False) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser("rez-context")
        cli_context.setup_parser(parser, completions=completions)
        _add_common_args(parser)
        return parser

    def _run_cli(self, args):
        parser = self._make_parser()
        opts = parser.parse_args(args)
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            cli_context.command(opts, parser)
        return stdout.getvalue(), stderr.getvalue()

    def test_setup_parser_completions(self) -> None:
        from rez.cli._complete_util import FilesCompleter

        parser = self._make_parser(completions=True)
        actions = {a.dest: a for a in parser._actions}
        self.assertIsInstance(actions["RXT"].completer, FilesCompleter)
        self.assertIsInstance(actions["diff"].completer, FilesCompleter)

    def test_setup_parser_without_json(self) -> None:
        parser = argparse.ArgumentParser("rez-context")
        with patch("rez.cli.context.json", None):
            cli_context.setup_parser(parser)
        format_action = next(a for a in parser._actions if a.dest == "format")
        self.assertNotIn("json", format_action.choices)

    def test_no_context_exits_with_error(self) -> None:
        parser = self._make_parser()
        opts = parser.parse_args([])
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch.object(status, "context_file", None):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                with self.assertRaises(SystemExit) as cm:
                    cli_context.command(opts, parser)
        self.assertEqual(cm.exception.code, 1)
        self.assertIn("not in a resolved environment context", stderr.getvalue())

    def test_uses_status_context_file_when_rxt_omitted(self) -> None:
        with patch.object(status, "context_file", self.rxt_v1):
            out, err = self._run_cli(["--req"])
        self.assertEqual(err, "")
        self.assertIn("app==1.0.0", out)

    def test_read_context_from_stdin(self) -> None:
        buf = io.StringIO()
        self.rc_v1.write_to_buffer(buf)
        buf.seek(0)
        with patch("sys.stdin", buf):
            out, err = self._run_cli(["--req", "-"])
        self.assertEqual(err, "")
        self.assertIn("app==1.0.0", out)

    def test_print_request(self) -> None:
        out, _ = self._run_cli(["--req", self.rxt_v1])
        self.assertEqual(out.strip(), "app==1.0.0")

        with self.subTest("excludes_implicit_packages"):
            self.update_settings({"implicit_packages": ["lib==1.0.0"]})
            rc_implicit = ResolvedContext(["app==1.0.0"])
            self.assertIn("lib==1.0.0", [str(r) for r in rc_implicit.requested_packages(True)])
            rxt_implicit = os.path.join(self.root, "implicit.rxt")
            rc_implicit.save(rxt_implicit)

            out_implicit, _ = self._run_cli(["--req", rxt_implicit])
            self.assertEqual(out_implicit.strip(), "app==1.0.0")
            self.assertNotIn("lib", out_implicit)

    def test_print_resolve_names_and_uris(self) -> None:
        out_names, _ = self._run_cli(["--res", self.rxt_v1])
        self.assertIn("app-1.0.0", out_names)
        self.assertIn("lib-1.0.0", out_names)

        out_uris, _ = self._run_cli(["--res", "--su", self.rxt_v1])
        self.assertIn(canonical_path(self.packages_path), out_uris)

    def test_print_tools(self) -> None:
        captured = io.StringIO()
        orig = ResolvedContext.print_tools
        with patch.object(
            ResolvedContext,
            "print_tools",
            autospec=True,
            side_effect=lambda rc_self, *a, **kw: orig(rc_self, *a, buf=captured, **kw),
        ):
            self._run_cli(["--tools", self.rxt_v1])
        self.assertIn("app_tool", captured.getvalue())

    def test_diff_against_other_context(self) -> None:
        with patch.object(ResolvedContext, "print_resolve_diff", autospec=True) as mock_diff:
            self._run_cli(["--diff", self.rxt_v2, self.rxt_v1])
        mock_diff.assert_called_once()
        rc_other = mock_diff.call_args.args[1]
        self.assertEqual([p.qualified_package_name for p in rc_other.resolved_packages], ["lib-2.0.0", "app-2.0.0"])
        self.assertTrue(mock_diff.call_args.args[2])

    def test_fetch_diff(self) -> None:
        fetch_pkgs = os.path.join(self.root, "fetch_pkgs")
        _write_package(
            os.path.join(fetch_pkgs, "lib", "1.0.0"),
            "lib",
            "1.0.0",
        )
        _write_package(
            os.path.join(fetch_pkgs, "app", "1.0.0"),
            "app",
            "1.0.0",
            requires=["lib-1.0.0"],
        )
        self.update_settings({"packages_path": [fetch_pkgs]})
        rc_unpinned = ResolvedContext(["app>=1.0.0"])
        rxt_unpinned = os.path.join(self.root, "unpinned.rxt")
        rc_unpinned.save(rxt_unpinned)

        _write_package(
            os.path.join(fetch_pkgs, "lib", "2.0.0"),
            "lib",
            "2.0.0",
        )
        _write_package(
            os.path.join(fetch_pkgs, "app", "2.0.0"),
            "app",
            "2.0.0",
            requires=["lib-2.0.0"],
        )
        system.clear_caches()

        orig = ResolvedContext.print_resolve_diff
        seen = {}

        def _capture_diff(rc_self, rc_other, *args, **kwargs):
            seen["rc_self"] = rc_self
            seen["rc_other"] = rc_other
            seen["heading"] = kwargs.get("heading")
            return orig(rc_self, rc_other, *args, **kwargs)

        with patch.object(
            ResolvedContext,
            "print_resolve_diff",
            autospec=True,
            side_effect=_capture_diff,
        ):
            out, err = self._run_cli(["--fetch", rxt_unpinned])

        self.assertEqual(err, "")
        self.assertIsNot(seen["rc_other"], seen["rc_self"])
        self.assertIsInstance(seen["rc_other"], ResolvedContext)
        self.assertEqual(seen["rc_other"].package_paths, [fetch_pkgs])
        self.assertEqual(
            [p.qualified_package_name for p in seen["rc_other"].resolved_packages],
            ["lib-2.0.0", "app-2.0.0"],
        )
        self.assertEqual(seen["heading"], ("current", "updated"))
        self.assertIn("current", out)
        self.assertIn("updated", out)
        self.assertIn("app-1.0.0", out)
        self.assertIn("app-2.0.0", out)

    def test_which_found_and_not_found(self) -> None:
        out, err = self._run_cli(["--which", "app_tool", self.rxt_v1])
        self.assertEqual(err, "")
        self.assertIn("app_tool", out)

        out_missing, err_missing = self._run_cli(["--which", "no_such_cmd_xyz", self.rxt_v1])
        self.assertEqual(out_missing, "")
        self.assertIn("'no_such_cmd_xyz' not found in the context", err_missing)

    def test_print_graph_and_dependency_graph(self) -> None:
        out_graph, _ = self._run_cli(["--pg", self.rxt_v1])
        self.assertIn("digraph", out_graph)
        self.assertIn("app==1.0.0", out_graph)

        out_dep, _ = self._run_cli(["--pg", "-d", self.rxt_v1])
        self.assertIn("digraph", out_dep)
        self.assertNotEqual(out_dep, out_graph)
        self.assertIn("app -> lib", out_dep)
        self.assertNotIn("app==1.0.0", out_dep)

    def test_graph_missing_exits_with_error(self) -> None:
        fake_rc = MagicMock(has_graph=False)
        parser = self._make_parser()
        opts = parser.parse_args(["--pg", self.rxt_v1])
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("rez.resolved_context.ResolvedContext.load", return_value=fake_rc):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                with self.assertRaises(SystemExit) as cm:
                    cli_context.command(opts, parser)
        self.assertEqual(cm.exception.code, 1)
        self.assertIn("The context does not contain a graph.", stderr.getvalue())

    def test_view_graph_options(self) -> None:
        with patch("rez.utils.graph_utils.view_graph") as mock_view:
            self._run_cli(["-g", self.rxt_v1])
        mock_view.assert_called_once()
        self.assertIsNone(mock_view.call_args.kwargs["dest_file"])

        with patch("rez.utils.graph_utils.view_graph") as mock_view:
            self._run_cli(["-d", self.rxt_v1])
        mock_view.assert_called_once()

    def test_write_graph_and_prune_package(self) -> None:
        dest = os.path.join(self.root, "out.png")
        with patch("rez.utils.graph_utils.save_graph") as mock_save:
            self._run_cli(["--wg", dest, "--pp", "app", self.rxt_v1])
        mock_save.assert_called_once()
        gstr = mock_save.call_args.args[0]
        self.assertIn("app-1.0.0", gstr)
        self.assertNotIn("lib-1.0.0", gstr)
        self.assertNotEqual(gstr, self.rc_v1.graph(as_dot=True))
        self.assertEqual(mock_save.call_args.kwargs["dest_file"], dest)

    def test_default_print_info(self) -> None:
        captured = io.StringIO()
        orig = ResolvedContext.print_info
        with patch.object(
            ResolvedContext,
            "print_info",
            autospec=True,
            side_effect=lambda rc_self, *a, **kw: orig(rc_self, *a, buf=captured, **kw),
        ):
            self._run_cli(["--so", "--su", "-v", self.rxt_v1])
        output = captured.getvalue()
        self.assertIn("resolved packages:", output)
        self.assertIn("app-1.0.0", output)

    def test_interpret_table_dict_json(self) -> None:
        out_table, _ = self._run_cli(["-i", "-f", "table", "--no-env", self.rxt_v1])
        self.assertIn("APP_VAR", out_table)
        self.assertIn("one", out_table)

        out_dict, _ = self._run_cli(["-i", "-f", "dict", "--no-env", self.rxt_v1])
        self.assertIn("'APP_VAR': 'one'", out_dict)

        out_json, _ = self._run_cli(["-i", "-f", "json", "--no-env", self.rxt_v1])
        parsed = json.loads(out_json)
        self.assertEqual(parsed["APP_VAR"], "one")

    def test_interpret_shell_code(self) -> None:
        shell = "cmd" if platform_.name == "windows" else "sh"
        out_sh, _ = self._run_cli(["-i", "-f", shell, "-s", "eval", "--no-env", self.rxt_v1])
        self.assertIn("APP_VAR", out_sh)
        self.assertIn("one", out_sh)
