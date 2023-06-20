# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
test shell invocation
"""
from __future__ import print_function

from rez.config import config
from rez.shells import create_shell
from rez.resolved_context import ResolvedContext
from rez.tests.util import TestBase, TempdirMixin, per_available_shell
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
        config.override("default_shell", shell)
        if shell == "gitbash":
            config.override("enable_path_normalization", True)

        sh = create_shell(shell)
        _, _, _, command = sh.startup_capabilities(command=True)
        if command:
            r = self._create_context(["shell"])
            p = r.execute_shell(command="echo asd", stdout=subprocess.PIPE, text=True)
            _, _ = p.communicate()
            self.assertEqual(p.returncode, 0)

            if p.returncode:
                raise RuntimeError(
                    "The subprocess failed with exitcode %d" % p.returncode
                )


if __name__ == "__main__":
    unittest.main()
