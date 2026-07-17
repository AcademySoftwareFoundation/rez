# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
unit tests for 'rez.utils.filesystem' module
"""
import os
import os.path
import sys
import tempfile
import unittest
import unittest.mock

from rez.tests.util import TestBase
from rez.tests.util import TempdirMixin
from rez.utils import filesystem
from rez.utils.filesystem import canonical_path, real_path, _windows_realpath
from rez.utils.platform_ import platform_
import unittest.mock


def rmtree_file_not_found_error(path, onerror):
    try:
        raise FileNotFoundError("File not found", path)
    except:
        onerror(None, path, sys.exc_info())


def rmtree_permission_error(path, onerror):
    try:
        raise PermissionError("Permission denied", path)
    except:
        onerror(None, path, sys.exc_info())


class TestFileSystem(TestBase, TempdirMixin):

    def __init__(self, *nargs, **kwargs) -> None:
        super().__init__(*nargs, **kwargs)

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        TempdirMixin.setUpClass()

    @classmethod
    def tearDownClass(cls) -> None:
        super().tearDownClass()
        TempdirMixin.tearDownClass()

    def test_windows_rename_fallback_to_robocopy(self) -> None:
        if platform_.name != 'windows':
            self.skipTest('Robocopy is only available on windows.')
        src = tempfile.mkdtemp(dir=self.root)
        dst = tempfile.mkdtemp(dir=self.root)
        with unittest.mock.patch("os.rename") as mock_rename:
            mock_rename.side_effect = PermissionError("Permission denied")
            filesystem.rename(src, dst)
            self.assertTrue(os.path.exists(dst))
            self.assertFalse(os.path.exists(src))

    def test_windows_robocopy_failed(self) -> None:
        if platform_.name != 'windows':
            self.skipTest('Robocopy is only available on windows.')
        src = tempfile.mkdtemp(dir=self.root)
        dst = tempfile.mkdtemp(dir=self.root)
        with unittest.mock.patch("os.rename") as mock_rename:
            mock_rename.side_effect = PermissionError("Permission denied")
            with unittest.mock.patch("rez.utils.filesystem.Popen") as mock_subprocess:
                mock_subprocess.return_value = unittest.mock.Mock(returncode=9)
                with self.assertRaises(OSError) as err:
                    filesystem.rename(src, dst)
                self.assertEqual(str(err.exception), "Rename {} to {} failed.".format(src, dst))

    def test_rename_folder_with_permission_error_and_no_robocopy(self) -> None:
        src = tempfile.mkdtemp(dir=self.root)
        dst = tempfile.mkdtemp(dir=self.root)
        with unittest.mock.patch("os.rename") as mock_rename:
            mock_rename.side_effect = PermissionError("Permission denied")
            with unittest.mock.patch("rez.utils.filesystem.which") as mock_which:
                mock_which.return_value = False
                with self.assertRaises(PermissionError) as err:
                    filesystem.rename(src, dst)
                self.assertEqual(str(err.exception), "Permission denied")

    def test_rename_folder_with_permission_error_and_src_is_file(self) -> None:
        src = tempfile.mktemp(dir=self.root)
        dst = tempfile.mktemp(dir=self.root)
        with open(src, "w") as file_:
            file_.write("content.")
        with unittest.mock.patch("os.rename") as mock_rename:
            mock_rename.side_effect = PermissionError("Permission denied")
            with self.assertRaises(PermissionError) as err:
                filesystem.rename(src, dst)
            self.assertEqual(str(err.exception), "Permission denied")
        self.assertFalse(os.path.exists(dst))
        self.assertTrue(os.path.exists(src))

    def test_rename_file(self) -> None:
        src = tempfile.mktemp(dir=self.root)
        dst = tempfile.mktemp(dir=self.root)
        with open(src, "w") as file_:
            file_.write("content.")
        filesystem.rename(src, dst)
        self.assertTrue(os.path.exists(dst))
        self.assertFalse(os.path.exists(src))

    def test_safe_rmtree_with_file_not_found(self) -> None:
        with unittest.mock.patch("shutil.rmtree", wraps=rmtree_file_not_found_error):
            with self.assertRaises(FileNotFoundError):
                filesystem.safe_rmtree("path")

    def test_safe_rmtree_with_other_error(self) -> None:
        with unittest.mock.patch("shutil.rmtree", wraps=rmtree_permission_error):
            with self.assertRaises(PermissionError):
                filesystem.safe_rmtree("path")

    def test_safe_rmtree_with_file_not_found_and_apple_double(self) -> None:
        with unittest.mock.patch("shutil.rmtree", wraps=rmtree_file_not_found_error) as mock_rmtree:
            if platform_.name == 'osx':
                filesystem.safe_rmtree("._path")
                mock_rmtree.assert_called_once_with("._path", onerror=unittest.mock.ANY)
            else:
                with self.assertRaises(FileNotFoundError):
                    filesystem.safe_rmtree("._path")

    def test_safe_rmtree_with_other_error_and_apple_double(self) -> None:
        with unittest.mock.patch("shutil.rmtree", wraps=rmtree_permission_error):
            with self.assertRaises(PermissionError):
                filesystem.safe_rmtree("._path")


class TestIsSubdirectoryBasic(TestBase, TempdirMixin):
    """Regression guards for is_subdirectory correctness.

    Uses real filesystem paths so the guards hold on every platform.
    They protect against regressions when the internal path
    normalisation inside is_subdirectory is changed - for example,
    replacing os.path.realpath with real_path().
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        TempdirMixin.setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        TempdirMixin.tearDownClass()

    def test_direct_child_is_subdirectory(self):
        parent = os.path.join(self.root, "parent")
        child = os.path.join(parent, "child")
        os.makedirs(child)
        self.assertTrue(filesystem.is_subdirectory(child, parent))

    def test_deep_nested_child_is_subdirectory(self):
        parent = os.path.join(self.root, "deep_parent")
        grandchild = os.path.join(parent, "a", "b", "c")
        os.makedirs(grandchild)
        self.assertTrue(filesystem.is_subdirectory(grandchild, parent))

    def test_sibling_is_not_subdirectory(self):
        base = os.path.join(self.root, "sib_base")
        left = os.path.join(base, "left")
        right = os.path.join(base, "right")
        os.makedirs(left)
        os.makedirs(right)
        self.assertFalse(filesystem.is_subdirectory(left, right))

    def test_unrelated_path_is_not_subdirectory(self):
        a = os.path.join(self.root, "unrelated_a")
        b = os.path.join(self.root, "unrelated_b")
        os.makedirs(a)
        os.makedirs(b)
        self.assertFalse(filesystem.is_subdirectory(a, b))


