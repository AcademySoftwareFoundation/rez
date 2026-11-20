# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Additional unit tests for rez.package_cache covering edge cases, error paths,
daemon/caching operations, cleaning, locking, and status transitions.
"""
from __future__ import annotations

import errno
import itertools
import json
import logging
import os
import os.path
import shutil
import stat
import tempfile
import time
import types
import unittest
from unittest.mock import MagicMock, patch

from rez.exceptions import PackageCacheError
from rez.package_cache import PackageCache
from rez.packages import get_package
from rez.system import system
from rez.tests.util import TempdirMixin, TestBase
from rez.utils.filesystem import canonical_path
from rez.utils.platform_ import platform_


class TestPackageCacheExtra(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        TempdirMixin.setUpClass()

        cls.py_packages_path = canonical_path(cls.data_path("packages", "py_packages"))
        cls.solver_packages_path = canonical_path(cls.data_path("solver", "packages"))

        cls.package_cache_path = os.path.join(cls.root, "package_cache")
        os.makedirs(cls.package_cache_path, exist_ok=True)

        cls.settings = dict(
            packages_path=[cls.py_packages_path, cls.solver_packages_path],
            cache_packages_path=cls.package_cache_path,
            default_cachable=True,
            package_cache_same_device=True,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        TempdirMixin.tearDownClass()
        super().tearDownClass()

    def _new_cache(self) -> PackageCache:
        cache_dir = tempfile.mkdtemp(dir=self.root, prefix="pkgcache_")
        return PackageCache(cache_dir)

    def _make_fs_package(self, repo_dir: str, name: str, version: str | None = "1.0.0",
                         variants: list | None = None, create_payload: bool = True,
                         allow_tmpdir: bool = True):
        """Create a minimal filesystem package in repo_dir and return its first variant."""
        from rez.packages import iter_packages

        if version:
            pkg_dir = os.path.join(repo_dir, name, version)
        else:
            pkg_dir = os.path.join(repo_dir, name)
        os.makedirs(pkg_dir, exist_ok=True)

        lines = [f"name = {name!r}"]
        if version:
            lines.append(f"version = {version!r}")
        if variants is not None:
            lines.append(f"variants = {variants!r}")
            if create_payload:
                for v in variants:
                    sub = os.path.join(pkg_dir, *v)
                    os.makedirs(sub, exist_ok=True)
                    with open(os.path.join(sub, "payload.txt"), "w") as f:
                        f.write("data")
        elif create_payload:
            with open(os.path.join(pkg_dir, "payload.txt"), "w") as f:
                f.write("data")

        with open(os.path.join(pkg_dir, "package.py"), "w") as f:
            f.write("\n".join(lines) + "\n")

        settings_update = {"packages_path": [repo_dir, self.py_packages_path]}
        if allow_tmpdir:
            settings_update["tmpdir"] = os.path.join(self.root, "other_tmpdir")
        self.update_settings(settings_update)
        pkg = get_package(name, version) if version else next(iter_packages(name))
        return next(pkg.iter_variants())

    # ------------------------------------------------------------------
    # __init__ & get_cached_root
    # ------------------------------------------------------------------

    def test_init_invalid_path_raises(self) -> None:
        """PackageCache raises PackageCacheError if path is not a directory."""
        missing = os.path.join(self.root, "does_not_exist")
        with self.assertRaises(PackageCacheError):
            PackageCache(missing)

        file_path = os.path.join(self.root, "not_a_dir.txt")
        with open(file_path, "w") as f:
            f.write("x")
        with self.assertRaises(PackageCacheError):
            PackageCache(file_path)

    def test_get_cached_root_not_found(self) -> None:
        """get_cached_root returns None when variant is not cached."""
        pkgcache = self._new_cache()
        pkg = get_package("versioned", "3.0")
        variant = next(pkg.iter_variants())
        self.assertIsNone(pkgcache.get_cached_root(variant))

    def test_get_cached_root_utime_enoent_returns_none(self) -> None:
        """get_cached_root returns None if os.utime raises ENOENT."""
        pkgcache = self._new_cache()
        pkg = get_package("versioned", "3.0")
        variant = next(pkg.iter_variants())
        pkgcache.add_variant(variant)

        err = OSError(errno.ENOENT, "No such file or directory")
        with patch("rez.package_cache.os.utime", side_effect=err):
            self.assertIsNone(pkgcache.get_cached_root(variant))

    def test_get_cached_root_utime_other_oserror_reraises(self) -> None:
        """get_cached_root re-raises OSError if errno is not ENOENT."""
        pkgcache = self._new_cache()
        pkg = get_package("versioned", "3.0")
        variant = next(pkg.iter_variants())
        pkgcache.add_variant(variant)

        err = OSError(errno.EACCES, "Permission denied")
        with patch("rez.package_cache.os.utime", side_effect=err):
            with self.assertRaises(OSError):
                pkgcache.get_cached_root(variant)

    # ------------------------------------------------------------------
    # get_variant_size
    # ------------------------------------------------------------------

    @unittest.skipIf(platform_.name == "windows", "DirEntry.stat() reports st_ino=0 on Windows")
    def test_get_variant_size_subdirs_inodes_broken_symlink_and_early_bail(self) -> None:
        """get_variant_size traverses subdirs, skips duplicate inodes/broken links, and bails early."""
        pkgcache = self._new_cache()
        root_dir = tempfile.mkdtemp(dir=self.root, prefix="varsize_")
        sub_dir = os.path.join(root_dir, "sub")
        os.makedirs(sub_dir)

        file_a = os.path.join(root_dir, "a.bin")
        with open(file_a, "wb") as f:
            f.write(b"x" * 100)

        file_b = os.path.join(sub_dir, "b.bin")
        with open(file_b, "wb") as f:
            f.write(b"y" * 200)

        try:
            # Symlink to file_a shares the same inode and should not be double-counted
            os.symlink(file_a, os.path.join(sub_dir, "link_a.bin"))
            # Broken symlink triggers OSError on stat(follow_symlinks=True)
            os.symlink(os.path.join(root_dir, "missing_target"), os.path.join(root_dir, "broken"))
        except OSError as e:
            self.skipTest(f"symlinks unsupported: {e}")

        self.update_settings({"package_cache_space_buffer": 50})
        # With plenty of free space, total should be exactly 300 bytes
        self.assertEqual(pkgcache.get_variant_size(10_000, root_dir), 300)

        # With free space barely above buffer, should bail out early once buffer is breached
        self.update_settings({"package_cache_space_buffer": 1000})
        early_size = pkgcache.get_variant_size(1050, root_dir)
        self.assertGreater(early_size, 0)
        self.assertLessEqual(early_size, 300)

        # Non-existent root triggers outer OSError -> returns 0
        self.assertEqual(pkgcache.get_variant_size(10_000, os.path.join(self.root, "nope")), 0)

    def test_variant_meets_space_requirements_below_and_above_threshold(self) -> None:
        """variant_meets_space_requirements checks disk usage against threshold and buffer."""
        pkgcache = self._new_cache()
        pkg = get_package("versioned", "3.0")
        variant = next(pkg.iter_variants())

        self.update_settings({
            "package_cache_used_threshold": 80,
            "package_cache_space_buffer": 100,
        })

        # Below threshold (50% used <= 80%): returns True without checking variant size
        with patch("rez.package_cache.shutil.disk_usage", return_value=(10_000, 5_000, 5_000)):
            self.assertTrue(pkgcache.variant_meets_space_requirements(variant.root))

        # Above threshold (90% used > 80%) with plenty of free space above buffer: returns True
        with patch("rez.package_cache.shutil.disk_usage", return_value=(100_000, 90_000, 10_000)):
            self.assertTrue(pkgcache.variant_meets_space_requirements(variant.root))

        # Above threshold (90% used > 80%) with buffer >= free: returns False
        self.update_settings({"package_cache_space_buffer": 10_000})
        with patch("rez.package_cache.shutil.disk_usage", return_value=(100_000, 90_000, 10_000)):
            self.assertFalse(pkgcache.variant_meets_space_requirements(variant.root))

    # ------------------------------------------------------------------
    # add_variant
    # ------------------------------------------------------------------

    def test_add_variant_no_root_raises(self) -> None:
        """add_variant raises PackageCacheError when variant has no root."""
        pkgcache = self._new_cache()
        pkg = get_package("versioned", "3.0")
        variant = next(pkg.iter_variants())
        with patch.object(type(variant), "root", new_callable=lambda: property(lambda self: None)):
            with self.assertRaises(PackageCacheError):
                pkgcache.add_variant(variant)

    def test_add_variant_local_disallowed_raises(self) -> None:
        """add_variant raises PackageCacheError for local variant when package_cache_local=False."""
        pkgcache = self._new_cache()
        pkg = get_package("versioned", "3.0")
        variant = next(pkg.iter_variants())
        self.update_settings({"package_cache_local": False})
        with patch.object(type(variant), "is_local", new_callable=lambda: property(lambda self: True)):
            with self.assertRaises(PackageCacheError):
                pkgcache.add_variant(variant)

    def test_add_variant_same_device_disallowed_raises(self) -> None:
        """add_variant raises PackageCacheError when package_cache_same_device=False and st_dev matches."""
        pkgcache = self._new_cache()
        pkg = get_package("versioned", "3.0")
        variant = next(pkg.iter_variants())
        self.update_settings({"package_cache_same_device": False})
        orig_stat = os.stat
        fake_stat = types.SimpleNamespace(st_dev=42, st_mode=stat.S_IFDIR | 0o755)

        def stat_same_dev(path, *args, **kwargs):
            if path in (pkgcache.path, variant.root):
                return fake_stat
            return orig_stat(path, *args, **kwargs)

        with patch("rez.package_cache.os.stat", side_effect=stat_same_dev):
            with self.assertRaises(PackageCacheError):
                pkgcache.add_variant(variant)

    def test_add_variant_temp_repo_disallowed_raises(self) -> None:
        """add_variant raises PackageCacheError for packages in a temp filesystem repository."""
        pkgcache = self._new_cache()
        tmpdir = canonical_path(self.root)
        temp_repo = tempfile.mkdtemp(dir=tmpdir, prefix="rez_temprepo_")
        try:
            variant = self._make_fs_package(temp_repo, "temp_pkg", "1.0.0", allow_tmpdir=False)
            self.update_settings({
                "packages_path": [temp_repo, self.py_packages_path],
                "tmpdir": tmpdir,
            })
            with self.assertRaises(PackageCacheError):
                pkgcache.add_variant(variant)
        finally:
            shutil.rmtree(temp_repo, ignore_errors=True)

    def test_add_variant_already_cached_logs_warning(self) -> None:
        """add_variant logs a warning when variant is already cached and logger is provided."""
        pkgcache = self._new_cache()
        pkg = get_package("versioned", "3.0")
        variant = next(pkg.iter_variants())
        pkgcache.add_variant(variant)

        logger = MagicMock(spec=logging.Logger)
        _, status = pkgcache.add_variant(variant, logger=logger)
        self.assertEqual(status, PackageCache.VARIANT_FOUND)
        logger.warning.assert_called_once()

    def test_add_variant_wait_for_copying_resolves_found_and_stalled(self) -> None:
        """add_variant with wait_for_copying=True polls until status changes and logs outcome."""
        pkgcache = self._new_cache()
        pkg = get_package("versioned", "3.0")
        variant = next(pkg.iter_variants())
        fake_root = "/fake/root/a"

        # Case 1: VARIANT_COPYING -> VARIANT_FOUND (logs info)
        logger_info = MagicMock(spec=logging.Logger)
        with patch.object(
            pkgcache,
            "_get_cached_root",
            side_effect=[
                (PackageCache.VARIANT_COPYING, fake_root),
                (PackageCache.VARIANT_FOUND, fake_root),
            ],
        ), patch("rez.package_cache.time.sleep"):
            rootpath, status = pkgcache.add_variant(variant, wait_for_copying=True, logger=logger_info)
        self.assertEqual(status, PackageCache.VARIANT_FOUND)
        self.assertEqual(rootpath, fake_root)
        logger_info.info.assert_called_once()

        # Case 2: VARIANT_COPYING -> VARIANT_COPY_STALLED (logs warning)
        logger_warn = MagicMock(spec=logging.Logger)
        with patch.object(
            pkgcache,
            "_get_cached_root",
            side_effect=[
                (PackageCache.VARIANT_COPYING, fake_root),
                (PackageCache.VARIANT_COPY_STALLED, fake_root),
            ],
        ), patch("rez.package_cache.time.sleep"):
            rootpath, status = pkgcache.add_variant(variant, wait_for_copying=True, logger=logger_warn)
        self.assertEqual(status, PackageCache.VARIANT_COPY_STALLED)
        logger_warn.warning.assert_called_once()

    def test_add_variant_with_indexed_variants_and_hash_collision(self) -> None:
        """add_variant stores variant data when index is not None and increments base26 name on collision."""
        pkgcache = self._new_cache()
        repo_dir = tempfile.mkdtemp(dir=self.root, prefix="repo_variants_")
        variant = self._make_fs_package(repo_dir, "multi_var", "1.0.0", variants=[["linux"], ["osx"]])

        # Pre-populate a.json with a different handle to force base26 increment to 'b'
        hash_path = pkgcache._get_hash_path(variant)
        os.makedirs(hash_path, exist_ok=True)
        with open(os.path.join(hash_path, "a.json"), "w") as f:
            json.dump({"handle": {"other": "variant"}}, f)

        rootpath, status = pkgcache.add_variant(variant)
        self.assertEqual(status, PackageCache.VARIANT_CREATED)
        self.assertEqual(os.path.basename(rootpath), "b")

        with open(rootpath + ".json") as f:
            stored = json.load(f)
        self.assertEqual(stored["data"], ["linux"])

    def test_add_variant_race_under_lock_returns_existing(self) -> None:
        """add_variant returns existing status if another process created it before lock acquired."""
        pkgcache = self._new_cache()
        pkg = get_package("versioned", "3.0")
        variant = next(pkg.iter_variants())

        with patch.object(
            pkgcache,
            "_get_cached_root",
            side_effect=[
                (PackageCache.VARIANT_NOT_FOUND, ""),
                (PackageCache.VARIANT_FOUND, "/some/cached/a"),
            ],
        ):
            rootpath, status = pkgcache.add_variant(variant)
        self.assertEqual(status, PackageCache.VARIANT_FOUND)
        self.assertEqual(rootpath, "/some/cached/a")

    def test_add_variant_while_copying_utime_exception_ignored(self) -> None:
        """_while_copying thread ignores errors from os.utime during copytree."""
        pkgcache = self._new_cache()
        pkg = get_package("versioned", "3.0")
        variant = next(pkg.iter_variants())

        orig_copytree = shutil.copytree
        orig_utime = os.utime

        def slow_copytree(*args, **kwargs):
            time.sleep(0.05)
            return orig_copytree(*args, **kwargs)

        def utime_fail_copying(path, times=None, *args, **kwargs):
            if ".copying-" in str(path):
                raise OSError("utime failed")
            return orig_utime(path, times, *args, **kwargs)

        with patch.object(pkgcache, "_COPYING_TIME_INC", 0.01), \
             patch("rez.package_cache.os.utime", side_effect=utime_fail_copying), \
             patch("rez.package_cache.shutil.copytree", side_effect=slow_copytree):
            _, status = pkgcache.add_variant(variant)
        self.assertEqual(status, PackageCache.VARIANT_CREATED)

    def test_add_variant_unversioned_package_hash_path(self) -> None:
        """_get_hash_path uses _NO_VERSION for unversioned packages."""
        pkgcache = self._new_cache()
        repo_dir = tempfile.mkdtemp(dir=self.root, prefix="repo_unver_")
        variant = self._make_fs_package(repo_dir, "unver_pkg", version=None)
        hash_path = pkgcache._get_hash_path(variant)
        self.assertIn("_NO_VERSION", hash_path.split(os.sep))

    # ------------------------------------------------------------------
    # remove_variant
    # ------------------------------------------------------------------

    def test_remove_variant_non_writable_and_stalled_copying_file(self) -> None:
        """remove_variant chmods non-writable root, removes .copying file, and stops at non-empty dir."""
        pkgcache = self._new_cache()
        repo_dir = tempfile.mkdtemp(dir=self.root, prefix="repo_rm_")
        v1 = self._make_fs_package(repo_dir, "rm_pkg", "1.0.0", variants=[["a"], ["b"]])
        pkg = get_package("rm_pkg", "1.0.0")
        variants = list(pkg.iter_variants())
        v2 = variants[1]

        root1, _ = pkgcache.add_variant(v1)
        pkgcache.add_variant(v2)

        # Simulate stalled copying file on v1 and non-writable root
        hash_dir, incname = os.path.split(root1)
        copying_file = os.path.join(hash_dir, ".copying-" + incname)
        with open(copying_file, "w") as f:
            f.write("")
        old_mtime = time.time() - (pkgcache._COPYING_TIME_MAX + 10)
        os.utime(copying_file, (old_mtime, old_mtime))

        with patch("rez.package_cache.os.access", return_value=False):
            status = pkgcache.remove_variant(v1)
        self.assertEqual(status, PackageCache.VARIANT_REMOVED)
        self.assertFalse(os.path.exists(copying_file))
        # Parent pkg dir still exists because v2 is still cached
        self.assertTrue(os.path.isdir(os.path.dirname(os.path.dirname(hash_dir))))

    def test_remove_variant_rename_enoent_and_other_error(self) -> None:
        """remove_variant returns VARIANT_NOT_FOUND on ENOENT and re-raises other OSError."""
        pkgcache = self._new_cache()
        pkg = get_package("versioned", "3.0")
        variant = next(pkg.iter_variants())
        pkgcache.add_variant(variant)

        with patch("rez.package_cache.rename", side_effect=OSError(errno.ENOENT, "gone")):
            self.assertEqual(pkgcache.remove_variant(variant), PackageCache.VARIANT_NOT_FOUND)

        with patch("rez.package_cache.rename", side_effect=OSError(errno.EACCES, "denied")):
            with self.assertRaises(OSError):
                pkgcache.remove_variant(variant)

    # ------------------------------------------------------------------
    # add_variants_async, add_variants, _subprocess_package_caching_daemon
    # ------------------------------------------------------------------

    def test_add_variants_async_delegates_and_early_return(self) -> None:
        """add_variants_async delegates to add_variants(package_cache_async=True); empty list returns early."""
        pkgcache = self._new_cache()
        pkg = get_package("versioned", "3.0")
        variant = next(pkg.iter_variants())

        with patch.object(type(system), "is_production_rez_install", True), \
             patch.object(pkgcache, "_subprocess_package_caching_daemon") as mock_daemon:
            pkgcache.add_variants_async([variant])
            mock_daemon.assert_called_once_with(pkgcache.path)

        # Calling again when already cached + clean_limit < 0 returns early without daemon
        self.update_settings({"package_cache_clean_limit": -1.0})
        pkgcache.add_variant(variant)
        uncachable_pkg = get_package("timestamped", "1.1.1")
        uncachable_variant = next(uncachable_pkg.iter_variants())
        with patch.object(type(system), "is_production_rez_install", True), \
             patch.object(pkgcache, "_subprocess_package_caching_daemon") as mock_daemon:
            pkgcache.add_variants([uncachable_variant, variant], package_cache_async=True)
            mock_daemon.assert_not_called()

    def test_add_variants_pending_dedup_and_corrupt_pending_file(self) -> None:
        """add_variants skips already-pending variants and ignores unreadable pending files."""
        pkgcache = self._new_cache()
        pkg = get_package("versioned", "3.0")
        variant = next(pkg.iter_variants())

        # Create a corrupt pending file with matching prefix
        prefix = variant.parent.qualified_name + "-"
        corrupt_file = os.path.join(pkgcache._pending_dir, prefix + "corrupt.json")
        with open(corrupt_file, "w") as f:
            f.write("{not valid json")

        # Create a valid pending file for the same variant
        valid_file = os.path.join(pkgcache._pending_dir, prefix + "valid.json")
        with open(valid_file, "w") as f:
            json.dump(variant.handle.to_dict(), f)

        with patch.object(type(system), "is_production_rez_install", True), \
             patch.object(pkgcache, "_subprocess_package_caching_daemon"):
            pkgcache.add_variants([variant], package_cache_async=True)

        # Only the 2 pre-existing files should be in pending dir (no duplicate written)
        self.assertEqual(sorted(os.listdir(pkgcache._pending_dir)), [prefix + "corrupt.json", prefix + "valid.json"])

    def test_subprocess_package_caching_daemon_branches(self) -> None:
        """Test _subprocess_package_caching_daemon non-selftest devnull, selftest, and Popen failure."""
        pkgcache = self._new_cache()

        # Non-selftest uses devnull and returns Popen handle
        fake_proc = MagicMock()
        with patch.object(type(system), "selftest_is_running", False), \
             patch.object(system, "rez_bin_path", "/fake/bin"), \
             patch("rez.package_cache.subprocess.Popen", return_value=fake_proc) as mock_popen:
            res = pkgcache._subprocess_package_caching_daemon(pkgcache.path)
            self.assertIs(res, fake_proc)
            mock_popen.assert_called_once()

        # Selftest running uses stdout=None, stderr=None
        with patch.object(type(system), "selftest_is_running", True), \
             patch.object(system, "rez_bin_path", "/fake/bin"), \
             patch("rez.package_cache.subprocess.Popen", return_value=fake_proc) as mock_popen:
            res = pkgcache._subprocess_package_caching_daemon(pkgcache.path)
            self.assertIs(res, fake_proc)
            _, kwargs = mock_popen.call_args
            self.assertIsNone(kwargs["stdout"])
            self.assertIsNone(kwargs["stderr"])

        # Popen exception prints warning and returns None
        with patch.object(system, "rez_bin_path", "/fake/bin"), \
             patch("rez.package_cache.subprocess.Popen", side_effect=OSError("spawn failed")), \
             patch("rez.package_cache.print_warning") as mock_warn:
            res = pkgcache._subprocess_package_caching_daemon(pkgcache.path)
            self.assertIsNone(res)
            mock_warn.assert_called_once()

    @unittest.expectedFailure
    def test_subprocess_package_caching_daemon_missing_bin_path_raises_runtime_error(self) -> None:
        """_subprocess_package_caching_daemon should raise RuntimeError when rez_bin_path is None.

        See src/rez/package_cache.py:600-603: os.path.join(system.rez_bin_path, ...)
        raises TypeError before the ``if not exe:`` RuntimeError guard is reached.
        """
        pkgcache = self._new_cache()
        with patch.object(system, "rez_bin_path", None):
            with self.assertRaises(RuntimeError):
                pkgcache._subprocess_package_caching_daemon(pkgcache.path)

    # ------------------------------------------------------------------
    # get_variants & _get_cached_root
    # ------------------------------------------------------------------

    def test_get_variants_includes_pending_skips_seen_and_corrupt(self) -> None:
        """get_variants returns pending variants not yet cached and skips corrupt/seen pending files."""
        pkgcache = self._new_cache()
        pkg1 = get_package("versioned", "3.0")
        v1 = next(pkg1.iter_variants())
        pkg2 = get_package("timestamped", "1.2.0")
        v2 = next(pkg2.iter_variants())

        # Cache v1
        pkgcache.add_variant(v1)
        # Add pending files for both v1 (already seen) and v2 (pending), plus a corrupt file
        with open(os.path.join(pkgcache._pending_dir, "v1.json"), "w") as f:
            json.dump(v1.handle.to_dict(), f)
        with open(os.path.join(pkgcache._pending_dir, "v2.json"), "w") as f:
            json.dump(v2.handle.to_dict(), f)
        with open(os.path.join(pkgcache._pending_dir, "bad.json"), "w") as f:
            f.write("bad-json")

        results = pkgcache.get_variants()
        status_by_ver = {str(v.version): status for v, _, status in results}
        self.assertEqual(status_by_ver["3.0"], PackageCache.VARIANT_FOUND)
        self.assertEqual(status_by_ver["1.2.0"], PackageCache.VARIANT_PENDING)

    def test_get_cached_root_internal_ioerror_and_copying_stalled(self) -> None:
        """_get_cached_root handles ENOENT/EACCES on json read and stalled/missing .copying file."""
        pkgcache = self._new_cache()
        pkg = get_package("versioned", "3.0")
        variant = next(pkg.iter_variants())

        hash_path = pkgcache._get_hash_path(variant)
        os.makedirs(hash_path, exist_ok=True)
        json_path = os.path.join(hash_path, "a.json")
        with open(json_path, "w") as f:
            json.dump({"handle": variant.handle.to_dict()}, f)
        copying_path = os.path.join(hash_path, ".copying-a")
        with open(copying_path, "w") as f:
            f.write("")

        # Stalled copying file
        old_time = time.time() - (pkgcache._COPYING_TIME_MAX + 5)
        os.utime(copying_path, (old_time, old_time))
        st, _ = pkgcache._get_cached_root(variant)
        self.assertEqual(st, PackageCache.VARIANT_COPY_STALLED)

        # os.stat on copying_path raises -> falls through to VARIANT_COPYING
        orig_exists = os.path.exists
        orig_stat = os.stat

        def exists_copying(path):
            if path == copying_path:
                return True
            return orig_exists(path)

        def stat_copying_fail(path, *args, **kwargs):
            if path == copying_path:
                raise OSError("vanished")
            return orig_stat(path, *args, **kwargs)

        with patch("rez.package_cache.os.path.exists", side_effect=exists_copying), \
             patch("rez.package_cache.os.stat", side_effect=stat_copying_fail):
            st, _ = pkgcache._get_cached_root(variant)
        self.assertEqual(st, PackageCache.VARIANT_COPYING)

        # open(json_path) raises ENOENT -> returns VARIANT_NOT_FOUND
        orig_open = open

        def open_enoent(path, *args, **kwargs):
            if path == json_path:
                raise IOError(errno.ENOENT, "gone")
            return orig_open(path, *args, **kwargs)

        with patch("builtins.open", side_effect=open_enoent):
            st, _ = pkgcache._get_cached_root(variant)
        self.assertEqual(st, PackageCache.VARIANT_NOT_FOUND)

        # open(json_path) raises EACCES -> re-raises
        def open_eacces(path, *args, **kwargs):
            if path == json_path:
                raise IOError(errno.EACCES, "denied")
            return orig_open(path, *args, **kwargs)

        with patch("builtins.open", side_effect=open_eacces):
            with self.assertRaises(IOError):
                pkgcache._get_cached_root(variant)

    # ------------------------------------------------------------------
    # run_daemon & _run_caching_operation
    # ------------------------------------------------------------------

    def test_run_daemon_fork_parent_and_child(self) -> None:
        """run_daemon exits in parent process and runs caching operation in child process."""
        pkgcache = self._new_cache()

        with patch("rez.package_cache.platform.system", return_value="Linux"), \
             patch("rez.package_cache.os.fork", return_value=123, create=True), \
             patch.object(pkgcache, "_run_caching_operation") as mock_op:
            with self.assertRaises(SystemExit) as cm:
                pkgcache.run_daemon()
            self.assertEqual(cm.exception.code, 0)
            mock_op.assert_not_called()

        with patch("rez.package_cache.platform.system", return_value="Linux"), \
             patch("rez.package_cache.os.fork", return_value=0, create=True), \
             patch.object(pkgcache, "_run_caching_operation") as mock_op:
            pkgcache.run_daemon()
            mock_op.assert_called_once_with(wait_for_copying=False)

    def test_run_caching_operation_step_error_and_clean_error(self) -> None:
        """_run_caching_operation logs and re-raises step errors, and logs clean errors."""
        pkgcache = self._new_cache()
        mock_logger = MagicMock(spec=logging.Logger)

        with patch.object(pkgcache, "_init_logging", return_value=mock_logger), \
             patch.object(pkgcache, "_run_caching_step", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                pkgcache._run_caching_operation()
            mock_logger.exception.assert_called_once()

        self.update_settings({"package_cache_clean_limit": 1.0})
        mock_logger.reset_mock()
        with patch.object(pkgcache, "_init_logging", return_value=mock_logger), \
             patch.object(pkgcache, "_run_caching_step", return_value=False), \
             patch.object(pkgcache, "clean", side_effect=RuntimeError("clean boom")):
            pkgcache._run_caching_operation()
            mock_logger.exception.assert_called_once()

    # ------------------------------------------------------------------
    # _run_caching_step
    # ------------------------------------------------------------------

    def test_run_caching_step_edge_cases(self) -> None:
        """Test _run_caching_step: cache_near_full, ENOENT/EACCES, space fail, errors, and statuses."""
        pkgcache = self._new_cache()
        mock_logger = MagicMock(spec=logging.Logger)
        state = {"logger": mock_logger}

        # 1. cache_near_full -> False
        with patch.object(pkgcache, "cache_near_full", return_value=True):
            self.assertFalse(pkgcache._run_caching_step(state))

        pkg = get_package("versioned", "3.0")
        variant = next(pkg.iter_variants())
        pending_file = os.path.join(pkgcache._pending_dir, "p1.json")

        def write_pending():
            with open(pending_file, "w") as f:
                json.dump(variant.handle.to_dict(), f)

        # 2. ENOENT reading pending file -> True
        write_pending()
        orig_open = open

        def open_enoent(path, *args, **kwargs):
            if path == pending_file:
                raise IOError(errno.ENOENT, "gone")
            return orig_open(path, *args, **kwargs)

        with patch.object(pkgcache, "cache_near_full", return_value=False), \
             patch("builtins.open", side_effect=open_enoent):
            self.assertTrue(pkgcache._run_caching_step(state))

        # 3. EACCES reading pending file -> raises IOError
        def open_eacces(path, *args, **kwargs):
            if path == pending_file:
                raise IOError(errno.EACCES, "denied")
            return orig_open(path, *args, **kwargs)

        with patch.object(pkgcache, "cache_near_full", return_value=False), \
             patch("builtins.open", side_effect=open_eacces):
            with self.assertRaises(IOError):
                pkgcache._run_caching_step(state)

        # 4. variant_meets_space_requirements False -> removes pending, returns True
        with patch.object(pkgcache, "cache_near_full", return_value=False), \
             patch.object(pkgcache, "variant_meets_space_requirements", return_value=False):
            self.assertTrue(pkgcache._run_caching_step(state))
        self.assertFalse(os.path.exists(pending_file))

        # 5. add_variant raises PackageCacheError -> removes pending, returns True
        write_pending()
        with patch.object(pkgcache, "cache_near_full", return_value=False), \
             patch.object(pkgcache, "variant_meets_space_requirements", return_value=True), \
             patch.object(pkgcache, "add_variant", side_effect=PackageCacheError("bad")):
            self.assertTrue(pkgcache._run_caching_step(state))
        self.assertFalse(os.path.exists(pending_file))

        # 6. add_variant raises generic Exception -> logs exception, removes pending, returns True
        write_pending()
        with patch.object(pkgcache, "cache_near_full", return_value=False), \
             patch.object(pkgcache, "variant_meets_space_requirements", return_value=True), \
             patch.object(pkgcache, "add_variant", side_effect=OSError("disk error")):
            self.assertTrue(pkgcache._run_caching_step(state))
        self.assertFalse(os.path.exists(pending_file))

        # 7. VARIANT_FOUND, VARIANT_COPY_STALLED, and VARIANT_COPYING statuses
        for st in (PackageCache.VARIANT_FOUND, PackageCache.VARIANT_COPY_STALLED):
            write_pending()
            with patch.object(pkgcache, "cache_near_full", return_value=False), \
                 patch.object(pkgcache, "variant_meets_space_requirements", return_value=True), \
                 patch.object(pkgcache, "add_variant", return_value=("/cached/a", st)):
                self.assertTrue(pkgcache._run_caching_step(state))
            self.assertFalse(os.path.exists(pending_file))

        # VARIANT_COPYING keeps pending file and adds to state["copying"]
        write_pending()
        with patch.object(pkgcache, "cache_near_full", return_value=False), \
             patch.object(pkgcache, "variant_meets_space_requirements", return_value=True), \
             patch.object(pkgcache, "add_variant", return_value=("/cached/a", PackageCache.VARIANT_COPYING)):
            self.assertTrue(pkgcache._run_caching_step(state, wait_for_copying=False))
        self.assertIn("p1.json", state["copying"])
        self.assertTrue(os.path.exists(pending_file))

        # Subsequent call with wait_for_copying=False skips p1.json and returns False
        with patch.object(pkgcache, "cache_near_full", return_value=False):
            self.assertFalse(pkgcache._run_caching_step(state, wait_for_copying=False))

    # ------------------------------------------------------------------
    # clean
    # ------------------------------------------------------------------

    def test_clean_unused_stalled_time_limit_and_remove_errors(self) -> None:
        """Test clean() for max_variant_days=0, expired variants, stalled variants, time_limit, and rmtree errors."""
        pkgcache = self._new_cache()
        pkg1 = get_package("versioned", "3.0")
        v1 = next(pkg1.iter_variants())
        pkg2 = get_package("timestamped", "1.2.0")
        v2 = next(pkg2.iter_variants())

        root1, _ = pkgcache.add_variant(v1)
        root2, _ = pkgcache.add_variant(v2)

        # Make v1 old (10 days ago)
        old_time = time.time() - (10 * 24 * 3600)
        os.utime(root1 + ".json", (old_time, old_time))

        # Make v2 stalled
        hash2, inc2 = os.path.split(root2)
        copying2 = os.path.join(hash2, ".copying-" + inc2)
        with open(copying2, "w") as f:
            f.write("")
        os.utime(copying2, (old_time, old_time))

        # 1. max_variant_days=0 skips unused variants; time_limit=0 exits after removing nothing/first
        self.update_settings({"package_cache_max_variant_days": 0})
        pkgcache.clean(time_limit=None)
        # v1 still exists (max_variant_days=0), v2 was stalled and removed
        self.assertIsNotNone(pkgcache.get_cached_root(v1))
        self.assertIsNone(pkgcache.get_cached_root(v2))

        # 2. max_variant_days=1 with time_limit=1.0 removes v1 then exits early on should_exit()
        self.update_settings({"package_cache_max_variant_days": 1})
        base_t = time.time()
        old_v1_time = base_t - (10 * 24 * 3600)
        os.utime(root1 + ".json", (old_v1_time, old_v1_time))
        stale_dir = os.path.join(pkgcache._remove_dir, "leftover")
        os.makedirs(stale_dir, exist_ok=True)
        times_iter = itertools.count(base_t, 2.0)
        with patch("rez.package_cache.time.time", side_effect=times_iter):
            pkgcache.clean(time_limit=1.0)
        self.assertIsNone(pkgcache.get_cached_root(v1))
        # Leftover still in _remove_dir because clean() exited early after unused_variants loop
        self.assertTrue(os.path.isdir(stale_dir))

        # 3. Clean _remove_dir with forceful_rmtree error logged, and should_exit() inside _remove_dir loop
        stale_dir2 = os.path.join(pkgcache._remove_dir, "leftover2")
        os.makedirs(stale_dir2, exist_ok=True)
        with patch("rez.package_cache.forceful_rmtree", side_effect=OSError("busy")):
            pkgcache.clean(time_limit=None)
        self.assertTrue(os.path.isdir(stale_dir2))

        for entry in os.listdir(pkgcache._remove_dir):
            shutil.rmtree(os.path.join(pkgcache._remove_dir, entry))
        stale_a = os.path.join(pkgcache._remove_dir, "leftover_a")
        stale_b = os.path.join(pkgcache._remove_dir, "leftover_b")
        os.makedirs(stale_a)
        os.makedirs(stale_b)

        times_iter2 = itertools.count(base_t, 2.0)
        with patch("rez.package_cache.time.time", side_effect=times_iter2):
            pkgcache.clean(time_limit=1.0)
        remaining = [d for d in (stale_a, stale_b) if os.path.isdir(d)]
        self.assertEqual(len(remaining), 1)

    def test_clean_stat_failure_on_json_continues(self) -> None:
        """clean() continues if os.stat on a cached variant json file raises."""
        pkgcache = self._new_cache()
        pkg1 = get_package("versioned", "3.0")
        v1 = next(pkg1.iter_variants())
        root1, _ = pkgcache.add_variant(v1)

        pkg2 = get_package("timestamped", "1.2.0")
        v2 = next(pkg2.iter_variants())
        root2, _ = pkgcache.add_variant(v2)
        old_time = time.time() - (10 * 24 * 3600)
        os.utime(root2 + ".json", (old_time, old_time))

        orig_stat = os.stat

        def stat_fail(path, *args, **kwargs):
            if path == root1 + ".json":
                raise OSError("vanished")
            return orig_stat(path, *args, **kwargs)

        self.update_settings({"package_cache_max_variant_days": 1})
        with patch("rez.package_cache.os.stat", side_effect=stat_fail):
            pkgcache.clean(time_limit=None)

        self.assertIsNotNone(pkgcache.get_cached_root(v1))
        self.assertIsNone(pkgcache.get_cached_root(v2))

    # ------------------------------------------------------------------
    # _lock & _init_logging
    # ------------------------------------------------------------------

    def test_lock_not_locked_on_release_is_ignored(self) -> None:
        """_lock ignores NotLocked raised during lock.release()."""
        from rez.vendor.lockfile import NotLocked

        pkgcache = self._new_cache()
        with patch("rez.package_cache.LockFile") as mock_lock_cls:
            mock_lock = mock_lock_cls.return_value
            mock_lock.release.side_effect = NotLocked()
            with pkgcache._lock():
                pass
            mock_lock.acquire.assert_called_once()
            mock_lock.release.assert_called_once()

    def test_init_logging_deletes_old_logs_and_handles_errors(self) -> None:
        """_init_logging removes logfiles older than package_cache_log_days and logs errors."""
        pkgcache = self._new_cache()
        old_log = os.path.join(pkgcache._log_dir, "old.log")
        with open(old_log, "w") as f:
            f.write("old")

        self.update_settings({"package_cache_log_days": 1})
        orig_stat = os.stat
        fake_stat = types.SimpleNamespace(st_ctime=0, st_mode=stat.S_IFREG | 0o644)

        def stat_old_log(path, *args, **kwargs):
            if path == old_log:
                return fake_stat
            return orig_stat(path, *args, **kwargs)

        with patch("rez.package_cache.os.stat", side_effect=stat_old_log):
            pkgcache._init_logging()
        self.assertFalse(os.path.exists(old_log))

        with patch("rez.package_cache.os.listdir", side_effect=OSError("boom")):
            logger = pkgcache._init_logging()
            self.assertIsNotNone(logger)
