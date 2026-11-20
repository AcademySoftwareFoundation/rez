# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
unit tests for the git release_vcs plugin
"""
import os
import unittest
from unittest.mock import patch

from rez.config import config
from rez.exceptions import ReleaseVCSError
from rez.plugin_managers import plugin_manager
from rez.release_vcs import create_release_vcs, get_release_vcs_types
from rez.tests.util import TempdirMixin, TestBase


class _FakePopen:
    """Fake Popen for mocking git CLI invocations in ReleaseVCS._cmd."""

    def __init__(self, handler, args, **kwargs):
        self.args = args
        self._handler = handler
        self.returncode = 0

    def communicate(self):
        out, err, rc = self._handler(self.args[1:])
        self.returncode = rc
        return out, err


class TestGitReleaseVCS(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        TempdirMixin.setUpClass()

    @classmethod
    def tearDownClass(cls):
        TempdirMixin.tearDownClass()
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        self.pkg_dir = os.path.join(self.root, "pkg_%s" % self._testMethodName)
        os.makedirs(os.path.join(self.pkg_dir, ".git"), exist_ok=True)
        with open(os.path.join(self.pkg_dir, "package.py"), "w") as f:
            f.write('name = "test_pkg"\nversion = "1.0.0"\n')

    def _make_vcs(self, handler, pkg_root=None, vcs_root=None):
        """Create a GitReleaseVCS with mocked `which` and `Popen`."""
        calls = []

        def _dispatch(args):
            calls.append(tuple(args))
            return handler(args)

        def _popen_factory(args, **kwargs):
            return _FakePopen(_dispatch, args, **kwargs)

        vcs_cls = plugin_manager.get_plugin_class("release_vcs", "git")
        with patch("rez.release_vcs.which", return_value="/usr/bin/git"), \
                patch("rez.release_vcs.Popen", side_effect=_popen_factory):
            vcs = vcs_cls(pkg_root or self.pkg_dir, vcs_root=vcs_root)
        return vcs, calls

    def _with_mocked_git(self, vcs, handler):
        """Return a context manager patching Popen for calls on an existing vcs."""
        calls = []

        def _dispatch(args):
            calls.append(tuple(args))
            return handler(args)

        def _popen_factory(args, **kwargs):
            return _FakePopen(_dispatch, args, **kwargs)

        return patch("rez.release_vcs.Popen", side_effect=_popen_factory), calls

    def test_plugin_metadata(self):
        from rezplugins.release_vcs.git import register_plugin

        vcs_cls = plugin_manager.get_plugin_class("release_vcs", "git")
        self.assertEqual(vcs_cls.name(), "git")
        self.assertTrue(vcs_cls.search_parents_for_root())
        self.assertIs(register_plugin(), vcs_cls)
        self.assertIn("git", get_release_vcs_types())

    def test_is_valid_root_and_find_vcs_root(self):
        vcs_cls = plugin_manager.get_plugin_class("release_vcs", "git")
        self.assertTrue(vcs_cls.is_valid_root(self.pkg_dir))
        no_git = os.path.join(self.root, "no_git_%s" % self._testMethodName)
        os.makedirs(no_git, exist_ok=True)
        self.assertFalse(vcs_cls.is_valid_root(no_git))

        # File named .git is not a directory
        file_git = os.path.join(self.root, "file_git_%s" % self._testMethodName)
        os.makedirs(file_git, exist_ok=True)
        with open(os.path.join(file_git, ".git"), "w") as f:
            f.write("gitdir: ../elsewhere\n")
        self.assertFalse(vcs_cls.is_valid_root(file_git))

        # Parent search finds .git in pkg_dir from a subdirectory
        subdir = os.path.join(self.pkg_dir, "sub", "nested")
        os.makedirs(subdir, exist_ok=True)
        found = vcs_cls.find_vcs_root(subdir)
        self.assertEqual(found, (self.pkg_dir, 2))

    def test_init_success_and_create_release_vcs(self):
        def handler(args):
            if args == ("rev-parse",):
                return ("", "", 0)
            raise AssertionError("Unexpected git args: %r" % (args,))

        vcs, calls = self._make_vcs(handler)
        self.assertEqual(vcs.executable, "/usr/bin/git")
        self.assertEqual(vcs.vcs_root, self.pkg_dir)
        self.assertEqual(calls, [("rev-parse",)])

        def _popen_factory(args, **kw):
            return _FakePopen(handler, args, **kw)

        with patch("rez.release_vcs.which", return_value="/usr/bin/git"), \
                patch("rez.release_vcs.Popen", side_effect=_popen_factory):
            vcs2 = create_release_vcs(self.pkg_dir, vcs_name="git")
        self.assertIsInstance(
            vcs2, plugin_manager.get_plugin_class("release_vcs", "git")
        )

    def test_init_not_a_git_repo_raises(self):
        from rezplugins.release_vcs.git import GitReleaseVCSError

        def handler(args):
            return ("", "fatal: not a git repository", 128)

        with self.assertRaises(GitReleaseVCSError) as cm:
            self._make_vcs(handler)
        self.assertIn("is not a git repository", str(cm.exception))

    def test_get_relative_to_remote(self):
        vcs, _ = self._make_vcs(lambda args: ("", "", 0))

        cases = [
            ("## main...origin/main", 0),
            ("## main...origin/main [ahead 3]", 3),
            ("## main...origin/main [behind 4]", -4),
            ("## [topic] main...origin/main [ahead 2]", 2),
        ]
        for line, expected in cases:
            with self.subTest(line=line):
                ctx, _ = self._with_mocked_git(vcs, lambda args, ln=line: (ln, "", 0))
                with ctx:
                    self.assertEqual(vcs.get_relative_to_remote(), expected)

        bad_cases = [
            "## main...origin/main [gone]",
            "## main...origin/main [ahead notanint]",
            "## main...origin/main [diverged 1]",
        ]
        for line in bad_cases:
            with self.subTest(bad_line=line):
                ctx, _ = self._with_mocked_git(vcs, lambda args, ln=line: (ln, "", 0))
                with ctx:
                    with self.assertRaises(ReleaseVCSError) as cm:
                        vcs.get_relative_to_remote()
                self.assertIn("Problem parsing first line", str(cm.exception))

    def test_get_local_branch(self):
        vcs, _ = self._make_vcs(lambda args: ("", "", 0))
        ctx, calls = self._with_mocked_git(vcs, lambda args: ("feature/xyz\n", "", 0))
        with ctx:
            self.assertEqual(vcs.get_local_branch(), "feature/xyz")
        self.assertEqual(calls, [("rev-parse", "--abbrev-ref", "HEAD")])

    def test_get_tracking_branch(self):
        vcs, _ = self._make_vcs(lambda args: ("", "", 0))

        # Upstream present (including slash in branch name)
        ctx, _ = self._with_mocked_git(
            vcs, lambda args: ("origin/feature/foo\n", "", 0)
        )
        with ctx:
            self.assertEqual(vcs.get_tracking_branch(), ["origin", "feature/foo"])

        # Known "no upstream" error messages return (None, None)
        no_upstream_msgs = [
            "fatal: no upstream configured for branch 'main'",
            "fatal: No upstream branch for 'main'",
            "fatal: HEAD does not point to a branch",
        ]
        for errmsg in no_upstream_msgs:
            with self.subTest(errmsg=errmsg):
                ctx, _ = self._with_mocked_git(
                    vcs, lambda args, msg=errmsg: ("", msg, 128)
                )
                with ctx:
                    self.assertEqual(vcs.get_tracking_branch(), (None, None))

        # Unexpected git error is re-raised
        ctx, _ = self._with_mocked_git(
            vcs, lambda args: ("", "fatal: repository corrupted", 128)
        )
        with ctx:
            with self.assertRaises(ReleaseVCSError):
                vcs.get_tracking_branch()

    def _validate_handler(
        self,
        upstream="origin/main",
        upstream_err=None,
        branch="main",
        dirty=False,
        status_line="## main...origin/main",
    ):
        def handler(args):
            if args == ("rev-parse", "--is-bare-repository"):
                return ("false\n", "", 0)
            if args == ("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"):
                if upstream_err:
                    return ("", upstream_err, 128)
                return (upstream + "\n", "", 0)
            if args == ("rev-parse", "--abbrev-ref", "HEAD"):
                return (branch + "\n", "", 0)
            if args == ("diff-index", "--quiet", "HEAD"):
                return ("", "", 1 if dirty else 0)
            if args == ("diff-index", "--stat", "HEAD"):
                return (" package.py | 1 +\n 1 file changed\n", "", 0)
            if args == ("remote", "update"):
                return ("", "", 0)
            if args == ("status", "--short", "-b"):
                return (status_line + "\n", "", 0)
            raise AssertionError("Unexpected git args: %r" % (args,))

        return handler

    def test_validate_repostate_success(self):
        vcs, _ = self._make_vcs(lambda args: ("", "", 0))
        ctx, calls = self._with_mocked_git(vcs, self._validate_handler())
        with ctx:
            vcs.validate_repostate()
        self.assertIn(("remote", "update"), calls)

    def test_validate_repostate_no_upstream_disallowed_and_allowed(self):
        vcs, _ = self._make_vcs(lambda args: ("", "", 0))
        handler = self._validate_handler(
            upstream_err="fatal: no upstream configured for branch 'main'"
        )
        ctx, _ = self._with_mocked_git(vcs, handler)
        with ctx:
            with self.assertRaises(ReleaseVCSError) as cm:
                vcs.validate_repostate()
        self.assertIn("no upstream branch", str(cm.exception))

        # Allowed via plugin config override (discarded by TestBase.tearDown)
        config.override("plugins.release_vcs.git.allow_no_upstream", True)
        vcs_allowed, _ = self._make_vcs(lambda args: ("", "", 0))
        ctx2, calls2 = self._with_mocked_git(vcs_allowed, handler)
        with ctx2:
            vcs_allowed.validate_repostate()
        self.assertNotIn(("remote", "update"), calls2)

    def test_validate_repostate_releasable_branches(self):
        config.override("plugins.release_vcs.releasable_branches", ["^main$", "^release/.*"])
        vcs, _ = self._make_vcs(lambda args: ("", "", 0))

        # Matching branch passes
        ctx_ok, _ = self._with_mocked_git(
            vcs, self._validate_handler(branch="release/1.0")
        )
        with ctx_ok:
            vcs.validate_repostate()

        # Non-matching branch fails
        ctx_bad, _ = self._with_mocked_git(
            vcs, self._validate_handler(branch="feature/wip")
        )
        with ctx_bad:
            with self.assertRaises(ReleaseVCSError) as cm:
                vcs.validate_repostate()
        self.assertIn("current branch is feature/wip", str(cm.exception))

    def test_validate_repostate_uncommitted_changes(self):
        vcs, _ = self._make_vcs(lambda args: ("", "", 0))
        ctx, _ = self._with_mocked_git(vcs, self._validate_handler(dirty=True))
        with ctx:
            with self.assertRaises(ReleaseVCSError) as cm:
                vcs.validate_repostate()
        self.assertIn("uncommitted changes", str(cm.exception))
        self.assertIn("package.py", str(cm.exception))

    def test_validate_repostate_ahead_or_behind_remote(self):
        vcs, _ = self._make_vcs(lambda args: ("", "", 0))

        for status_line, expected_substr in [
            ("## main...origin/main [ahead 2]", "2 commits ahead of origin/main"),
            ("## main...origin/main [behind 3]", "3 commits behind origin/main"),
        ]:
            with self.subTest(status_line=status_line):
                ctx, _ = self._with_mocked_git(
                    vcs, self._validate_handler(status_line=status_line)
                )
                with ctx:
                    with self.assertRaises(ReleaseVCSError) as cm:
                        vcs.validate_repostate()
                self.assertIn(expected_substr, str(cm.exception))

    def test_get_changelog(self):
        vcs, _ = self._make_vcs(lambda args: ("", "", 0))

        def handler(args):
            return ("commit abc\ncommit def\n", "", 0)

        # No args
        ctx, calls = self._with_mocked_git(vcs, handler)
        with ctx:
            log = vcs.get_changelog()
        self.assertEqual(log, "commit abc\ncommit def")
        self.assertEqual(calls, [("log",)])

        # With previous_revision and max_revisions
        ctx, calls = self._with_mocked_git(vcs, handler)
        with ctx:
            log = vcs.get_changelog(
                previous_revision={"commit": "111aaa"}, max_revisions=5
            )
        self.assertEqual(log, "commit abc\ncommit def")
        self.assertEqual(calls, [("log", "-n", "5", "111aaa..HEAD")])

        # Invalid previous_revision with debug_package_release disabled
        ctx, calls = self._with_mocked_git(vcs, handler)
        with ctx, patch("rez.utils.logging_.logger.debug") as mock_debug:
            log = vcs.get_changelog(previous_revision="not-a-dict")
        self.assertEqual(log, "commit abc\ncommit def")
        self.assertEqual(calls, [("log",)])
        mock_debug.assert_not_called()

        # Invalid previous_revision with debug_package_release enabled
        self.update_settings({"debug_package_release": True})
        vcs_dbg, _ = self._make_vcs(lambda args: ("", "", 0))
        ctx, calls = self._with_mocked_git(vcs_dbg, handler)
        with ctx, self.assertLogs("rez.utils.logging_", level="DEBUG") as cm:
            log = vcs_dbg.get_changelog(previous_revision="not-a-dict")
        self.assertEqual(log, "commit abc\ncommit def")
        self.assertEqual(calls, [("log",)])
        self.assertTrue(
            any("couldn't determine previous commit" in msg for msg in cm.output)
        )

    def test_get_current_revision_with_tracking_branch(self):
        vcs, _ = self._make_vcs(lambda args: ("", "", 0))

        def handler(args):
            if args == ("rev-parse", "HEAD"):
                return ("deadbeef1234\n", "", 0)
            if args == ("rev-parse", "--abbrev-ref", "HEAD"):
                return ("main\n", "", 0)
            if args == ("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"):
                return ("origin/main\n", "", 0)
            if args == ("remote", "-v"):
                return (
                    (
                        "origin\thttps://example.com/repo.git (fetch)\n"
                        "origin\thttps://example.com/repo.git (push)\n"
                        "upstream\thttps://other.com/repo.git (fetch)\n"
                    ),
                    "",
                    0,
                )
            raise AssertionError("Unexpected git args: %r" % (args,))

        ctx, _ = self._with_mocked_git(vcs, handler)
        with ctx:
            rev = vcs.get_current_revision()

        self.assertEqual(
            rev,
            {
                "commit": "deadbeef1234",
                "branch": "main",
                "tracking_branch": "origin/main",
                "fetch_url": "https://example.com/repo.git",
                "push_url": "https://example.com/repo.git",
            },
        )

    def test_get_current_revision_without_tracking_and_url_error(self):
        vcs, _ = self._make_vcs(lambda args: ("", "", 0))

        # No tracking branch
        def handler_no_upstream(args):
            if args == ("rev-parse", "HEAD"):
                return ("deadbeef1234\n", "", 0)
            if args == ("rev-parse", "--abbrev-ref", "HEAD"):
                return ("main\n", "", 0)
            if args == ("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"):
                return ("", "fatal: no upstream branch", 128)
            raise AssertionError("Unexpected git args: %r" % (args,))

        ctx, _ = self._with_mocked_git(vcs, handler_no_upstream)
        with ctx:
            rev = vcs.get_current_revision()
        self.assertEqual(
            rev,
            {
                "commit": "deadbeef1234",
                "branch": "main",
                "tracking_branch": None,
            },
        )

        # Tracking branch present, but remote -v lacks matching URLs & branch fails
        def handler_bad_remote(args):
            if args == ("rev-parse", "HEAD"):
                return ("deadbeef1234\n", "", 0)
            if args == ("rev-parse", "--abbrev-ref", "HEAD"):
                return ("", "fatal: detached HEAD error", 128)
            if args == ("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"):
                return ("origin/main\n", "", 0)
            if args == ("remote", "-v"):
                return ("other\thttps://other.com/repo.git (fetch)\n", "", 0)
            raise AssertionError("Unexpected git args: %r" % (args,))

        ctx2, _ = self._with_mocked_git(vcs, handler_bad_remote)
        with ctx2:
            rev2 = vcs.get_current_revision()
        self.assertEqual(rev2["commit"], "deadbeef1234")
        self.assertEqual(rev2["tracking_branch"], "origin/main")
        self.assertNotIn("branch", rev2)
        self.assertNotIn("fetch_url", rev2)
        self.assertNotIn("push_url", rev2)

    def test_tag_exists_and_create_release_tag(self):
        vcs, _ = self._make_vcs(lambda args: ("", "", 0))

        # tag_exists True/False
        ctx, _ = self._with_mocked_git(vcs, lambda args: ("v1.0.0\nv1.1.0\n", "", 0))
        with ctx:
            self.assertTrue(vcs.tag_exists("v1.0.0"))
            self.assertFalse(vcs.tag_exists("v2.0.0"))

        # create_release_tag returns early when tag already exists
        ctx, calls = self._with_mocked_git(vcs, lambda args: ("v1.0.0\n", "", 0))
        with ctx:
            vcs.create_release_tag("v1.0.0", message="ignored")
        self.assertEqual(calls, [("tag",)])

        # create_release_tag without tracking branch creates tag locally only
        def handler_local_only(args):
            if args == ("tag",):
                return ("", "", 0)
            if args[:2] == ("tag", "-a"):
                return ("", "", 0)
            if args == ("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"):
                return ("", "fatal: no upstream branch", 128)
            raise AssertionError("Unexpected git args: %r" % (args,))

        ctx, calls = self._with_mocked_git(vcs, handler_local_only)
        with ctx:
            vcs.create_release_tag("v2.0.0")
        self.assertEqual(
            calls,
            [
                ("tag",),
                ("tag", "-a", "v2.0.0", "-m", ""),
                ("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"),
            ],
        )

        # create_release_tag with tracking branch creates and pushes tag
        def handler_with_remote(args):
            if args == ("tag",):
                return ("", "", 0)
            if args[:2] == ("tag", "-a"):
                return ("", "", 0)
            if args == ("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"):
                return ("origin/main\n", "", 0)
            if args == ("push", "origin", "v2.0.0"):
                return ("", "", 0)
            raise AssertionError("Unexpected git args: %r" % (args,))

        ctx, calls = self._with_mocked_git(vcs, handler_with_remote)
        with ctx:
            vcs.create_release_tag("v2.0.0", message="Release 2.0.0")
        self.assertEqual(
            calls,
            [
                ("tag",),
                ("tag", "-a", "v2.0.0", "-m", "Release 2.0.0"),
                ("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"),
                ("push", "origin", "v2.0.0"),
            ],
        )

    @unittest.expectedFailure
    def test_validate_repostate_bare_repository(self):
        # src/rezplugins/release_vcs/git.py:94-96 compares list[str] from self.git() to "true"
        vcs, _ = self._make_vcs(lambda args: ("", "", 0))
        base_handler = self._validate_handler()

        def handler(args):
            if args == ("rev-parse", "--is-bare-repository"):
                return ("true\n", "", 0)
            return base_handler(args)

        ctx, _ = self._with_mocked_git(vcs, handler)
        with ctx:
            with self.assertRaises(ReleaseVCSError) as cm:
                vcs.validate_repostate()
        self.assertIn("bare git repository", str(cm.exception))

    @unittest.expectedFailure
    def test_export(self):
        # src/rezplugins/release_vcs/git.py:225-237 references undefined retain_cwd and git
        vcs_cls = plugin_manager.get_plugin_class("release_vcs", "git")
        export_path = os.path.join(self.root, "export_%s" % self._testMethodName)
        revision = {
            "fetch_url": "https://example.com/repo.git",
            "commit": "deadbeef1234",
        }
        vcs_cls.export(revision, export_path)


if __name__ == "__main__":
    unittest.main()