class TestCanonicalPathIdempotency(TestBase, TempdirMixin):
    """canonical_path(canonical_path(x)) must equal canonical_path(x).

    This invariant guards against naive changes to canonical_path internals that
    produce an asymmetry on a given platform
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        TempdirMixin.setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        TempdirMixin.tearDownClass()

    def test_idempotent_on_existing_directory(self):
        once = canonical_path(self.root, platform_)
        twice = canonical_path(once, platform_)
        self.assertEqual(once, twice)

    def test_idempotent_on_nested_path(self):
        subdir = os.path.join(self.root, "a", "b")
        os.makedirs(subdir)
        once = canonical_path(subdir, platform_)
        twice = canonical_path(once, platform_)
        self.assertEqual(once, twice)


class TestRealPath(TestBase, TempdirMixin):
    """Cross-platform regression guards for real_path().

    real_path() is the form-stable absolute-path helper for file I/O and
    path storage.  Key contracts verified here:

    - relative paths become absolute
    - case is never lowercased (unlike canonical_path on case-insensitive FSes)
    - on non-Windows, symlinks are resolved (delegates to os.path.realpath)
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        TempdirMixin.setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        TempdirMixin.tearDownClass()

    def test_result_is_absolute(self):
        self.assertTrue(os.path.isabs(real_path(self.root)))

    def test_preserves_case(self):
        """real_path() must not lowercase path components.

        canonical_path() lowercases on case-insensitive filesystems;
        real_path() must not, so stored paths are not corrupted for
        case-sensitive consumers (e.g. a Linux NFS mount from Windows).
        """
        mixed = os.path.join(self.root, "FooBar")
        os.makedirs(mixed)
        result = real_path(mixed)
        self.assertIn(
            "FooBar", result,
            "real_path() lowercased a path component: %r" % result,
        )

    @unittest.skipIf(
        platform_.name == "windows",
        "Symlink resolution via realpath is non-Windows only.",
    )
    def test_resolves_symlinks_on_non_windows(self):
        """On non-Windows real_path() resolves symlinks (os.path.realpath).

        Guards against real_path() being switched to abspath on all
        platforms, which would silently break symlink resolution on
        Linux/macOS.
        """
        target = os.path.join(self.root, "real_target")
        link = os.path.join(self.root, "sym_link")
        os.makedirs(target)
        os.symlink(target, link)
        self.assertEqual(real_path(link), real_path(target))


