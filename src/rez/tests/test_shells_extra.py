# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Unit tests for rez.shells base classes, helpers, and UnixShell.spawn_shell branches.
"""

from __future__ import annotations

import os
import types
import unittest
from unittest import mock

from rez.config import config
from rez.exceptions import RezSystemError
from rez.rex import EscapedString, OutputStyle, RexExecutor, literal
from rez.shells import (
    Shell,
    UnixShell,
    create_shell,
    get_shell_class,
)
from rez.tests.util import TempdirMixin, TestBase, restore_os_environ
from rez.utils.platform_ import platform_


_GENERIC_SHELL = "cmd" if platform_.name == "windows" else "sh"


class TestShellHelpersAndBase(TestBase, TempdirMixin):
    """Tests for module-level shell helpers and Shell base class methods."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        TempdirMixin.setUpClass()

    @classmethod
    def tearDownClass(cls) -> None:
        TempdirMixin.tearDownClass()
        super().tearDownClass()

    def test_get_shell_class_default_shell_and_system_fallback(self) -> None:
        self.update_settings({"default_shell": _GENERIC_SHELL})
        cls = get_shell_class()
        self.assertEqual(cls.name(), _GENERIC_SHELL)

        self.update_settings({"default_shell": ""})
        with mock.patch("rez.system.system.shell", _GENERIC_SHELL):
            cls = get_shell_class()
            self.assertEqual(cls.name(), _GENERIC_SHELL)

    def test_create_shell_default_shell_and_system_fallback(self) -> None:
        self.update_settings({"default_shell": _GENERIC_SHELL})
        sh = create_shell()
        self.assertEqual(sh.name(), _GENERIC_SHELL)

        self.update_settings({"default_shell": None})
        with mock.patch("rez.system.system.shell", _GENERIC_SHELL):
            sh = create_shell()
            self.assertEqual(sh.name(), _GENERIC_SHELL)

    def test_shell_abstract_methods_raise_not_implemented(self) -> None:
        with self.assertRaises(NotImplementedError):
            Shell.name()
        with self.assertRaises(NotImplementedError):
            Shell.file_extension()
        with self.assertRaises(NotImplementedError):
            Shell.startup_capabilities()
        with self.assertRaises(NotImplementedError):
            Shell.get_syspaths()
        with self.assertRaises(NotImplementedError):
            Shell.get_all_key_tokens("FOO")
        with self.assertRaises(NotImplementedError):
            Shell.line_terminator()
        with self.assertRaises(NotImplementedError):
            Shell.spawn_shell(None, "ctx.sh", self.root)

    def test_is_available_returns_false_on_runtime_error(self) -> None:
        cls = get_shell_class(_GENERIC_SHELL)
        with mock.patch.object(
            cls, "executable_filepath", side_effect=RuntimeError("missing")
        ):
            self.assertFalse(cls.is_available())

    def test_get_output_eval_style(self) -> None:
        sh = create_shell(_GENERIC_SHELL)
        sh.comment("a comment line")
        if platform_.name == "windows":
            sh._addline("set FOO=1")
            sh._addline("set BAR=2")
            expected = "set FOO=1&& set BAR=2"
        else:
            sh._addline("export FOO=1;  ")
            sh._addline("export BAR=2")
            expected = "export FOO=1;export BAR=2"
        output = sh.get_output(style=OutputStyle.eval)
        self.assertEqual(output, expected)

        empty_sh = create_shell(_GENERIC_SHELL)
        self.assertEqual(empty_sh.get_output(style=OutputStyle.eval), "")

    def test_unsupported_and_overruled_option_warnings(self) -> None:
        cls = get_shell_class(_GENERIC_SHELL)

        self.update_settings({"warn_shell_startup": True})
        with mock.patch("rez.shells.print_warning") as mock_warn:
            cls._unsupported_option("rcfile", True)
            mock_warn.assert_called_once()
            self.assertIn("rcfile ignored", mock_warn.call_args[0][0])

            mock_warn.reset_mock()
            cls._overruled_option("rcfile", "norc", True)
            mock_warn.assert_called_once()
            self.assertIn("overruled by norc", mock_warn.call_args[0][0])

            mock_warn.reset_mock()
            cls._unsupported_option("rcfile", False)
            cls._overruled_option("rcfile", "norc", False)
            mock_warn.assert_not_called()

        self.update_settings({"warn_shell_startup": False})
        with mock.patch("rez.shells.print_warning") as mock_warn:
            cls._unsupported_option("rcfile", True)
            cls._overruled_option("rcfile", "norc", True)
            mock_warn.assert_not_called()

    def test_find_executable_errors_and_syspaths(self) -> None:
        cls = get_shell_class(_GENERIC_SHELL)

        # Fallback to check_syspaths when initial which() returns None
        with mock.patch("rez.shells.which", side_effect=[None, "/usr/bin/sh"]) as mock_which:
            with mock.patch.object(cls, "get_syspaths", return_value=["/bin", "/usr/bin"]):
                found = cls.find_executable(_GENERIC_SHELL, check_syspaths=True)
                self.assertEqual(found, "/usr/bin/sh")
                self.assertEqual(mock_which.call_count, 2)
                second_call_env = mock_which.call_args_list[1][1]["env"]
                self.assertEqual(
                    second_call_env["PATH"], os.pathsep.join(["/bin", "/usr/bin"])
                )

        # Neither PATH nor syspaths finds the executable
        with mock.patch("rez.shells.which", return_value=None):
            with self.assertRaises(RuntimeError) as ctx:
                cls.find_executable("nonexistent_shell_bin", check_syspaths=False)
            self.assertIn("nonexistent_shell_bin", str(ctx.exception))

        # Configured executable_fullpath does not exist
        missing_exe = os.path.join(self.root, "no_such_sh")
        config.override("plugins.shell.%s.executable_fullpath" % _GENERIC_SHELL, missing_exe)
        with self.assertRaises(RuntimeError) as ctx:
            cls.find_executable(_GENERIC_SHELL)
        self.assertIn(missing_exe, str(ctx.exception))


