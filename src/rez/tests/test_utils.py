# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
unit tests for 'utils.filesystem' module
"""
import os
import unittest
import unittest.mock
from rez.tests.util import TestBase
from rez.utils import filesystem
from rez.utils.platform_ import Platform, platform_


class TestCanonicalPath(TestBase):
    class CaseSensitivePlatform(Platform):
        @property
        def has_case_sensitive_filesystem(self) -> bool:
            return True

    class CaseInsensitivePlatform(Platform):
        @property
        def has_case_sensitive_filesystem(self) -> bool:
            return False

    def test_win32_case_insensitive(self) -> None:
        if platform_.name != 'windows':
            self.skipTest('on linux/macos, `os.path.realpath()` treats windows '
                          'abspaths as relpaths, and prepends `os.getcwd()`')
        platform = self.CaseInsensitivePlatform()
        path = filesystem.canonical_path('C:\\dir\\File.txt', platform)
        expects = 'c:\\dir\\file.txt'.replace('\\', os.sep)
        self.assertEqual(path, expects)

    def test_unix_case_sensistive_platform(self) -> None:
        if platform_.name == 'windows':
            self.skipTest('on windows, `os.path.realpath()` treats unix abspaths '
                          'as relpaths, and prepends `os.getcwd()`')
        platform = self.CaseSensitivePlatform()
        path = filesystem.canonical_path('/a/b/File.txt', platform)
        expects = '/a/b/File.txt'.replace('\\', os.sep)
        self.assertEqual(path, expects)

    def test_unix_case_insensistive_platform(self) -> None:
        if platform_.name == 'windows':
            self.skipTest('on windows, `os.path.realpath()` treats unix abspaths '
                          'as relpaths, and prepends `os.getcwd()`')
        platform = self.CaseInsensitivePlatform()
        path = filesystem.canonical_path('/a/b/File.txt', platform)
        expects = '/a/b/file.txt'.replace('\\', os.sep)
        self.assertEqual(path, expects)


@unittest.skipIf(
    platform_.name != "windows",
    "Windows-only: physical core count helpers only exist on WindowsPlatform.",
)
class TestWindowsPlatformCoreCounting(TestBase):
    """Unit tests for WindowsPlatform._physical_cores_from_powershell and
    _physical_cores_from_wmic, plus integration smoke-tests for the public
    logical_cores / physical_cores properties."""

    def _make_proc(self, stdout, returncode=0):
        proc = unittest.mock.Mock()
        proc.returncode = returncode
        proc.communicate.return_value = (stdout, "")
        return proc

    # -- _physical_cores_from_powershell --------------------------------------

    def test_powershell_returns_core_count(self):
        """Happy path: powershell outputs an integer, method returns it."""
        with unittest.mock.patch('rez.utils.platform_.Popen',
                                 return_value=self._make_proc("4\n")):
            self.assertEqual(platform_._physical_cores_from_powershell(), 4)

    def test_powershell_oserror_returns_none(self):
        """OSError launching powershell (not found / access denied) → None."""
        with unittest.mock.patch('rez.utils.platform_.Popen',
                                 side_effect=OSError):
            self.assertIsNone(platform_._physical_cores_from_powershell())

    def test_powershell_nonzero_returncode_returns_none(self):
        """Non-zero exit code from powershell → None."""
        with unittest.mock.patch('rez.utils.platform_.Popen',
                                 return_value=self._make_proc("", returncode=1)):
            self.assertIsNone(platform_._physical_cores_from_powershell())

    def test_powershell_bad_output_returns_none(self):
        """Unexpected non-integer stdout (e.g. WMI unavailable message) → None."""
        with unittest.mock.patch('rez.utils.platform_.Popen',
                                 return_value=self._make_proc("not a number\n")):
            self.assertIsNone(platform_._physical_cores_from_powershell())

    # -- _physical_cores_from_wmic --------------------------------------------

    def test_wmic_single_cpu_returns_core_count(self):
        """Single CPU: wmic outputs one NumberOfCores line, method returns it."""
        with unittest.mock.patch('rez.utils.platform_.Popen',
                                 return_value=self._make_proc("NumberOfCores=6\r\n\r\n")):
            self.assertEqual(platform_._physical_cores_from_wmic(), 6)

    def test_wmic_multi_cpu_sums_cores(self):
        """Multiple CPUs: wmic outputs one line per socket, method returns sum."""
        output = "NumberOfCores=8\r\n\r\nNumberOfCores=8\r\n\r\n"
        with unittest.mock.patch('rez.utils.platform_.Popen',
                                 return_value=self._make_proc(output)):
            self.assertEqual(platform_._physical_cores_from_wmic(), 16)

    def test_wmic_oserror_returns_none(self):
        """OSError launching wmic (removed on Win11 24H2+) → None."""
        with unittest.mock.patch('rez.utils.platform_.Popen',
                                 side_effect=OSError):
            self.assertIsNone(platform_._physical_cores_from_wmic())

    def test_wmic_nonzero_returncode_returns_none(self):
        with unittest.mock.patch('rez.utils.platform_.Popen',
                                 return_value=self._make_proc("", returncode=1)):
            self.assertIsNone(platform_._physical_cores_from_wmic())

    def test_wmic_no_match_returns_none(self):
        """Parseable but unexpected output with no NumberOfCores= token → None."""
        with unittest.mock.patch('rez.utils.platform_.Popen',
                                 return_value=self._make_proc("Caption=Intel64 Family\r\n")):
            self.assertIsNone(platform_._physical_cores_from_wmic())

    # -- _physical_cores fallback chain ---------------------------------------

    def test_physical_cores_prefers_powershell(self):
        """powershell succeeds → wmic is never called."""
        with unittest.mock.patch.object(platform_, '_physical_cores_from_powershell',
                                        return_value=4) as mock_ps, \
             unittest.mock.patch.object(platform_, '_physical_cores_from_wmic',
                                        return_value=4) as mock_wmic:
            result = platform_._physical_cores()
            mock_ps.assert_called_once()
            mock_wmic.assert_not_called()
            self.assertEqual(result, 4)

    def test_physical_cores_falls_back_to_wmic(self):
        """powershell returns None (e.g. older Windows) → wmic result used."""
        with unittest.mock.patch.object(platform_, '_physical_cores_from_powershell',
                                        return_value=None), \
             unittest.mock.patch.object(platform_, '_physical_cores_from_wmic',
                                        return_value=4):
            self.assertEqual(platform_._physical_cores(), 4)

    def test_physical_cores_both_fail_returns_none(self):
        """Both helpers return None → _physical_cores returns None."""
        with unittest.mock.patch.object(platform_, '_physical_cores_from_powershell',
                                        return_value=None), \
             unittest.mock.patch.object(platform_, '_physical_cores_from_wmic',
                                        return_value=None):
            self.assertIsNone(platform_._physical_cores())

    # -- integration smoke-tests ----------------------------------------------

    def test_logical_cores_is_positive(self):
        """logical_cores returns a positive integer on this machine."""
        self.assertGreaterEqual(platform_.logical_cores, 1)

    def test_physical_cores_is_positive_and_lte_logical(self):
        """physical_cores returns a positive integer no greater than logical_cores."""
        physical = platform_.physical_cores
        logical = platform_.logical_cores
        self.assertGreaterEqual(physical, 1)
        self.assertLessEqual(physical, logical)
