# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Unit tests for rez.cli.selftest.
"""
import argparse
import contextlib
import importlib
import io
import os
import sys
import tempfile
import types
import unittest
from unittest.mock import MagicMock, patch

from rez.cli import selftest
from rez.packages import iter_packages
from rez.tests.util import TempdirMixin, TestBase, restore_os_environ


class TestCliSelftestImport(TestBase):
    """Tests for module-level import behavior in rez.cli.selftest."""

    def test_use_pytest_fallback_when_pytest_missing(self) -> None:
        """When pytest cannot be imported, use_pytest must be False."""
        try:
            with patch.dict(sys.modules, {"pytest": None}):
                reloaded = importlib.reload(selftest)
                self.assertFalse(reloaded.use_pytest)
        finally:
            reloaded = importlib.reload(selftest)
            self.assertTrue(reloaded.use_pytest)


class TestCliSelftestSetupParser(TestBase):
    """Tests for rez.cli.selftest.setup_parser."""

    def _make_fake_module(self, doc, file_path="/fake/test_mod.py"):
        mod = types.ModuleType("test_fake")
        mod.__doc__ = doc
        mod.__file__ = file_path
        return mod

    def test_setup_parser_registers_valid_modules_and_action(self) -> None:
        """setup_parser discovers test_* modules, adds flags, and populates module_tests."""
        fake_mod_a = self._make_fake_module("Alpha tests.")
        fake_mod_b = self._make_fake_module("Beta tests.")

        def make_importer(mod):
            spec = MagicMock()
            spec.loader = MagicMock()
            importer = MagicMock()
            importer.find_spec.return_value = spec
            return importer, spec

        imp_a, _ = make_importer(fake_mod_a)
        imp_b, _ = make_importer(fake_mod_b)
        fake_entries = [
            (imp_a, "test_alpha", False),
            (imp_b, "test_beta", False),
            (MagicMock(), "not_a_test", False),
            (MagicMock(), "test_pkg", True),
        ]

        modules_by_name = {"test_alpha": fake_mod_a, "test_beta": fake_mod_b}
        parser = argparse.ArgumentParser()
        fake_all = []

        with patch("rez.cli.selftest.iter_modules", return_value=fake_entries):
            with patch("rez.cli.selftest.all_module_tests", fake_all):
                with patch(
                    "rez.cli.selftest.importlib.util.module_from_spec",
                    side_effect=lambda spec: modules_by_name[
                        "test_alpha" if spec is imp_a.find_spec.return_value else "test_beta"
                    ],
                ):
                    with patch.dict(sys.modules, {}):
                        selftest.setup_parser(parser)

        self.assertEqual(fake_all, ["alpha", "beta"])

        opts = parser.parse_args(["--alpha", "--beta", "extra_test"])
        self.assertEqual(opts.module_tests, ["alpha", "beta"])
        self.assertEqual(opts.tests, ["extra_test"])

        # Exercise AddTestModuleAction when namespace.module_tests is None
        action = next(a for a in parser._actions if "--alpha" in a.option_strings)
        ns = argparse.Namespace()
        action(parser, ns, [], option_string="--alpha")
        self.assertEqual(ns.module_tests, ["alpha"])

    def test_setup_parser_raises_on_missing_docstring(self) -> None:
        """setup_parser raises RuntimeError when a test module has no docstring."""
        fake_mod = self._make_fake_module(None, file_path="/fake/test_nodoc.py")
        spec = MagicMock()
        spec.loader = MagicMock()
        importer = MagicMock()
        importer.find_spec.return_value = spec

        parser = argparse.ArgumentParser()
        with patch("rez.cli.selftest.iter_modules", return_value=[(importer, "test_nodoc", False)]):
            with patch("rez.cli.selftest.all_module_tests", []):
                with patch("rez.cli.selftest.importlib.util.module_from_spec", return_value=fake_mod):
                    with patch.dict(sys.modules, {}):
                        with self.assertRaises(RuntimeError) as cm:
                            selftest.setup_parser(parser)

        self.assertIn("/fake/test_nodoc.py", str(cm.exception))


class TestCliSelftestCommand(TestBase, TempdirMixin):
    """Tests for rez.cli.selftest.command."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        TempdirMixin.setUpClass()

    @classmethod
    def tearDownClass(cls) -> None:
        TempdirMixin.tearDownClass()
        super().tearDownClass()

    def _make_opts(
        self,
        module_tests=None,
        tests=None,
        only_shell=None,
        keep_tmpdirs=False,
        verbose=0,
    ):
        return argparse.Namespace(
            module_tests=module_tests or [],
            tests=tests or [],
            only_shell=only_shell,
            keep_tmpdirs=keep_tmpdirs,
            verbose=verbose,
        )

    def test_command_runs_all_tests_with_pytest_and_sets_env(self) -> None:
        """command() sets env vars, creates/cleans repo, and invokes run_pytest."""
        opts = self._make_opts(only_shell="bash", keep_tmpdirs=True, verbose=2)
        expected_repo = os.path.join(self.root, "__tests_pkg_repo")

        with restore_os_environ():
            with patch("rez.cli.selftest.os.getcwd", return_value=self.root):
                with patch("rez.cli.selftest.all_module_tests", ["cli", "solver"]):
                    with patch("rez.cli.selftest.use_pytest", True):
                        with patch("rez.cli.selftest.create_python_package") as mock_create:
                            with patch("rez.cli.selftest.run_pytest") as mock_run_pytest:
                                with patch("rez.cli.selftest.safe_rmtree") as mock_rmtree:
                                    selftest.command(opts, MagicMock(), extra_arg_groups=[["-k", "foo"]])

            self.assertEqual(os.environ.get("__REZ_SELFTEST_RUNNING"), "1")
            self.assertEqual(os.environ.get("__REZ_SELFTEST_SHELL"), "bash")
            self.assertEqual(os.environ.get("REZ_KEEP_TMPDIRS"), "1")
            self.assertEqual(os.environ.get("__REZ_SELFTEST_PYTHON_REPO"), expected_repo)

        mock_create.assert_called_once_with(expected_repo)
        mock_run_pytest.assert_called_once_with(["cli", "solver"], [], 2, [["-k", "foo"]])
        mock_rmtree.assert_called_once_with(expected_repo)

    def test_command_runs_selected_tests_with_unittest_and_cleans_on_error(self) -> None:
        """command() uses opts.module_tests, calls run_unittest when use_pytest is False, and cleans repo."""
        opts = self._make_opts(module_tests=["config"], tests=["extra"], verbose=1)
        expected_repo = os.path.join(self.root, "__tests_pkg_repo")

        with restore_os_environ():
            os.environ.pop("__REZ_SELFTEST_SHELL", None)
            os.environ.pop("REZ_KEEP_TMPDIRS", None)
            with patch("rez.cli.selftest.os.getcwd", return_value=self.root):
                with patch("rez.cli.selftest.use_pytest", False):
                    with patch("rez.cli.selftest.create_python_package"):
                        with patch("rez.cli.selftest.run_unittest", side_effect=RuntimeError("boom")) as mock_unittest:
                            with patch("rez.cli.selftest.safe_rmtree") as mock_rmtree:
                                with self.assertRaises(RuntimeError):
                                    selftest.command(opts, MagicMock())

            self.assertNotIn("__REZ_SELFTEST_SHELL", os.environ)
            self.assertNotIn("REZ_KEEP_TMPDIRS", os.environ)

        mock_unittest.assert_called_once_with(["config"], ["extra"], 1)
        mock_rmtree.assert_called_once_with(expected_repo)


