from rez.tests.util import TestBase
from rez.utils.platform_ import Platform, platform_
from rez.utils import filesystem
import os


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
            self.skipTest('os.path.realpath() treats ntpath as relpath, and prepends os.getcwd')
        platform = self.CaseInsensitivePlatform()
        path = filesystem.canonical_path('C:\\dir\\File.txt', platform)
        expects = 'c:\\dir\\file.txt'.replace('\\', os.sep)
        self.assertEqual(path, expects)

    def test_unix_case_sensistive_platform(self):
        if platform_.name == 'windows':
            self.skipTest('os.path.realpath() treats unixpath as relpath, and prepends C:\\')
        platform = self.CaseSensitivePlatform()
        path = filesystem.canonical_path('/var/tmp/File.txt', platform)
        expects = '/var/tmp/File.txt'.replace('\\', os.sep)
        self.assertEqual(path, expects)

    def test_unix_case_insensistive_platform(self):
        if platform_.name == 'windows':
            self.skipTest('os.path.realpath() treats unixpath as relpath, and prepends C:\\')
        platform = self.CaseInsensitivePlatform()
        path = filesystem.canonical_path('/var/tmp/File.txt', platform)
        expects = '/var/tmp/file.txt'.replace('\\', os.sep)
        self.assertEqual(path, expects)
