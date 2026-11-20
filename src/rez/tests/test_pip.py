# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Unit tests for rez.pip.
"""
import os
import stat
import sys
import tempfile
from types import SimpleNamespace
from unittest import mock

from rez.exceptions import (
    BuildError,
    PackageFamilyNotFoundError,
    PackageNotFoundError,
    RezSystemError,
)
from rez.pip import (
    InstallMode,
    _check_found,
    _cmd,
    _get_distribution_files_mapping,
    _is_exe,
    _log,
    _option_present,
    find_pip,
    find_pip_from_context,
    find_python_in_context,
    pip_install_package,
    run_pip_command,
)
from rez.tests.util import TempdirMixin, TestBase
from rez.vendor.distlib.database import DistributionPath
from rez.version import Version


class TestPipHelpers(TestBase):
    """Tests for small helper functions in rez.pip."""

    def test_install_mode_enum(self) -> None:
        self.assertEqual(InstallMode.no_deps.value, 0)
        self.assertEqual(InstallMode.min_deps.value, 1)

    def test_is_exe(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            missing = os.path.join(tmpdir, "missing")
            non_exe = os.path.join(tmpdir, "plain.txt")
            exe_file = os.path.join(tmpdir, "run.sh")

            with open(non_exe, "w") as f:
                f.write("hello\n")
            os.chmod(non_exe, stat.S_IRUSR | stat.S_IWUSR)

            with open(exe_file, "w") as f:
                f.write("#!/bin/sh\n")
            os.chmod(exe_file, stat.S_IRWXU)

            self.assertFalse(_is_exe(missing))
            if sys.platform != "win32" and os.geteuid() != 0:
                self.assertFalse(_is_exe(non_exe))
            self.assertTrue(_is_exe(exe_file))

    def test_option_present(self) -> None:
        self.assertTrue(_option_present(["-t", "/tmp/out"], "-t", "--target"))
        self.assertTrue(_option_present(["--target=/tmp/out"], "-t", "--target"))
        self.assertFalse(_option_present(["--target-dir", "/tmp"], "-t", "--target"))
        self.assertFalse(_option_present([], "-t", "--target"))

    def test_check_found(self) -> None:
        with mock.patch("rez.pip.print_debug") as mock_debug, \
                mock.patch("rez.pip.print_warning") as mock_warn:
            self.assertFalse(_check_found(None, "23.0", log_invalid=True))
            mock_debug.assert_called_once()
            mock_warn.assert_not_called()

        with mock.patch("rez.pip.print_debug") as mock_debug:
            self.assertFalse(_check_found("/usr/bin/python", None, log_invalid=False))
            mock_debug.assert_not_called()

        with mock.patch("rez.pip.print_warning") as mock_warn:
            self.assertFalse(_check_found("/usr/bin/python", "18.1", log_invalid=True))
            mock_warn.assert_called_once()

        with mock.patch("rez.pip.print_warning") as mock_warn:
            self.assertFalse(_check_found("/usr/bin/python", "18.1", log_invalid=False))
            mock_warn.assert_not_called()

        self.assertTrue(_check_found("/usr/bin/python", "19.0"))
        self.assertTrue(_check_found("/usr/bin/python", "24.2"))

    def test_log(self) -> None:
        with mock.patch("rez.pip._verbose", True), \
                mock.patch("rez.pip.print_debug") as mock_debug:
            _log("hello")
            mock_debug.assert_called_once_with("hello")

        with mock.patch("rez.pip._verbose", False), \
                mock.patch("rez.pip.print_debug") as mock_debug:
            _log("hello")
            mock_debug.assert_not_called()

    def test_cmd_without_context(self) -> None:
        proc = mock.MagicMock()
        proc.__enter__.return_value = proc
        proc.returncode = 0

        with mock.patch("rez.pip.Popen", return_value=proc) as mock_popen:
            _cmd(None, ["python", "-m", "pip", "install", "pkg"])

        mock_popen.assert_called_once_with(["python", "-m", "pip", "install", "pkg"])
        proc.wait.assert_called_once()

    def test_cmd_with_context_and_failure(self) -> None:
        proc = mock.MagicMock()
        proc.__enter__.return_value = proc
        proc.returncode = 1
        context = mock.MagicMock()
        context.execute_shell.return_value = proc

        with self.assertRaises(BuildError):
            _cmd(context, ["python", "-m", "pip", "install", "bad pkg"])

        context.execute_shell.assert_called_once_with(
            command=["python", "-m", "pip", "install", "bad pkg"],
            block=False,
        )
        proc.wait.assert_called_once()


class TestFindPip(TestBase):
    """Tests for pip and python discovery functions in rez.pip."""

    def test_run_pip_command_without_context(self) -> None:
        proc = mock.MagicMock()
        with mock.patch("rez.pip.find_pip", return_value=("/usr/bin/python", None)), \
                mock.patch("rez.pip.Popen", return_value=proc) as mock_popen:
            result = run_pip_command(["list", "--format=json"], pip_version="23.0", python_version="3.11")

        self.assertIs(result, proc)
        mock_popen.assert_called_once_with(["/usr/bin/python", "-m", "pip", "list", "--format=json"])

    def test_run_pip_command_with_context(self) -> None:
        proc = mock.MagicMock()
        context = mock.MagicMock()
        context.execute_shell.return_value = proc

        with mock.patch("rez.pip.find_pip", return_value=("/ctx/bin/python", context)):
            result = run_pip_command(["--version"])

        self.assertIs(result, proc)
        context.execute_shell.assert_called_once_with(
            command=["/ctx/bin/python", "-m", "pip", "--version"],
            block=False,
        )

    def test_find_python_in_context(self) -> None:
        copied_ctx = mock.MagicMock()
        copied_ctx.append_sys_path = True
        copied_ctx.get_resolved_package.return_value = SimpleNamespace(version=Version("3.11.4"))
        copied_ctx.which.side_effect = [None, None, "/ctx/bin/python"]

        original_ctx = mock.MagicMock()
        original_ctx.copy.return_value = copied_ctx

        result = find_python_in_context(original_ctx)
        self.assertEqual(result, "/ctx/bin/python")
        self.assertFalse(copied_ctx.append_sys_path)
        self.assertEqual(
            [c.args[0] for c in copied_ctx.which.call_args_list],
            ["python3.11", "python3", "python"],
        )

        # Returns None when no executable is found
        copied_ctx.which.side_effect = [None, None, None]
        self.assertIsNone(find_python_in_context(original_ctx))

    def test_find_pip_from_context_no_python_package(self) -> None:
        with mock.patch("rez.pip.get_latest_package", return_value=None):
            with self.assertRaises(BuildError):
                find_pip_from_context(python_version=None)

    def test_find_pip_from_context_latest_python_success(self) -> None:
        latest_py = SimpleNamespace(version=Version("3.11.9"))
        variant = SimpleNamespace(parent=SimpleNamespace(uri="/repo/python/3.11.9"))
        proc = mock.MagicMock()
        proc.communicate.return_value = ("23.2.1\n", "")
        proc.returncode = 0

        ctx = mock.MagicMock()
        ctx.execute_command.return_value = proc
        ctx.get_resolved_package.return_value = variant

        with mock.patch("rez.pip.get_latest_package", return_value=latest_py), \
                mock.patch("rez.pip.ResolvedContext", return_value=ctx) as mock_rc, \
                mock.patch("rez.pip.find_python_in_context", return_value="/ctx/python3.11"):
            py_exe, pip_ver, out_ctx = find_pip_from_context(python_version=None, pip_version=None)

        mock_rc.assert_called_once_with(["python-3.11"])
        self.assertEqual(py_exe, "/ctx/python3.11")
        self.assertEqual(pip_ver, "23.2.1")
        self.assertIs(out_ctx, ctx)

    def test_find_pip_from_context_with_pip_version(self) -> None:
        variant = SimpleNamespace(parent=SimpleNamespace(uri="/repo/pip/23.1"))
        proc = mock.MagicMock()
        proc.communicate.return_value = ("23.1\n", "")
        proc.returncode = 0

        ctx = mock.MagicMock()
        ctx.execute_command.return_value = proc
        ctx.get_resolved_package.return_value = variant

        with mock.patch("rez.pip.ResolvedContext", return_value=ctx) as mock_rc, \
                mock.patch("rez.pip.find_python_in_context", return_value="/ctx/python3.11"):
            py_exe, pip_ver, out_ctx = find_pip_from_context("3.11.4", pip_version="latest")

        mock_rc.assert_called_once_with(["python-3.11", "pip"])
        self.assertEqual(pip_ver, "23.1")
        self.assertIs(out_ctx, ctx)

        with mock.patch("rez.pip.ResolvedContext", return_value=ctx) as mock_rc, \
                mock.patch("rez.pip.find_python_in_context", return_value="/ctx/python3.11"):
            find_pip_from_context("3.11.4", pip_version="23.1")

        mock_rc.assert_called_once_with(["python-3.11", "pip-23.1"])

    def test_find_pip_from_context_missing_package(self) -> None:
        for exc in (PackageFamilyNotFoundError("no family"), PackageNotFoundError("no pkg")):
            with self.subTest(exc=type(exc).__name__):
                with mock.patch("rez.pip.ResolvedContext", side_effect=exc):
                    self.assertEqual(find_pip_from_context("3.11"), (None, None, None))

    def test_find_pip_from_context_no_py_exe(self) -> None:
        ctx = mock.MagicMock()
        with mock.patch("rez.pip.ResolvedContext", return_value=ctx), \
                mock.patch("rez.pip.find_python_in_context", return_value=None):
            self.assertEqual(find_pip_from_context("3.11"), (None, None, ctx))

    def test_find_pip_from_context_nonzero_returncode(self) -> None:
        proc = mock.MagicMock()
        proc.communicate.return_value = ("", "No module named pip")
        proc.returncode = 1
        ctx = mock.MagicMock()
        ctx.execute_command.return_value = proc

        with mock.patch("rez.pip.ResolvedContext", return_value=ctx), \
                mock.patch("rez.pip.find_python_in_context", return_value="/ctx/python3.11"):
            self.assertEqual(find_pip_from_context("3.11"), (None, None, None))

    def test_find_pip_uses_requested_version(self) -> None:
        ctx = mock.MagicMock()
        with mock.patch("rez.pip.find_pip_from_context", return_value=("/ctx/py", "23.0", ctx)) as mock_find:
            py_exe, out_ctx = find_pip(pip_version="23.0", python_version="3.11")

        mock_find.assert_called_once_with("3.11", pip_version="23.0")
        self.assertEqual(py_exe, "/ctx/py")
        self.assertIs(out_ctx, ctx)

    def test_find_pip_falls_back_to_latest_context(self) -> None:
        ctx = mock.MagicMock()
        with mock.patch(
            "rez.pip.find_pip_from_context",
            side_effect=[(None, None, None), ("/ctx/py", "24.0", ctx)],
        ) as mock_find:
            py_exe, out_ctx = find_pip(pip_version="20.0", python_version="3.11")

        self.assertEqual(mock_find.call_count, 2)
        self.assertEqual(py_exe, "/ctx/py")
        self.assertIs(out_ctx, ctx)

    def test_find_pip_falls_back_to_system_pip(self) -> None:
        fake_pip = SimpleNamespace(__version__="23.1", __file__="/fake/pip/__init__.py")
        with mock.patch(
            "rez.pip.find_pip_from_context",
            side_effect=[BuildError("no python"), (None, None, None)],
        ), mock.patch.dict(sys.modules, {"pip": fake_pip}), \
                mock.patch("rez.pip.print_warning") as mock_warn:
            py_exe, out_ctx = find_pip(pip_version="20.0")

        self.assertEqual(py_exe, sys.executable)
        self.assertIsNone(out_ctx)
        self.assertGreaterEqual(mock_warn.call_count, 3)

    def test_find_pip_raises_when_pip_too_old(self) -> None:
        fake_pip = SimpleNamespace(__version__="18.0", __file__="/fake/pip/__init__.py")
        with mock.patch("rez.pip.find_pip_from_context", return_value=(None, None, None)), \
                mock.patch.dict(sys.modules, {"pip": fake_pip}), \
                mock.patch("rez.pip.print_warning"):
            with self.assertRaises(RezSystemError):
                find_pip()


class TestDistributionFilesMapping(TestBase, TempdirMixin):
    """Tests for _get_distribution_files_mapping."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        TempdirMixin.setUpClass()

    @classmethod
    def tearDownClass(cls) -> None:
        TempdirMixin.tearDownClass()
        super().tearDownClass()

    def _make_dist(self, files):
        dist = mock.MagicMock()
        dist.name = "demo"
        dist.version = "1.0.0"
        dist.list_installed_files.return_value = [(f, "", "") for f in files]
        return dist

    def test_mapping_dist_info_remaps_and_missing(self) -> None:
        targetdir = tempfile.mkdtemp(dir=self.root)
        dist_info_rel = os.path.join("demo-1.0.0.dist-info", "METADATA")
        pkg_mod_rel = os.path.join("demo", "__init__.py")
        bin_rel_in_target = os.path.join("bin", "democli")
        bin_rel_in_record = os.path.join(os.pardir, os.pardir, "bin", "democli")
        missing_rel = os.path.join("demo", "missing.py")

        for rel in (dist_info_rel, pkg_mod_rel, bin_rel_in_target):
            full = os.path.join(targetdir, rel)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w") as f:
                f.write("x\n")

        dist = self._make_dist([dist_info_rel, pkg_mod_rel, bin_rel_in_record, missing_rel])
        with mock.patch("rez.pip.print_warning") as mock_warn:
            mapping = _get_distribution_files_mapping(dist, targetdir)

        self.assertEqual(mapping[dist_info_rel], os.path.join("python", dist_info_rel))
        self.assertEqual(mapping[pkg_mod_rel], os.path.join("python", pkg_mod_rel))
        self.assertEqual(mapping[bin_rel_in_target], bin_rel_in_target)
        self.assertNotIn(missing_rel, mapping)
        mock_warn.assert_called_once()

    def test_mapping_unknown_pardir_raises_ioerror(self) -> None:
        targetdir = tempfile.mkdtemp(dir=self.root)
        unknown_rel = os.path.join(os.pardir, "weird", "file.txt")
        dist = self._make_dist([unknown_rel])

        with mock.patch("rez.pip.print_error") as mock_err:
            with self.assertRaises(IOError) as ctx:
                _get_distribution_files_mapping(dist, targetdir)

        # src/rez/pip.py:549 hardcodes 89 instead of errno.EDESTADDRREQ
        # (which is 39 on macOS and 10039 on Windows).
        self.assertEqual(ctx.exception.errno, 89)
        mock_err.assert_called_once()