@unittest.skipIf(platform_.name == "windows", "UnixShell plugins are not registered on Windows")
class TestUnixShellMethodsAndSpawn(TestBase, TempdirMixin):
    """Tests for UnixShell methods and spawn_shell code paths."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        TempdirMixin.setUpClass()

    @classmethod
    def tearDownClass(cls) -> None:
        TempdirMixin.tearDownClass()
        super().tearDownClass()

    def _make_context_file(self, name: str = "context.sh") -> str:
        path = os.path.join(self.root, name)
        with open(path, "w") as f:
            f.write("# rez context\n")
        return path

    def test_unix_shell_class_and_rex_methods(self) -> None:
        self.assertTrue(UnixShell.supports_norc())
        self.assertTrue(UnixShell.supports_command())
        self.assertTrue(UnixShell.supports_stdin())
        self.assertEqual(UnixShell.line_terminator(), "\n")
        with self.assertRaises(NotImplementedError):
            UnixShell.get_startup_sequence(None, False, False, False)

        sh = create_shell("sh")
        self.assertEqual(sh._startup_env_var(), "HOME")

        with restore_os_environ():
            os.environ["HOME"] = "/tmp/fake_home"
            ex = RexExecutor(
                interpreter=sh.new_shell(),
                parent_environ={},
                add_default_namespaces=False,
            )
            sh._write_startup_env(ex)
            self.assertIn('export HOME="/tmp/fake_home"', ex.get_output())

        sh_reset = create_shell("sh")
        sh_reset.resetenv("FOO", "bar")
        self.assertIn('export FOO="bar"', sh_reset._lines)

        sh_err = create_shell("sh")
        sh_err.error("err1\nerr2")
        err_out = sh_err.get_output()
        self.assertIn('echo "err1" 1>&2', err_out)
        self.assertIn('echo "err2" 1>&2', err_out)

        sh_cmd = create_shell("sh")
        sh_cmd.command(["echo", "hello world", literal("$VAR")])
        self.assertIn("echo \"hello world\" '$VAR'", sh_cmd.get_output())

        # EscapedString in program position is disallowed
        with self.assertRaises(Exception):
            sh_cmd.command([EscapedString.promote("echo"), "arg"])

    def test_spawn_shell_do_rcfile_interactive_and_debug(self) -> None:
        context_file = self._make_context_file()
        rcfile = os.path.join(self.root, "custom_rc")
        with open(rcfile, "w") as f:
            f.write("# custom rc\n")

        tmpdir = os.path.join(self.root, "spawn_rcfile")
        os.makedirs(tmpdir, exist_ok=True)

        self.update_settings(
            {
                "debug_shell_startup": True,
                "package_commands_sourced_first": False,
            }
        )

        sh = create_shell("bash")
        mock_proc = mock.MagicMock()

        with mock.patch.object(type(sh), "executable_filepath", return_value="/bin/bash"):
            with mock.patch("rez.shells.Popen", return_value=mock_proc) as mock_popen:
                with mock.patch("rez.shells.print_debug") as mock_dbg:
                    with mock.patch(
                        "rez.shells.system",
                        types.SimpleNamespace(is_production_rez_install=True),
                    ):
                        proc = sh.spawn_shell(
                            context_file=context_file,
                            tmpdir=tmpdir,
                            rcfile=rcfile,
                            package_commands_sourced_first=False,
                            pre_command="env -i",
                        )

        self.assertIs(proc, mock_proc)
        mock_popen.assert_called_once()
        cmd = mock_popen.call_args[0][0]
        self.assertEqual(cmd[:2], ["env", "-i"])
        self.assertEqual(cmd[2], "/bin/bash")
        self.assertTrue(mock_dbg.called)

        rc_generated = os.path.join(tmpdir, "rcfile.sh")
        self.assertTrue(os.path.isfile(rc_generated))
        with open(rc_generated) as f:
            rc_content = f.read()
        self.assertIn("You are now in a rez-configured environment.", rc_content)
        self.assertIn("rezolve context", rc_content)
        self.assertIn(context_file, rc_content)

        rez_shell = os.path.join(tmpdir, "rez-shell.sh")
        with open(rez_shell) as f:
            rez_shell_content = f.read()
        self.assertIn("--rcfile %s" % rc_generated, rez_shell_content)

    def test_spawn_shell_envvar_branch_and_no_prompt(self) -> None:
        context_file = self._make_context_file("ctx_envvar.sh")
        tmpdir = os.path.join(self.root, "spawn_envvar")
        os.makedirs(tmpdir, exist_ok=True)

        config.override("plugins.shell.sh.prompt", "")
        sh = create_shell("sh")
        mock_proc = mock.MagicMock()

        with mock.patch.object(type(sh), "executable_filepath", return_value="/bin/sh"):
            with mock.patch("rez.shells.Popen", return_value=mock_proc) as mock_popen:
                proc = sh.spawn_shell(
                    context_file=context_file,
                    tmpdir=tmpdir,
                    pre_command=["nice", "-n", "10"],
                )

        self.assertIs(proc, mock_proc)
        cmd = mock_popen.call_args[0][0]
        self.assertEqual(cmd[:3], ["nice", "-n", "10"])

        env_script = os.path.join(tmpdir, "ENV.sh")
        self.assertTrue(os.path.isfile(env_script))
        with open(os.path.join(tmpdir, "rez-shell.sh")) as f:
            rez_shell_content = f.read()
        self.assertIn('export ENV="%s"' % env_script, rez_shell_content)
        self.assertNotIn("REZ_ENV_PROMPT", rez_shell_content)

    def test_spawn_shell_home_hijack_with_histfile_and_empty_files(self) -> None:
        context_file = self._make_context_file("ctx_home.sh")

        # Case 1: files non-empty + histfile exists + debug_shell_startup
        tmpdir1 = os.path.join(self.root, "spawn_home_files")
        os.makedirs(tmpdir1, exist_ok=True)
        fake_home = os.path.join(self.root, "fake_home_hist")
        os.makedirs(fake_home, exist_ok=True)
        hist_path = os.path.join(fake_home, ".history")
        with open(hist_path, "w") as f:
            f.write("ls\n")

        self.update_settings({"debug_shell_startup": True})
        sh = create_shell("sh")
        seq_with_files = {
            "stdin": False,
            "command": None,
            "do_rcfile": False,
            "envvar": None,
            "files": ["~/.profile"],
            "bind_files": ["~/.profile"],
            "source_bind_files": False,
        }
        with restore_os_environ():
            os.environ["HOME"] = fake_home
            with mock.patch.object(type(sh), "executable_filepath", return_value="/bin/sh"):
                with mock.patch.object(sh, "get_startup_sequence", return_value=seq_with_files):
                    with mock.patch.object(sh, "histfile", "~/.history"):
                        with mock.patch.object(sh, "histvar", "HISTFILE"):
                            with mock.patch("rez.shells.Popen", return_value=mock.MagicMock()):
                                with mock.patch("rez.shells.print_debug"):
                                    sh.spawn_shell(context_file=context_file, tmpdir=tmpdir1)

        with open(os.path.join(tmpdir1, "rez-shell.sh")) as f:
            rez_shell_content = f.read()
        self.assertIn('export HOME="%s"' % tmpdir1, rez_shell_content)
        self.assertIn('export HISTFILE="%s"' % hist_path, rez_shell_content)

        # Case 2: files empty -> warning + source context_file in parent shell
        tmpdir2 = os.path.join(self.root, "spawn_home_empty")
        os.makedirs(tmpdir2, exist_ok=True)
        self.update_settings({"warn_shell_startup": True})
        seq_empty = {
            "stdin": False,
            "command": None,
            "do_rcfile": False,
            "envvar": None,
            "files": [],
            "bind_files": [],
            "source_bind_files": False,
        }
        with mock.patch.object(type(sh), "executable_filepath", return_value="/bin/sh"):
            with mock.patch.object(sh, "get_startup_sequence", return_value=seq_empty):
                with mock.patch("rez.shells.Popen", return_value=mock.MagicMock()):
                    with mock.patch("rez.shells.print_warning") as mock_warn:
                        sh.spawn_shell(context_file=context_file, tmpdir=tmpdir2)
        mock_warn.assert_called_once()
        self.assertIn("Could not configure environment", mock_warn.call_args[0][0])
        with open(os.path.join(tmpdir2, "rez-shell.sh")) as f:
            self.assertIn(context_file, f.read())

        # Case 3: files empty + warn_shell_startup=False -> no warning
        tmpdir3 = os.path.join(self.root, "spawn_home_empty_nowarn")
        os.makedirs(tmpdir3, exist_ok=True)
        self.update_settings({"warn_shell_startup": False})
        with mock.patch.object(type(sh), "executable_filepath", return_value="/bin/sh"):
            with mock.patch.object(sh, "get_startup_sequence", return_value=seq_empty):
                with mock.patch("rez.shells.Popen", return_value=mock.MagicMock()):
                    with mock.patch("rez.shells.print_warning") as mock_warn:
                        sh.spawn_shell(context_file=context_file, tmpdir=tmpdir3)
        mock_warn.assert_not_called()

        # Case 4: files non-empty + histvar is None -> skips history export
        tmpdir4 = os.path.join(self.root, "spawn_home_nohist")
        os.makedirs(tmpdir4, exist_ok=True)
        with mock.patch.object(type(sh), "executable_filepath", return_value="/bin/sh"):
            with mock.patch.object(sh, "get_startup_sequence", return_value=seq_with_files):
                with mock.patch.object(sh, "histvar", None):
                    with mock.patch("rez.shells.Popen", return_value=mock.MagicMock()):
                        sh.spawn_shell(context_file=context_file, tmpdir=tmpdir4)
        with open(os.path.join(tmpdir4, "rez-shell.sh")) as f:
            self.assertNotIn("HISTFILE", f.read())

    def test_spawn_shell_popen_error_raises_rez_system_error(self) -> None:
        context_file = self._make_context_file("ctx_err.sh")
        tmpdir = os.path.join(self.root, "spawn_err")
        os.makedirs(tmpdir, exist_ok=True)

        sh = create_shell("sh")
        with mock.patch.object(type(sh), "executable_filepath", return_value="/bin/sh"):
            with mock.patch("rez.shells.Popen", side_effect=OSError("spawn failed")):
                with self.assertRaises(RezSystemError) as ctx:
                    sh.spawn_shell(
                        context_file=context_file,
                        tmpdir=tmpdir,
                        command="echo hi",
                    )
        self.assertIn("Error running command", str(ctx.exception))
        self.assertIn("spawn failed", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
