# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
test shell invocation
"""
from __future__ import print_function
import os

from rez.config import config
from rez.shells import create_shell, get_shell_types
from rez.resolved_context import ResolvedContext
from rez.tests.util import TestBase, TempdirMixin, per_available_shell
from rez.utils.filesystem import canonical_path
import unittest
import subprocess


class TestShells(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls):
        TempdirMixin.setUpClass()

        packages_path = cls.data_path("packages")

        cls.settings = dict(
            packages_path=[packages_path],
            package_filter=None,
            implicit_packages=[],
            warn_untimestamped=False,
        )

    @classmethod
    def tearDownClass(cls):
        TempdirMixin.tearDownClass()

    @classmethod
    def _create_context(cls, pkgs):
        return ResolvedContext(pkgs, caching=False)

    @per_available_shell()
    def test_shell_execution(self, shell):
        """Test that a shell can be invoked."""
        sh = create_shell(shell)
        _, _, _, command = sh.startup_capabilities(command=True)
        if command:
            r = self._create_context(["shell"])
            p = r.execute_shell(command="echo asd", stdout=subprocess.PIPE, text=True)
            stdout, _ = p.communicate()

            self.assertEqual(stdout, "asd\n")
            self.assertEqual(p.returncode, 0)

            if p.returncode:
                raise RuntimeError(
                    "The subprocess failed with exitcode %d" % p.returncode
                )

    @per_available_shell()
    def test_shell_root_path_normalization(self, shell):
        """Test {root} path is normalized to a platform native canonical path."""
        pkg = "shell"
        sh = create_shell(shell)
        _, _, stdin, _ = sh.startup_capabilities(command=None, stdin=True)
        if stdin:
            r = self._create_context([pkg])
            p = r.execute_shell(
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                text=True,
            )
            stdout, _ = p.communicate(input="echo $REZ_SHELL_ROOT\n")
            version = str(r.get_key("version")[pkg][-1])
            expected_result = os.path.join(
                self.settings.get("packages_path")[0], pkg, version
            )
            self.assertEqual(stdout.strip(), canonical_path(expected_result))

    def test_shell_pythonpath_normalization(self, shell="gitbash"):
        """Test PYTHONPATHs are being normalized by the shell."""
        if shell not in get_shell_types():
            self.skipTest("shell {!r} not available".format(shell))

        config.override("default_shell", shell)
        config.override("enable_path_normalization", True)

        sh = create_shell(shell)
        r = self._create_context(["shell"])
        p = r.execute_shell(
            command="echo $PYTHONPATH", stdout=subprocess.PIPE, text=True
        )
        stdout, _ = p.communicate()
        env = r.get_environ()
        self.assertEqual(stdout.strip(), sh.as_shell_path(env["PYTHONPATH"]))

    def test_shell_disabled_normalization(self, shell="gitbash"):
        """Test disabled normalization."""
        if shell not in get_shell_types():
            self.skipTest("shell {!r} not available".format(shell))

        config.override("default_shell", shell)
        config.override("enable_path_normalization", False)

        sh = create_shell(shell)
        r = self._create_context(["shell"])
        p = r.execute_shell(
            command="echo $PYTHONPATH", stdout=subprocess.PIPE, text=True
        )
        stdout, _ = p.communicate()
        env = r.get_environ()
        self.assertEqual(stdout.strip(), sh.as_shell_path(env["PYTHONPATH"]))

        p = r.execute_shell(
            command="echo $PATH", stdout=subprocess.PIPE, text=True
        )
        stdout, _ = p.communicate()
        self.assertNotEqual(
            stdout.strip().split(os.pathsep)[0],
            sh.normalize_path(env["PATH"].split(os.pathsep)[0])
        )

    @per_available_shell()
    def test_shell_invoking_script(self, shell):
        """Test script used to invoke the shell."""
        sh = create_shell(shell)

        _, _, stdin, _ = sh.startup_capabilities(command=None, stdin=True)
        if not stdin:
            return

        r = self._create_context(["shell"])
        p = r.execute_shell(
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
        )
        _, stderr = p.communicate()
        self.assertEqual(p.returncode, 0)
        assert stderr is None

        lines = []
        script_arg = next(iter(arg for arg in p.args if "rez-shell" in arg))
        exec_script = next(iter(arg for arg in script_arg.split() if "rez-shell" in arg))
        with open(exec_script, "r") as f:
            lines = f.readlines()

        self.assertNotEqual(lines, [])
        if sh.name() == "gitbash":
            self.assertEqual(
                lines[0].strip(), "#!/usr/bin/env {}".format(sh.executable_name())
            )
            assert any(
                l.strip() == "'{}' {}".format(sh.executable_filepath(), sh.stdin_arg)
                for l in lines
            )


if __name__ == "__main__":
    unittest.main()