# Simulate py3.8+ Windows os.path.realpath: N:\ expands to \\nas\studio\
_MOCK_DRIVE_TO_UNC = {"n": "\\\\nas\\studio"}


def _unc_expanding_realpath(path):
    """Replicate the py3.8+ Windows realpath behaviour that converts a mapped
    drive letter to the underlying UNC server path."""
    norm = path.replace("/", "\\")
    if len(norm) >= 2 and norm[1] == ":":
        drive = norm[0].lower()
        rest = norm[2:]  # e.g. "\\packages\\mypkg"
        if drive in _MOCK_DRIVE_TO_UNC:
            return _MOCK_DRIVE_TO_UNC[drive] + rest
    return path


@unittest.skipIf(
    platform_.name != "windows",
    "Windows drive-letter / UNC path form tests are Windows-only.",
)
class TestCanonicalPathWindowsFormPreservation(TestBase):
    """canonical_path must never change the *form* of a Windows path.

    A drive-letter path (N:\\...) must stay drive-letter.
    A UNC path (\\\\server\\...) must stay UNC.

    Before the fix these tests fail because canonical_path calls
    os.path.realpath, which on Python 3.8+ Windows silently converts
    drive-letter paths to their underlying UNC equivalents.
    """

    def _mock_windows_platform(self):
        """Return a mock Platform object that behaves like Windows."""
        m = unittest.mock.Mock(spec=["has_case_sensitive_filesystem", "name"])
        m.has_case_sensitive_filesystem = False
        m.name = "windows"
        return m

    # ------------------------------------------------------------------
    # Tests that must FAIL before the fix and PASS after.
    # ------------------------------------------------------------------

    def test_drive_letter_form_preserved(self):
        """canonical_path on a drive-letter path must not return a UNC path.

        Fails today because os.path.realpath (py3.8+ Windows) expands
        N:\\ -> \\\\nas\\studio\\, so canonical_path returns a UNC string.
        """
        mock_plat = self._mock_windows_platform()
        with unittest.mock.patch("os.path.realpath", side_effect=_unc_expanding_realpath):
            result = canonical_path("N:\\packages\\mypkg", platform=mock_plat)

        self.assertFalse(
            result.startswith("\\\\"),
            f"canonical_path UNC-expanded a drive-letter path: {result!r}",
        )
        self.assertTrue(
            result.lower().startswith("n:\\"),
            f"Expected drive-letter result starting with 'n:\\', got: {result!r}",
        )

    def test_drive_letter_form_preserved_forward_slashes(self):
        """Same as above but input uses forward slashes (N:/packages)."""
        mock_plat = self._mock_windows_platform()
        with unittest.mock.patch("os.path.realpath", side_effect=_unc_expanding_realpath):
            result = canonical_path("N:/packages/mypkg", platform=mock_plat)

        self.assertFalse(
            result.startswith("\\\\"),
            f"canonical_path UNC-expanded a drive-letter path: {result!r}",
        )
        self.assertTrue(
            result.lower().startswith("n:\\") or result.lower().startswith("n:/"),
            f"Expected drive-letter result, got: {result!r}",
        )

    # ------------------------------------------------------------------
    # Tests that already PASS today and must continue to PASS after the fix.
    # ------------------------------------------------------------------

    def test_unc_form_preserved(self):
        """canonical_path on a UNC path must return a UNC path."""
        mock_plat = self._mock_windows_platform()
        unc = "\\\\nas\\studio\\packages\\mypkg"
        # realpath on an already-UNC path returns the same UNC path unchanged.
        with unittest.mock.patch("os.path.realpath", return_value=unc):
            result = canonical_path(unc, platform=mock_plat)

        self.assertTrue(
            result.startswith("\\\\"),
            f"canonical_path changed UNC form unexpectedly: {result!r}",
        )

    def test_drive_letter_case_folded(self):
        """canonical_path lowercases drive-letter paths on Windows (case-insensitive FS)."""
        mock_plat = self._mock_windows_platform()
        # Use a local temp path that abspath can handle so we are not
        # depending on UNC expansion behaviour here.
        with unittest.mock.patch("os.path.realpath", side_effect=lambda p: p):
            result = canonical_path("C:\\Packages\\MyPkg", platform=mock_plat)

        self.assertEqual(
            result, result.lower(),
            f"canonical_path did not lowercase on case-insensitive platform: {result!r}",
        )


