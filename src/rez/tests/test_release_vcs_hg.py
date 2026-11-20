# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Unit tests for rezplugins.release_vcs.hg (HgReleaseVCS).
"""
import os
import sys
import tempfile
import unittest
from unittest import mock

from rez.exceptions import ReleaseVCSError
from rez.plugin_managers import plugin_manager
from rez.tests.util import TestBase, TempdirMixin


class TestHgReleaseVCS(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        TempdirMixin.setUpClass()

    @classmethod
    def tearDownClass(cls) -> None:
        TempdirMixin.tearDownClass()
        super().tearDownClass()

    def _make_repo_dir(self, with_hg=True, with_patches=False, subdir=None):
        repo_root = tempfile.mkdtemp(dir=self.root, prefix="hg_repo_")
        pkg_root = repo_root
        if subdir:
            pkg_root = os.path.join(repo_root, subdir)
            os.makedirs(pkg_root)

        pkg_py = os.path.join(pkg_root, "package.py")
        with open(pkg_py, "w") as f:
            f.write('name = "test_pkg"\nversion = "1.0.0"\n')

        if with_hg:
            hg_dir = os.path.join(repo_root, ".hg")
            os.makedirs(hg_dir)
            if with_patches:
                os.makedirs(os.path.join(hg_dir, "patches"))

        return repo_root, pkg_root

    def _get_hg_cls(self):
        return plugin_manager.get_plugin_class("release_vcs", "hg")

    def _get_hg_error_cls(self):
        hg_cls = self._get_hg_cls()
        return sys.modules[hg_cls.__module__].HgReleaseVCSError

    def _make_vcs(self, with_patches=False, subdir=None):
        hg_cls = self._get_hg_cls()
        repo_root, pkg_root = self._make_repo_dir(
            with_hg=True, with_patches=with_patches, subdir=subdir
        )

        def fake_cmd(self_vcs, exe, *nargs):
            if nargs and nargs[0] == "root":
                return [repo_root]
            return []

        with mock.patch("rez.release_vcs.which", return_value="/usr/bin/hg"):
            with mock.patch.object(hg_cls, "_cmd", fake_cmd):
                vcs = hg_cls(pkg_root)
        return vcs, repo_root, pkg_root

    def test_register_plugin_and_class_methods(self):
        hg_cls = self._get_hg_cls()
        hg_mod = sys.modules[hg_cls.__module__]
        self.assertIs(hg_mod.register_plugin(), hg_cls)
        self.assertEqual(hg_cls.name(), "hg")
        self.assertTrue(hg_cls.search_parents_for_root())

        repo_root, _ = self._make_repo_dir(with_hg=True)
        self.assertTrue(hg_cls.is_valid_root(repo_root))
        non_hg_root, _ = self._make_repo_dir(with_hg=False)
        self.assertFalse(hg_cls.is_valid_root(non_hg_root))

    def test_init_success_with_and_without_patches(self):
        vcs, repo_root, _ = self._make_vcs(with_patches=False, subdir="sub/pkg")
        self.assertEqual(vcs.vcs_root, repo_root)
        self.assertEqual(vcs.executable, "/usr/bin/hg")
        self.assertIsNone(vcs.patch_path)

        vcs_patch, repo_root_p, _ = self._make_vcs(with_patches=True)
        self.assertEqual(
            vcs_patch.patch_path,
            os.path.join(repo_root_p, ".hg", "patches"),
        )

    def test_init_missing_hg_dir_raises(self):
        hg_cls = self._get_hg_cls()
        hg_err = self._get_hg_error_cls()
        repo_root, pkg_root = self._make_repo_dir(with_hg=False)
        with mock.patch("rez.release_vcs.which", return_value="/usr/bin/hg"):
            with mock.patch.object(hg_cls, "is_valid_root", return_value=True):
                with self.assertRaises(hg_err) as ctx:
                    hg_cls(pkg_root, vcs_root=repo_root)
        self.assertIn("is not a mercurial working copy", str(ctx.exception))

    def test_init_wrong_root_raises(self):
        hg_cls = self._get_hg_cls()
        hg_err = self._get_hg_error_cls()
        repo_root, pkg_root = self._make_repo_dir(with_hg=True)
        with mock.patch("rez.release_vcs.which", return_value="/usr/bin/hg"):
            with mock.patch.object(hg_cls, "_cmd", return_value=["/other/root"]):
                with self.assertRaises(hg_err) as ctx:
                    hg_cls(pkg_root, vcs_root=repo_root)
        self.assertIn("is not the root of a mercurial working copy", str(ctx.exception))

    def test_init_hg_binary_failure_raises(self):
        hg_cls = self._get_hg_cls()
        hg_err = self._get_hg_error_cls()
        repo_root, pkg_root = self._make_repo_dir(with_hg=True)
        with mock.patch("rez.release_vcs.which", return_value="/usr/bin/hg"):
            with mock.patch.object(
                hg_cls, "_cmd", side_effect=RuntimeError("boom")
            ):
                with self.assertRaises(hg_err) as ctx:
                    hg_cls(pkg_root, vcs_root=repo_root)
        self.assertIn("failed to call hg binary: boom", str(ctx.exception))

        # Empty output from `hg root` triggers IndexError -> same handler
        with mock.patch("rez.release_vcs.which", return_value="/usr/bin/hg"):
            with mock.patch.object(hg_cls, "_cmd", return_value=[]):
                with self.assertRaises(hg_err) as ctx2:
                    hg_cls(pkg_root, vcs_root=repo_root)
        self.assertIn("failed to call hg binary:", str(ctx2.exception))

    def test_hg_command_builder(self):
        vcs, repo_root, _ = self._make_vcs()
        with mock.patch.object(vcs, "_cmd", return_value=["ok"]) as mock_cmd:
            res = vcs.hg("status")
            self.assertEqual(res, ["ok"])
            mock_cmd.assert_called_once_with(
                "/usr/bin/hg", "status", "--repository", repo_root
            )

        with mock.patch.object(vcs, "_cmd", return_value=[]) as mock_cmd:
            vcs.hg("tags", patch=True)
            mock_cmd.assert_called_once_with(
                "/usr/bin/hg", "tags", "--mq", "--repository", repo_root
            )

        for repo_args in [
            ("-R", "/custom"),
            ("--repository", "/custom"),
            ("-R/custom",),
            ("--repository=/custom",),
        ]:
            with self.subTest(repo_args=repo_args):
                with mock.patch.object(vcs, "_cmd", return_value=[]) as mock_cmd:
                    vcs.hg("log", *repo_args)
                    mock_cmd.assert_called_once_with("/usr/bin/hg", "log", *repo_args)

        hg_err = self._get_hg_error_cls()
        with self.assertRaises(hg_err) as ctx:
            vcs.hg("status", bogus=True)
        self.assertIn("Unrecognized keyword args to hg command: bogus", str(ctx.exception))

    def test_get_tags_and_tag_exists(self):
        vcs, _, _ = self._make_vcs()
        hg_output = [
            "tip                              157:2d82ff68b9f5",
            "ilmbase-2.1.0                    156:a27f2a7b3375",
            "tag with spaces                  10:abcdef123456",
            "   ",
        ]
        with mock.patch.object(vcs, "hg", return_value=hg_output) as mock_hg:
            tags = vcs.get_tags(patch=True)
            mock_hg.assert_called_once_with("tags", patch=True)

        self.assertEqual(
            tags,
            {
                "tip": {"rev": "157", "shortnode": "2d82ff68b9f5"},
                "ilmbase-2.1.0": {"rev": "156", "shortnode": "a27f2a7b3375"},
                "tag with spaces": {"rev": "10", "shortnode": "abcdef123456"},
            },
        )

        with mock.patch.object(vcs, "get_tags", return_value=tags):
            self.assertTrue(vcs.tag_exists("ilmbase-2.1.0"))
            self.assertFalse(vcs.tag_exists("nonexistent"))

    def test_is_ancestor(self):
        vcs, _, _ = self._make_vcs()
        with mock.patch.object(vcs, "hg", return_value=["exists"]) as mock_hg:
            self.assertTrue(vcs.is_ancestor("10", ".", patch=True))
            mock_hg.assert_called_once_with(
                "log", "-r", "first(10::.)", "--template", "exists", patch=True
            )

        with mock.patch.object(vcs, "hg", return_value=[]):
            self.assertFalse(vcs.is_ancestor("10", "."))

    def test_get_paths_and_default_url(self):
        vcs, _, _ = self._make_vcs()
        paths_out = [
            "default = https://example.com/repo",
            "upstream = ssh://hg@example.com/upstream",
            "",
        ]
        with mock.patch.object(vcs, "hg", return_value=paths_out) as mock_hg:
            paths = vcs.get_paths(patch=True)
            mock_hg.assert_called_once_with("paths", patch=True)
        self.assertEqual(
            paths,
            {
                "default": "https://example.com/repo",
                "upstream": "ssh://hg@example.com/upstream",
            },
        )

        with mock.patch.object(vcs, "get_paths", return_value=paths):
            self.assertEqual(vcs.get_default_url(), "https://example.com/repo")

        with mock.patch.object(vcs, "get_paths", return_value={"upstream": "x"}):
            self.assertIsNone(vcs.get_default_url())

    def test_validate_repostate(self):
        vcs_no_patch, _, _ = self._make_vcs(with_patches=False)
        with mock.patch.object(vcs_no_patch, "hg", return_value=[]) as mock_hg:
            vcs_no_patch.validate_repostate()
            mock_hg.assert_called_once_with("status", "-m", "-a")

        vcs, repo_root, _ = self._make_vcs(with_patches=True)

        # Both main and patch repos clean
        with mock.patch.object(vcs, "hg", return_value=[]) as mock_hg:
            vcs.validate_repostate()
            self.assertEqual(
                mock_hg.call_args_list,
                [
                    mock.call("status", "-m", "-a"),
                    mock.call("status", "-m", "-a", "--mq"),
                ],
            )

        # Dirty main repo
        with mock.patch.object(vcs, "hg", return_value=["M foo.py", "A bar.py"]):
            with self.assertRaises(ReleaseVCSError) as ctx:
                vcs.validate_repostate()
            self.assertIn(repo_root, str(ctx.exception))
            self.assertIn("foo.py, bar.py", str(ctx.exception))

        # Clean main repo, dirty patch repo
        with mock.patch.object(
            vcs, "hg", side_effect=[[], ["M series"]]
        ):
            with self.assertRaises(ReleaseVCSError) as ctx:
                vcs.validate_repostate()
            self.assertIn(vcs.patch_path, str(ctx.exception))
            self.assertIn("series", str(ctx.exception))

    def test_get_current_revision(self):
        vcs, _, _ = self._make_vcs()

        def fake_hg(*args, **kwargs):
            if args[0] == "log":
                return ["deadbeef1234"]
            if args[0] == "branch":
                return ["default"]
            if args[0] == "paths":
                return ["default = https://example.com/repo"]
            return []

        with mock.patch.object(vcs, "hg", side_effect=fake_hg):
            rev = vcs.get_current_revision()
        self.assertEqual(
            rev,
            {
                "commit": "deadbeef1234",
                "branch": "default",
                "push_url": "https://example.com/repo",
            },
        )

        # When get_default_url raises, print_error is called and push_url omitted
        with mock.patch.object(
            vcs, "hg", side_effect=[["deadbeef1234"], ["default"]]
        ):
            with mock.patch.object(
                vcs, "get_default_url", side_effect=RuntimeError("no paths")
            ):
                with self.assertLogs("rez.utils.logging_", level="ERROR") as cm:
                    rev_err = vcs.get_current_revision()
        self.assertEqual(rev_err, {"commit": "deadbeef1234", "branch": "default"})
        self.assertIn("Error retrieving push_url: no paths", "\n".join(cm.output))

    def test_get_changelog(self):
        vcs, _, _ = self._make_vcs()

        with mock.patch.object(vcs, "hg", return_value=["line1", "line2"]) as mock_hg:
            out = vcs.get_changelog()
            mock_hg.assert_called_once_with("log")
        self.assertEqual(out, "line1\nline2")

        with mock.patch.object(vcs, "hg", return_value=["c1"]) as mock_hg:
            out = vcs.get_changelog(
                previous_revision={"commit": "abc123"}, max_revisions=5
            )
            mock_hg.assert_called_once_with(
                "log", "-l", "5", "-r", "reverse(ancestor(abc123, .)::.)"
            )
        self.assertEqual(out, "c1")

        # Invalid previous_revision with debug disabled does not call logger.debug
        with mock.patch.object(vcs, "hg", return_value=[]) as mock_hg:
            with mock.patch("rez.utils.logging_.logger.debug") as mock_dbg:
                vcs.get_changelog(previous_revision="not-a-dict")
            mock_hg.assert_called_once_with("log")
            mock_dbg.assert_not_called()

        # Invalid previous_revision triggers except branch and debug log when enabled
        self.update_settings({"debug_package_release": True})
        with mock.patch.object(vcs, "hg", return_value=[]) as mock_hg:
            with self.assertLogs("rez.utils.logging_", level="DEBUG") as cm:
                vcs.get_changelog(previous_revision="not-a-dict")
            mock_hg.assert_called_once_with("log")
            self.assertIn(
                "couldn't determine previous commit from: 'not-a-dict'",
                "\n".join(cm.output),
            )

    def test_create_tag_lowlevel(self):
        vcs, _, _ = self._make_vcs()

        # New tag with message and force=True
        with mock.patch.object(vcs, "get_tags", return_value={}):
            with mock.patch.object(vcs, "hg") as mock_hg:
                created = vcs._create_tag_lowlevel("v1.0", message="rel 1.0", force=True)
        self.assertTrue(created)
        mock_hg.assert_called_once_with(
            "tag", "v1.0", "--message", "rel 1.0", "--force", patch=False
        )

        # New tag without message and force=False
        with mock.patch.object(vcs, "get_tags", return_value={}):
            with mock.patch.object(vcs, "hg") as mock_hg:
                created = vcs._create_tag_lowlevel("v1.0", force=False)
        self.assertTrue(created)
        mock_hg.assert_called_once_with("tag", "v1.0", patch=False)

        # Existing tag with force=False -> False
        existing = {"v1.0": {"rev": "42", "shortnode": "abcdef"}}
        with mock.patch.object(vcs, "get_tags", return_value=existing):
            with mock.patch.object(vcs, "hg") as mock_hg:
                created = vcs._create_tag_lowlevel("v1.0", force=False)
        self.assertFalse(created)
        mock_hg.assert_not_called()

        # Existing tag, direct ancestor, no altered files -> False
        with mock.patch.object(vcs, "get_tags", return_value=existing):
            with mock.patch.object(vcs, "is_ancestor", return_value=True):
                with mock.patch.object(vcs, "hg", return_value=[]) as mock_hg:
                    created = vcs._create_tag_lowlevel("v1.0", force=True)
        self.assertFalse(created)
        mock_hg.assert_called_once_with(
            "status", "--rev", "42", "--rev", ".", "--no-status"
        )

        # Existing tag, direct ancestor, only .hgtags altered -> False
        with mock.patch.object(vcs, "get_tags", return_value=existing):
            with mock.patch.object(vcs, "is_ancestor", return_value=True):
                with mock.patch.object(vcs, "hg", return_value=[".hgtags"]):
                    created = vcs._create_tag_lowlevel("v1.0", force=True)
        self.assertFalse(created)

        # Existing tag, direct ancestor, other file altered -> re-tags with --force
        with mock.patch.object(vcs, "get_tags", return_value=existing):
            with mock.patch.object(vcs, "is_ancestor", return_value=True):
                with mock.patch.object(
                    vcs, "hg", side_effect=[["src/main.py"], []]
                ) as mock_hg:
                    created = vcs._create_tag_lowlevel("v1.0", force=True)
        self.assertTrue(created)
        self.assertEqual(mock_hg.call_count, 2)

        # Existing tag, NOT direct ancestor -> re-tags with --force
        with mock.patch.object(vcs, "get_tags", return_value=existing):
            with mock.patch.object(vcs, "is_ancestor", return_value=False):
                with mock.patch.object(vcs, "hg") as mock_hg:
                    created = vcs._create_tag_lowlevel("v1.0", force=True, patch=True)
        self.assertTrue(created)
        mock_hg.assert_called_once_with("tag", "v1.0", "--force", patch=True)

    @unittest.expectedFailure  # src/rezplugins/release_vcs/hg.py:126-127
    def test_create_tag_lowlevel_patch_status_bug(self):
        """_create_tag_lowlevel with patch=True should pass patch=True to hg status."""
        vcs, _, _ = self._make_vcs(with_patches=True)
        existing = {"v1.0": {"rev": "42", "shortnode": "abcdef"}}
        with mock.patch.object(vcs, "get_tags", return_value=existing):
            with mock.patch.object(vcs, "is_ancestor", return_value=True):
                with mock.patch.object(vcs, "hg", return_value=[]) as mock_hg:
                    created = vcs._create_tag_lowlevel("v1.0", force=True, patch=True)
        self.assertFalse(created)
        mock_hg.assert_called_once_with(
            "status", "--rev", "42", "--rev", ".", "--no-status", patch=True
        )

    def test_create_tag_highlevel(self):
        # Without patch_path
        vcs, _, _ = self._make_vcs(with_patches=False)
        with mock.patch.object(vcs, "_create_tag_lowlevel", return_value=True) as mock_low:
            res = vcs._create_tag_highlevel("v1.0", message="msg")
        mock_low.assert_called_once_with("v1.0", message="msg", patch=False)
        self.assertEqual(res, [{"type": "tag", "patch": False}])

        with mock.patch.object(vcs, "_create_tag_lowlevel", return_value=False):
            self.assertEqual(vcs._create_tag_highlevel("v1.0"), [])

        # With patch_path
        vcs_p, _, _ = self._make_vcs(with_patches=True)
        with mock.patch.object(vcs_p, "_create_tag_lowlevel", return_value=True) as mock_low:
            with mock.patch.object(vcs_p, "hg") as mock_hg:
                res = vcs_p._create_tag_highlevel("v1.0", message="msg")
        mock_low.assert_called_once_with("v1.0", message="msg", patch=True)
        mock_hg.assert_called_once_with("bookmark", "-f", "v1.0")
        self.assertEqual(
            res,
            [
                {"type": "tag", "patch": True},
                {"type": "bookmark", "patch": False},
            ],
        )

        # With patch_path when lowlevel returns False -> still creates bookmark
        with mock.patch.object(vcs_p, "_create_tag_lowlevel", return_value=False):
            with mock.patch.object(vcs_p, "hg") as mock_hg:
                res = vcs_p._create_tag_highlevel("v1.0")
        mock_hg.assert_called_once_with("bookmark", "-f", "v1.0")
        self.assertEqual(res, [{"type": "bookmark", "patch": False}])

    def test_create_release_tag(self):
        vcs, _, _ = self._make_vcs()

        # Tag and bookmark with default URLs
        created = [
            {"type": "tag", "patch": True},
            {"type": "bookmark", "patch": False},
        ]
        with mock.patch.object(vcs, "_create_tag_highlevel", return_value=created):
            with mock.patch.object(
                vcs, "get_default_url", side_effect=["https://mq.url", "https://main.url"]
            ):
                with mock.patch.object(vcs, "hg") as mock_hg:
                    vcs.create_release_tag("v1.0", message="msg")
        self.assertEqual(
            mock_hg.call_args_list,
            [
                mock.call("push", "https://mq.url", patch=True),
                mock.call("push", "--bookmark", "v1.0", "https://main.url", patch=False),
            ],
        )

        # No default URL -> skips push
        with mock.patch.object(
            vcs, "_create_tag_highlevel", return_value=[{"type": "tag", "patch": False}]
        ):
            with mock.patch.object(vcs, "get_default_url", return_value=None):
                with mock.patch.object(vcs, "hg") as mock_hg:
                    vcs.create_release_tag("v1.0")
        mock_hg.assert_not_called()

        # Unknown type -> ValueError
        with mock.patch.object(
            vcs, "_create_tag_highlevel", return_value=[{"type": "unknown", "patch": False}]
        ):
            with mock.patch.object(vcs, "get_default_url", return_value="https://main.url"):
                with self.assertRaises(ValueError) as ctx:
                    vcs.create_release_tag("v1.0")
        self.assertEqual(str(ctx.exception), "unknown")
