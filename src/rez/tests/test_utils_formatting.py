# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
unit tests for 'utils.formatting' module
"""
from rez.tests.util import TestBase
from rez.utils import formatting


class TestFormatting(TestBase):
    def test_readable_units(self):
        readable_units = formatting._readable_units(
            0,
            formatting.memory_divs
        )
        self.assertEqual(readable_units, "0 bytes")

        readable_units = formatting._readable_units(
            1024,
            formatting.memory_divs
        )
        self.assertEqual(readable_units, "1 Kb")

        readable_units = formatting._readable_units(
            1200,
            formatting.memory_divs
        )
        self.assertEqual(readable_units, "1.2 Kb")

        readable_units = formatting._readable_units(
            -30000,
            formatting.memory_divs
        )
        self.assertEqual(readable_units, "-29 Kb")

        readable_units = formatting._readable_units(
            1024,
            formatting.memory_divs,
            plural_aware=True
        )
        self.assertEqual(readable_units, "1 K")
