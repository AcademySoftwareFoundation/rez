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
from rez.version import Version


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


@unittest.skipIf(
    platform_.name != "windows",
    "URI normcase bug only manifests on Windows where os.path.normcase is not a no-op.",
)
class TestFilesystemRepoUriCaseSensitivity(TestBase, TempdirMixin):
    """get_package_from_uri and get_variant_from_uri must find packages when
    the package name or version contains uppercase letters.

    Root cause: get_package_from_uri applies os.path.normcase to the entire URI
    before slicing out pkg_name and pkg_ver_str. Windows normcase lowercases
    the whole string, so '1.0B' becomes '1.0b' and 'FooBar' becomes 'foobar'.
    The subsequent get_package call (version equality check) and _get_family
    case-guard then both return None.
    """

    @classmethod
    def setUpClass(cls):
        TempdirMixin.setUpClass()
        cls.settings = {}

    @classmethod
    def tearDownClass(cls):
        TempdirMixin.tearDownClass()

    def _make_repo(self):
        pool = filesystem.ResourcePool(cache_size=None)
        return filesystem.FileSystemPackageRepository(self.root, pool)

    def _install(self, repo, name, version_str):
        data = {"version": version_str} if version_str else {}
        package = create_package(name, data=data)
        variant = next(package.iter_variants())
        return repo._create_variant(variant, overrides={})

    def test_get_package_from_uri_uppercase_version(self):
        """get_package_from_uri finds a package whose version contains uppercase letters."""
        repo = self._make_repo()
        installed = self._install(repo, "foo", "1.0B")
        pkg_uri = installed.parent.uri

        result = repo.get_package_from_uri(pkg_uri)
        self.assertIsNotNone(
            result,
            "get_package_from_uri returned None for %r — "
            "version '1.0B' was normcased to '1.0b' before lookup" % pkg_uri,
        )
        self.assertEqual(result.version, Version("1.0B"))

    def test_get_package_from_uri_uppercase_name(self):
        """get_package_from_uri finds a package whose name contains uppercase letters."""
        repo = self._make_repo()
        installed = self._install(repo, "FooBar", "1.0")
        pkg_uri = installed.parent.uri

        result = repo.get_package_from_uri(pkg_uri)
        self.assertIsNotNone(
            result,
            "get_package_from_uri returned None for %r — "
            "name 'FooBar' was normcased to 'foobar' before lookup" % pkg_uri,
        )
        self.assertEqual(result.name, "FooBar")

    def test_get_variant_from_uri_uppercase_version(self):
        """get_variant_from_uri finds a variant whose version contains uppercase letters."""
        repo = self._make_repo()
        installed = self._install(repo, "foo", "1.0B")
        variant_uri = installed.uri

        result = repo.get_variant_from_uri(variant_uri)
        self.assertIsNotNone(
            result,
            "get_variant_from_uri returned None for %r — "
            "version '1.0B' was normcased to '1.0b' before lookup" % variant_uri,
        )
