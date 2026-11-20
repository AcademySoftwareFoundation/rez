# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Unit tests for rezplugins.release_vcs.svn
"""
import importlib
import io
import os
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

from rez.exceptions import ReleaseVCSError
from rez.tests.util import TempdirMixin, TestBase


def _make_mock_pysvn():
    """Build a minimal fake pysvn module for tests."""
    mock_pysvn = types.ModuleType("pysvn")

    class MockClientError(Exception):
        pass

    mock_pysvn.ClientError = MockClientError
    mock_pysvn.opt_revision_kind = types.SimpleNamespace(head="head")
    mock_pysvn.Revision = MagicMock()
    mock_pysvn.Client = MagicMock()
    return mock_pysvn


class TestReleaseVCSSvn(TestBase, TempdirMixin):
    """Tests for SvnReleaseVCS and helper functions in rezplugins.release_vcs.svn."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        TempdirMixin.setUpClass()

        cls.pkg_root = os.path.join(cls.root, "pkg")
        os.makedirs(os.path.join(cls.pkg_root, ".svn"))
        with open(os.path.join(cls.pkg_root, "package.py"), "w") as f:
            f.write('name = "test_svn_pkg"\nversion = "1.0.0"\n')

        cls.sub_pkg_root = os.path.join(cls.pkg_root, "subpkg")
        os.makedirs(cls.sub_pkg_root)
        with open(os.path.join(cls.sub_pkg_root, "package.py"), "w") as f:
            f.write('name = "test_svn_subpkg"\nversion = "1.0.0"\n')

        cls._injected_pysvn = "pysvn" not in sys.modules
        cls._had_svn_module = "rezplugins.release_vcs.svn" in sys.modules
        if cls._injected_pysvn:
            sys.modules["pysvn"] = _make_mock_pysvn()

        cls.svn_mod = importlib.import_module("rezplugins.release_vcs.svn")

    @classmethod
    def tearDownClass(cls) -> None:
        if cls._injected_pysvn:
            sys.modules.pop("pysvn", None)
            if not cls._had_svn_module:
                sys.modules.pop("rezplugins.release_vcs.svn", None)
        TempdirMixin.tearDownClass()
        super().tearDownClass()

    def setUp(self) -> None:
        super().setUp()
        self.mock_pysvn = _make_mock_pysvn()
        self.mock_client = MagicMock()
        self.mock_client.info.return_value = {
            "url": "https://svn.example.com/repo/trunk",
            "revision": types.SimpleNamespace(number=42),
        }
        self.mock_pysvn.Client.return_value = self.mock_client

        patcher = patch.object(self.svn_mod, "pysvn", self.mock_pysvn)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _create_vcs(self, pkg_root=None, vcs_root=None):
        return self.svn_mod.SvnReleaseVCS(
            pkg_root or self.pkg_root,
            vcs_root=vcs_root,
        )

    def test_register_plugin_and_class_metadata(self) -> None:
        cls = self.svn_mod.register_plugin()
        self.assertIs(cls, self.svn_mod.SvnReleaseVCS)
        self.assertEqual(cls.name(), "svn")
        self.assertTrue(cls.search_parents_for_root())
        self.assertTrue(cls.is_valid_root(self.pkg_root))
        self.assertFalse(cls.is_valid_root(self.sub_pkg_root))

    def test_find_vcs_root_in_parent(self) -> None:
        vcs = self._create_vcs(pkg_root=self.sub_pkg_root)
        self.assertEqual(vcs.vcs_root, self.pkg_root)
        self.assertEqual(vcs.this_url, "https://svn.example.com/repo/trunk")

    def test_init_raises_when_not_working_copy(self) -> None:
        self.mock_client.info.return_value = None
        with self.assertRaises(self.svn_mod.SvnReleaseVCSError):
            self._create_vcs()

    def test_svn_get_client_configures_client(self) -> None:
        client = self.svn_mod.svn_get_client()
        self.assertIs(client, self.mock_client)
        client.set_interactive.assert_called_once_with(True)
        client.set_auth_cache.assert_called_once_with(False)
        client.set_store_passwords.assert_called_once_with(False)
        self.assertIs(client.callback_get_login, self.svn_mod.get_svn_login)

    def test_get_svn_login_retries_blank_and_returns_credentials(self) -> None:
        with patch("getpass.getpass", side_effect=["", "   ", "secret"]), \
                patch("sys.stdout", new_callable=io.StringIO) as stdout:
            result = self.svn_mod.get_svn_login("realm", "alice", True)

        self.assertEqual(result, (True, "alice", "secret", False))
        self.assertIn("alice", stdout.getvalue())

    def test_get_last_changed_revision_success(self) -> None:
        entry = types.SimpleNamespace(last_changed_rev=123)
        self.mock_client.info2.return_value = [("path", entry)]
        rev = self.svn_mod.get_last_changed_revision(
            self.mock_client,
            "https://svn.example.com/repo/trunk",
        )
        self.assertEqual(rev, 123)
        self.mock_pysvn.Revision.assert_called_once_with(
            self.mock_pysvn.opt_revision_kind.head
        )
        self.mock_client.info2.assert_called_once_with(
            "https://svn.example.com/repo/trunk",
            self.mock_pysvn.Revision.return_value,
            recurse=False,
        )

    def test_get_last_changed_revision_empty_results(self) -> None:
        self.mock_client.info2.return_value = []
        with self.assertRaises(ReleaseVCSError):
            self.svn_mod.get_last_changed_revision(
                self.mock_client,
                "https://svn.example.com/repo/trunk",
            )

    def test_get_last_changed_revision_client_error(self) -> None:
        self.mock_client.info2.side_effect = self.mock_pysvn.ClientError("boom")
        with self.assertRaises(ReleaseVCSError):
            self.svn_mod.get_last_changed_revision(
                self.mock_client,
                "https://svn.example.com/repo/trunk",
            )

    def test_validate_repostate_clean_and_unversioned_only(self) -> None:
        vcs = self._create_vcs()
        self.mock_client.status.return_value = []
        vcs.validate_repostate()

        unversioned = types.SimpleNamespace(entry=None)
        self.mock_client.status.return_value = [unversioned]
        vcs.validate_repostate()

    def test_validate_repostate_dirty_raises(self) -> None:
        vcs = self._create_vcs()
        modified = types.SimpleNamespace(entry="file.py")
        self.mock_client.status.return_value = [modified]
        with self.assertRaises(ReleaseVCSError):
            vcs.validate_repostate()

    def test_get_tag_url_trunk_branches_and_invalid(self) -> None:
        vcs = self._create_vcs()
        self.assertEqual(vcs.get_tag_url(), "https://svn.example.com/repo/tags")
        self.assertEqual(
            vcs.get_tag_url("1.0.0"),
            "https://svn.example.com/repo/tags/1.0.0",
        )

        vcs.this_url = "https://svn.example.com/repo/branches/dev"
        self.assertEqual(
            vcs.get_tag_url("1.0.0"),
            "https://svn.example.com/repo/tags/1.0.0",
        )

        vcs.this_url = "https://svn.example.com/repo/other"
        with self.assertRaises(ReleaseVCSError):
            vcs.get_tag_url("1.0.0")

    @unittest.expectedFailure
    def test_create_tag_impl(self) -> None:
        # Bug in src/rezplugins/release_vcs/svn.py:96-100: _create_tag_impl
        # assigns `lambda x: (True, x)` instead of a 0-arg callback returning
        # `message`, which fails pysvn's 0-argument callback_get_log_message().
        vcs = self._create_vcs()
        with patch("sys.stdout", new_callable=io.StringIO) as stdout:
            vcs._create_tag_impl("1.0.0", message="hello")

        self.assertIn("https://svn.example.com/repo/tags/1.0.0", stdout.getvalue())
        self.assertEqual(
            self.mock_client.callback_get_log_message(),
            (True, "hello"),
        )
        self.mock_client.copy2.assert_called_once_with(
            [("https://svn.example.com/repo/trunk",)],
            "https://svn.example.com/repo/tags/1.0.0",
            make_parents=True,
        )

    def test_create_release_tag_default_and_custom_message(self) -> None:
        vcs = self._create_vcs()
        vcs.create_release_tag("1.0.0")
        self.assertEqual(
            self.mock_client.callback_get_log_message(),
            (True, "1.0.0"),
        )
        self.mock_client.copy.assert_called_once_with(
            self.pkg_root,
            "https://svn.example.com/repo/tags/1.0.0",
        )

        self.mock_client.copy.reset_mock()
        vcs.create_release_tag("1.0.1", message="Release 1.0.1")
        self.assertEqual(
            self.mock_client.callback_get_log_message(),
            (True, "Release 1.0.1"),
        )
        self.mock_client.copy.assert_called_once_with(
            self.pkg_root,
            "https://svn.example.com/repo/tags/1.0.1",
        )

    def test_svn_url_exists(self) -> None:
        vcs = self._create_vcs()
        self.mock_client.info2.return_value = [("entry", {})]
        self.assertTrue(vcs.svn_url_exists("https://svn.example.com/repo/tags/1.0.0"))

        self.mock_client.info2.return_value = []
        self.assertFalse(vcs.svn_url_exists("https://svn.example.com/repo/tags/1.0.0"))

        self.mock_client.info2.side_effect = self.mock_pysvn.ClientError("not found")
        self.assertFalse(vcs.svn_url_exists("https://svn.example.com/repo/tags/1.0.0"))

    def test_get_current_revision_and_changelog(self) -> None:
        vcs = self._create_vcs()
        self.assertEqual(vcs.get_current_revision(), 42)
        self.assertEqual(vcs.get_changelog(), "TODO")
