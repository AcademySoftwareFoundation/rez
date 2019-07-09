"""
Tests for 'test' command
"""
import unittest

import sys

import rez.vendor.mock as mock

from rez.cli.test import get_package, is_dev_run, prepare_dev_env_package, update_package_in_local_packages_path, \
    install_package_in_local_packages_path
from rez.developer_package import DeveloperPackage
from rez.exceptions import PackageMetadataError


class TestRezTest(unittest.TestCase):
    @mock.patch('rez.cli.test.get_developer_package', side_effect=PackageMetadataError())
    def test_getPackage_invalidPackageName_returnsNone(self, get_developer_package):
        # Arrange / Act
        result = get_package('invalid_package_name')

        # Assert
        self.assertIsNone(result)

    @mock.patch('rez.cli.test.get_developer_package', return_value=mock.MagicMock(spec=DeveloperPackage))
    def test_getPackage_validPackageName_packageReturned(self, get_developer_package):
        # Act
        result = get_package('valid_package_name')

        # Assert
        self.assertIsInstance(result, DeveloperPackage)

    def test_isDevRun_predefinedCases_properValueReturned(self):
        # Arrange
        test_cases = {
            True: ('.', None),
            False: ('rez', 'testtool', 'breeze')
        }

        # Act / Assert
        for result, test_data in test_cases.items():
            for case in test_data:
                self.assertEqual(result, is_dev_run(case))

    @mock.patch('rez.cli.test.install_package_in_local_packages_path')
    @mock.patch('rez.cli.test.get_developer_package', side_effect=PackageMetadataError())
    def test_prepareDevEnv_packageNotExistsInLocalPath_installationProcessCalledOnce(self, get_developer_package, install_package):
        # Arrange
        package = mock.MagicMock()
        package.name = 'rez'
        package.version = '1.0.0'

        # Act
        prepare_dev_env_package(package)

        # Assert
        self.assertEqual(install_package.call_count, 1)

    @mock.patch('rez.cli.test.update_package_in_local_packages_path')
    @mock.patch('rez.cli.test.get_developer_package')
    def test_prepareDevEnv_packageAlreadyInstalledInLocalPath_updateProcessCalledOnce(self, get_developer_package, update_package):
        # Arrange
        package = mock.MagicMock()
        package.name = 'rez'
        package.version = '1.0.0'

        # Act
        prepare_dev_env_package(package)

        # Assert
        self.assertEqual(update_package.call_count, 1)

    @mock.patch('rez.cli.test.run', side_effect=SystemExit(1))
    def test_installPackageInLocalPackagesPath_buildError_notZeroExitCode(self, run):
        # Arrange / Act / Assert
        with self.assertRaises(SystemExit) as exit_code:
            install_package_in_local_packages_path()

            self.assertNotEqual(exit_code.exception.code, 0)

    @mock.patch('rez.cli.test.run')
    def test_installPackageInLocalPath_properRun_sysArgvDoesntChange(self, run):
        # Arrange
        argv_before = sys.argv

        # Act
        install_package_in_local_packages_path()
        argv_after = sys.argv

        # Assert
        self.assertEqual(argv_before, argv_after)

    @mock.patch("__builtin__.open")
    def test_updatePackageInLocalPath_noDiff_fileNotOpenToWrite(self, mock_file):
        # Arrange
        tests = {'a': None, 'b': None}
        package = mock.MagicMock(tests=tests)
        installed_package = mock.MagicMock(tests=tests)

        # Act
        update_package_in_local_packages_path(package, installed_package)

        # Assert
        self.assertEqual(mock_file.call_count, 0)
