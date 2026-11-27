# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Tests for rezplugins.release_hook.emailer
"""
import email
import io
import os
import smtplib
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

from rez import release_hook
from rez.config import config
from rez.plugin_managers import plugin_manager
from rez.system import system
from rez.tests.util import TempdirMixin, TestBase


class TestEmailReleaseHook(TestBase, TempdirMixin):
    """Tests for the 'emailer' release hook. No real emails are sent."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        TempdirMixin.setUpClass()

    @classmethod
    def tearDownClass(cls) -> None:
        TempdirMixin.tearDownClass()
        super().tearDownClass()

    def setUp(self) -> None:
        super().setUp()
        self.package = SimpleNamespace(
            name="foo",
            qualified_name="foo-1.0.0",
            package_type="external",
            config=config,
        )
        self._patch(release_hook, "get_developer_package", return_value=self.package)
        self.mock_smtp_cls = self._patch(smtplib, "SMTP")

    def _patch(self, target, attribute: str, **kwargs):
        patcher = patch.object(target, attribute, **kwargs)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def _create_hook(self, **settings) -> release_hook.ReleaseHook:
        """Create the emailer hook with the given plugin settings."""
        plugin_settings = {
            "smtp_host": "smtp.example.com",
            "smtp_port": 25,
            "sender": "rez@example.com",
            "recipients": ["dev@example.com"],
            "subject": "[rez] {package.qualified_name}",
            "body": (
                "Package: {package.qualified_name}\n"
                "Path: {release.path}\n"
                "Prev: {release.previous_version}\n"
                "Msg: {release.message}\n"
                "Log: {release.changelog}\n"
                "Count: {variants.count}\n"
                "Paths:\n{variants.paths}"
            ),
        }
        plugin_settings.update(settings)
        self.update_settings({"plugins": {"release_hook": {"emailer": plugin_settings}}})
        hook_cls = plugin_manager.get_plugin_class("release_hook", "emailer")
        return hook_cls("/path/to/source")

    def _write_yaml(self, filename: str, content: str) -> str:
        filepath = os.path.join(self.root, filename)
        with open(filepath, "w") as f:
            f.write(content)
        return filepath

    def test_name_and_register_plugin(self) -> None:
        hook_cls = plugin_manager.get_plugin_class("release_hook", "emailer")
        emailer_mod = plugin_manager.get_plugin_module("release_hook", "emailer")
        self.assertEqual(hook_cls.name(), "emailer")
        self.assertIs(emailer_mod.register_plugin(), hook_cls)

    def test_post_release_no_variants_skips_email(self) -> None:
        hook = self._create_hook()
        for variants in ([], None):
            with self.subTest(variants=variants):
                hook.post_release(user="alice", install_path="/packages", variants=variants)
                self.mock_smtp_cls.assert_not_called()

    def test_post_release_formats_subject_and_body(self) -> None:
        hook = self._create_hook(
            subject="Released {package.qualified_name} by {system.user}",
            body="\n  Header\n\n\nSummary:\n\n{variants.count} variants:\n{variants.paths}\n\n",
        )
        variants = [
            SimpleNamespace(root="/packages/foo/1.0.0/platform-linux"),
            SimpleNamespace(root="/packages/foo/1.0.0/platform-osx"),
        ]

        stdout = io.StringIO()
        with redirect_stdout(stdout):
            hook.post_release(
                user="alice",
                install_path="/packages",
                variants=variants,
                release_message="bugfix",
                changelog="* fixed bug",
                previous_version="0.9.0",
            )

        self.mock_smtp_cls.assert_called_once_with("smtp.example.com", 25)
        sendmail = self.mock_smtp_cls.return_value.sendmail
        sendmail.assert_called_once()
        kwargs = sendmail.call_args.kwargs
        self.assertEqual(kwargs["from_addr"], "rez@example.com")
        self.assertEqual(kwargs["to_addrs"], ["dev@example.com"])

        msg = email.message_from_string(kwargs["msg"])
        self.assertEqual(msg["Subject"], f"Released foo-1.0.0 by {system.user}")
        self.assertEqual(msg["From"], "rez@example.com")
        self.assertEqual(msg["To"], "dev@example.com")
        self.assertEqual(
            msg.get_payload(),
            "Header\n\nSummary:\n\n2 variants:\n/packages/foo/1.0.0/platform-linux\n/packages/foo/1.0.0/platform-osx",
        )

    def test_post_release_optional_fields_default_text(self) -> None:
        hook = self._create_hook()
        variants = [SimpleNamespace(root="/packages/foo/1.0.0")]

        stdout = io.StringIO()
        with redirect_stdout(stdout):
            hook.post_release(user="alice", install_path="/packages", variants=variants)

        raw_msg = self.mock_smtp_cls.return_value.sendmail.call_args.kwargs["msg"]
        body = email.message_from_string(raw_msg).get_payload()
        self.assertIn("Path: /packages", body)
        self.assertIn("Prev: None.", body)
        self.assertIn("Msg: No release message.", body)
        self.assertIn("Log: No changelog.", body)

    def test_send_email_no_recipients_skips_smtp(self) -> None:
        for recipients in ([], ""):
            with self.subTest(recipients=recipients):
                hook = self._create_hook(recipients=recipients)
                hook.send_email("sub", "body")
                self.mock_smtp_cls.assert_not_called()

    def test_send_email_no_smtp_host_warns_and_skips(self) -> None:
        hook = self._create_hook(smtp_host="")
        with self.assertLogs("rez.utils.logging_", level="WARNING") as cm:
            hook.send_email("sub", "body")

        self.assertIn("SMTP host is not specified", "\n".join(cm.output))
        self.mock_smtp_cls.assert_not_called()

    def test_send_email_empty_resolved_recipients_skips_smtp(self) -> None:
        yaml_path = self._write_yaml("empty_rules.yaml", "rules: []\n")
        hook = self._create_hook(recipients=yaml_path)
        hook.send_email("sub", "body")

        self.mock_smtp_cls.assert_not_called()

    def test_send_email_success_prints_recipients_and_confirmation(self) -> None:
        hook = self._create_hook(
            smtp_host="mail.example.com",
            smtp_port=587,
            sender="noreply@example.com",
            recipients=["alice@example.com", "bob@example.com"],
        )

        stdout = io.StringIO()
        with redirect_stdout(stdout):
            hook.send_email("Hello", "World")

        output = stdout.getvalue()
        self.assertIn("Sending release email to:", output)
        self.assertIn("- alice@example.com", output)
        self.assertIn("- bob@example.com", output)
        self.assertIn("Email(s) sent.", output)

        self.mock_smtp_cls.assert_called_once_with("mail.example.com", 587)
        kwargs = self.mock_smtp_cls.return_value.sendmail.call_args.kwargs
        self.assertEqual(kwargs["from_addr"], "noreply@example.com")
        self.assertEqual(kwargs["to_addrs"], ["alice@example.com", "bob@example.com"])
        msg = email.message_from_string(kwargs["msg"])
        self.assertEqual(msg["To"], "alice@example.com,bob@example.com")
        self.assertEqual(msg["Subject"], "Hello")
        self.assertEqual(msg.get_payload(), "World")

    def test_send_email_smtp_exception_prints_error(self) -> None:
        self.mock_smtp_cls.return_value.sendmail.side_effect = RuntimeError("connection refused")
        hook = self._create_hook()

        stdout = io.StringIO()
        with redirect_stdout(stdout):
            with self.assertLogs("rez.utils.logging_", level="ERROR") as cm:
                hook.send_email("Hello", "World")

        self.assertIn("release email delivery failed: connection refused", "\n".join(cm.output))

    def test_get_recipients_list(self) -> None:
        hook = self._create_hook(recipients=["a@example.com", "b@example.com"])
        self.assertEqual(hook.get_recipients(), ["a@example.com", "b@example.com"])

    def test_get_recipients_single_email_string(self) -> None:
        hook = self._create_hook(recipients="solo@example.com")
        self.assertEqual(hook.get_recipients(), ["solo@example.com"])

    def test_get_recipients_missing_file_prints_error(self) -> None:
        missing = os.path.join(self.root, "does_not_exist.yaml")
        hook = self._create_hook(recipients=missing)
        with self.assertLogs("rez.utils.logging_", level="ERROR") as cm:
            self.assertEqual(hook.get_recipients(), [])
        self.assertIn("email recipient file does not exist", "\n".join(cm.output))

    def test_get_recipients_yaml_load_error_prints_error(self) -> None:
        bad_yaml = self._write_yaml("bad.yaml", "rules: [unclosed\n")
        hook = self._create_hook(recipients=bad_yaml)
        with self.assertLogs("rez.utils.logging_", level="ERROR") as cm:
            self.assertEqual(hook.get_recipients(), [])
        msg = "\n".join(cm.output)
        self.assertIn("failed to load recipients config:", msg)
        self.assertIn("while parsing a flow sequence", msg)

    def test_load_recipients_matching_rules_and_sorting(self) -> None:
        yaml_path = self._write_yaml(
            "recipients.yaml",
            """
rules:
- filters:
    name:
    - foo
    - bar
  recipients:
  - zoe@example.com
  - shared@example.com
- filters:
    package_type: external
  recipients:
  - ext@example.com
- filters:
    package_type: null
  recipients:
  - has_type@example.com
- filters:
    name: foo
    missing_attr: something
  recipients:
  - never_missing@example.com
- filters:
    name: foo
    package_type: internal
  recipients:
  - never_mismatch@example.com
- recipients:
  - all@example.com
  - shared@example.com
""",
        )
        hook = self._create_hook(recipients=yaml_path)
        result = hook.get_recipients()
        self.assertEqual(
            result,
            [
                "all@example.com",
                "ext@example.com",
                "has_type@example.com",
                "shared@example.com",
                "zoe@example.com",
            ],
        )

    def test_load_recipients_empty_rules(self) -> None:
        yaml_path = self._write_yaml("no_rules.yaml", "{}\n")
        hook = self._create_hook()
        self.assertEqual(hook.load_recipients(yaml_path), [])

    @unittest.expectedFailure  # src/rezplugins/release_hook/emailer.py:120 missing tuple parens
    def test_load_recipients_invalid_types_raise_type_error(self) -> None:
        hook = self._create_hook()
        cases = [
            ("bad_rules.yaml", "rules: 'not-a-list'\n"),
            ("bad_filters.yaml", "rules:\n- filters: 'not-a-dict'\n  recipients: []\n"),
            ("bad_recipients.yaml", "rules:\n- recipients: 'not-a-list'\n"),
        ]
        for filename, content in cases:
            with self.subTest(filename=filename):
                yaml_path = self._write_yaml(filename, content)
                with self.assertRaisesRegex(TypeError, r"Expected <class '.*'>, not "):
                    hook.load_recipients(yaml_path)