class TestCliSelftestRunners(TestBase):
    """Tests for run_unittest and run_pytest."""

    def test_run_unittest(self) -> None:
        """run_unittest builds sorted module list and invokes unittest.main.main."""
        unittest_main_mod = importlib.import_module("unittest.main")
        with patch.object(unittest_main_mod, "main") as mock_main:
            selftest.run_unittest(["solver", "cli"], ["rez.tests.test_foo.TestFoo"], 2)

        mock_main.assert_called_once_with(
            module=None,
            argv=[
                sys.argv[0],
                "rez.tests.test_cli",
                "rez.tests.test_solver",
                "rez.tests.test_foo.TestFoo",
            ],
            verbosity=2,
        )

    def test_run_pytest_with_verbosity_and_extra_args(self) -> None:
        """run_pytest sorts module_tests, appends verbosity/extra args, and exits with pytest exitcode."""
        tests_dir = os.path.abspath(os.path.join(selftest.__file__, "..", "..", "tests"))

        with patch("pytest.main", return_value=0) as mock_main:
            with self.assertRaises(SystemExit) as cm:
                selftest.run_pytest(
                    ["cli", "build"],
                    ["nonexistent.TestNone"],
                    2,
                    [["-k", "test_01"]],
                )

        self.assertEqual(cm.exception.code, 0)
        expected_args = [
            os.path.join(tests_dir, "test_build.py"),
            os.path.join(tests_dir, "test_cli.py"),
            "-vv",
            "-k",
            "test_01",
        ]
        mock_main.assert_called_once_with(args=expected_args)

    @unittest.expectedFailure
    def test_run_pytest_dotted_spec_from_non_tests_cwd(self) -> None:
        """run_pytest fails to resolve dotted specs when cwd != tests_dir (src/rez/cli/selftest.py:140)."""
        tests_dir = os.path.abspath(os.path.join(selftest.__file__, "..", "..", "tests"))
        old_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                os.chdir(tmpdir)
                with patch("pytest.main", return_value=0) as mock_main:
                    with self.assertRaises(SystemExit) as cm:
                        selftest.run_pytest([], ["rez.tests.test_solver.TestSolver.test_01"], 0, None)
            finally:
                os.chdir(old_cwd)

        self.assertEqual(cm.exception.code, 0)
        expected_spec = os.path.join(tests_dir, "test_solver.py") + "::TestSolver::test_01"
        mock_main.assert_called_once_with(args=[expected_spec])

    def test_run_pytest_no_verbosity_no_extra_args(self) -> None:
        """run_pytest omits verbosity and extra args when falsy and forwards nonzero exitcode."""
        tests_dir = os.path.abspath(os.path.join(selftest.__file__, "..", "..", "tests"))

        with patch("pytest.main", return_value=1) as mock_main:
            with self.assertRaises(SystemExit) as cm:
                selftest.run_pytest(["cli"], [], 0, None)

        self.assertEqual(cm.exception.code, 1)
        mock_main.assert_called_once_with(args=[os.path.join(tests_dir, "test_cli.py")])


