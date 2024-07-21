# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
unit tests for 'rez.utils.elf' module
"""
import platform
import unittest

from rez.tests.util import TestBase, program_dependent
from rez.utils.elf import get_rpaths, patch_rpaths


class TestElfUtils(TestBase):

    def __init__(self, *nargs, **kwargs):
        super().__init__(*nargs, **kwargs)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

    @unittest.skipUnless(platform.system() == "Linux", "Linux only")
    @program_dependent("readelf")
    def test_get_rpaths_raises_runtime_exception(self):
        """Tests that no TypeError from elf functions are raised."""
        with self.assertRaises(RuntimeError) as exc:
            get_rpaths("/path/to/elfpath")
        self.assertIn("'/path/to/elfpath': No such file", str(exc.exception))

        with self.assertRaises(RuntimeError) as exc:
            patch_rpaths("/path/to/elfpath", ["$ORIGIN", "$ORIGINTEST"])
        self.assertIn("'/path/to/elfpath': No such file", str(exc.exception))
