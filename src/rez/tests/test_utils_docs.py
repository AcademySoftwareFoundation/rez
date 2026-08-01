# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project

"""Unit tests for :mod:`rez.utils.docs`."""

import unittest

from rez.tests.test_rezconfig import _new_settings_without_versionadded
from rez.utils.docs import parse_documented_settings


class TestUtilsDocs(unittest.TestCase):
    def test_collects_top_level_documented_settings(self) -> None:
        source = """\
# __DOC_START__
first = 1
if True:
    nested = 2
annotated: int = 3
# __DOC_END__
outside = 4
"""
        self.assertEqual(
            {
                setting.name: setting.lineno
                for setting in parse_documented_settings(source)
            },
            {"first": 2, "annotated": 5},
        )

    def test_requires_documentation_sentinels(self) -> None:
        with self.assertRaisesRegex(ValueError, "sentinels were not found"):
            parse_documented_settings("setting = 1\n")

    def test_compares_setting_names(self) -> None:
        baseline = """\
# __DOC_START__
existing = 1
# __DOC_END__
"""
        current = """\
# __DOC_START__
existing = 2
# Documentation for the new setting.
#
# .. versionadded:: 3.3.0
added = 1
# __DOC_END__
"""
        self.assertEqual(
            _new_settings_without_versionadded(baseline, current),
            [],
        )

    def test_directive_must_be_in_immediately_preceding_comment_block(self) -> None:
        baseline = """\
# __DOC_START__
existing = 1
# __DOC_END__
"""
        current = """\
# __DOC_START__
existing = 1
# .. versionadded:: 3.3.0

# Documentation without a directive.
missing = 2
# __DOC_END__
"""
        self.assertEqual(
            _new_settings_without_versionadded(baseline, current),
            ["missing"],
        )


if __name__ == "__main__":
    unittest.main()
