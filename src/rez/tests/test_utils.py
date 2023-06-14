# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
test 'utils' modules
"""
import os

from rez.config import config
from rez.tests.util import TestBase, platform_dependent
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

    @classmethod
    def setUpClass(cls):
        TestBase.setUpClass()
        # for convenience while developing
        if not config.debug("none"):
            config.override("debug_none", True)

    @platform_dependent(["windows"])
    def test_convert_unix(self):
        """Test the path conversion to unix style."""
        test_path = r'C:\foo\bar\spam'
        converted_path = cygpath.convert(test_path)
        expected_path = '/c/foo/bar/spam'

        self.assertEqual(converted_path, expected_path)

    @platform_dependent(["windows"])
    def test_convert_unix_override_path_sep(self):
        """Test the path conversion to unix style overriding env path sep."""
        test_path = r'${SOMEPATH}:C:\foo/bar/spam'
        separators = {'SOMEPATH': ';'}
        converted_path = cygpath.convert(test_path, env_var_seps=separators)
        expected_path = '${SOMEPATH};/c/foo/bar/spam'

        self.assertEqual(converted_path, expected_path)

    @platform_dependent(["windows"])
    def test_convert_mixed(self):
        """Test the path conversion to mixed style."""
        test_path = r'C:\foo\bar\spam'
        converted_path = cygpath.convert(test_path, mode='mixed')
        expected_path = 'C:/foo/bar/spam'

        self.assertEqual(converted_path, expected_path)

    @platform_dependent(["windows"])
    def test_convert_mixed_override_path_sep(self):
        """Test the path conversion to mixed style overriding env path sep."""
        test_path = r'${SOMEPATH}:C:/foo\bar/spam'
        separators = {'SOMEPATH': ';'}
        converted_path = cygpath.convert(
            test_path, mode='mixed', env_var_seps=separators
        )
        expected_path = '${SOMEPATH};C:/foo/bar/spam'

        self.assertEqual(converted_path, expected_path)


class TestToCygdrive(TestBase):
    """Test cygpath.to_cygdrive() function."""

    # Test valid paths with NT drive letters
    @platform_dependent(["windows"])
    def test_valid_paths(self):
        self.assertEqual(cygpath.to_cygdrive("C:\\"), "/c/")
        self.assertEqual(cygpath.to_cygdrive("D:\\folder"), "/d/")
        self.assertEqual(cygpath.to_cygdrive("E:\\file.txt"), "/e/")
        self.assertEqual(cygpath.to_cygdrive("F:\\dir1\\dir2\\dir3"), "/f/")
        self.assertEqual(cygpath.to_cygdrive("G:\\dir1\\dir2\\file.txt"), "/g/")

    # Test paths with mixed slashes
    @platform_dependent(["windows"])
    def test_forward_slashes(self):
        self.assertEqual(cygpath.to_cygdrive(r"C:\/folder"), "/c/")
        self.assertEqual(cygpath.to_cygdrive(r"D:/dir1\dir2"), "/d/")
        self.assertEqual(cygpath.to_cygdrive(r"E:\/file.txt"), "/e/")
        self.assertEqual(cygpath.to_cygdrive(r"F:/dir1\/dir2\dir3"), "/f/")
        self.assertEqual(cygpath.to_cygdrive(r"G:/dir1/dir2\file.txt"), "/g/")

    # Test invalid paths
    @platform_dependent(["windows"])
    def test_invalid_paths(self):
        self.assertEqual(cygpath.to_cygdrive("\\folder"), "")
        self.assertEqual(cygpath.to_cygdrive("1:\\folder"), "")
        self.assertEqual(cygpath.to_cygdrive("AB:\\folder"), "")
        self.assertEqual(cygpath.to_cygdrive(r":\folder"), "")
        self.assertEqual(cygpath.to_cygdrive(r":\file.txt"), "")
        self.assertEqual(cygpath.to_cygdrive(r":\dir1\dir2\dir3"), "")
        self.assertEqual(cygpath.to_cygdrive(r":\dir1\dir2\file.txt"), "")

    # Test unsupported cases
    @platform_dependent(["windows"])
    def test_unsupported_cases(self):
        self.assertEqual(cygpath.to_cygdrive("\\\\server\\share\\folder"), "")
        self.assertEqual(cygpath.to_cygdrive(".\\folder"), "")

    # Test edge cases
    @platform_dependent(["windows"])
    def test_edge_cases(self):
        self.assertEqual(cygpath.to_cygdrive(""), "")
        self.assertEqual(cygpath.to_cygdrive("C:"), "/c/")
        self.assertEqual(cygpath.to_cygdrive("C:\\"), "/c/")
        self.assertEqual(cygpath.to_cygdrive("C:/"), "/c/")
        self.assertEqual(cygpath.to_cygdrive("D:\\folder with space"), "/d/")
        # Unsupported and reserved characters
        self.assertEqual(cygpath.to_cygdrive("E:\\folder!@#$%^&*()_+-={}[]|;:,.<>?"), "/e/")
        self.assertEqual(cygpath.to_cygdrive("F:\\folder_日本語"), "/f/")
        self.assertEqual(cygpath.to_cygdrive("\\\\?\\C:\\folder\\file.txt"), "/c/")
