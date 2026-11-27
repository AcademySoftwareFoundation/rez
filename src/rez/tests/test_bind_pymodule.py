# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Unit tests for rez.bind._pymodule.
"""
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from rez.bind import _pymodule
from rez.exceptions import RezBindError
from rez.packages import get_package
from rez.system import system
from rez.tests.util import TempdirMixin, TestBase
from rez.version import Requirement, Version, VersionRange


class TestCommands(TestBase):
    def test_commands_appends_pythonpath(self) -> None:
        mock_env = MagicMock()
        with patch.object(_pymodule, "env", mock_env, create=True):
            _pymodule.commands()

        mock_env.PYTHONPATH.append.assert_called_once_with("{this.root}/python")

    def test_commands_with_bin_appends_pythonpath_and_path(self) -> None:
        mock_env = MagicMock()
        with patch.object(_pymodule, "env", mock_env, create=True):
            _pymodule.commands_with_bin()

        mock_env.PYTHONPATH.append.assert_called_once_with("{this.root}/python")
        mock_env.PATH.append.assert_called_once_with("{this.root}/bin")


class TestCopyModule(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        TempdirMixin.setUpClass()

    @classmethod
    def tearDownClass(cls) -> None:
        TempdirMixin.tearDownClass()
        super().tearDownClass()

    def test_copy_package_directory(self) -> None:
        src_dir = tempfile.mkdtemp(dir=self.root)
        pkg_dir = os.path.join(src_dir, "mypkg")
        os.makedirs(pkg_dir)
        with open(os.path.join(pkg_dir, "__init__.py"), "w") as f:
            f.write("# init\n")
        with open(os.path.join(pkg_dir, "sub.py"), "w") as f:
            f.write("VALUE = 1\n")

        dest_dir = tempfile.mkdtemp(dir=self.root)
        with patch(
            "rez.bind._pymodule.run_python_command",
            return_value=(True, pkg_dir, ""),
        ) as mock_run:
            _pymodule.copy_module("mypkg", dest_dir)

        mock_run.assert_called_once()
        self.assertTrue(os.path.isfile(os.path.join(dest_dir, "mypkg", "__init__.py")))
        self.assertTrue(os.path.isfile(os.path.join(dest_dir, "mypkg", "sub.py")))

    def test_copy_single_py_file(self) -> None:
        src_dir = tempfile.mkdtemp(dir=self.root)
        src_file = os.path.join(src_dir, "mymod.py")
        with open(src_file, "w") as f:
            f.write("X = 42\n")

        dest_dir = tempfile.mkdtemp(dir=self.root)
        with patch(
            "rez.bind._pymodule.run_python_command",
            side_effect=[(True, "", ""), (True, src_file, "")],
        ):
            _pymodule.copy_module("mymod", dest_dir)

        copied = os.path.join(dest_dir, "mymod.py")
        self.assertTrue(os.path.isfile(copied))
        with open(copied) as f:
            self.assertEqual(f.read(), "X = 42\n")

    def test_copy_pyc_prefers_py_when_present(self) -> None:
        src_dir = tempfile.mkdtemp(dir=self.root)
        py_file = os.path.join(src_dir, "mymod.py")
        pyc_file = os.path.join(src_dir, "mymod.pyc")
        with open(py_file, "w") as f:
            f.write("# source\n")
        with open(pyc_file, "wb") as f:
            f.write(b"\x00\x00\x00\x00")

        dest_dir = tempfile.mkdtemp(dir=self.root)
        with patch(
            "rez.bind._pymodule.run_python_command",
            side_effect=[(True, "", ""), (True, pyc_file, "")],
        ):
            _pymodule.copy_module("mymod", dest_dir)

        self.assertTrue(os.path.isfile(os.path.join(dest_dir, "mymod.py")))
        self.assertFalse(os.path.exists(os.path.join(dest_dir, "mymod.pyc")))

    def test_copy_pyc_falls_back_to_pyc_when_py_missing(self) -> None:
        src_dir = tempfile.mkdtemp(dir=self.root)
        pyc_file = os.path.join(src_dir, "mymod.pyc")
        with open(pyc_file, "wb") as f:
            f.write(b"\x00\x00\x00\x00")

        dest_dir = tempfile.mkdtemp(dir=self.root)
        with patch(
            "rez.bind._pymodule.run_python_command",
            side_effect=[(True, "", ""), (True, pyc_file, "")],
        ):
            _pymodule.copy_module("mymod", dest_dir)

        self.assertTrue(os.path.isfile(os.path.join(dest_dir, "mymod.pyc")))

    def test_copy_module_failure_raises_rez_bind_error(self) -> None:
        dest_dir = tempfile.mkdtemp(dir=self.root)
        with patch(
            "rez.bind._pymodule.run_python_command",
            side_effect=[
                (False, "", "No module named 'missing'"),
                (False, "", "No module named 'missing'"),
            ],
        ):
            with self.assertRaises(RezBindError) as ctx:
                _pymodule.copy_module("missing", dest_dir)

        self.assertIn("Couldn't locate module missing", str(ctx.exception))


class TestBind(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        TempdirMixin.setUpClass()

    @classmethod
    def tearDownClass(cls) -> None:
        TempdirMixin.tearDownClass()
        super().tearDownClass()

    def _py_req(self) -> str:
        return "python-%s.%s" % (sys.version_info[0], sys.version_info[1])

    def test_pure_python_none_raises_not_implemented(self) -> None:
        repo_path = tempfile.mkdtemp(dir=self.root)
        with self.assertRaises(NotImplementedError):
            _pymodule.bind("foo", repo_path, version="1.0.0", pure_python=None)

    def test_bind_version_range_mismatch_raises(self) -> None:
        repo_path = tempfile.mkdtemp(dir=self.root)
        with self.assertRaises(RezBindError):
            _pymodule.bind(
                "foo",
                repo_path,
                version=Version("1.0.0"),
                version_range=VersionRange("2+"),
                pure_python=True,
            )

    def test_bind_pure_python_with_explicit_version(self) -> None:
        repo_path = tempfile.mkdtemp(dir=self.root)
        src_dir = tempfile.mkdtemp(dir=self.root)
        src_file = os.path.join(src_dir, "foo.py")
        with open(src_file, "w") as f:
            f.write("__version__ = '1.2.3'\n")

        with patch(
            "rez.bind._pymodule.run_python_command",
            side_effect=[(True, "", ""), (True, src_file, "")],
        ):
            variants = _pymodule.bind(
                "foo",
                repo_path,
                version="1.2.3",
                pure_python=True,
            )

        self.assertEqual(len(variants), 1)
        pkg = get_package("foo", "1.2.3", paths=[repo_path])
        self.assertIsNotNone(pkg)
        self.assertEqual(pkg.variants, [[Requirement(self._py_req())]])
        self.assertIsNone(pkg.tools)
        self.assertIn("PYTHONPATH", pkg.commands.source)
        self.assertNotIn("env.PATH.append", pkg.commands.source)

        variant = pkg.get_variant(0)
        self.assertTrue(os.path.isfile(os.path.join(variant.root, "python", "foo.py")))

    def test_bind_non_pure_python_includes_system_variant(self) -> None:
        repo_path = tempfile.mkdtemp(dir=self.root)
        with patch("rez.bind._pymodule.copy_module"):
            variants = _pymodule.bind(
                "bar",
                repo_path,
                version="2.0.0",
                pure_python=False,
            )

        self.assertEqual(len(variants), 1)
        pkg = get_package("bar", "2.0.0", paths=[repo_path])
        expected_reqs = [Requirement(r) for r in (system.variant + [self._py_req()])]
        self.assertEqual(pkg.variants, [expected_reqs])

    def test_bind_auto_detects_version_and_import_name(self) -> None:
        repo_path = tempfile.mkdtemp(dir=self.root)
        with patch(
            "rez.bind._pymodule.get_version_in_python",
            return_value="3.4.5",
        ) as mock_get_ver, patch("rez.bind._pymodule.copy_module") as mock_copy:
            variants = _pymodule.bind(
                "my_pkg",
                repo_path,
                import_name="real_pkg",
                pure_python=True,
            )

        self.assertEqual(len(variants), 1)
        mock_get_ver.assert_called_once_with(
            "my_pkg",
            ["import real_pkg", "print(real_pkg.__version__)"],
        )
        mock_copy.assert_called_once()
        self.assertEqual(mock_copy.call_args[0][0], "real_pkg")
        pkg = get_package("my_pkg", "3.4.5", paths=[repo_path])
        self.assertIsNotNone(pkg)

    def test_bind_with_tools_requires_extra_modules_and_attrs(self) -> None:
        repo_path = tempfile.mkdtemp(dir=self.root)
        bin_src = tempfile.mkdtemp(dir=self.root)
        tool_a = os.path.join(bin_src, "tool_a")
        tool_b = os.path.join(bin_src, "tool_b")
        for tool_path in (tool_a, tool_b):
            with open(tool_path, "w") as f:
                f.write("#!/bin/sh\necho ok\n")

        def fake_find_exe(name: str) -> str:
            if name == "tool_a":
                return tool_a
            if name == "tool_b":
                return tool_b
            raise RezBindError("could not find executable: %s" % name)

        with patch("rez.bind._pymodule.find_exe", side_effect=fake_find_exe), \
                patch("rez.bind._pymodule.print_warning") as mock_warn, \
                patch("rez.bind._pymodule.copy_module") as mock_copy:
            variants = _pymodule.bind(
                "mytoolpkg",
                repo_path,
                version="1.0.0",
                requires=["dep-1"],
                pure_python=True,
                tools=["tool_b", "missing_tool", "tool_a"],
                extra_module_names=["extra1", "extra2"],
                extra_attrs={"description": "Custom description"},
            )

        self.assertEqual(len(variants), 1)
        mock_warn.assert_called_once_with("could not find executable: missing_tool")
        self.assertEqual(
            [c[0][0] for c in mock_copy.call_args_list],
            ["mytoolpkg", "extra1", "extra2"],
        )

        pkg = get_package("mytoolpkg", "1.0.0", paths=[repo_path])
        self.assertEqual(pkg.requires, [Requirement("dep-1")])
        self.assertEqual(sorted(pkg.tools), ["tool_a", "tool_b"])
        self.assertEqual(pkg.description, "Custom description")
        self.assertIn("{this.root}/bin", pkg.commands.source)

        variant = pkg.get_variant(0)
        self.assertTrue(os.path.isfile(os.path.join(variant.root, "bin", "tool_a")))
        self.assertTrue(os.path.isfile(os.path.join(variant.root, "bin", "tool_b")))


if __name__ == "__main__":
    unittest.main()
