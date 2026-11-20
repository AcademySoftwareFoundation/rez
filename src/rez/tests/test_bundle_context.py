# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Unit tests for rez.bundle_context.
"""
from __future__ import annotations

import os
import stat
import sys
from types import SimpleNamespace
from unittest import mock

from rez.bundle_context import _ContextBundler, bundle_context
from rez.exceptions import ContextBundleError, PackageCopyError
from rez.package_maker import make_package
from rez.resolved_context import ResolvedContext
from rez.tests.util import TempdirMixin, TestBase
from rez.utils.filesystem import is_subdirectory
from rez.utils.yaml import load_yaml


_EXE_EXT = ".bat" if sys.platform == "win32" else ""


def _write_file(path: str, content: str = "", executable: bool = False) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)
    if executable:
        st = os.stat(path)
        os.chmod(path, st.st_mode | stat.S_IXUSR)


class TestBundleContext(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        TempdirMixin.setUpClass()

        cls.packages_path = os.path.join(cls.root, "packages")
        os.makedirs(cls.packages_path, exist_ok=True)

        cls.settings = dict(
            packages_path=[cls.packages_path],
            package_filter=None,
            resolve_caching=False,
            implicit_packages=[],
        )

    @classmethod
    def tearDownClass(cls) -> None:
        TempdirMixin.tearDownClass()
        super().tearDownClass()

    def setup_once(self) -> None:
        def make_pkg_a_root(variant, path):
            _write_file(os.path.join(path, "bin", "mytool" + _EXE_EXT), "#!/bin/sh\n", executable=True)
            _write_file(os.path.join(path, "lib", "libfoo.so"), "so")
            _write_file(os.path.join(path, "lib", "libbar.so.1"), "so.1")
            _write_file(os.path.join(path, "lib", "libbaz.so-2"), "so-2")
            try:
                os.symlink("libfoo.so", os.path.join(path, "lib", "liblink.so"))
            except OSError:
                pass
            _write_file(os.path.join(path, "share", "readme.txt"), "readme")

        with make_package("pkg_a", self.packages_path, make_root=make_pkg_a_root) as pkg:
            pkg.version = "1.0.0"
            pkg.relocatable = True

        def make_pkg_b_root(variant, path):
            _write_file(os.path.join(path, "bin", "app" + _EXE_EXT), "#!/bin/sh\n", executable=True)

        with make_package("pkg_b", self.packages_path, make_root=make_pkg_b_root) as pkg:
            pkg.version = "1.0.0"
            pkg.requires = ["pkg_a-1"]
            pkg.relocatable = True

        def make_plain_root(variant, path):
            _write_file(os.path.join(path, "share", "data.txt"), "data")

        with make_package("plain_pkg", self.packages_path, make_root=make_plain_root) as pkg:
            pkg.version = "1.0.0"
            pkg.relocatable = True

        with make_package("nonreloc", self.packages_path, make_root=make_plain_root) as pkg:
            pkg.version = "1.0.0"
            pkg.relocatable = False

        self._bundle_counter = 0

    def _next_bundle_dir(self, name: str = "bundle") -> str:
        self._bundle_counter += 1
        return os.path.join(self.root, "%s_%d" % (name, self._bundle_counter))

    def test_bundle_basic(self) -> None:
        dest_dir = self._next_bundle_dir("basic")
        ctx = ResolvedContext(["pkg_b"])

        bundle_context(ctx, dest_dir)

        self.assertTrue(os.path.isfile(os.path.join(dest_dir, "context.rxt")))
        self.assertTrue(os.path.isfile(os.path.join(dest_dir, "bundle.yaml")))
        settings_path = os.path.join(dest_dir, "packages", "settings.yaml")
        self.assertTrue(os.path.isfile(settings_path))

        settings_data = load_yaml(settings_path)
        self.assertEqual(settings_data, {"disable_memcached": True})

        bundle_meta = load_yaml(os.path.join(dest_dir, "bundle.yaml"))
        self.assertIn("logs", bundle_meta)
        self.assertTrue(any(entry.startswith("INFO: Copied ") for entry in bundle_meta["logs"]))

        reloaded = ResolvedContext.load(os.path.join(dest_dir, "context.rxt"))
        self.assertEqual(len(reloaded.resolved_packages), 2)
        for variant in reloaded.resolved_packages:
            self.assertTrue(is_subdirectory(variant.root, dest_dir))

    def test_bundle_dest_exists_raises(self) -> None:
        dest_dir = self._next_bundle_dir("exists")
        os.makedirs(dest_dir)
        ctx = ResolvedContext(["plain_pkg"])

        with self.assertRaises(ContextBundleError):
            bundle_context(ctx, dest_dir)

    def test_bundle_quiet_overrides_verbose(self) -> None:
        dest_dir = self._next_bundle_dir("quiet")
        ctx = ResolvedContext(["plain_pkg"])

        with mock.patch("rez.bundle_context.print_info") as mock_info:
            bundle_context(ctx, dest_dir, quiet=True, verbose=True)

        mock_info.assert_not_called()

    def test_bundle_verbose_with_load_path(self) -> None:
        rxt_path = os.path.join(self.root, "saved_ctx.rxt")
        ctx = ResolvedContext(["plain_pkg"])
        ctx.save(rxt_path)
        loaded_ctx = ResolvedContext.load(rxt_path)

        dest_dir = self._next_bundle_dir("verbose")
        with mock.patch("rez.bundle_context.print_info") as mock_info:
            bundle_context(loaded_ctx, dest_dir, quiet=False, verbose=True)

        self.assertTrue(mock_info.called)
        first_call_args = mock_info.call_args_list[0][0]
        self.assertEqual(first_call_args[1], loaded_ctx.load_path)
        self.assertTrue(
            any("Bundled context written" in call[0][0] for call in mock_info.call_args_list)
        )

    def test_bundle_non_relocatable_raises(self) -> None:
        dest_dir = self._next_bundle_dir("nonreloc_err")
        ctx = ResolvedContext(["nonreloc"])

        with self.assertRaises(PackageCopyError):
            bundle_context(ctx, dest_dir, skip_non_relocatable=False, force=False, quiet=True)

    def test_bundle_skip_non_relocatable(self) -> None:
        dest_dir = self._next_bundle_dir("skip_nonreloc")
        ctx = ResolvedContext(["plain_pkg", "nonreloc"])

        with mock.patch.object(ctx, "retargeted", wraps=ctx.retargeted) as mock_retargeted:
            with mock.patch("rez.bundle_context.print_warning") as mock_warn:
                bundle_context(ctx, dest_dir, skip_non_relocatable=True, quiet=True)

        mock_retargeted.assert_called_once_with(
            package_paths=[os.path.join(dest_dir, "packages")],
            package_names=["plain_pkg"],
            skip_missing=True,
        )
        mock_warn.assert_called_once()
        self.assertIn("Skipped bundling of non-relocatable package", mock_warn.call_args[0][0])

        bundle_meta = load_yaml(os.path.join(dest_dir, "bundle.yaml"))
        self.assertTrue(
            any(
                entry.startswith("WARNING: Skipped bundling of non-relocatable package nonreloc-1.0.0")
                for entry in bundle_meta["logs"]
            )
        )

        reloaded = ResolvedContext.load(os.path.join(dest_dir, "context.rxt"))
        by_name = {v.name: v for v in reloaded.resolved_packages}
        self.assertTrue(is_subdirectory(by_name["plain_pkg"].root, dest_dir))
        self.assertFalse(is_subdirectory(by_name["nonreloc"].root, dest_dir))

    def test_bundle_force_overrides_skip_non_relocatable(self) -> None:
        dest_dir = self._next_bundle_dir("force_nonreloc")
        ctx = ResolvedContext(["nonreloc"])

        bundle_context(ctx, dest_dir, force=True, skip_non_relocatable=True, quiet=True)

        reloaded = ResolvedContext.load(os.path.join(dest_dir, "context.rxt"))
        self.assertTrue(is_subdirectory(reloaded.resolved_packages[0].root, dest_dir))

    def test_patch_libs_non_linux_skips(self) -> None:
        ctx = ResolvedContext(["plain_pkg"])
        for plat_name in ("osx", "windows"):
            with self.subTest(platform=plat_name):
                dest_dir = self._next_bundle_dir("plat_%s" % plat_name)
                with mock.patch("rez.bundle_context.platform_", SimpleNamespace(name=plat_name)):
                    with mock.patch.object(_ContextBundler, "_patch_libs_linux") as mock_linux:
                        bundle_context(ctx, dest_dir, patch_libs=True, quiet=True)
                mock_linux.assert_not_called()

    def test_patch_libs_linux_no_elfs(self) -> None:
        dest_dir = self._next_bundle_dir("no_elfs")
        ctx = ResolvedContext(["plain_pkg"])

        with mock.patch("rez.bundle_context.platform_", SimpleNamespace(name="linux")):
            bundle_context(ctx, dest_dir, patch_libs=True, quiet=True)

        bundle_meta = load_yaml(os.path.join(dest_dir, "bundle.yaml"))
        self.assertIn("INFO: No elfs found, thus no patching performed", bundle_meta["logs"])

    def test_patch_libs_linux_missing_readelf(self) -> None:
        dest_dir = self._next_bundle_dir("no_readelf")
        ctx = ResolvedContext(["pkg_a"])

        with mock.patch("rez.bundle_context.platform_", SimpleNamespace(name="linux")):
            with mock.patch("rez.bundle_context.which", return_value=None):
                with mock.patch("rez.bundle_context.print_warning") as mock_warn:
                    with mock.patch("rez.utils.elf.get_rpaths") as mock_get_rpaths:
                        bundle_context(ctx, dest_dir, patch_libs=True, quiet=True)

        mock_get_rpaths.assert_not_called()
        mock_warn.assert_called_once()
        self.assertIn("cannot find 'readelf' utility", mock_warn.call_args[0][0])

    def test_patch_libs_linux_get_rpaths_errors_and_empty(self) -> None:
        dest_dir = self._next_bundle_dir("rpaths_err")
        ctx = ResolvedContext(["pkg_a"])

        def fake_get_rpaths(elf):
            if elf.endswith("mytool" + _EXE_EXT):
                raise RuntimeError("Not an ELF file")
            if elf.endswith("libfoo.so"):
                raise RuntimeError("Failed to read file header")
            if elf.endswith("libbar.so.1"):
                raise RuntimeError("unexpected readelf error")
            return []

        def fake_which(cmd):
            return "/usr/bin/" + cmd

        with mock.patch("rez.bundle_context.platform_", SimpleNamespace(name="linux")):
            with mock.patch("rez.bundle_context.which", side_effect=fake_which):
                with mock.patch("rez.utils.elf.get_rpaths", side_effect=fake_get_rpaths):
                    with mock.patch("rez.bundle_context.print_warning") as mock_warn:
                        bundle_context(ctx, dest_dir, patch_libs=True, quiet=True)

        mock_warn.assert_called_once_with("unexpected readelf error")
        bundle_meta = load_yaml(os.path.join(dest_dir, "bundle.yaml"))
        self.assertIn("WARNING: unexpected readelf error", bundle_meta["logs"])

    def test_patch_libs_linux_remapping_and_unchanged(self) -> None:
        dest_dir = self._next_bundle_dir("remap")
        ctx = ResolvedContext(["pkg_b"])
        src_pkg_a_root = next(v.root for v in ctx.resolved_packages if v.name == "pkg_a")
        src_rpath_in_pkg_a = os.path.join(src_pkg_a_root, "lib")

        def fake_get_rpaths(elf):
            if elf.endswith("app" + _EXE_EXT):
                return ["$ORIGIN/../lib", src_rpath_in_pkg_a, "/usr/lib"]
            return ["$ORIGIN", "/usr/lib"]

        def fake_which(cmd):
            return "/usr/bin/" + cmd

        with mock.patch("rez.bundle_context.platform_", SimpleNamespace(name="linux")):
            with mock.patch("rez.bundle_context.which", side_effect=fake_which):
                with mock.patch("rez.utils.elf.get_rpaths", side_effect=fake_get_rpaths):
                    with mock.patch("rez.utils.elf.patch_rpaths") as mock_patch_rpaths:
                        bundle_context(ctx, dest_dir, patch_libs=True, quiet=True)

        mock_patch_rpaths.assert_called_once()
        patched_elf, patched_rpaths = mock_patch_rpaths.call_args[0]
        self.assertTrue(patched_elf.endswith("app" + _EXE_EXT))
        self.assertEqual(patched_rpaths[0], "$ORIGIN/../lib")
        self.assertTrue(patched_rpaths[1].startswith("$ORIGIN" + os.sep))
        self.assertEqual(patched_rpaths[2], "/usr/lib")

        bundle_meta = load_yaml(os.path.join(dest_dir, "bundle.yaml"))
        self.assertTrue(any(entry.startswith("INFO: Remapped rpath ") for entry in bundle_meta["logs"]))
        self.assertTrue(any(entry.startswith("INFO: Patched rpaths in file ") for entry in bundle_meta["logs"]))
        self.assertTrue(any(entry.startswith("INFO: Left rpaths unchanged in ") for entry in bundle_meta["logs"]))

    def test_patch_libs_linux_missing_patchelf(self) -> None:
        dest_dir = self._next_bundle_dir("no_patchelf")
        ctx = ResolvedContext(["pkg_b"])
        src_pkg_a_root = next(v.root for v in ctx.resolved_packages if v.name == "pkg_a")
        src_rpath_in_pkg_a = os.path.join(src_pkg_a_root, "lib")

        def fake_get_rpaths(elf):
            if elf.endswith("app" + _EXE_EXT):
                return [src_rpath_in_pkg_a]
            return []

        def fake_which(cmd):
            return "/usr/bin/readelf" if cmd == "readelf" else None

        with mock.patch("rez.bundle_context.platform_", SimpleNamespace(name="linux")):
            with mock.patch("rez.bundle_context.which", side_effect=fake_which):
                with mock.patch("rez.utils.elf.get_rpaths", side_effect=fake_get_rpaths):
                    with mock.patch("rez.utils.elf.patch_rpaths") as mock_patch_rpaths:
                        with mock.patch("rez.bundle_context.print_warning") as mock_warn:
                            bundle_context(ctx, dest_dir, patch_libs=True, quiet=True)

        mock_patch_rpaths.assert_not_called()
        mock_warn.assert_called_once()
        self.assertIn("cannot find 'patchelf' utility", mock_warn.call_args[0][0])

    def test_patch_libs_linux_patch_rpaths_error(self) -> None:
        dest_dir = self._next_bundle_dir("patchelf_err")
        ctx = ResolvedContext(["pkg_b"])
        src_pkg_a_root = next(v.root for v in ctx.resolved_packages if v.name == "pkg_a")
        src_rpath_in_pkg_a = os.path.join(src_pkg_a_root, "lib")

        def fake_get_rpaths(elf):
            if elf.endswith("app" + _EXE_EXT):
                return [src_rpath_in_pkg_a]
            return []

        def fake_which(cmd):
            return "/usr/bin/" + cmd

        with mock.patch("rez.bundle_context.platform_", SimpleNamespace(name="linux")):
            with mock.patch("rez.bundle_context.which", side_effect=fake_which):
                with mock.patch("rez.utils.elf.get_rpaths", side_effect=fake_get_rpaths):
                    with mock.patch("rez.utils.elf.patch_rpaths", side_effect=RuntimeError("patchelf failed")):
                        with mock.patch("rez.bundle_context.print_warning") as mock_warn:
                            bundle_context(ctx, dest_dir, patch_libs=True, quiet=True)

        mock_warn.assert_called_once_with("patchelf failed")
        bundle_meta = load_yaml(os.path.join(dest_dir, "bundle.yaml"))
        self.assertIn("WARNING: patchelf failed", bundle_meta["logs"])

    def test_find_files_filtering(self) -> None:
        dest_dir = self._next_bundle_dir("find_files")
        ctx = ResolvedContext(["pkg_a"])
        bundler = _ContextBundler(ctx, dest_dir, quiet=True)
        bundler.bundle()

        found = bundler._find_files(executable=True, filename_substrs=(".so", ".so.", ".so-"))
        basenames = sorted(os.path.basename(p) for p in found)
        expected = sorted(["libbar.so.1", "libbaz.so-2", "libfoo.so", "mytool" + _EXE_EXT])
        self.assertEqual(basenames, expected)

        self.assertEqual(bundler._find_files(executable=False, filename_substrs=None), [])
