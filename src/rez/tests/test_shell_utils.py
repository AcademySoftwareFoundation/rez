# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project

"""Tests for shell utils."""

from rez.tests.util import TestBase
from rezplugins.shell._utils.windows import convert_path


class ShellUtils(TestBase):
    """Test shell util functions."""

    def test_path_conversion_windows(self):
        """Test the path conversion to windows style."""
        test_path = r'C:\foo/bar/spam'
        converted_path = convert_path(test_path, 'windows')
        expected_path = r'C:\foo\bar\spam'

        self.assertEqual(converted_path, expected_path)

    def test_path_conversion_unix(self):
        """Test the path conversion to unix style."""
        test_path = r'C:\foo\bar\spam'
        converted_path = convert_path(test_path, 'unix')
        expected_path = r'/c/foo/bar/spam'

        self.assertEqual(converted_path, expected_path)

    def test_path_conversion_mixed(self):
        """Test the path conversion to mixed style."""
        test_path = r'C:\foo\bar\spam'
        converted_path = convert_path(test_path, 'unix')
        expected_path = r'/c/foo/bar/spam'

        self.assertEqual(converted_path, expected_path)

    def test_path_conversion_unix_forced_fwdslash(self):
        """Test the path conversion to unix style."""
        test_path = r'C:\foo\bar\spam'
        converted_path = convert_path(test_path, 'unix', force_fwdslash=True)
        expected_path = r'/c/foo/bar/spam'

        self.assertEqual(converted_path, expected_path)

    def test_path_conversion_mixed_forced_fwdslash(self):
        """Test the path conversion to mixed style."""
        test_path = r'C:\foo\bar\spam'
        converted_path = convert_path(test_path, 'mixed', force_fwdslash=True)
        expected_path = r'C:/foo/bar/spam'

        self.assertEqual(converted_path, expected_path)
