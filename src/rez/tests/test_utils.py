# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
unit tests for 'utils.filesystem' module
"""
import os
import sys
import tempfile
from rez.tests.util import TestBase
from rez.utils import filesystem
from rez.util import load_module_from_file
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

class TestLoadModuleFromFile(TestBase):
    def test_load_module(self):
        """Ensure that the imported module does not show up in sys.modules"""
        # Random chars are used in the module name to ensure that the module name is unique
        # and the test won't fail because some other module with the same name
        # shows up in sys.modules
        module = 'utils_test_7cd3a335'

        filename = '{0}.py'.format(module)
        tmpdir = tempfile.mkdtemp(prefix="rez_selftest_")

        with open(os.path.join(tmpdir, filename), 'w') as fd:
            fd.write('')

        load_module_from_file(module,os.path.join(tmpdir, filename))
        self.assertEqual(sys.modules.get(module), None, msg='Module was found in sys.modules')
