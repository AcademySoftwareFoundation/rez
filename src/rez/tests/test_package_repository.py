# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Test package repository plugin.
"""
import unittest

from rezplugins.package_repository import filesystem
from rez.packages import create_package
from rez.tests.util import TestBase, TempdirMixin
from rez.utils.platform_ import platform_


class TestFilesystemPackageRepository(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls):
        TempdirMixin.setUpClass()

        cls.settings = dict()

    @classmethod
    def tearDownClass(cls):
        TempdirMixin.tearDownClass()

    @unittest.skipIf(platform_.name != "windows",
                     "Skipping because this issue only affects case-insensitive platforms.")
    def test_mismatching_case(self):
        """Test that we get a caught PackageRepositoryError on case-insensitive platforms."""
        pool = filesystem.ResourcePool(cache_size=None)
        pkg_repository = filesystem.FileSystemPackageRepository(self.root, pool)

        package = create_package("myTestPackage", data={})
        variant = next(package.iter_variants())
        case_mismatch_package = create_package("MyTestPackage", data={})
        case_mismatch_variant = next(case_mismatch_package.iter_variants())

        pkg_repository._create_variant(variant, overrides={})
        with self.assertRaises(filesystem.PackageRepositoryError):
            pkg_repository._create_variant(case_mismatch_variant, overrides={})
