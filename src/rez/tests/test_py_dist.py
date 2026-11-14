# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Tests for rez.utils.py_dist.
"""
import os
from types import SimpleNamespace
import unittest
import unittest.mock

from rez.utils import py_dist
from rez.tests.util import TestBase, TempdirMixin


class TestConvertDistSymlinkedLocation(TestBase, TempdirMixin):
    """convert_dist with a symlinked dist.location.

    Regression test for the py_dist containment/composition fix: when the
    distribution lives behind a symlink (analogous to a junctioned
    site-packages on Windows), the converted package must include files
    from the distribution, placed at their correct relative location inside
    the package root.
    """

    settings = {}

    @classmethod
    def setUpClass(cls) -> None:
        TempdirMixin.setUpClass()

    @classmethod
    def tearDownClass(cls) -> None:
        TempdirMixin.tearDownClass()

    def _make_site(self, parent):
        site_real = os.path.join(parent, "site_real")
        egginfo = os.path.join(site_real, "fake_dist.egg-info")
        os.makedirs(egginfo)
        with open(os.path.join(site_real, "mod.py"), "w") as f:
            f.write("x = 1\n")
        with open(os.path.join(egginfo, "installed-files.txt"), "w") as f:
            f.write("../mod.py\n")
        return site_real

    def _fake_dist(self, location):
        return SimpleNamespace(
            project_name="fake-dist",
            version="1.0.0",
            requires=lambda: [],
            location=location,
            egg_name=lambda: "fake_dist",
        )

    def test_symlinked_location_file_included_at_correct_path(self):
        parent = os.path.join(self.root, self._testMethodName)
        os.makedirs(parent)
        site_real = self._make_site(parent)
        site_link = os.path.join(self.root, "site_link")
        os.symlink(site_real, site_link)

        dest = os.path.join(self.root, "packages")
        self._patch_dist(self._fake_dist(site_link))
        out = py_dist.convert_dist("fake-dist", dest, make_variant=False)

        # mod.py must be inside the package root, at its correct relative
        # location - NOT skipped, and NOT composed outside the root.
        mod = os.path.join(out, "mod.py")
        self.assertTrue(
            os.path.isfile(mod),
            "mod.py missing from the converted package (was it skipped "
            "or misplaced?): %s" % sorted(
                os.path.join(root, f)
                for root, _, files in os.walk(dest)
                for f in files
            ),
        )
        with open(mod) as f:
            self.assertEqual(f.read(), "x = 1\n")
        self.assertTrue(os.path.isfile(os.path.join(out, "package.py")))

    def test_plain_location_file_included(self):
        parent = os.path.join(self.root, self._testMethodName)
        os.makedirs(parent)
        site_real = self._make_site(parent)

        dest = os.path.join(self.root, "packages")
        self._patch_dist(self._fake_dist(site_real))
        out = py_dist.convert_dist("fake-dist", dest, make_variant=False)

        self.assertTrue(os.path.isfile(os.path.join(out, "mod.py")))
        self.assertTrue(os.path.isfile(os.path.join(out, "package.py")))

    def test_windows_junction_location_file_included(self):
        # Simulates Windows with resolve_links_on_windows=True: there,
        # real_path() is an alias-preserving abspath (no link resolution),
        # while a canonicalised location would have been resolved. The
        # regression: mixing canonical (resolved) location with real_path'd
        # (alias-based) entries made relpath() emit ".." components and copy
        # files OUTSIDE the package root. The fix gives both operands the
        # same, alias-preserving form.
        parent = os.path.join(self.root, self._testMethodName)
        os.makedirs(parent)
        site_real = self._make_site(parent)
        site_alias = os.path.join(parent, "Alias_Site")
        os.symlink(site_real, site_alias)

        dest = os.path.join(self.root, "packages")
        self._patch_dist(self._fake_dist(site_alias))
        with unittest.mock.patch.object(py_dist, "real_path", os.path.abspath):
            out = py_dist.convert_dist("fake-dist", dest, make_variant=False)

        mod = os.path.join(out, "mod.py")
        walked = [os.path.join(root, f)
                  for root, _, files in os.walk(dest) for f in files]
        self.assertTrue(
            os.path.isfile(mod),
            "mod.py not inside the package version dir (was it copied "
            "outside?): %s" % sorted(walked),
        )
        # nothing may land outside the version dir
        outsiders = [f for f in walked
                     if not f.startswith(out + os.sep)
                     and f != os.path.join(out, "package.py")]
        self.assertEqual(outsiders, [])

    def _patch_dist(self, fake):
        orig = py_dist.importlib_metadata.distribution
        py_dist.importlib_metadata.distribution = lambda name: fake
        self.addCleanup(setattr, py_dist.importlib_metadata,
                        "distribution", orig)


if __name__ == "__main__":
    unittest.main()
