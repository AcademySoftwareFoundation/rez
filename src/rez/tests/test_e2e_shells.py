# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
test shell invocation
"""
from __future__ import print_function
import os

from rez.config import config
from rez.exceptions import PackageFamilyNotFoundError
from rez.shells import create_shell
from rez.resolved_context import ResolvedContext
from rez.tests.util import TestBase, TempdirMixin, per_available_shell
from rez.utils import platform_
from rez.utils.filesystem import canonical_path
import unittest
import subprocess


CI = os.getenv("CI") != ""


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
        # TODO: Remove the check below when this test is fixed. See comments below.
        if CI:
            if platform_.name == "windows" and shell != "cmd":
                return
            elif shell == "pwsh":
                return

        pkg = "shell"
        sh = create_shell(shell)
        _, _, _, command = sh.startup_capabilities(command=True)

        cmds = {
            "bash": "echo $REZ_SHELL_ROOT",
            "cmd": "echo %REZ_SHELL_ROOT%",
            "csh": "echo $REZ_SHELL_ROOT",
            "tcsh": "echo $REZ_SHELL_ROOT",
            "gitbash": "echo $REZ_SHELL_ROOT",
            "powershell": "echo $env:REZ_SHELL_ROOT",
            "pwsh": "echo $env:REZ_SHELL_ROOT",
            "sh": "echo $REZ_SHELL_ROOT",
            "tcsh": "echo $REZ_SHELL_ROOT",
            "zsh": "echo $REZ_SHELL_ROOT",
        }

        if command:
            r = self._create_context([pkg])
            # Running this command on Windows CI outputs $REZ_SHELL_ROOT or
            # $env:REZ_SHELL_ROOT depending on the shell, not the actual path.
            # In pwsh on Linux or Mac CI it outputs :REZ_SHELL_ROOT
            # Switching to stdin also does not help.
            p = r.execute_shell(
                command=cmds[shell], stdout=subprocess.PIPE, text=True
            )
            stdout, _ = p.communicate()
            version = str(r.get_key("version")[pkg][-1])
            expected_result = os.path.join(
                self.settings.get("packages_path")[0], pkg, version
            )
            self.assertEqual(stdout.strip(), canonical_path(expected_result))

    @per_available_shell(include=["gitbash"])
    def test_shell_pythonpath_normalization(self, shell):
        """Test PYTHONPATHs are being normalized by the shell."""
        # TODO: Remove the check below when this test is fixed on CI.
        # See comments below.
        if CI:
            if shell != "cmd":
                return

        sh = create_shell(shell)
        r = self._create_context(["shell"])
        # Running this command on Windows CI sometimes outputs $PYTHONPATH
        # not the actual path. The behavior is inconsistent.
        # Switching to stdin also does not help.
        p = r.execute_shell(
            command="echo $PYTHONPATH", stdout=subprocess.PIPE, text=True
        )
        stdout, _ = p.communicate()
        env = r.get_environ()
        self.assertEqual(stdout.strip(), sh.as_shell_path(env["PYTHONPATH"]))

    @per_available_shell(include=["gitbash"])
    def test_shell_disabled_normalization(self, shell):
        """Test disabled normalization."""
        # TODO: Remove the check below when this test is fixed on CI.
        # See comments below.
        if CI:
            if shell != "cmd":
                return

        sh = create_shell(shell)
        r = self._create_context(["shell"])
        # Running this command on Windows CI sometimes outputs $PYTHONPATH
        # not the actual path. The behavior is inconsistent.
        # Switching to stdin also does not help.
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

        # Skip the following tests on CI, as it is unknown why it fails there.
        # TODO: Remove the check below when this test is fixed. See comments below.
        if CI:
            return

        if sh.name() == "gitbash":
            # First line on CI is `set REZ_ENV_PROMPT=%REZ_ENV_PROMPT%$G`
            self.assertEqual(
                lines[0].strip(), "#!/usr/bin/env {}".format(sh.executable_name())
            )
            assert any(
                l.strip() == "'{}' {}".format(sh.executable_filepath(), sh.stdin_arg)
                for l in lines
            )

    @per_available_shell(include=["gitbash"])
    def test_invalid_packages_path(self, shell):
        """Test invalid packages path errors."""
        old_packages_path = config.packages_path
        config.override("packages_path", ["/foo bar/baz"])

        self.assertRaises(PackageFamilyNotFoundError, self._create_context, ["shell"])

        config.override("packages_path", old_packages_path)


if __name__ == "__main__":
    unittest.main()
