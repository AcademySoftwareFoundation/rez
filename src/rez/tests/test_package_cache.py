"""
Test package caching.
"""
from rez.tests.util import TestBase, TempdirMixin, restore_os_environ
from rez.packages import get_package
from rez.package_cache import PackageCache
from rez.resolved_context import ResolvedContext
from rez.exceptions import PackageCacheError
import os
import os.path
import time


class TestPackageCache(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls):
        TempdirMixin.setUpClass()

        path = os.path.realpath(os.path.dirname(__file__))
        cls.py_packages_path = os.path.join(path, "data", "packages", "py_packages")
        cls.solver_packages_path = os.path.join(path, "data", "solver", "packages")

        cls.package_cache_path = os.path.join(cls.root, "package_cache")
        os.mkdir(cls.package_cache_path)

        cls.settings = dict(
            packages_path=[cls.py_packages_path, cls.solver_packages_path],
            cache_packages_path=cls.package_cache_path,
            default_cachable=True,

            # ensure test packages will get cached
            package_cache_same_device=True,

            default_cachable_per_repository = {
                cls.solver_packages_path: False
            },

            default_cachable_per_package = {
                "late_binding": False
            }
        )

    @classmethod
    def tearDownClass(cls):
        TempdirMixin.tearDownClass()

    def _pkgcache(self):
        return PackageCache(self.package_cache_path)

    def test_cache_variant(self):
        """Test direct caching of a cachable variant."""
        pkgcache = self._pkgcache()

        package = get_package("versioned", "3.0")
        variant = next(package.iter_variants())

        _, status = pkgcache.add_variant(variant)
        self.assertEqual(status, PackageCache.VARIANT_CREATED)

        # adding again should indicate the variant is already cached
        _, status = pkgcache.add_variant(variant)
        self.assertEqual(status, PackageCache.VARIANT_FOUND)

    def test_delete_cached_variant(self):
        """Test variant deletion from cache."""
        pkgcache = self._pkgcache()

        package = get_package("versioned", "3.0")
        variant = next(package.iter_variants())

        pkgcache.add_variant(variant)

        result = pkgcache.remove_variant(variant)
        self.assertEqual(result, PackageCache.VARIANT_REMOVED)

        # another deletion should say not found
        result = pkgcache.remove_variant(variant)
        self.assertEqual(result, PackageCache.VARIANT_NOT_FOUND)

    def test_cache_fail_uncachable_variant(self):
        """Test that caching of an uncachable variant fails."""
        pkgcache = self._pkgcache()

        package = get_package("timestamped", "1.1.1")
        variant = next(package.iter_variants())

        with self.assertRaises(PackageCacheError):
            pkgcache.add_variant(variant)

    def test_cache_fail_no_variant_payload(self):
        """Test that adding a variant with no disk payload, fails."""
        pkgcache = self._pkgcache()

        package = get_package("variants_py", "2.0")
        variant = next(package.iter_variants())

        with self.assertRaises(PackageCacheError):
            pkgcache.add_variant(variant)

    def test_cache_fail_per_repo(self):
        """Test that caching fails on a package from a repo set to non-cachable."""
        pkgcache = self._pkgcache()

        package = get_package("pyfoo", "3.1.0")
        variant = next(package.iter_variants())

        with self.assertRaises(PackageCacheError):
            pkgcache.add_variant(variant)

    def test_cache_fail_per_package(self):
        """Test that caching fails on a package with a blacklisted name."""
        pkgcache = self._pkgcache()

        package = get_package("late_binding", "1.0")
        variant = next(package.iter_variants())

        with self.assertRaises(PackageCacheError):
            pkgcache.add_variant(variant)

    def test_caching_on_resolve(self):
        """Test that cache is updated as expected on resolved env."""
        pkgcache = self._pkgcache()

        with restore_os_environ():
            # set config settings into env so rez-pkg-cache proc sees them
            os.environ.update(self.get_settings_env())

            # Creating the context will asynchronously add variants to the cache
            # in a separate proc.
            #
            c = ResolvedContext([
                "timestamped-1.2.0",
                "pyfoo-3.1.0"  # won't cache, see earlier test
            ])

        variant = c.get_resolved_package("timestamped")

        # Retry 50 times with 0.1 sec interval, 5 secs is more than enough for
        # the very small variant to be copied to cache.
        #
        path = None
        for _ in range(50):
            time.sleep(0.1)
            path = pkgcache.get_cached_root(variant)
            if path:
                break

        self.assertNotEqual(path, None)

        expected_payload_file = os.path.join(path, "stuff.txt")
        self.assertTrue(os.path.exists(expected_payload_file))
