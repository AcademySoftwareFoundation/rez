# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
test running rez bind commandline tool
"""
from rez.tests.util import restore_os_environ, TestBase, TempdirMixin
import os.path
import subprocess
import unittest

from rez.system import system


class TestBindCLI(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls):
        TempdirMixin.setUpClass()

        cls.local_root = os.path.join(cls.root, "local", "packages")
        cls.release_root = os.path.join(cls.root, "release", "packages")

        cls.settings = dict(
            local_packages_path=cls.local_root,
            release_packages_path=cls.release_root
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
        with restore_os_environ():
            # set config settings into env so subprocess sees them
            os.environ.update(self.get_settings_env())
            subprocess.check_output([binfile, "platform"])
        package_exists = os.path.exists(os.path.join(self.local_root, 'platform'))
        self.assertTrue(package_exists)

    def test_release(self):
        """run release bind test"""

        # skip if cli not available
        if not system.rez_bin_path:
            self.skipTest("Not a production install")

        binfile = os.path.join(system.rez_bin_path, 'rez-bind')
        with restore_os_environ():
            # set config settings into env so subprocess sees them
            os.environ.update(self.get_settings_env())
            subprocess.check_output([binfile, "-r", "platform"])
        package_exists = os.path.exists(os.path.join(self.release_root, 'platform'))
        self.assertTrue(package_exists)

    def test_custom_path(self):
        """run custom path bind test"""

        # skip if cli not available
        if not system.rez_bin_path:
            self.skipTest("Not a production install")

        binfile = os.path.join(system.rez_bin_path, 'rez-bind')
        custom_path = os.path.join(self.root, "custom", "packages")
        with restore_os_environ():
            # set config settings into env so subprocess sees them
            os.environ.update(self.get_settings_env())
            subprocess.check_output([binfile, "-i", custom_path, "platform"])
        package_exists = os.path.exists(os.path.join(custom_path, 'platform'))
        self.assertTrue(package_exists)


if __name__ == '__main__':
    unittest.main()
