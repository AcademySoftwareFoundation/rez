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
    def test_get_bind_modules(self):
        """Test get_bind_modules returns the expected modules"""
        self.assertEqual(
            sorted(package_bind.get_bind_modules().keys()),
            [
                "PyQt",
                "PySide",
                "arch",
                "cmake",
                "gcc",
                "hello_world",
                "os",
                "pip",
                "platform",
                "python",
                "rez",
                "rezgui",
                "setuptools",
                "sip",
            ]
        )

    def test_os_module_override(self):
        """Test that bind_module_path can override built-in bind modules"""
        self.update_settings({
            "bind_module_path": [self.data_path("bind")]
        })

        os_module_path = os.path.join(self.data_path("bind"), "os.py")
        os_bind_module = package_bind.find_bind_module("os")
        self.assertEqual(os_bind_module, os_module_path)


if __name__ == '__main__':
    unittest.main()
