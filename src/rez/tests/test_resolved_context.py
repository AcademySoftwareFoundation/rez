# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Call-site tests for rez.utils.filesystem exercised through
ResolvedContext and Suite.

Split out of test_utils_filesystem.py so that filesystem-utility tests and
higher-level call-site tests live in their own modules.
"""

import os
import unittest
import unittest.mock

from rez.exceptions import SuiteError
from rez.resolved_context import ResolvedContext
from rez.suite import Suite
from rez.tests.util import TestBase
from rez.utils.filesystem import canonical_path, real_path
from rez.utils.platform_ import Platform, platform_


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
