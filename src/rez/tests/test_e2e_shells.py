# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
test shell invocation
"""
from __future__ import print_function
import json
import os
import sys
from fnmatch import fnmatch
from textwrap import dedent

from rez.config import config
from rez.exceptions import PackageFamilyNotFoundError
from rez.shells import create_shell
from rez.resolved_context import ResolvedContext
from rez.tests.util import TestBase, TempdirMixin, per_available_shell
from rez.utils import platform_
from rez.utils.filesystem import canonical_path
import unittest
import subprocess


CI = "_IMAGE_NAME" in os.environ


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

        cls.env_cmd_txt = dedent(
            """
            {{
                "bash": "echo ${var}",
                "cmd": "echo %{var}%",
                "csh": "echo ${var}",
                "tcsh": "echo ${var}",
                "gitbash": "echo ${var}",
                "powershell": "echo $env:{var}",
                "pwsh": "echo $env:{var}",
                "sh": "echo ${var}",
                "tcsh": "echo ${var}",
                "zsh": "echo ${var}"
            }}
            """
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
    def test_shell_disabled_normalization(self, shell):
        """Test {root} path is normalized to a platform native canonical path."""
        # TODO: Remove the check below when this test is fixed. See comments below.
        if CI:
            if shell != "cmd":
                return
        elif platform_.name in ["linux", "darwin"] and shell == "pwsh":
            return

        config.override("enable_path_normalization", False)

        pkg = "shell"
        sh = create_shell(shell)
        _, _, _, command = sh.startup_capabilities(command=True)

        if command:
            cmd = json.loads(self.env_cmd_txt.format(var="REZ_SHELL_ROOT")).get(shell)
            r = self._create_context([pkg])
            # Running this command on Windows CI outputs $REZ_SHELL_ROOT or
            # $env:REZ_SHELL_ROOT depending on the shell, not the actual path.
            # In pwsh on Linux or Mac CI it outputs :REZ_SHELL_ROOT
            # Switching to stdin also does not help.
            p = r.execute_shell(
                command=cmd, stdout=subprocess.PIPE, text=True
            )
            stdout, _ = p.communicate()
            version = str(r.get_key("version")[pkg][-1])
            expected_result = os.path.join(
                self.settings.get("packages_path")[0], pkg, version
            )
            self.assertEqual(stdout.strip(), canonical_path(expected_result))

    @per_available_shell(include=["gitbash"])
    def test_shell_pathed_env_vars(self, shell):
        """Test shell pathed env variable normalization"""
        # TODO: Remove the check below when this test is fixed on CI.
        # See comments below.
        if CI:
            return

        sh = create_shell(shell)
        r = self._create_context(["shell"])
        env = r.get_environ()

        # Keep in mind support for wildcards
        env_vars = []
        for ptrn in config.shell_pathed_env_vars.get(shell, []):
            env_vars.extend([key for key in env if fnmatch(key, ptrn)])

        for key in env_vars:
            cmd = json.loads(self.env_cmd_txt.format(var=key)).get(shell)
            # Running this command on Windows CI sometimes outputs $THE_VARIABLE
            # not the expanded value e.g. /a/b/c. The behavior is inconsistent.
            # Switching to stdin also does not help and the point is to execute
            # in a subshell, IOW without using `execute_command`.
            p = r.execute_shell(
                command=cmd, stdout=subprocess.PIPE, text=True
            )
            stdout, _ = p.communicate()
            self.assertEqual(stdout.strip(), sh.as_shell_path(env[key]))

    @per_available_shell(include=["gitbash"])
    def test_shell_pathed_env_var_seps(self, shell):
        """Test shell path env variable separators"""
        # TODO: Remove the check below when this test is fixed on CI.
        # See comments below.
        if CI:
            return

        sh = create_shell(shell)
        r = self._create_context(["shell"])
        env = r.get_environ()

        # The separator can be set in platform separators or shell separators
        env_var_seps = config.get("env_var_separators")
        env_var_seps.update(config.shell_env_var_separators.get(shell, {}))

        # Only testing shell normalized paths
        shell_env_var_seps = dict(
            (k, v)
            for k, v in env_var_seps.items()
            if k in config.shell_pathed_env_vars.get(shell, [])
        )

        # Keep in mind support for wildcards
        env_var_seps = {}
        for ptrn, sep in shell_env_var_seps.items():
            env_var_seps.update(dict((key, sep) for key in env if fnmatch(key, ptrn)))

        for key, sep in env_var_seps.items():
            cmd = json.loads(self.env_cmd_txt.format(var=key)).get(shell)
            # Running this command on Windows CI sometimes outputs $THE_VARIABLE
            # not the expanded value e.g. /a/b/c. The behavior is inconsistent.
            # Switching to stdin also does not help and the point is to execute
            # in a subshell, IOW without using `execute_command`.
            p = r.execute_shell(
                command=cmd, stdout=subprocess.PIPE, text=True
            )
            stdout, _ = p.communicate()
            self.assertEqual(stdout.strip(), sh.as_shell_path(env[key]))
            self.assertIn(sep, stdout.strip())

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

        # Popen args added in v3.3
        if sys.version_info < (3, 3):
            return

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
