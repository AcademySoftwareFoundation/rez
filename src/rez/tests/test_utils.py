# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
test 'utils' modules
"""
import os
import sys

from rez.config import config
from rez.tests.util import TestBase, platform_dependent
from rez.utils import cygpath, filesystem
from rez.utils.platform_ import Platform, platform_

if platform_.name == "windows":
    from rez.utils import uncpath
    uncpath_available = True
else:
    uncpath_available = False

if sys.version_info[:2] >= (3, 3):
    from unittest.mock import patch
    patch_available = True
else:
    patch_available = False


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

    @platform_dependent(["windows"])
    def test_convert_empty_path(self):
        """Test the path conversion on empty paths.
        Path conversion can expect empty paths when normalizing rex paths such as
        variant subpaths.
        """
        converted_path = cygpath.convert('')
        self.assertEqual(converted_path, '')


class TestToPosixPath(TestBase):

    @platform_dependent(["windows"])
    def test_normal_windows_paths(self):
        self.assertEqual(cygpath.to_posix_path(
            "C:\\Users\\John\\Documents"), "/c/Users/John/Documents"
        )
        self.assertEqual(
            cygpath.to_posix_path("D:\\Projects\\Python"), "/d/Projects/Python"
        )

    @platform_dependent(["windows"])
    def test_windows_paths_with_spaces(self):
        self.assertEqual(cygpath.to_posix_path(
            "C:\\Program Files\\Python"), "/c/Program Files/Python"
        )
        self.assertEqual(cygpath.to_posix_path(
            "D:\\My Documents\\Photos"), "/d/My Documents/Photos"
        )

    @platform_dependent(["windows"])
    def test_windows_paths_with_special_characters(self):
        self.assertEqual(cygpath.to_posix_path(
            "C:\\Users\\John\\#Projects"), "/c/Users/John/#Projects"
        )
        self.assertEqual(cygpath.to_posix_path(
            "D:\\Projects\\Python@Home"), "/d/Projects/Python@Home"
        )

    @platform_dependent(["windows"])
    def test_windows_paths_with_mixed_slashes(self):
        self.assertEqual(cygpath.to_posix_path(
            "C:\\Users/John/Documents"), "/c/Users/John/Documents"
        )
        self.assertEqual(
            cygpath.to_posix_path("D:/Projects\\Python"), "/d/Projects/Python"
        )

    @platform_dependent(["windows"])
    def test_windows_paths_with_lowercase_drive_letters(self):
        self.assertEqual(cygpath.to_posix_path(
            "c:\\Users\\John\\Documents"), "/c/Users/John/Documents"
        )
        self.assertEqual(
            cygpath.to_posix_path("d:\\Projects\\Python"), "/d/Projects/Python"
        )

    @platform_dependent(["windows"])
    def test_already_posix_style_paths(self):
        self.assertEqual(cygpath.to_posix_path(
            "/c/Users/John/Documents"),
            "/c/Users/John/Documents"
        )
        self.assertEqual(
            cygpath.to_posix_path("/d/projects/python"),
            "/d/projects/python"
        )
        self.assertEqual(
            cygpath.to_posix_path("/home/john/documents"),
            "/home/john/documents"
        )
        self.assertEqual(
            cygpath.to_posix_path("/mingw64/bin"),
            "/mingw64/bin"
        )
        self.assertEqual(
            cygpath.to_posix_path("/usr/bin"),
            "/usr/bin"
        )

    @platform_dependent(["windows"])
    def test_relative_paths(self):
        self.assertEqual(cygpath.to_posix_path("jane/documents"), "jane/documents")
        self.assertEqual(
            cygpath.to_posix_path("projects/python/file.py"),
            "projects/python/file.py"
        )
        self.assertEqual(
            cygpath.to_posix_path("f2dd99c6c010d9ea710dad6233ebfcdf64ee1355"),
            "f2dd99c6c010d9ea710dad6233ebfcdf64ee1355"
        )
        self.assertEqual(cygpath.to_posix_path("spangle-1.0"), "spangle-1.0")

    @platform_dependent(["windows"])
    def test_windows_unc_paths(self):
        self.assertEqual(cygpath.to_posix_path(
            "//Server/Share/folder"), "//Server/Share/folder"
        )
        self.assertEqual(cygpath.to_posix_path(
            "\\\\Server\\Share\\folder"), "//Server/Share/folder"
        )
        self.assertEqual(cygpath.to_posix_path(
            "\\\\server\\share\\folder\\file.txt"), "//server/share/folder/file.txt"
        )
        self.assertEqual(cygpath.to_posix_path(
            "\\\\server\\share/folder/file.txt"), "//server/share/folder/file.txt"
        )
        self.assertEqual(cygpath.to_posix_path(
            r"\\server\share/folder\//file.txt"), "//server/share/folder/file.txt"
        )

    @platform_dependent(["windows"])
    def test_windows_long_paths(self):
        self.assertEqual(cygpath.to_posix_path(
            "\\\\?\\C:\\Users\\Jane\\Documents"), "/c/Users/Jane/Documents"
        )
        self.assertEqual(cygpath.to_posix_path(
            "\\\\?\\d:\\projects\\python"), "/d/projects/python"
        )

    @platform_dependent(["windows"])
    def test_windows_malformed_paths(self):
        self.assertEqual(cygpath.to_posix_path(
            "C:\\Users/Jane/\\Documents"), "/c/Users/Jane/Documents"
        )
        self.assertEqual(
            cygpath.to_posix_path("D:/Projects\\/Python"), "/d/Projects/Python"
        )
        self.assertEqual(cygpath.to_posix_path(
            "C:/Users\\Jane/Documents"), "/c/Users/Jane/Documents"
        )
        self.assertEqual(
            cygpath.to_posix_path("D:\\projects/python"), "/d/projects/python"
        )
        self.assertRaisesRegex(
            ValueError,
            "Cannot convert path to posix path: '.*' "
            "This is most likely due to a malformed path",
            cygpath.to_posix_path,
            "D:\\..\\Projects"
        )
        self.assertRaisesRegex(
            ValueError,
            "Cannot convert path to posix path: '.*' "
            "This is most likely due to a malformed path",
            cygpath.to_posix_path,
            "/d/..\\projects"
        )

    @platform_dependent(["windows"])
    def test_dotted_paths(self):
        self.assertEqual(cygpath.to_posix_path(
            "C:\\Users\\John\\..\\Projects"), "/c/Users/Projects"
        )
        self.assertEqual(cygpath.to_posix_path(
            "/c/users/./jane"), "/c/users/jane"
        )
        # Dotted relative path
        self.assertEqual(
            cygpath.to_posix_path("./projects/python"),
            "projects/python"
        )
        self.assertEqual(
            cygpath.to_posix_path(".\\projects\\python"),
            "projects/python"
        )


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
        self.assertEqual(
            cygpath.to_cygdrive("E:\\folder!@#$%^&*()_+-={}[]|;:,.<>?"), "/e/"
        )
        self.assertEqual(cygpath.to_cygdrive("F:\\folder_日本語"), "/f/")
        self.assertEqual(cygpath.to_cygdrive("\\\\?\\C:\\folder\\file.txt"), "/c/")


class TestToMixedPath(TestBase):

    @platform_dependent(["windows"])
    def test_normal_windows_paths(self):
        self.assertEqual(cygpath.to_mixed_path('C:\\foo\\bar'), 'C:/foo/bar')
        self.assertEqual(cygpath.to_mixed_path(
            'D:\\my_folder\\my_file.txt'), 'D:/my_folder/my_file.txt')
        self.assertEqual(cygpath.to_mixed_path(
            'E:\\projects\\python\\main.py'), 'E:/projects/python/main.py')

    @platform_dependent(["windows"])
    def test_already_mixed_style_paths(self):
        self.assertEqual(
            cygpath.to_mixed_path('C:/home/john/documents'), 'C:/home/john/documents'
        )
        self.assertEqual(cygpath.to_mixed_path(
            'Z:/projects/python'), 'Z:/projects/python'
        )

    @platform_dependent(["windows"])
    def test_paths_with_escaped_backslashes(self):
        self.assertEqual(cygpath.to_mixed_path('C:\\\\foo\\\\bar'), 'C:/foo/bar')
        self.assertEqual(cygpath.to_mixed_path(
            'D:\\my_folder\\\\my_file.txt'), 'D:/my_folder/my_file.txt'
        )
        self.assertEqual(cygpath.to_mixed_path(
            'E:\\projects\\python\\\\main.py'), 'E:/projects/python/main.py'
        )

    @platform_dependent(["windows"])
    def test_paths_with_mixed_slashes(self):
        self.assertEqual(cygpath.to_mixed_path('C:\\foo/bar'), 'C:/foo/bar')
        self.assertEqual(cygpath.to_mixed_path(
            'D:/my_folder\\my_file.txt'), 'D:/my_folder/my_file.txt'
        )
        self.assertEqual(cygpath.to_mixed_path(
            'E:/projects/python\\main.py'), 'E:/projects/python/main.py'
        )

    @platform_dependent(["windows"])
    def test_paths_with_no_drive_letter(self):
        self.assertRaisesRegex(
            ValueError,
            "Cannot convert path to mixed path: '.*' "
            "Please ensure that the path is not absolute",
            cygpath.to_mixed_path,
            '\\foo\\bar'
        )

        self.assertRaisesRegex(
            ValueError,
            "Cannot convert path to mixed path: '.*' "
            "Please ensure that the path is not absolute",
            cygpath.to_mixed_path,
            '/projects/python/main.py'
        )

    @platform_dependent(["windows"])
    def test_relative_paths(self):
        self.assertEqual(
            cygpath.to_mixed_path("shell\\1.0.0"),
            "shell/1.0.0"
        )
        self.assertEqual(
            cygpath.to_mixed_path("projects/python/main.py"),
            "projects/python/main.py"
        )
        self.assertEqual(
            cygpath.to_mixed_path("f2dd99c6c010d9ea710dad6233ebfcdf64ee1355"),
            "f2dd99c6c010d9ea710dad6233ebfcdf64ee1355"
        )
        self.assertEqual(cygpath.to_mixed_path("spangle-1.0"), "spangle-1.0")

    @platform_dependent(["windows"])
    def test_paths_with_only_a_drive_letter(self):
        self.assertEqual(cygpath.to_mixed_path('C:'), 'C:/')
        self.assertEqual(cygpath.to_mixed_path('D:'), 'D:/')
        self.assertEqual(cygpath.to_mixed_path('E:'), 'E:/')

    @platform_dependent(["windows"])
    def test_dotted_paths(self):
        self.assertEqual(cygpath.to_mixed_path(
            "C:\\Users\\John\\..\\Projects"), "C:/Users/Projects"
        )
        self.assertEqual(cygpath.to_mixed_path(
            "C:/users/./jane"), "C:/users/jane"
        )
        # Dotted relative path
        self.assertEqual(
            cygpath.to_mixed_path("./projects/python"),
            "projects/python"
        )

    @platform_dependent(["windows"])
    def test_windows_unc_paths(self):
        self.assertEqual(
            cygpath.to_mixed_path("\\\\my_folder\\my_file.txt"),
            "//my_folder/my_file.txt"
        )
        self.assertEqual(
            cygpath.to_mixed_path("\\\\Server\\Share\\folder"),
            "//Server/Share/folder"
        )
        self.assertEqual(
            cygpath.to_mixed_path("\\\\server\\share\\folder\\file.txt"),
            "//server/share/folder/file.txt"
        )
        self.assertEqual(
            cygpath.to_mixed_path("\\\\server\\share/folder/file.txt"),
            "//server/share/folder/file.txt"
        )
        self.assertEqual(
            cygpath.to_mixed_path(r"\\server\share/folder\//file.txt"),
            "//server/share/folder/file.txt"
        )

    @platform_dependent(["windows"])
    def test_windows_unc_paths_strict(self):
        self.assertRaisesRegex(
            ValueError,
            "Cannot convert path to mixed path: '.*' "
            "Unmapped UNC paths are not supported",
            cygpath.to_mixed_path,
            '\\\\my_folder\\my_file.txt',
            strict=True,
        )
        self.assertRaisesRegex(
            ValueError,
            "Cannot convert path to mixed path: '.*' "
            "Unmapped UNC paths are not supported",
            cygpath.to_mixed_path,
            "\\\\Server\\Share\\folder",
            strict=True,
        )
        self.assertRaisesRegex(
            ValueError,
            "Cannot convert path to mixed path: '.*' "
            "Unmapped UNC paths are not supported",
            cygpath.to_mixed_path,
            "\\\\server\\share\\folder\\file.txt",
            strict=True,
        )
        self.assertRaisesRegex(
            ValueError,
            "Cannot convert path to mixed path: '.*' "
            "Unmapped UNC paths are not supported",
            cygpath.to_mixed_path,
            "\\\\server\\share/folder/file.txt",
            strict=True,
        )
        self.assertRaisesRegex(
            ValueError,
            "Cannot convert path to mixed path: '.*' "
            "Unmapped UNC paths are not supported",
            cygpath.to_mixed_path,
            r"\\server\share/folder\//file.txt",
            strict=True,
        )

    @platform_dependent(["windows"])
    def test_windows_mapped_unc_paths(self):
        if not patch_available:
            raise self.skipTest("Patching not available")
        with patch.object(cygpath, 'to_mapped_drive', return_value="X:"):
            self.assertEqual(
                cygpath.to_mixed_path('\\\\server\\share\\folder'), 'X:/folder'
            )


class TestToMappedDrive(TestBase):

    @platform_dependent(["windows"])
    def test_already_mapped_drive(self):
        if not uncpath_available:
            raise self.skipTest("UNC path util not available")
        if not patch_available:
            raise self.skipTest("Unittest patch not available")
        with patch.object(uncpath, 'to_drive', return_value="X:"):
            self.assertEqual(cygpath.to_mapped_drive('\\\\server\\share'), 'X:')