def _windows_longpaths_enabled() -> bool:
    """Return True if the Windows LongPathsEnabled registry key is set.

    When False, the Win32 API cannot open paths longer than MAX_PATH (260
    chars) without an explicit ``\\?\\`` extended-length prefix.
    """
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\FileSystem",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "LongPathsEnabled")
            return bool(value)
    except OSError:
        return False


@unittest.skipIf(
    platform_.name != "windows",
    "Windows symlink/junction resolution tests are Windows-only.",
)
class TestCanonicalPathWindowsSymlinkResolution(TestBase, TempdirMixin):
    """canonical_path resolves symlinks/junctions on Windows when
    resolve_links_on_windows=True, without expanding mapped drive letters."""

    @classmethod
    def setUpClass(cls):
        TempdirMixin.setUpClass()
        cls.settings = {"resolve_links_on_windows": True}

        # Probe for symlink capability. Dir symlinks require Developer
        # Mode from Windows 10 Creators Update onward, or an elevated process.
        probe_src = os.path.join(cls.root, "_symlink_probe_src")
        probe_lnk = os.path.join(cls.root, "_symlink_probe_lnk")
        os.makedirs(probe_src)
        try:
            os.symlink(probe_src, probe_lnk, target_is_directory=True)
            os.unlink(probe_lnk)
        except OSError:
            raise unittest.SkipTest(
                "Dir symlink creation not supported on this host "
                "(enable Developer Mode or run as Admin)."
            )
        finally:
            if os.path.isdir(probe_src):
                os.rmdir(probe_src)

    @classmethod
    def tearDownClass(cls):
        TempdirMixin.tearDownClass()

    def _mock_windows_platform(self):
        m = unittest.mock.Mock(spec=["has_case_sensitive_filesystem", "name"])
        m.has_case_sensitive_filesystem = False
        m.name = "windows"
        return m

    def test_symlink_resolved(self):
        """canonical_path follows a directory symlink when resolve_links_on_windows=True."""
        target = os.path.join(self.root, "real_target")
        link = os.path.join(self.root, "link_to_target")
        os.makedirs(target)
        os.symlink(target, link, target_is_directory=True)

        result = canonical_path(link, platform=self._mock_windows_platform())
        self.assertEqual(result, target.lower())

    def test_symlink_chain_resolved(self):
        """canonical_path follows a chain of two symlinks."""
        target = os.path.join(self.root, "final_target")
        mid = os.path.join(self.root, "mid_link")
        link = os.path.join(self.root, "outer_link")
        os.makedirs(target)
        os.symlink(target, mid, target_is_directory=True)
        os.symlink(mid, link, target_is_directory=True)

        result = canonical_path(link, platform=self._mock_windows_platform())
        self.assertEqual(result, target.lower())

    def test_non_symlink_path_unchanged(self):
        """canonical_path on a plain directory is stable with resolve_links_on_windows=True."""
        d = os.path.join(self.root, "plain_dir")
        os.makedirs(d)

        result = canonical_path(d, platform=self._mock_windows_platform())
        self.assertEqual(result, d.lower())

    def test_relative_symlink_resolved(self):
        """canonical_path resolves a symlink whose target is a relative path."""
        target = os.path.join(self.root, "rel_target")
        link_parent = os.path.join(self.root, "linkdir")
        os.makedirs(target)
        os.makedirs(link_parent)
        link = os.path.join(link_parent, "rel_link")
        os.symlink(os.path.join("..", "rel_target"), link, target_is_directory=True)

        result = canonical_path(link, platform=self._mock_windows_platform())
        self.assertEqual(result, target.lower())

    def test_intermediate_dir_symlink_resolved(self):
        """canonical_path resolves symlinks on intermediate directory
        components, not just the final component.

        This is the symlink-chain-through-prefix case: if /a is a symlink to
        /real_a, then /a/b/link should resolve through /real_a/b/link, not
        break because /a was already "passed" by the component walk.
        """
        real_a = os.path.join(self.root, "real_a")
        b_dir = os.path.join(real_a, "b")
        target = os.path.join(b_dir, "final_target")
        a_link = os.path.join(self.root, "a")
        link = os.path.join(a_link, "b", "link_to_target")

        os.makedirs(target)
        os.symlink(target, link, target_is_directory=True)
        # Create the intermediate symlink *after* the target tree so the
        # link overlays the directory structure.
        os.symlink(real_a, a_link, target_is_directory=True)

        result = canonical_path(link, platform=self._mock_windows_platform())
        self.assertEqual(result, target.lower())

    def test_nested_intermediate_symlink_resolved(self):
        """canonical_path resolves multiple intermediate directory symlinks
        in a single path.

        /link_a -> /real_a
        /link_a/link_b -> /real_b
        /link_a/link_b/target should resolve to /real_b/target
        """
        real_a = os.path.join(self.root, "real_a")
        real_b = os.path.join(self.root, "real_b")
        target = os.path.join(real_b, "target")
        link_a = os.path.join(self.root, "link_a")
        link_b = os.path.join(link_a, "link_b")

        os.makedirs(target)
        os.symlink(real_b, link_b, target_is_directory=True)
        os.symlink(real_a, link_a, target_is_directory=True)

        test_path = os.path.join(link_a, "link_b", "target")
        result = canonical_path(test_path, platform=self._mock_windows_platform())
        self.assertEqual(result, target.lower())

    def test_long_path_symlink_resolved(self):
        """canonical_path resolves a symlink whose target exceeds MAX_PATH (260
        chars) on hosts with LongPathsEnabled set in the registry."""
        if not _windows_longpaths_enabled():
            self.skipTest(
                "LongPathsEnabled not set in registry; skipping long-path test."
            )

        # self.root is typically ~60-70 chars; 220 'a' chars puts the full
        # target path comfortably past the 260-char Win32 MAX_PATH limit.
        target = os.path.join(self.root, "a" * 220)
        link = os.path.join(self.root, "longpath_link")
        os.makedirs(target)
        os.symlink(target, link, target_is_directory=True)

        result = canonical_path(link, platform=self._mock_windows_platform())
        self.assertEqual(result, target.lower())


