# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Extra unit tests for rez.rex covering Actions, ActionManager, ActionInterpreter,
Python interpreter, EscapedString, optionvars, NamespaceFormatter,
EnvironmentDict, EnvironmentVariable, and RexExecutor edge cases.
"""
import contextlib
import io
import os
import sys
import types
import unittest
from unittest import mock

from rez.exceptions import (
    RexError,
    RexStopError,
    RezSystemError,
)
from rez.rex import (
    Action,
    ActionInterpreter,
    ActionManager,
    EscapedString,
    NamespaceFormatter,
    OutputStyle,
    Python,
    Resetenv,
    RexExecutor,
    Setenv,
    Shebang,
    Stop,
    Unsetenv,
    expandable,
    literal,
    optionvars,
)
from rez.system import system
from rez.tests.util import TestBase, restore_os_environ, restore_sys_path
from rez.utils.sourcecode import SourceCode


class _DummyInterpreter(ActionInterpreter):
    """Minimal concrete ActionInterpreter with expand_env_vars=False."""

    expand_env_vars = False

    def __init__(self):
        self.calls = []
        self._environ = set()

    def _env_sep(self, name):
        return ":"

    def get_output(self, style=OutputStyle.file):
        return list(self.calls)

    def setenv(self, key, value):
        self.calls.append(("setenv", key, value))

    def unsetenv(self, key):
        self.calls.append(("unsetenv", key))

    def resetenv(self, key, value, friends=None):
        self.calls.append(("resetenv", key, value, friends))

    def prependenv(self, key, value):
        raise NotImplementedError

    def appendenv(self, key, value):
        raise NotImplementedError

    def alias(self, key, value):
        self.calls.append(("alias", key, value))

    def info(self, value):
        self.calls.append(("info", value))

    def error(self, value):
        self.calls.append(("error", value))

    def command(self, value):
        self.calls.append(("command", value))

    def comment(self, value):
        self.calls.append(("comment", value))

    def source(self, value):
        self.calls.append(("source", value))

    def shebang(self):
        self.calls.append(("shebang",))

    def get_key_token(self, key):
        return "${%s}" % key

    def _saferefenv(self, key):
        self.calls.append(("_saferefenv", key))


class _ExpandingDummyInterpreter(_DummyInterpreter):
    """Minimal concrete ActionInterpreter with expand_env_vars=True."""

    expand_env_vars = True


class TestRexActions(TestBase):

    def test_action_repr_and_eq(self) -> None:
        a = Setenv("FOO", "bar")
        self.assertEqual(repr(a), "Setenv('FOO', 'bar')")
        self.assertEqual(repr(Shebang()), "Shebang()")
        self.assertEqual(repr(Stop("msg")), "Stop('msg')")
        self.assertEqual(a, Setenv("FOO", "bar"))
        self.assertNotEqual(a, Setenv("FOO", "baz"))
        self.assertNotEqual(a, Unsetenv("FOO"))
        self.assertIn(("setenv", Setenv), Action.get_command_types())

    def test_env_action_key_and_value(self) -> None:
        s = Setenv("FOO", "bar")
        self.assertEqual(s.key, "FOO")
        self.assertEqual(s.value, "bar")

        u = Unsetenv("FOO")
        self.assertEqual(u.key, "FOO")
        self.assertIsNone(u.value)

    def test_setenv_pre_and_post_exec(self) -> None:
        interp = _DummyInterpreter()
        s_list = Setenv("PATH", ["/a", "/b"])
        s_list.pre_exec(interp)
        self.assertEqual(s_list.args, ("PATH", "/a:/b"))
        self.assertEqual(s_list.post_exec(interp, "res"), "res")
        self.assertIn("PATH", interp._environ)

        s_tuple = Setenv("FOO", ("/a", "/b"))
        s_tuple.pre_exec(interp)
        self.assertEqual(s_tuple.args, ("FOO", "/a:/b"))

        s_str = Setenv("FOO", "bar")
        s_str.pre_exec(interp)
        self.assertEqual(s_str.args, ("FOO", "bar"))

    def test_resetenv_friends_pre_and_post_exec(self) -> None:
        interp = _DummyInterpreter()
        r_with_friends = Resetenv("FOO", ["x", "y"], ["BAR"])
        self.assertEqual(r_with_friends.friends, ["BAR"])
        r_with_friends.pre_exec(interp)
        self.assertEqual(r_with_friends.args, ("FOO", "x:y", ["BAR"]))
        self.assertEqual(r_with_friends.post_exec(interp, 42), 42)
        self.assertIn("FOO", interp._environ)

        r_no_friends = Resetenv("BAZ", "val")
        self.assertIsNone(r_no_friends.friends)

        r_str = Resetenv("QUX", "val", None)
        r_str.pre_exec(interp)
        self.assertEqual(r_str.args, ("QUX", "val", None))


class TestActionManagerExtra(TestBase):

    def test_is_verbose(self) -> None:
        interp = _DummyInterpreter()
        mgr_list = ActionManager(interp, verbose=["setenv", "info"])
        self.assertTrue(mgr_list._is_verbose("setenv"))
        self.assertFalse(mgr_list._is_verbose("alias"))

        mgr_true = ActionManager(interp, verbose=True)
        self.assertTrue(mgr_true._is_verbose("anything"))

        mgr_false = ActionManager(interp, verbose=False)
        self.assertFalse(mgr_false._is_verbose("anything"))

    def test_format_handles_keyerror_and_valueerror(self) -> None:
        interp = _DummyInterpreter()
        fmt = NamespaceFormatter({"A": "1"})
        mgr = ActionManager(interp, formatter=fmt.format)
        # Missing key triggers KeyError -> returns unformatted string
        self.assertEqual(mgr._format("{MISSING}"), "{MISSING}")
        # Malformed format string triggers ValueError -> returns unformatted string
        self.assertEqual(mgr._format("{A"), "{A")

    def test_expandvars(self) -> None:
        interp = _DummyInterpreter()
        fmt = NamespaceFormatter({"A": "hello"})
        mgr = ActionManager(interp, parent_environ={"P": "world"}, formatter=fmt.format)
        self.assertEqual(mgr.expandvars("{A}-${P}", format=True), "hello-world")
        self.assertEqual(mgr.expandvars("{A}-${P}", format=False), "{A}-world")

    def test_resetenv_expand_and_no_expand(self) -> None:
        # expand_env_vars = False
        interp_no = _DummyInterpreter()
        mgr_no = ActionManager(
            interp_no,
            parent_environ={"BASE": "b"},
            formatter=lambda x: str(x),
        )
        mgr_no.resetenv("MYVAR", "${BASE}/sub")
        self.assertEqual(mgr_no.environ["MYVAR"], "b/sub")
        self.assertEqual(mgr_no.actions[-1], Resetenv("MYVAR", "${BASE}/sub", None))
        self.assertEqual(interp_no.calls[-1], ("resetenv", "MYVAR", "${BASE}/sub", None))

        # expand_env_vars = True
        interp_yes = _ExpandingDummyInterpreter()
        mgr_yes = ActionManager(
            interp_yes,
            parent_environ={"BASE": "b"},
            formatter=lambda x: str(x),
        )
        mgr_yes.resetenv("MYVAR", "${BASE}/sub")
        self.assertEqual(mgr_yes.environ["MYVAR"], "b/sub")
        self.assertEqual(mgr_yes.actions[-1], Resetenv("MYVAR", "${BASE}/sub", None))
        self.assertEqual(interp_yes.calls[-1], ("resetenv", "MYVAR", "b/sub", None))

    @unittest.expectedFailure
    def test_resetenv_forwards_friends_to_interpreter(self) -> None:
        # Bug in src/rez/rex.py:361: ActionManager.resetenv calls
        # self.interpreter.resetenv(key, value) without forwarding friends.
        interp = _DummyInterpreter()
        mgr = ActionManager(
            interp,
            parent_environ={"BASE": "b"},
            formatter=lambda x: str(x),
        )
        mgr.resetenv("MYVAR", "${BASE}/sub", friends=["OTHER"])
        self.assertEqual(
            interp.calls[-1],
            ("resetenv", "MYVAR", "${BASE}/sub", ["OTHER"]),
        )

    def test_pendenv_no_expand_with_parent_variables(self) -> None:
        interp = _DummyInterpreter()
        mgr = ActionManager(
            interp,
            parent_environ={"PATH": "/usr/bin"},
            parent_variables=["PATH"],
            formatter=lambda x: str(x),
        )
        mgr.prependenv("PATH", "/custom/bin")
        self.assertIn(("_saferefenv", "PATH"), interp.calls)
        self.assertIn(
            ("setenv", "PATH", f"/custom/bin{os.pathsep}${{PATH}}"),
            interp.calls,
        )

    def test_stop_raises_rex_stop_error(self) -> None:
        ex = RexExecutor()
        with self.assertRaises(RexStopError) as ctx:
            ex.stop("halt: %s (%d)", "bad", 3)
        self.assertEqual(str(ctx.exception), "halt: bad (3)")


class TestActionInterpreterBase(TestBase):

    def test_abstract_and_default_methods(self) -> None:
        interp = ActionInterpreter()
        for fn, args in (
            (interp.get_output, ()),
            (interp.setenv, ("K", "V")),
            (interp.unsetenv, ("K",)),
            (interp.resetenv, ("K", "V")),
            (interp.prependenv, ("K", "V")),
            (interp.appendenv, ("K", "V")),
            (interp.alias, ("K", "V")),
            (interp.info, ("msg",)),
            (interp.error, ("msg",)),
            (interp.command, ("cmd",)),
            (interp.comment, ("msg",)),
            (interp.source, ("file.sh",)),
            (interp.shebang, ()),
            (interp.get_key_token, ("K",)),
            (interp._saferefenv, ("K",)),
            (interp._bind_interactive_rez, ()),
        ):
            with self.subTest(method=fn.__name__):
                with self.assertRaises(NotImplementedError):
                    fn(*args)

        self.assertEqual(interp.escape_string("abc"), "abc")
        self.assertEqual(interp.normalize_path("/a/b"), "/a/b")
        sep = interp.pathsep
        self.assertEqual(
            interp.normalize_paths(sep.join(["/a", "/b"])),
            sep.join(["/a", "/b"]),
        )


class TestPythonInterpreterExtra(TestBase):

    def test_apply_environ_without_manager_raises(self) -> None:
        interp = Python(target_environ={})
        with self.assertRaises(RezSystemError):
            interp.apply_environ()

    def test_update_session_pythonpath_mutations(self) -> None:
        with restore_os_environ(), restore_sys_path():
            interp = Python(target_environ=None)
            mgr = ActionManager(interp)
            interp.set_manager(mgr)

            interp.setenv("PYTHONPATH", os.pathsep.join(["/p1", "/p2"]))
            self.assertEqual(sys.path, ["/p1", "/p2"])

            interp.setenv("OTHER_VAR", "val")
            self.assertEqual(sys.path, ["/p1", "/p2"])

            interp.prependenv("PYTHONPATH", "/p0")
            self.assertEqual(sys.path[0], "/p0")
            interp.prependenv("OTHER_VAR", "val")
            self.assertEqual(sys.path, ["/p0", "/p1", "/p2"])

            interp.appendenv("PYTHONPATH", "/p3")
            self.assertEqual(sys.path[-1], "/p3")
            interp.appendenv("OTHER_VAR", "val")
            self.assertEqual(sys.path, ["/p0", "/p1", "/p2", "/p3"])

    def test_info_and_error_non_passive(self) -> None:
        interp = Python(target_environ={}, passive=False)
        out_buf = io.StringIO()
        err_buf = io.StringIO()
        with contextlib.redirect_stdout(out_buf), contextlib.redirect_stderr(err_buf):
            interp.info("hello out")
            interp.error("hello err")
        self.assertEqual(out_buf.getvalue().strip(), "hello out")
        self.assertEqual(err_buf.getvalue().strip(), "hello err")

    def test_command_passive_and_non_passive(self) -> None:
        # passive=True skips execution
        interp_passive = Python(target_environ={}, passive=True)
        with mock.patch("rez.rex.Popen") as mock_popen:
            interp_passive.command("echo hi")
            mock_popen.assert_not_called()

        # passive=False with string and iterable
        interp = Python(target_environ={}, passive=False)
        mgr = ActionManager(interp)
        interp.set_manager(mgr)

        fake_proc = mock.MagicMock()
        with mock.patch("rez.rex.Popen", return_value=fake_proc) as mock_popen:
            interp.command("echo hi")
            mock_popen.assert_called_once()
            self.assertTrue(mock_popen.call_args.kwargs["shell"])
            fake_proc.communicate.assert_called_once()

        fake_proc2 = mock.MagicMock()
        with mock.patch("rez.rex.Popen", return_value=fake_proc2) as mock_popen:
            interp.command(["echo", "hi"])
            mock_popen.assert_called_once()
            self.assertEqual(mock_popen.call_args.args[0], ["echo", "hi"])
            self.assertFalse(mock_popen.call_args.kwargs["shell"])
            fake_proc2.communicate.assert_called_once()

        # EscapedString disallowed
        with self.assertRaises(RexError):
            interp.command(literal("echo hi"))
        with self.assertRaises(RexError):
            interp.command([literal("echo"), "hi"])

        # Subprocess failure wrapped in RexError
        with mock.patch("rez.rex.Popen", side_effect=OSError("boom")):
            with self.assertRaises(RexError) as ctx:
                interp.command(["badcmd", "arg"])
            self.assertIn("Error executing command", str(ctx.exception))

        # subprocess with manager=None
        interp_no_mgr = Python(target_environ={}, passive=False)
        with mock.patch("rez.rex.Popen", return_value=fake_proc) as mock_popen:
            interp_no_mgr.subprocess("echo ok")
            mock_popen.assert_called_once()

    def test_noop_methods_and_win32_systemroot(self) -> None:
        interp = Python(target_environ={})
        interp.resetenv("K", "V")
        interp._bind_interactive_rez()

        # _add_systemroot_to_env_win32 branches
        interp._add_systemroot_to_env_win32(None)

        env_with_sr = {"SYSTEMROOT": "C:\\Win"}
        interp._add_systemroot_to_env_win32(env_with_sr)
        self.assertEqual(env_with_sr["SYSTEMROOT"], "C:\\Win")

        with restore_os_environ():
            os.environ.pop("SYSTEMROOT", None)
            env_empty = {}
            interp._add_systemroot_to_env_win32(env_empty)
            self.assertNotIn("SYSTEMROOT", env_empty)

            os.environ["SYSTEMROOT"] = "C:\\Windows"
            interp._add_systemroot_to_env_win32(env_empty)
            self.assertEqual(env_empty["SYSTEMROOT"], "C:\\Windows")


class TestEscapedStringExtra(TestBase):

    def test_repr_eq_ne(self) -> None:
        s1 = literal("foo")
        s2 = literal("foo")
        s3 = expandable("foo")
        self.assertEqual(repr(s1), "EscapedString([(True, 'foo')])")
        self.assertTrue(s1 == "foo")
        self.assertTrue(s1 == s2)
        self.assertFalse(s1 == s3)
        self.assertFalse(s1 == 123)
        self.assertTrue(s1 != s3)
        self.assertFalse(s1 != s2)

    def test_split_across_literal_and_expandable(self) -> None:
        s = literal("a:b").expandable(":c:d").literal("e")
        parts = s.split(":")
        self.assertEqual(len(parts), 4)
        self.assertEqual(parts[0], literal("a"))
        self.assertEqual(parts[1], literal("b").expandable(""))
        self.assertEqual(parts[2], expandable("c"))
        self.assertEqual(parts[3], expandable("d").literal("e"))

        # Trailing delimiter leaves current=None at loop end
        self.assertEqual(literal("a:").split(":"), [literal("a"), literal("")])
        # Empty EscapedString split
        self.assertEqual(literal("").split(":"), [literal("")])
        empty_es = literal("")
        empty_es.strings = []
        self.assertEqual(empty_es.split(":"), [])

    def test_join_empty_demote_disallow(self) -> None:
        joined = EscapedString.join(":", [])
        self.assertEqual(joined, expandable(""))

        self.assertEqual(EscapedString.demote(literal("abc")), "abc")
        self.assertEqual(EscapedString.demote("abc"), "abc")

        self.assertEqual(EscapedString.disallow("plain"), "plain")
        with self.assertRaises(RexError):
            EscapedString.disallow(literal("nope"))


class TestOptionvarsAndFormatter(TestBase):

    def test_optionvars(self) -> None:
        self.update_settings({"optionvars": {"a": {"b": 42}, "scalar": "hi"}})
        self.assertEqual(optionvars("a.b"), 42)
        self.assertEqual(optionvars("a.missing", default="fallback"), "fallback")
        self.assertIsNone(optionvars("missing"))
        with self.assertRaises(RexError):
            optionvars("scalar.nested")

        self.update_settings({"optionvars": None})
        self.assertEqual(optionvars("anything", default="d"), "d")

    def test_namespace_formatter_edge_cases(self) -> None:
        fmt = NamespaceFormatter({"lit": literal("val"), "num": 7})
        self.assertEqual(fmt.format("{lit}"), "val")
        self.assertEqual(fmt.format("{num}"), "7")
        self.assertEqual(fmt.format("{0}", "pos"), "pos")
        with self.assertRaises(ValueError):
            fmt.get_value("", (), {})


class TestEnvironmentDictAndVarExtra(TestBase):

    def test_environment_dict_mapping_ops(self) -> None:
        ex = RexExecutor(parent_environ={"A": "1", "B": "2"})
        self.assertEqual(set(ex.environ.keys()), {"A", "B"})
        self.assertIn("EnvironmentDict(", repr(ex.environ))
        self.assertEqual(len(ex.environ), 2)
        self.assertEqual(set(iter(ex.environ)), {"A", "B"})
        del ex.environ["A"]
        self.assertNotIn("A", ex.environ)
        self.assertEqual(len(ex.environ), 1)

    def test_environment_variable_methods(self) -> None:
        ex = RexExecutor(parent_environ={"EXISTING": "yes"})
        var_existing = ex.environ["EXISTING"]
        self.assertEqual(repr(var_existing), "EnvironmentVariable('EXISTING', 'yes')")
        var_existing.setdefault("no")
        self.assertEqual(var_existing.value(), "yes")

        var_new = ex.environ["NEW_VAR"]
        var_new.setdefault("init")
        self.assertEqual(var_new.value(), "init")

        var_new.reset("reset_val", friends=["EXISTING"])
        self.assertEqual(var_new.value(), "reset_val")
        self.assertIsInstance(ex.actions[-1], Resetenv)

        self.assertTrue(var_new != "other")
        self.assertFalse(var_new != "reset_val")
        self.assertTrue(var_new != var_existing)


class TestRexExecutorExtra(TestBase):

    def test_default_interpreter_and_getattr(self) -> None:
        ex = RexExecutor()
        self.assertIsInstance(ex.interpreter, Python)
        self.assertIsInstance(ex.actions[0], Shebang)
        with self.assertRaises(AttributeError):
            _ = ex.this_attribute_does_not_exist

    def test_rez_bin_path_helpers(self) -> None:
        ex = RexExecutor(shebang=False)
        with mock.patch.object(system, "rez_bin_path", "/rez/bin"):
            ex.prepend_rez_path()
            ex.append_rez_path()
        self.assertEqual(
            ex.get_output()["PATH"],
            os.pathsep.join(["/rez/bin", "/rez/bin"]),
        )

        ex_none = RexExecutor(shebang=False)
        with mock.patch.object(system, "rez_bin_path", None):
            ex_none.prepend_rez_path()
            ex_none.append_rez_path()
        self.assertEqual(ex_none.actions, [])

    def test_compile_code_sourcecode_and_errors(self) -> None:
        # exec_namespace=None compiles without executing
        pyc = RexExecutor.compile_code("x = 1", exec_namespace=None)
        self.assertIsInstance(pyc, types.CodeType)

        # SyntaxError in plain string -> RexError
        with self.assertRaises(RexError) as ctx:
            RexExecutor.compile_code("def broken(:", filename="bad.py")
        self.assertIn("Failed to compile bad.py", str(ctx.exception))

        # SourceCode with filename=None and valid exec
        sc_ok = SourceCode("FOO = 123", eval_as_function=False)
        ns = {}
        RexExecutor.compile_code(sc_ok, exec_namespace=ns)
        self.assertEqual(ns["FOO"], 123)

    @unittest.expectedFailure
    def test_compile_code_sourcecode_errors_reraise_as_rex_error(self) -> None:
        # Bug in src/rez/utils/__init__.py:15-29 & src/rez/rex.py:1452-1453,1469-1470:
        # reraise(e, RexError) ignores RexError and re-raises SourceCodeError.
        sc_bad_syntax = SourceCode("def broken(:", eval_as_function=False)
        with self.assertRaises(RexError):
            RexExecutor.compile_code(sc_bad_syntax)

        sc_bad_exec = SourceCode("raise RuntimeError('boom')", eval_as_function=False)
        with self.assertRaises(RexError):
            RexExecutor.compile_code(sc_bad_exec, exec_namespace={})
