# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Tests for rezplugins.release_hook.command
"""
import io
import os
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from subprocess import PIPE, STDOUT
from types import SimpleNamespace
from unittest.mock import patch

from rez import release_hook
from rez.config import config
from rez.exceptions import ReleaseHookCancellingError
from rez.tests.util import TestBase
from rezplugins.release_hook import command


class TestCommandReleaseHook(TestBase):
    """Tests for the 'command' release hook. No real commands are run."""

    def setUp(self) -> None:
        super().setUp()
        package = SimpleNamespace(name="foo", config=config)
        self._patch(release_hook, "get_developer_package", return_value=package)

        # Patch the module object we imported, not a dotted path, so the mocks
        # still apply if another test has removed rezplugins from sys.modules.
        self.mock_which = self._patch(command, "which", side_effect=lambda name: "/usr/bin/" + name)
        self.mock_popen = self._patch(command, "Popen")
        self._set_result(returncode=0)

    def _patch(self, target, attribute: str, **kwargs):
        patcher = patch.object(target, attribute, **kwargs)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def _set_result(self, returncode: int, output: bytes = b"") -> None:
        """Set the exit code and output of the mocked process."""
        process = self.mock_popen.return_value
        process.returncode = returncode
        process.communicate.return_value = (output, None)

    def _create_hook(self, **settings) -> command.CommandReleaseHook:
        """Create the hook with the given plugin settings.

        Printing is off unless a test turns it on.
        """
        plugin_settings = {"print_commands": False, "print_output": False, "print_error": False}
        plugin_settings.update(settings)
        self.update_settings({"plugins": {"release_hook": {"command": plugin_settings}}})
        return command.CommandReleaseHook("/path/to/source")

    def _popen_args(self) -> list:
        """The argument list of each Popen call, in order."""
        return [call.args[0] for call in self.mock_popen.call_args_list]

    def _capture_success_and_failure(self, hook: command.CommandReleaseHook) -> tuple:
        """Run a passing command, then a failing one. Return (stdout, stderr)."""
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            self._set_result(returncode=0, output=b"all good")
            hook.execute_command("echo", [], user=None, errors=[])
            self._set_result(returncode=1, output=b"it broke")
            hook.execute_command("echo", [], user=None, errors=[])
        return stdout.getvalue(), stderr.getvalue()

    def test_name_and_register_plugin(self) -> None:
        self.assertEqual(command.CommandReleaseHook.name(), "command")
        self.assertIs(command.register_plugin(), command.CommandReleaseHook)

    def test_command_is_found_with_which(self) -> None:
        hook = self._create_hook()
        errors = []
        result = hook.execute_command("echo", ["hello"], user=None, errors=errors)

        self.assertTrue(result)
        self.assertEqual(errors, [])
        self.mock_which.assert_called_once_with("echo")
        self.mock_popen.assert_called_once_with(["/usr/bin/echo", "hello"], stdout=PIPE, stderr=STDOUT)

    def test_command_given_as_file_path_skips_which(self) -> None:
        hook = self._create_hook()
        hook.execute_command(sys.executable, None, user=None, errors=[])

        self.mock_which.assert_not_called()
        self.assertEqual(self._popen_args(), [[sys.executable]])

    def test_command_not_found(self) -> None:
        self.mock_which.side_effect = lambda name: None
        hook = self._create_hook()
        errors = []
        result = hook.execute_command("missing", [], user=None, errors=errors)

        self.assertFalse(result)
        self.assertEqual(errors, ["missing: command not found"])
        self.mock_popen.assert_not_called()

    def test_failing_command_records_its_output(self) -> None:
        self._set_result(returncode=1, output=b"it broke")
        hook = self._create_hook()
        errors = []
        result = hook.execute_command("echo", [], user=None, errors=errors)

        self.assertFalse(result)
        self.assertEqual(len(errors), 1)
        self.assertIn("command failed", errors[0])
        self.assertIn("it broke", errors[0])

    def test_root_user_runs_with_sudo(self) -> None:
        hook = self._create_hook(pre_release_commands=[
            {"command": "echo", "args": ["hi"], "user": "root"},
        ])
        hook.pre_release(user="alice", install_path="/packages")

        self.assertEqual(self._popen_args(), [["sudo", "/usr/bin/echo", "hi"]])

    def test_current_user_runs_without_sudo(self) -> None:
        hook = self._create_hook()
        with patch.object(command.getpass, "getuser", return_value="alice"):
            hook.execute_command("echo", [], user="alice", errors=[])

        self.assertEqual(self._popen_args(), [["/usr/bin/echo"]])

    def test_other_user_is_not_supported(self) -> None:
        hook = self._create_hook()
        with patch.object(command.getpass, "getuser", return_value="alice"):
            with self.assertRaises(NotImplementedError):
                hook.execute_command("echo", [], user="bob", errors=[])

        self.mock_popen.assert_not_called()

    def test_env_is_passed_to_popen(self) -> None:
        hook = self._create_hook()
        hook.execute_command("echo", [], user=None, errors=[], env={"FOO": "bar"})

        self.assertEqual(self.mock_popen.call_args.kwargs["env"], {"FOO": "bar"})

    def test_output_and_errors_are_printed_when_enabled(self) -> None:
        hook = self._create_hook(print_output=True, print_error=True)
        stdout, stderr = self._capture_success_and_failure(hook)

        self.assertIn("all good", stdout)
        self.assertIn("it broke", stderr)

    def test_output_and_errors_are_not_printed_when_disabled(self) -> None:
        hook = self._create_hook(print_output=False, print_error=False)
        stdout, stderr = self._capture_success_and_failure(hook)

        self.assertEqual((stdout, stderr), ("", ""))

    def test_args_are_split_and_formatted(self) -> None:
        hook = self._create_hook(pre_release_commands=[
            {"command": "echo", "args": "{package.name} {release.path}"},
        ])
        hook.pre_release(user="alice", install_path="/packages")

        self.assertEqual(self._popen_args(), [["/usr/bin/echo", "foo", "/packages"]])

    def test_pretty_args(self) -> None:
        hook = self._create_hook(pre_release_commands=[
            {"command": "echo", "args": ["{variants}"]},
            {"command": "echo", "args": ["{variants}"], "pretty_args": False},
        ])
        hook.pre_release(user="alice", install_path="/packages", variants=[0, 1])

        self.assertEqual(self._popen_args(), [
            ["/usr/bin/echo", "0 1"],
            ["/usr/bin/echo", "[0, 1]"],
        ])

    def test_env_is_added_to_os_environ_and_expanded_in_args(self) -> None:
        hook = self._create_hook(pre_release_commands=[
            {"command": "echo", "args": ["$GREETING"], "env": {"GREETING": "hello"}},
        ])
        with patch.dict(os.environ, {"REZ_TEST_EXISTING": "1"}):
            hook.pre_release(user="alice", install_path="/packages")

        self.assertEqual(self._popen_args(), [["/usr/bin/echo", "hello"]])
        env = self.mock_popen.call_args.kwargs["env"]
        self.assertEqual(env["GREETING"], "hello")
        self.assertEqual(env["REZ_TEST_EXISTING"], "1")

    def test_print_commands(self) -> None:
        hook = self._create_hook(print_commands=True, pre_release_commands=[
            {"command": "echo", "args": "hello world", "env": {"FOO": "bar"}},
        ])
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            hook.pre_release(user="alice", install_path="/packages")

        self.assertIn("running command: echo hello world", stdout.getvalue())
        self.assertIn("with: FOO=bar", stdout.getvalue())

    def test_commands_are_debug_printed_when_release_debugging_is_on(self) -> None:
        hook = self._create_hook(pre_release_commands=[{"command": "echo"}])
        with patch.object(command, "print_debug") as mock_debug:
            hook.pre_release(user="alice", install_path="/packages")
            mock_debug.assert_not_called()

            # TestBase gives each test its own config, so this is undone in tearDown.
            config.override("debug_package_release", True)
            hook.pre_release(user="alice", install_path="/packages")
            mock_debug.assert_called_once_with("running command: echo")

    def test_passing_pre_build_command_does_not_cancel(self) -> None:
        hook = self._create_hook(pre_build_commands=[{"command": "echo"}])
        hook.pre_build(user="alice", install_path="/packages")

        self.assertEqual(self._popen_args(), [["/usr/bin/echo"]])

    def test_failing_pre_build_command_cancels(self) -> None:
        self._set_result(returncode=1)
        hook = self._create_hook(pre_build_commands=[{"command": "echo"}])

        with self.assertRaisesRegex(ReleaseHookCancellingError, "pre-build commands failed"):
            hook.pre_build(user="alice", install_path="/packages")

    def test_failing_pre_release_command_cancels(self) -> None:
        self._set_result(returncode=1)
        hook = self._create_hook(pre_release_commands=[{"command": "echo"}])

        with self.assertRaisesRegex(ReleaseHookCancellingError, "pre-release commands failed"):
            hook.pre_release(user="alice", install_path="/packages")

    def test_no_cancel_when_cancel_on_error_is_off(self) -> None:
        self._set_result(returncode=1)
        hook = self._create_hook(
            cancel_on_error=False,
            pre_build_commands=[{"command": "echo"}],
            pre_release_commands=[{"command": "echo"}],
        )
        hook.pre_build(user="alice", install_path="/packages")
        hook.pre_release(user="alice", install_path="/packages")

        self.assertEqual(self.mock_popen.call_count, 2)

    def test_stop_on_error_skips_remaining_commands(self) -> None:
        self._set_result(returncode=1)
        hook = self._create_hook(
            cancel_on_error=False,
            stop_on_error=True,
            pre_release_commands=[{"command": "first"}, {"command": "second"}],
        )
        hook.pre_release(user="alice", install_path="/packages")

        self.assertEqual(self._popen_args(), [["/usr/bin/first"]])

    def test_commands_continue_after_error_without_stop_on_error(self) -> None:
        self._set_result(returncode=1)
        hook = self._create_hook(
            cancel_on_error=False,
            stop_on_error=False,
            pre_release_commands=[{"command": "first"}, {"command": "second"}],
        )
        hook.pre_release(user="alice", install_path="/packages")

        self.assertEqual(self._popen_args(), [["/usr/bin/first"], ["/usr/bin/second"]])

    def test_post_release_formats_with_installed_package(self) -> None:
        installed = SimpleNamespace(name="foo", root="/packages/foo/1.0")
        variant = SimpleNamespace(
            parent=installed,
            resource=SimpleNamespace(variables={"index": 0}, variant_requires=["python-3"]),
        )
        hook = self._create_hook(post_release_commands=[
            {"command": "echo", "args": "{package.root} {num_variants} {variants[0][variant_requires]}"},
        ])
        hook.post_release(user="alice", install_path="/packages", variants=[variant])

        self.assertEqual(self._popen_args(), [["/usr/bin/echo", "/packages/foo/1.0", "1", "python-3"]])

    def test_failing_post_release_command_does_not_cancel(self) -> None:
        self._set_result(returncode=1, output=b"it broke")
        hook = self._create_hook(post_release_commands=[{"command": "echo"}])
        with patch.object(command, "print_debug") as mock_debug:
            hook.post_release(user="alice", install_path="/packages", variants=[])

        mock_debug.assert_called_once()
        self.assertIn("post-release commands failed", mock_debug.call_args.args[0])
        self.assertIn("it broke", mock_debug.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
