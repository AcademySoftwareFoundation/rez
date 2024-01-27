# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
test package_bind module
"""
import os
import unittest
from rez import package_bind
from rez.tests.util import TestBase


class TestPackageBind(TestBase):
    def test_os_module_override(self):
        """Test that bind_module_path can override built-in bind modules"""
        self.update_settings(dict(
            bind_module_path=[self.data_path("bind")]
        ))

        os_module_path = os.path.join(self.data_path("bind"), "os.py")
        os_bind_module = package_bind.find_bind_module("os")
        self.assertEqual(os_bind_module, os_module_path)


if __name__ == '__main__':
    unittest.main()