class TestCliSelftestCreatePythonPackage(TestBase, TempdirMixin):
    """Tests for rez.cli.selftest.create_python_package."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        TempdirMixin.setUpClass()

    @classmethod
    def tearDownClass(cls) -> None:
        TempdirMixin.tearDownClass()
        super().tearDownClass()

    def test_create_python_package_writes_package(self) -> None:
        """create_python_package creates a python package with expected version, tools, and venv root."""
        repo = os.path.join(self.root, "pkg_repo")
        os.makedirs(repo, exist_ok=True)
        buf = io.StringIO()

        with contextlib.redirect_stdout(buf):
            with patch("venv.create") as mock_venv_create:
                selftest.create_python_package(repo)

        self.assertIn("Creating python package in", buf.getvalue())
        self.assertEqual(mock_venv_create.call_count, 1)

        pkgs = list(iter_packages("python", paths=[repo]))
        self.assertEqual(len(pkgs), 1)
        expected_version = ".".join(map(str, sys.version_info[:3]))
        self.assertEqual(str(pkgs[0].version), expected_version)
        self.assertEqual(pkgs[0].tools, ["python"])

    def test_create_python_package_commands_windows_and_posix(self) -> None:
        """Inner commands() function prepends Scripts on Windows and bin on POSIX."""
        captured = {}

        @contextlib.contextmanager
        def fake_make_package(name, path, make_root=None, warn_on_skip=True):
            pkg = MagicMock()
            yield pkg
            captured["commands"] = pkg.commands

        mock_env = MagicMock()
        mock_system = MagicMock()

        with contextlib.redirect_stdout(io.StringIO()):
            with patch("rez.package_maker.make_package", side_effect=fake_make_package):
                with patch("rez.utils.lint_helper.env", mock_env):
                    with patch("rez.utils.lint_helper.system", mock_system):
                        selftest.create_python_package("/fake/repo")

                        mock_system.platform = "windows"
                        captured["commands"]()
                        mock_env.PATH.prepend.assert_called_with("{this.root}/Scripts")

                        mock_env.PATH.prepend.reset_mock()
                        mock_system.platform = "linux"
                        captured["commands"]()
                        mock_env.PATH.prepend.assert_called_with("{this.root}/bin")
