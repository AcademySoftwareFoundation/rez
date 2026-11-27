# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Additional unit tests for the filesystem package repository plugin.
"""
import os
import sys
import time
import unittest
import unittest.mock

from rez.config import config
from rez.exceptions import (
    ConfigurationError,
    PackageMetadataError,
    PackageRepositoryError,
    ResourceError,
    RezSystemError,
)
from rez.packages import create_package
from rez.tests.util import TempdirMixin, TestBase
from rez.utils.filesystem import canonical_path
from rez.utils.logging_ import get_debug_printer
from rez.utils.resources import ResourceHandle, ResourcePool
from rez.version import Version
from rezplugins.package_repository import filesystem


class _FileSystemRepoTestBase(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        TempdirMixin.setUpClass()
        cls.settings = {}

    @classmethod
    def tearDownClass(cls):
        TempdirMixin.tearDownClass()
        super().tearDownClass()

    def _make_repo(self, path=None, disable_memcache=True, disable_pkg_ignore=False):
        if path is None:
            path = os.path.join(self.root, "repo")
            os.makedirs(path, exist_ok=True)
        pool = ResourcePool(cache_size=None)
        return filesystem.FileSystemPackageRepository(
            path,
            pool,
            disable_memcache=disable_memcache,
            disable_pkg_ignore=disable_pkg_ignore,
        )

    def _write_file(self, relpath, content, base=None):
        root = base or os.path.join(self.root, "repo")
        fullpath = os.path.join(root, relpath)
        os.makedirs(os.path.dirname(fullpath), exist_ok=True)
        with open(fullpath, "w") as f:
            f.write(content)
        return fullpath


class TestFormatVersionAndResources(_FileSystemRepoTestBase):
    def test_check_format_version_non_int_and_newer(self):
        # Non-integer format_version is silently ignored
        data = {"format_version": "not-an-int"}
        filesystem.check_format_version("pkg.py", data)
        self.assertNotIn("format_version", data)

        # Newer format_version emits a warning
        newer_ver = filesystem.format_version + 5
        data2 = {"format_version": newer_ver}
        with self.assertLogs("rez.utils.logging_", level="WARNING") as cm:
            filesystem.check_format_version("pkg.py", data2)
        log_out = "\n".join(cm.output)
        self.assertIn("pkg.py", log_out)
        self.assertIn(str(newer_ver), log_out)

    def test_family_uri_and_last_release_time(self):
        repo_path = os.path.join(self.root, "repo_fam")
        self._write_file(
            "foo/1.0/package.py",
            "name = 'foo'\nversion = '1.0'\n",
            base=repo_path,
        )
        repo = self._make_repo(repo_path)
        fam = repo.get_package_family("foo")
        self.assertEqual(fam._uri(), fam.path)
        self.assertGreater(repo.get_last_release_time(fam), 0)

        # Missing family directory returns 0
        missing_fam = repo.get_resource(
            filesystem.FileSystemPackageFamilyResource.key,
            location=repo.location,
            name="missing_pkg",
        )
        self.assertEqual(missing_fam.get_last_release_time(), 0)

    def test_package_state_handle_and_missing_file(self):
        repo_path = os.path.join(self.root, "repo_pkg")
        self._write_file(
            "bar/1.0/package.py",
            "name = 'bar'\nversion = '1.0'\nvariants = [['a']]\n",
            base=repo_path,
        )
        repo = self._make_repo(repo_path)
        pkg = repo.get_package("bar", Version("1.0"))
        self.assertIsNotNone(pkg.state_handle)
        variant = next(repo.iter_variants(pkg))
        self.assertEqual(repo.get_variant_state_handle(variant), pkg.state_handle)

        # Resource without a definition file on disk
        ghost_pkg = repo.get_resource(
            filesystem.FileSystemPackageResource.key,
            location=repo.location,
            name="bar",
            version="9.9",
        )
        self.assertIsNone(ghost_pkg.state_handle)
        with self.assertRaises(filesystem.PackageDefinitionFileMissing):
            ghost_pkg._load()

    def test_iter_packages_unversioned_and_check_pkg_def_files(self):
        repo_path = os.path.join(self.root, "repo_unver")
        self._write_file(
            "unver/package.py",
            "name = 'unver'\n",
            base=repo_path,
        )
        self._write_file(
            "verpkg/1.0/package.py",
            "name = 'verpkg'\nversion = '1.0'\n",
            base=repo_path,
        )
        os.makedirs(os.path.join(repo_path, "verpkg", "2.0"), exist_ok=True)
        os.makedirs(os.path.join(repo_path, "verpkg", ".hidden"), exist_ok=True)

        self.update_settings({"allow_unversioned_packages": True})
        orig_check = config.plugins.package_repository.filesystem.check_package_definition_files
        config.override(
            "plugins.package_repository.filesystem.check_package_definition_files",
            True,
        )
        try:
            repo = self._make_repo(repo_path)
            unver_fam = repo.get_package_family("unver")
            unver_pkgs = list(repo.iter_packages(unver_fam))
            self.assertEqual(len(unver_pkgs), 1)
            self.assertEqual(str(unver_pkgs[0].version), "")

            ver_fam = repo.get_package_family("verpkg")
            ver_pkgs = list(repo.iter_packages(ver_fam))
            self.assertEqual([str(p.version) for p in ver_pkgs], ["1.0"])

            # Defensive check in iter_packages when _get_version_dirs returns an invalid dir
            repo.clear_caches()
            with unittest.mock.patch.object(
                repo, "_get_version_dirs", return_value=["1.0", "2.0"]
            ):
                ver_pkgs2 = list(repo.iter_packages(ver_fam))
                self.assertEqual([str(p.version) for p in ver_pkgs2], ["1.0"])
        finally:
            config.override(
                "plugins.package_repository.filesystem.check_package_definition_files",
                orig_check,
            )


class TestOldFormatsAndChangelog(_FileSystemRepoTestBase):
    def test_load_old_format_release_yaml_and_changelog_truncation(self):
        repo_path = os.path.join(self.root, "repo_old_yaml")
        self._write_file(
            "oldpkg/1.0/package.yaml",
            "name: oldpkg\nversion: '1.0'\n",
            base=repo_path,
        )
        self._write_file(
            "oldpkg/1.0/release.yaml",
            "timestamp: 123456\nchangelog:\n- line one\n- line two\n- line three\n",
            base=repo_path,
        )

        self.update_settings({"max_package_changelog_chars": 10})
        repo = self._make_repo(repo_path)
        pkg = repo.get_package("oldpkg", Version("1.0"))
        data = pkg._load()
        self.assertEqual(data["timestamp"], 123456)
        self.assertTrue(data["changelog"].endswith("..."))
        self.assertEqual(len(data["changelog"]), 13)

        # max_package_changelog_chars == 0 leaves changelog untouched
        self.update_settings({"max_package_changelog_chars": 0})
        repo2 = self._make_repo(repo_path)
        pkg2 = repo2.get_package("oldpkg", Version("1.0"))
        data2 = pkg2._load()
        self.assertEqual(data2["changelog"], ["line one", "line two", "line three"])

    def test_load_old_format_rez1_metadata_and_bad_release_time(self):
        repo_path = os.path.join(self.root, "repo_rez1")
        self._write_file(
            "rez1pkg/1.0/package.yaml",
            "name: rez1pkg\nversion: '1.0'\n",
            base=repo_path,
        )
        self._write_file(
            "rez1pkg/1.0/.metadata/changelog.txt",
            "a very long changelog entry for rez 1",
            base=repo_path,
        )
        self._write_file(
            "rez1pkg/1.0/.metadata/release_time.txt",
            "789012\n",
            base=repo_path,
        )

        self.update_settings({"max_package_changelog_chars": 8})
        repo = self._make_repo(repo_path)
        pkg = repo.get_package("rez1pkg", Version("1.0"))
        data = pkg._load()
        self.assertEqual(data["timestamp"], 789012)
        self.assertEqual(data["changelog"], "a very l...")

        # Invalid release_time.txt is ignored without raising
        self._write_file(
            "rez1pkg/2.0/package.yaml",
            "name: rez1pkg\nversion: '2.0'\n",
            base=repo_path,
        )
        self._write_file(
            "rez1pkg/2.0/.metadata/release_time.txt",
            "not-a-timestamp\n",
            base=repo_path,
        )
        repo.clear_caches()
        pkg2 = repo.get_package("rez1pkg", Version("2.0"))
        data2 = pkg2._load()
        self.assertNotIn("timestamp", data2)


class TestCombinedPackages(_FileSystemRepoTestBase):
    def test_combined_family_and_package_methods(self):
        repo_path = os.path.join(self.root, "repo_comb")
        comb_file = self._write_file(
            "combpkg.yaml",
            (
                "name: combpkg\n"
                "versions:\n"
                "- '1.0'\n"
                "- '2.0'\n"
                "variants:\n"
                "- ['python-3']\n"
                "- ['python-2']\n"
            ),
            base=repo_path,
        )
        repo = self._make_repo(repo_path)
        fam = repo.get_package_family("combpkg")
        self.assertEqual(fam._uri(), canonical_path(comb_file))
        self.assertGreater(fam.get_last_release_time(), 0)

        pkg = repo.get_package("combpkg", Version("1.0"))
        self.assertGreater(pkg.state_handle, 0)
        variants = list(pkg.iter_variants())
        self.assertEqual(len(variants), 2)

        # Missing combined file returns 0 for get_last_release_time
        os.remove(comb_file)
        self.assertEqual(fam.get_last_release_time(), 0)

    def test_combined_family_case_mismatch_on_case_insensitive_fs(self):
        repo_path = os.path.join(self.root, "repo_comb_case")
        self._write_file(
            "mycomb.yaml",
            "name: mycomb\nversions:\n- '1.0'\n",
            base=repo_path,
        )
        repo = self._make_repo(repo_path)

        mock_plat = unittest.mock.Mock(spec=["has_case_sensitive_filesystem", "name"])
        mock_plat.has_case_sensitive_filesystem = False
        mock_plat.name = "windows"

        # Simulate case-insensitive filesystem finding mycomb.yaml when asked for MyComb
        with unittest.mock.patch.object(filesystem, "platform_", mock_plat):
            with unittest.mock.patch.object(
                repo,
                "get_file",
                return_value=(
                    os.path.join(repo.location, "mycomb.yaml"),
                    filesystem.FileFormat.yaml,
                ),
            ):
                self.assertIsNone(repo._get_family("MyComb"))


class TestURILookups(_FileSystemRepoTestBase):
    def test_get_package_from_uri_variants(self):
        repo_path = os.path.join(self.root, "repo_uri")
        unver_file = self._write_file(
            "unver/package.py",
            "name = 'unver'\n",
            base=repo_path,
        )
        self._write_file(
            "verpkg/1.0/package.py",
            "name = 'verpkg'\nversion = '1.0'\nvariants = [['a']]\n",
            base=repo_path,
        )
        self._write_file(
            "nullvar/1.0/package.py",
            "name = 'nullvar'\nversion = '1.0'\n",
            base=repo_path,
        )

        self.update_settings({"allow_unversioned_packages": True})
        repo = self._make_repo(repo_path)

        # Unversioned package URI (2 parts, no '<')
        pkg_unver = repo.get_package_from_uri(canonical_path(unver_file))
        self.assertIsNotNone(pkg_unver)
        self.assertEqual(pkg_unver.name, "unver")

        # Combined-style 2-part URI with '<...>'
        combined_uri = os.path.join(repo.location, "verpkg", "<1.0>")
        pkg_comb = repo.get_package_from_uri(combined_uri)
        self.assertIsNotNone(pkg_comb)
        self.assertEqual(str(pkg_comb.version), "1.0")

        # Unexpected path depth returns None
        self.assertIsNone(
            repo.get_package_from_uri(os.path.join(repo.location, "verpkg"))
        )
        self.assertIsNone(
            repo.get_package_from_uri(
                os.path.join(repo.location, "verpkg", "1.0", "extra", "package.py")
            )
        )

        # get_variant_from_uri edge cases
        ver_file = os.path.join(repo.location, "verpkg", "1.0", "package.py")
        null_file = os.path.join(repo.location, "nullvar", "1.0", "package.py")
        self.assertIsNone(repo.get_variant_from_uri(ver_file))
        self.assertIsNotNone(repo.get_variant_from_uri(null_file + "[]"))
        self.assertIsNone(repo.get_variant_from_uri(ver_file + "[nonint]"))
        self.assertIsNone(repo.get_variant_from_uri(ver_file + "[99]"))

    @unittest.expectedFailure
    def test_get_package_from_combined_uri_bug(self):
        # Bug in src/rezplugins/package_repository/filesystem.py:361,620-623:
        # FileSystemCombinedPackageResource._uri() produces a 1-part relative
        # URI '<name>.<ext><ver>', while get_package_from_uri() only checks
        # '<' in part when len(parts) == 2.
        repo_path = os.path.join(self.root, "repo_comb_uri")
        self._write_file(
            "comb.yaml",
            "name: comb\nversions:\n- '1.0'\n",
            base=repo_path,
        )
        repo = self._make_repo(repo_path)
        combined_pkg = repo.get_package("comb", Version("1.0"))
        self.assertIsNotNone(combined_pkg)
        pkg = repo.get_package_from_uri(combined_pkg.uri)
        self.assertIsNotNone(pkg)


class TestIgnoreAndRemove(_FileSystemRepoTestBase):
    def test_remove_package_missing_and_existing(self):
        repo_path = os.path.join(self.root, "repo_rm")
        self._write_file(
            "foo/1.0/package.py",
            "name: foo\nversion: '1.0'\n",
            base=repo_path,
        )
        repo = self._make_repo(repo_path)
        self.assertFalse(repo.remove_package("missing", Version("1.0")))
        self.assertTrue(repo.remove_package("foo", Version("1.0")))
        self.assertIsNone(repo.get_package("foo", Version("1.0")))

    def test_remove_ignored_since_dry_run_verbose_and_age_filter(self):
        repo_path = os.path.join(self.root, "repo_rm_ign")
        self._write_file(
            "comb.yaml",
            "name: comb\nversions:\n- '1.0'\n",
            base=repo_path,
        )
        self._write_file(
            "pkg/1.0/package.py",
            "name = 'pkg'\nversion = '1.0'\n",
            base=repo_path,
        )
        repo = self._make_repo(repo_path)
        self.assertEqual(repo.ignore_package("pkg", Version("1.0")), 1)

        # Age < days skips removal
        self.assertEqual(repo.remove_ignored_since(days=10), 0)

        # dry_run=True and verbose=True logs and counts without deleting
        with self.assertLogs("rez.utils.logging_", level="INFO") as cm:
            count = repo.remove_ignored_since(days=0, dry_run=True, verbose=True)
        self.assertEqual(count, 1)
        self.assertIn("Would remove pkg-1.0", "\n".join(cm.output))
        self.assertTrue(
            os.path.isdir(os.path.join(repo.location, "pkg", "1.0"))
        )


class TestHandlesAndLocking(_FileSystemRepoTestBase):
    def test_get_resource_from_handle_errors(self):
        repo_path = os.path.join(self.root, "repo_handles")
        other_path = os.path.join(self.root, "repo_other")
        os.makedirs(repo_path, exist_ok=True)
        os.makedirs(other_path, exist_ok=True)
        repo = self._make_repo(repo_path)

        # Wrong repository_type
        bad_type_handle = ResourceHandle(
            filesystem.FileSystemPackageFamilyResource.key,
            {"repository_type": "memory", "location": repo.location, "name": "foo"},
        )
        with self.assertRaises(ResourceError):
            repo.get_resource_from_handle(bad_type_handle)

        # Non-existent location
        missing_loc_handle = ResourceHandle(
            filesystem.FileSystemPackageFamilyResource.key,
            {
                "repository_type": "filesystem",
                "location": os.path.join(self.root, "does_not_exist"),
                "name": "foo",
            },
        )
        with self.assertRaises(ResourceError):
            repo.get_resource_from_handle(missing_loc_handle)

        # Different existing location (samefile returns False)
        other_loc_handle = ResourceHandle(
            filesystem.FileSystemPackageFamilyResource.key,
            {"repository_type": "filesystem", "location": other_path, "name": "foo"},
        )
        with self.assertRaises(ResourceError):
            repo.get_resource_from_handle(other_loc_handle)

        # os.path.samefile raises OSError
        with unittest.mock.patch("os.path.samefile", side_effect=OSError("boom")):
            with self.assertRaises(ResourceError):
                repo.get_resource_from_handle(other_loc_handle)

    def test_file_lock_dir_validation_and_lock_types(self):
        repo_path = os.path.join(self.root, "repo_locks")
        os.makedirs(repo_path, exist_ok=True)

        # Invalid file_lock_dir (absolute or nested)
        orig_lock_dir = config.plugins.package_repository.filesystem.file_lock_dir
        orig_lock_type = config.plugins.package_repository.filesystem.file_lock_type
        config.override("plugins.package_repository.filesystem.file_lock_dir", "/abs/dir")
        try:
            repo = self._make_repo(repo_path)
            with self.assertRaises(ConfigurationError):
                _ = repo.file_lock_dir
        finally:
            config.override("plugins.package_repository.filesystem.file_lock_dir", orig_lock_dir)

        # Valid relative file_lock_dir that doesn't exist yet -> None
        config.override("plugins.package_repository.filesystem.file_lock_dir", ".locks")
        try:
            repo = self._make_repo(repo_path)
            self.assertIsNone(repo.file_lock_dir)

            # Once created, file_lock_dir returns ".locks" and _get_family_dirs skips it
            os.makedirs(os.path.join(repo_path, ".locks"), exist_ok=True)
            repo2 = self._make_repo(repo_path)
            self.assertEqual(repo2.file_lock_dir, ".locks")
            self.assertEqual(repo2._get_family_dirs(), [])

            for lock_type in ("mkdir", "link", "symlink"):
                if lock_type == "symlink":
                    probe_link = os.path.join(self.root, "_symlink_probe")
                    try:
                        os.symlink(repo_path, probe_link)
                    except OSError:
                        if sys.platform == "win32":
                            continue
                        raise
                    finally:
                        if os.path.islink(probe_link):
                            os.unlink(probe_link)
                config.override(
                    "plugins.package_repository.filesystem.file_lock_type", lock_type
                )
                repo_lt = self._make_repo(repo_path)
                with repo_lt._lock_package("mypkg", "1.0"):
                    pass
        finally:
            config.override("plugins.package_repository.filesystem.file_lock_type", orig_lock_type)
            config.override("plugins.package_repository.filesystem.file_lock_dir", orig_lock_dir)

        # Missing lockfile directory raises PackageRepositoryError
        missing_repo = self._make_repo(os.path.join(self.root, "nonexistent_repo"))
        with self.assertRaises(PackageRepositoryError):
            with missing_repo._lock_package("mypkg", "1.0"):
                pass

        # NotLocked on release is silently ignored
        from rez.vendor.lockfile import NotLocked

        repo3 = self._make_repo(repo_path)
        with unittest.mock.patch(
            "rez.vendor.lockfile.LockFile.release", side_effect=NotLocked("not locked")
        ):
            with repo3._lock_package("mypkg", "1.0"):
                pass


class TestInstallVariantAndBuildTagfiles(_FileSystemRepoTestBase):
    def test_pre_variant_install_unversioned_and_stale_tagfiles(self):
        repo_path = os.path.join(self.root, "repo_tags")
        self._write_file(
            "pkg/1.0/package.py",
            "name = 'pkg'\nversion = '1.0'\n",
            base=repo_path,
        )
        repo = self._make_repo(repo_path)

        # Unversioned variant returns early in pre_variant_install
        unver_pkg = create_package("unver", data={})
        unver_var = next(unver_pkg.iter_variants()).resource
        repo.pre_variant_install(unver_var)
        self.assertFalse(os.path.exists(os.path.join(repo.location, "unver")))

        # Stale build tagfiles: valid pkg dir -> removed; missing dir & old -> removed; recent -> kept
        fam_dir = os.path.join(repo.location, "pkg")
        valid_tag = os.path.join(fam_dir, ".building1.0")
        old_tag = os.path.join(fam_dir, ".building2.0")
        recent_tag = os.path.join(fam_dir, ".building3.0")
        for tag in (valid_tag, old_tag, recent_tag):
            with open(tag, "w"):
                pass

        old_time = time.time() - 7200
        os.utime(old_tag, (old_time, old_time))

        # Also exercises _get_version_dirs skipping .building3.0 when 3.0 dir doesn't exist
        self.assertEqual(repo._get_version_dirs(fam_dir), ["1.0"])

        pkg_var = next(create_package("pkg", data={"version": "1.0"}).iter_variants()).resource
        repo.on_variant_install_cancelled(pkg_var)
        self.assertFalse(os.path.exists(valid_tag))
        self.assertFalse(os.path.exists(old_tag))
        self.assertTrue(os.path.exists(recent_tag))

    def test_install_variant_error_paths(self):
        repo_path = os.path.join(self.root, "repo_err")
        self._write_file(
            "comb.yaml",
            "name: comb\nversions:\n- '1.0'\n",
            base=repo_path,
        )
        repo = self._make_repo(repo_path)

        pkg = create_package("foo", data={"version": "1.0"})
        var = next(pkg.iter_variants()).resource

        # Removing 'name' or 'version' via overrides is forbidden
        with self.assertRaises(PackageRepositoryError):
            repo.install_variant(var, overrides={"name": repo.remove})
        with self.assertRaises(PackageRepositoryError):
            repo.install_variant(var, overrides={"version": repo.remove})

        # makedirs OSError wraps in PackageRepositoryError
        with unittest.mock.patch("os.makedirs", side_effect=OSError("perm denied")):
            with self.assertRaises(PackageRepositoryError):
                repo.install_variant(var)

        # Installing into combined-style package raises NotImplementedError
        with self.assertRaises(NotImplementedError):
            repo.install_variant(var, overrides={"name": "comb"})

        # Unversioned package disallowed when allow_unversioned_packages is False
        self.update_settings({"allow_unversioned_packages": False})
        unver = next(create_package("unver", data={}).iter_variants()).resource
        with self.assertRaises(PackageMetadataError):
            repo.install_variant(unver)

    def test_install_variant_mismatches_and_debug_and_overrides(self):
        repo_path = os.path.join(self.root, "repo_inst")
        os.makedirs(os.path.join(repo_path, "foo", "1.0"), exist_ok=True)
        repo = self._make_repo(repo_path)

        # Installing when 1.0/ dir exists without package.py hits PackageDefinitionFileMissing break
        pkg_v1 = create_package(
            "foo",
            data={
                "version": "1.0",
                "uuid": "uuid-1",
                "config": {"quiet": True},
            },
        )
        var_v1 = next(pkg_v1.iter_variants()).resource
        installed = repo.install_variant(
            var_v1,
            overrides={"description": "hello", "obsolete": repo.remove},
        )
        self.assertEqual(installed.parent.description, "hello")

        # UUID mismatch raises ResourceError
        pkg_bad_uuid = create_package(
            "foo", data={"version": "1.0", "uuid": "uuid-2"}
        )
        with self.assertRaises(ResourceError):
            repo.install_variant(next(pkg_bad_uuid.iter_variants()).resource)

        # Variant with index into package without variants raises ResourceError
        pkg_with_var = create_package(
            "foo",
            data={"version": "1.0", "uuid": "uuid-1", "variants": [["a"]]},
        )
        with self.assertRaises(ResourceError):
            repo.install_variant(next(pkg_with_var.iter_variants()).resource)

        # Variant without index into package with variants raises ResourceError
        pkg_var2 = create_package(
            "bar", data={"version": "1.0", "variants": [["a"]]}
        )
        repo.install_variant(next(pkg_var2.iter_variants()).resource)
        pkg_novar = create_package("bar", data={"version": "1.0"})
        with self.assertRaises(ResourceError):
            repo.install_variant(next(pkg_novar.iter_variants()).resource)

        # Debug printing (matching and changed) + overrides on existing package
        pkg_bar_changed = create_package(
            "bar",
            data={"version": "1.0", "variants": [["b"]], "authors": ["alice"]},
        )
        with unittest.mock.patch.object(
            filesystem, "debug_print", get_debug_printer(True)
        ):
            # Matching package data; schema keys in validated_data() (like
            # 'help': None) are preserved on existing packages, while new
            # non-schema override keys are written.
            v = repo.install_variant(
                next(pkg_var2.iter_variants()).resource,
                overrides={
                    "help": "https://example.com",
                    "custom_meta": "https://example.com",
                },
            )
            self.assertIsNone(v.parent.help)
            self.assertEqual(
                v.parent._load()["custom_meta"], "https://example.com"
            )
            # Changed package data (authors added)
            v2 = repo.install_variant(next(pkg_bar_changed.iter_variants()).resource)
            self.assertEqual(v2.parent.authors, ["alice"])
            self.assertEqual(len(v2.parent.variants), 2)

        # Cleanup exceptions during .building removal and stale tagfile deletion
        pkg_baz = create_package("baz", data={"version": "1.0"})
        var_baz = next(pkg_baz.iter_variants()).resource
        repo.pre_variant_install(var_baz)
        with unittest.mock.patch("os.remove", side_effect=OSError("busy")):
            with unittest.mock.patch.object(
                repo,
                "_delete_stale_build_tagfiles",
                side_effect=OSError("busy"),
            ):
                v_baz = repo.install_variant(var_baz)
        self.assertEqual(v_baz.name, "baz")

        # Internal failure if installed variant cannot be reloaded
        pkg_qux = create_package("qux", data={"version": "1.0"})
        with unittest.mock.patch.object(
            repo, "iter_variants", return_value=iter([])
        ):
            with self.assertRaises(RezSystemError):
                repo.install_variant(next(pkg_qux.iter_variants()).resource)


class TestMemcacheKeyMethods(_FileSystemRepoTestBase):
    def test_memcache_key_methods(self):
        repo_path = os.path.join(self.root, "repo_mc")
        self._write_file(
            "mc/1.0/package.py",
            "name = 'mc'\nversion = '1.0'\n",
            base=repo_path,
        )
        repo = self._make_repo(repo_path, disable_memcache=False)
        key1 = repo._get_family_dirs__key()
        self.assertIn(repr(repo.location), key1)
        key2 = repo._get_version_dirs__key(os.path.join(repo.location, "mc"))
        self.assertIn("mc", key2)

        missing_repo = self._make_repo(
            os.path.join(self.root, "repo_mc_missing"), disable_memcache=False
        )
        key3 = missing_repo._get_family_dirs__key()
        self.assertIn("listdir", key3)