@unittest.skipIf(
    platform_.name != "windows",
    "Windows _windows_realpath internal-branch tests are Windows-only.",
)
class TestWindowsRealpathInternals(TestBase):
    """Unit tests for _windows_realpath edge-case branches.

    These use mocking so no real symlinks or network paths are required.
    """

    def test_readlink_extended_prefix_stripped(self):
        """_windows_realpath strips a \\\\?\\ prefix returned by os.readlink."""
        link_path = "C:\\some\\link"
        target_path = "C:\\real\\target"

        def _fake_islink(p):
            return p == link_path

        with unittest.mock.patch("os.path.islink", side_effect=_fake_islink):
            with unittest.mock.patch("os.readlink", return_value="\\\\?\\" + target_path):
                result = _windows_realpath(link_path)

        self.assertEqual(result, os.path.normpath(target_path))

    def test_readlink_unc_extended_prefix_stripped(self):
        """_windows_realpath strips a \\\\?\\UNC\\ prefix returned by os.readlink."""
        link_path = "C:\\some\\link"
        target_unc = "\\\\server\\share\\target"

        def _fake_islink(p):
            return p == link_path

        with unittest.mock.patch("os.path.islink", side_effect=_fake_islink):
            with unittest.mock.patch(
                "os.readlink",
                return_value="\\\\?\\UNC\\" + target_unc[2:],
            ):
                result = _windows_realpath(link_path)

        self.assertEqual(result, os.path.normpath(target_unc))

    def test_symlink_depth_limit_terminates(self):
        """_windows_realpath stops after 40 hops and returns without hanging."""
        with unittest.mock.patch("os.path.islink", return_value=True):
            with unittest.mock.patch("os.readlink", return_value="C:\\loop"):
                result = _windows_realpath("C:\\loop")

        self.assertIsInstance(result, str)


