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
from rez.utils.filesystem import canonical_path
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
        N:\\ → \\\\nas\\studio\\, so canonical_path returns a UNC string.
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
