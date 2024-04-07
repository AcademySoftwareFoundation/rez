# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
test running rez bind commandline tool
"""
from rez.tests.util import TestBase, TempdirMixin
import os.path
import subprocess
import unittest

from rez.system import system


class TestBindCLI(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls):
        TempdirMixin.setUpClass()

        cls.install_root = os.path.join(cls.root, "packages")

        cls.settings = dict(
            local_packages_path=[cls.install_root]
        )

    @classmethod
    def tearDownClass(cls):
        TempdirMixin.tearDownClass()

    def test_basic(self):
        """run basic bind test"""

        # skip if cli not available
        if not system.rez_bin_path:
            self.skipTest("Not a production install")

        binfile = os.path.join(system.rez_bin_path, 'rez-bind')
        subprocess.check_output([binfile, "platform"])
        package_exists = os.path.exists(os.path.join(self.install_root, 'platform'))
        self.assertTrue(package_exists)


if __name__ == '__main__':
    unittest.main()