class TestPipInstallPackage(TestBase, TempdirMixin):
    """Tests for pip_install_package."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        TempdirMixin.setUpClass()

    @classmethod
    def tearDownClass(cls) -> None:
        TempdirMixin.tearDownClass()
        super().tearDownClass()

    def _populate_target(self, targetdir: str, include_files: bool = True) -> None:
        dist_info = os.path.join(targetdir, "my_pkg-1.2.3.dist-info")
        os.makedirs(dist_info, exist_ok=True)

        metadata = (
            "Metadata-Version: 2.1\n"
            "Name: my-pkg\n"
            "Version: 1.2.3\n"
            "Summary: Sample pip package\n"
            "Home-page: https://example.com/home\n"
            "Download-URL: https://example.com/dl\n"
            "Author: Jane Doe\n"
            "Author-email: jane@example.com\n"
        )
        with open(os.path.join(dist_info, "METADATA"), "w") as f:
            f.write(metadata)

        with open(os.path.join(dist_info, "WHEEL"), "w") as f:
            f.write("Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n")

        if include_files:
            pkg_dir = os.path.join(targetdir, "my_pkg")
            os.makedirs(pkg_dir, exist_ok=True)
            with open(os.path.join(pkg_dir, "__init__.py"), "w") as f:
                f.write("__version__ = '1.2.3'\n")

            bin_dir = os.path.join(targetdir, "bin")
            os.makedirs(bin_dir, exist_ok=True)
            cli_path = os.path.join(bin_dir, "mycli")
            with open(cli_path, "w") as f:
                f.write("#!/usr/bin/env python\n")
            os.chmod(cli_path, stat.S_IRWXU)

            record_lines = [
                "my_pkg/__init__.py,,",
                "my_pkg-1.2.3.dist-info/METADATA,,",
                "my_pkg-1.2.3.dist-info/WHEEL,,",
                "../../bin/mycli,,",
            ]
        else:
            record_lines = [
                "my_pkg/nonexistent.py,,",
            ]

        with open(os.path.join(dist_info, "RECORD"), "w") as f:
            f.write("\n".join(record_lines) + "\n")

    def test_install_package_full_flow_and_skip_on_reinstall(self) -> None:
        repo_dir = tempfile.mkdtemp(dir=self.root)
        target1 = tempfile.mkdtemp(dir=self.root)
        target2 = tempfile.mkdtemp(dir=self.root)
        self._populate_target(target1, include_files=True)
        self._populate_target(target2, include_files=True)

        fake_reqs = {
            "requires": ["python-3.11+"],
            "variant_requires": ["platform-linux"],
            "metadata": {"is_pure_python": True},
        }

        with mock.patch("rez.pip.find_pip", return_value=(sys.executable, None)), \
                mock.patch("rez.pip.mkdtemp", side_effect=[target1, target2]), \
                mock.patch("rez.pip._cmd") as mock_cmd, \
                mock.patch("rez.pip.get_rez_requirements", return_value=fake_reqs):
            installed, skipped = pip_install_package(
                "my-pkg",
                mode=InstallMode.no_deps,
                prefix=repo_dir,
            )

            self.assertEqual(len(installed), 1)
            self.assertEqual(skipped, [])
            cmd_args = mock_cmd.call_args.kwargs["command"]
            self.assertIn("--use-pep517", cmd_args)
            self.assertIn(f"--target={target1}", cmd_args)
            self.assertIn("--no-deps", cmd_args)
            self.assertFalse(os.path.exists(target1))

            pkg = installed[0].parent
            self.assertEqual(pkg.name, "my_pkg")
            self.assertEqual(str(pkg.version), "1.2.3")
            self.assertEqual(pkg.description, "Sample pip package")
            self.assertEqual(pkg.tools, ["mycli"])
            self.assertTrue(pkg.hashed_variants)
            self.assertEqual(pkg.pip_name, "my-pkg (1.2.3)")
            self.assertTrue(pkg.from_pip)
            self.assertTrue(pkg.is_pure_python)
            self.assertEqual(pkg.authors, ["Jane Doe jane@example.com"])
            self.assertEqual(
                pkg.help,
                [
                    ["Home Page", "https://example.com/home"],
                    ["Source Code", "https://example.com/dl"],
                ],
            )
            installed_cli = os.path.join(installed[0].root, "bin", "mycli")
            self.assertTrue(_is_exe(installed_cli))

            # Second install into same repo skips existing variant
            installed2, skipped2 = pip_install_package(
                "my-pkg",
                mode=InstallMode.min_deps,
                prefix=repo_dir,
            )
            cmd_args2 = mock_cmd.call_args.kwargs["command"]
            self.assertNotIn("--no-deps", cmd_args2)
            self.assertEqual(installed2, [])
            self.assertEqual(len(skipped2), 1)

    def test_install_package_with_context_debug_and_extra_args(self) -> None:
        release_dir = tempfile.mkdtemp(dir=self.root)
        targetdir = tempfile.mkdtemp(dir=self.root)
        self._populate_target(targetdir, include_files=False)

        self.update_settings({
            "release_packages_path": release_dir,
            "debug_package_release": True,
        })

        ctx = mock.MagicMock()
        ctx.get_resolved_package.return_value = SimpleNamespace(version=Version("3.11.5"))

        with mock.patch("rez.pip.find_pip", return_value=("/ctx/python", ctx)), \
                mock.patch("rez.pip.mkdtemp", return_value=targetdir), \
                mock.patch("rez.pip._cmd") as mock_cmd, \
                mock.patch("rez.pip.DistributionPath") as mock_dist_path, \
                mock.patch("rez.pip._verbose", False), \
                mock.patch("rez.pip.print_warning") as mock_warn:
            real_dp = DistributionPath([targetdir])
            mock_dist_path.return_value = real_dp

            installed, skipped = pip_install_package(
                "my-pkg",
                mode=InstallMode.no_deps,
                release=True,
                extra_args=["--no-use-pep517", "--target=/custom", "--no-deps"],
            )

        ctx.print_info.assert_called_once()
        cmd_args = mock_cmd.call_args.kwargs["command"]
        self.assertNotIn("--use-pep517", cmd_args)
        self.assertEqual(cmd_args.count("--no-deps"), 1)
        self.assertEqual(
            [arg for arg in cmd_args if arg.startswith("--target=")],
            ["--target=/custom"],
        )
        self.assertEqual(len(installed), 1)
        self.assertEqual(skipped, [])
        self.assertTrue(
            any("No source files exist" in str(c) for c in mock_warn.call_args_list)
        )

    def test_install_package_no_distributions_warns(self) -> None:
        repo_dir = tempfile.mkdtemp(dir=self.root)
        targetdir = tempfile.mkdtemp(dir=self.root)

        with mock.patch("rez.pip.find_pip", return_value=(sys.executable, None)), \
                mock.patch("rez.pip.mkdtemp", return_value=targetdir), \
                mock.patch("rez.pip._cmd"), \
                mock.patch("rez.pip.print_warning") as mock_warn:
            installed, skipped = pip_install_package("empty-pkg", prefix=repo_dir)

        self.assertEqual(installed, [])
        self.assertEqual(skipped, [])
        mock_warn.assert_called_once_with("NO packages were installed.")

    def test_install_package_minimal_metadata_and_verbose_empty_warning(self) -> None:
        repo_dir = tempfile.mkdtemp(dir=self.root)
        targetdir = tempfile.mkdtemp(dir=self.root)
        dist_info = os.path.join(targetdir, "min_pkg-0.1.0.dist-info")
        os.makedirs(dist_info, exist_ok=True)

        with open(os.path.join(dist_info, "METADATA"), "w") as f:
            f.write("Metadata-Version: 2.1\nName: min-pkg\nVersion: 0.1.0\nAuthor: Solo\n")
        with open(os.path.join(dist_info, "WHEEL"), "w") as f:
            f.write("Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n")
        with open(os.path.join(dist_info, "RECORD"), "w") as f:
            f.write("min_pkg/missing.py,,\n")

        with mock.patch("rez.pip.find_pip", return_value=(sys.executable, None)), \
                mock.patch("rez.pip.mkdtemp", return_value=targetdir), \
                mock.patch("rez.pip._cmd"), \
                mock.patch("rez.pip._verbose", True), \
                mock.patch("rez.pip.print_warning") as mock_warn:
            installed, skipped = pip_install_package("min-pkg", prefix=repo_dir)

        self.assertEqual(len(installed), 1)
        self.assertEqual(skipped, [])
        pkg = installed[0].parent
        self.assertEqual(pkg.authors, ["Solo"])
        self.assertEqual(pkg.description, "UNKNOWN")
        self.assertIsNone(pkg.help)
        self.assertFalse(
            any("--verbose" in str(c) for c in mock_warn.call_args_list)
        )
