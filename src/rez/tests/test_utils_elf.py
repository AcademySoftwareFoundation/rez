# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
unit tests for 'rez.utils.elf' module
"""
from rez.tests.util import TestBase
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

    def test_get_rpaths_raises_runtime_exception(self):
        """Tests that no TypeError from elf functions are raised."""
        self.assertRaises(
            RuntimeError,
            get_rpaths("/path/to/elfpath")
        )

        self.assertRaises(
            RuntimeError,
            patch_rpaths("/path/to/elfpath", ["$ORIGIN", "$ORIGINTEST"])
        )