# Map two different drive letters to two different UNC roots.
# This simulates the py3.8+ realpath expansion that triggers the ValueError
# in os.path.relpath when the two paths end up on different UNC servers.
_MOCK_MULTI_DRIVE_TO_UNC = {
    "n": "\\\\nas\\studio",
    "m": "\\\\backup\\bundles",
}


def _multi_drive_unc_realpath(path):
    """Expand two different drive letters to two different UNC roots."""
    norm = path.replace("/", "\\")
    if len(norm) >= 2 and norm[1] == ":":
        drive = norm[0].lower()
        if drive in _MOCK_MULTI_DRIVE_TO_UNC:
            return _MOCK_MULTI_DRIVE_TO_UNC[drive] + norm[2:]
    return path


@unittest.skipIf(
    platform_.name != "windows",
    "Windows-specific real_path() call-site regression tests",
)
class TestRealPathCallSitesWindowsUNC(TestBase):
    """tests that document where os.path.realpath must be replaced with
    real_path() to avoid drive-letter -> UNC expansion on Windows.

    Each test demonstrates a concrete failure against direct use of
    os.path.realpath. They represent call sites that need real_path
    """

    def test_bundle_relpath_does_not_raise_on_different_unc_roots(self):
        """_adjust_variant_for_bundling must not raise ValueError when
        os.path.realpath would have expanded drive-letter paths to UNC form.

        Exercises the real call site in resolved_context.py. is_subdirectory
        is mocked True to force the relpath branch. With real_path() (abspath)
        the drive-letter form is preserved and os.path.relpath succeeds.
        """
        from rez.resolved_context import ResolvedContext

        bundle_path = "N:\\bundles\\mybundle"
        repo_path = "N:\\bundles\\mybundle\\packages\\mypkg"

        handle = {
            "variables": {
                "repository_type": "filesystem",
                "location": repo_path,
            }
        }

        with unittest.mock.patch.object(
            ResolvedContext, "_get_bundle_path", return_value=bundle_path
        ), unittest.mock.patch(
            "rez.resolved_context.is_subdirectory", return_value=True
        ):
            try:
                ResolvedContext._adjust_variant_for_bundling(handle, out=True)
            except ValueError as e:
                self.fail(
                    "_adjust_variant_for_bundling raised ValueError: %s\n"
                    "Ensure real_path() (not os.path.realpath) is used at "
                    "the os.path.relpath call site in resolved_context.py." % e
                )

        self.assertNotEqual(
            handle["variables"]["location"],
            repo_path,
            "Expected location to be updated to a relative path, was unchanged.",
        )

    def test_bundle_relpath_must_not_use_canonical_path_regression(self):
        """canonical_path lowercases the path, which corrupts case-sensitive
        path components stored in bundle files.

        This is a regression guard: if the resolved_context.py call site is
        fixed by substituting canonical_path() (which lowercases on Windows),
        the stored relative path will have wrong capitalisation on Linux NFS
        mounts that are case-sensitive.

        real_path() preserves the original casing, so it is the correct fix.
        """
        from rez.utils.platform_ import Platform

        class _CaseInsensitivePlatform(Platform):
            name = "windows"

            @property
            def has_case_sensitive_filesystem(self):
                return False

        mock_plat = _CaseInsensitivePlatform()
        repo_path = "N:\\packages\\MyPkg\\1.0B"
        bundle_path = "N:\\bundles\\MyBundle"

        relpath_via_canonical = os.path.relpath(
            canonical_path(repo_path, mock_plat),
            canonical_path(bundle_path, mock_plat),
        )
        relpath_via_real = os.path.relpath(
            real_path(repo_path),
            real_path(bundle_path),
        )

        # canonical_path lowercases everything; real_path preserves case.
        self.assertNotEqual(
            relpath_via_canonical,
            relpath_via_real,
            "canonical_path and real_path produced the same relpath - "
            "expected canonical_path to lowercase and real_path to preserve case.",
        )
        self.assertIn(
            "MyPkg", relpath_via_real,
            "real_path() must preserve mixed-case package name in relpath.",
        )
        self.assertIn(
            "1.0B", relpath_via_real,
            "real_path() must preserve mixed-case version string in relpath.",
        )

    def test_suite_save_does_not_raise_suiteerror_when_saving_over_loaded_suite(self):
        """Suite.save() raises SuiteError when the save path differs from
        suite.load_path due to UNC expansion.

        Suite.save() calls os.path.realpath(path) and compares it to
        os.path.realpath(self.load_path). When both were originally the
        same drive-letter path (e.g. N:\\suites\\mysuite), py3.8+ realpath
        expands each independently to the same UNC path, so they still
        compare equal and no error is raised - on the first call.

        The real failure occurs when the suite was loaded from a drive-letter
        path but is saved to what looks like the same path: the UNC expansion
        changes the string, so subsequent code that compares the stored
        load_path against the UNC-expanded save path will see a mismatch.

        This test documents the fragility. Fix: replace os.path.realpath
        with real_path() in Suite.save() and Suite.load().
        """
        from rez.suite import Suite, SuiteError

        drive_path = "N:\\suites\\mysuite"
        suite = Suite()
        suite.load_path = drive_path

        patch_context_names = unittest.mock.patch.object(
            Suite, "context_names",
            new_callable=unittest.mock.PropertyMock,
            return_value=[],
        )
        with unittest.mock.patch("os.path.realpath", side_effect=_unc_expanding_realpath), \
             unittest.mock.patch("os.path.exists", return_value=True), \
             unittest.mock.patch("os.makedirs") as mock_makedirs, \
             unittest.mock.patch("shutil.rmtree") as mock_rmtree, \
             unittest.mock.patch("builtins.open", unittest.mock.mock_open()), \
             patch_context_names, \
             unittest.mock.patch.object(suite, "to_dict", return_value={}), \
             unittest.mock.patch.object(suite, "get_tools", return_value={}):
            try:
                suite.save(drive_path)
            except SuiteError as e:
                self.fail("Suite.save() raised SuiteError: %s" % e)

            # Reachable only after the fix - verify the save actually ran:
            # existing dir must be cleared before re-creating
            mock_rmtree.assert_called_once()
            # suite directory must be (re)created
            mock_makedirs.assert_called()

    def test_suite_load_stores_drive_letter_load_path_not_unc(self):
        """Suite.load() must store load_path in drive-letter form, not UNC.

        Currently FAILS because Suite.load() calls os.path.realpath(path)
        at line 531, which on py3.8+ Windows silently expands a mapped
        drive-letter path to its UNC equivalent.

        A UNC-form load_path causes Suite.save() to raise SuiteError when
        the caller saves back to the same drive-letter path, because
        ``os.path.realpath(drive_letter_save_path)`` returns the same UNC
        string while ``self.load_path`` is also UNC - but if load_path was
        set directly in drive-letter form (e.g. from user config or a
        partially-fixed code path), the string comparison fails.

        Fix: replace os.path.realpath with real_path() in Suite.load().
        """
        from rez.suite import Suite

        drive_path = "N:\\suites\\mysuite"

        with unittest.mock.patch("os.path.realpath", side_effect=_unc_expanding_realpath), \
             unittest.mock.patch("os.path.exists", return_value=True), \
             unittest.mock.patch("os.path.isfile", return_value=True), \
             unittest.mock.patch("builtins.open", unittest.mock.mock_open(read_data="{}")), \
             unittest.mock.patch.object(Suite, "from_dict", return_value=Suite()):
            s = Suite.load(drive_path)

        self.assertFalse(
            s.load_path.startswith("\\\\"),
            "Suite.load_path was UNC-expanded: %r. "
            "Replace os.path.realpath with real_path() in Suite.load()." % s.load_path,
        )
        self.assertTrue(
            s.load_path.lower().startswith("n:\\"),
            "Expected drive-letter form load_path, got: %r" % s.load_path,
        )
