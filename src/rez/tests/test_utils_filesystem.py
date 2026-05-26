# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
unit tests for 'rez.utils.filesystem' module
"""
import os
import os.path
import tempfile
import unittest
import unittest.mock

from rez.tests.util import TestBase
from rez.tests.util import TempdirMixin
from rez.utils import filesystem
from rez.utils.filesystem import canonical_path, _windows_realpath
from rez.utils.platform_ import platform_


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
