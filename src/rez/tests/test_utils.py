# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
test 'utils' modules
"""
import os
from rez.tests.util import TestBase
from rez.utils import cygpath, filesystem
from rez.utils.platform_ import Platform, platform_


class TestCanonicalPath(TestBase):
    class CaseSensitivePlatform(Platform):
        @property
        def has_case_sensitive_filesystem(self):
            return True

    class CaseInsensitivePlatform(Platform):
        @property
        def has_case_sensitive_filesystem(self):
            return False

    def test_win32_case_insensitive(self):
        if platform_.name != 'windows':
            self.skipTest('on linux/macos, `os.path.realpath()` treats windows '
                          'abspaths as relpaths, and prepends `os.getcwd()`')
        platform = self.CaseInsensitivePlatform()
        path = filesystem.canonical_path('C:\\dir\\File.txt', platform)
        expects = 'c:\\dir\\file.txt'.replace('\\', os.sep)
        self.assertEqual(path, expects)

    def test_unix_case_sensistive_platform(self):
        if platform_.name == 'windows':
            self.skipTest('on windows, `os.path.realpath()` treats unix abspaths '
                          'as relpaths, and prepends `os.getcwd()`')
        platform = self.CaseSensitivePlatform()
        path = filesystem.canonical_path('/a/b/File.txt', platform)
        expects = '/a/b/File.txt'.replace('\\', os.sep)
        self.assertEqual(path, expects)

    def test_unix_case_insensistive_platform(self):
        if platform_.name == 'windows':
            self.skipTest('on windows, `os.path.realpath()` treats unix abspaths '
                          'as relpaths, and prepends `os.getcwd()`')
        platform = self.CaseInsensitivePlatform()
        path = filesystem.canonical_path('/a/b/File.txt', platform)
        expects = '/a/b/file.txt'.replace('\\', os.sep)
        self.assertEqual(path, expects)


class TestPathConversion(TestBase):
    """Test path conversion functions, required for gitbash."""

    def test_convert_windows(self):
        """Test the path conversion to windows style."""
        test_path = r'C:\foo/bar/spam'
        converted_path = cygpath.convert(test_path, mode='windows')
        expected_path = r'C:\foo\bar\spam'

        self.assertEqual(converted_path, expected_path)

    def test_convert_unix(self):
        """Test the path conversion to unix style."""
        test_path = r'C:\foo\bar\spam'
        converted_path = cygpath.convert(test_path)
        expected_path = r'/c/foo/bar/spam'

        self.assertEqual(converted_path, expected_path)

    def test_convert_mixed(self):
        """Test the path conversion to mixed style."""
        test_path = r'C:\foo\bar\spam'
        converted_path = cygpath.convert(test_path)
        expected_path = r'/c/foo/bar/spam'

        self.assertEqual(converted_path, expected_path)

    def test_convert_unix_forced_fwdslash(self):
        """Test the path conversion to unix style."""
        test_path = r'C:\foo\bar\spam'
        converted_path = cygpath.convert(test_path, force_fwdslash=True)
        expected_path = r'/c/foo/bar/spam'

        self.assertEqual(converted_path, expected_path)

    def test_convert_mixed_forced_fwdslash(self):
        """Test the path conversion to mixed style while forcing fwd slashes."""
        test_path = r'C:\foo\bar\spam'
        converted_path = cygpath.convert(test_path, mode='mixed', force_fwdslash=True)
        expected_path = r'C:/foo/bar/spam'

        self.assertEqual(converted_path, expected_path)
