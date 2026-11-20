# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Unit tests for 'rez.utils.platform_' module.
"""
import ctypes
from ctypes import wintypes
import os
import platform
import tempfile
import types
import unittest
import unittest.mock

from rez.exceptions import RezSystemError
from rez.tests.util import TestBase
from rez.utils.platform_ import (
    LinuxPlatform,
    OSXPlatform,
    Platform,
    WindowsPlatform,
)


def _make_proc(stdout="", stderr="", returncode=0):
    proc = unittest.mock.Mock()
    proc.returncode = returncode
    proc.communicate.return_value = (stdout, stderr)
    return proc


class TestPlatformBase(TestBase):
    """Tests for the abstract Platform base class."""

    def test_not_implemented_methods(self):
        plat = Platform()
        for method_name in (
            "_os",
            "_terminal_emulator_command",
            "_new_session_popen_args",
            "_image_viewer",
            "_editor",
            "_difftool",
            "_physical_cores",
        ):
            with self.subTest(method=method_name):
                with self.assertRaises(NotImplementedError):
                    getattr(plat, method_name)()

    def test_physical_cores_exception_defaults_to_one(self):
        plat = Platform()
        with unittest.mock.patch.object(
            plat, "_physical_cores_base", side_effect=RuntimeError("boom")
        ), unittest.mock.patch("rez.utils.logging_.print_error") as mock_err:
            self.assertEqual(plat.physical_cores, 1)
            mock_err.assert_called_once()
            self.assertIn("boom", mock_err.call_args[0][0])

    def test_logical_cores_exception_defaults_to_one(self):
        plat = Platform()
        with unittest.mock.patch.object(
            plat, "_logical_cores", side_effect=RuntimeError("no cpus")
        ), unittest.mock.patch("rez.utils.logging_.print_error") as mock_err:
            self.assertEqual(plat.logical_cores, 1)
            mock_err.assert_called_once()
            self.assertIn("no cpus", mock_err.call_args[0][0])

    def test_physical_cores_base_single_logical_core(self):
        plat = Platform()
        with unittest.mock.patch.object(plat, "_logical_cores", return_value=1), \
             unittest.mock.patch.object(plat, "_physical_cores") as mock_phys:
            self.assertEqual(plat.physical_cores, 1)
            mock_phys.assert_not_called()

    def test_physical_cores_base_falls_back_to_logical_when_none(self):
        plat = Platform()
        with unittest.mock.patch.object(plat, "_logical_cores", return_value=4), \
             unittest.mock.patch.object(plat, "_physical_cores", return_value=None), \
             unittest.mock.patch("rez.utils.logging_.print_warning") as mock_warn:
            self.assertEqual(plat.physical_cores, 4)
            mock_warn.assert_called_once()

    def test_symlink_delegates_to_os_symlink(self):
        plat = Platform()
        with unittest.mock.patch("rez.utils.platform_.os.symlink") as mock_symlink:
            plat.symlink("/src/path", "/dst/path")
            mock_symlink.assert_called_once_with("/src/path", "/dst/path")

    def test_basic_properties(self):
        plat = Platform()
        self.assertTrue(plat.has_case_sensitive_filesystem)
        self.assertEqual(plat.arch, platform.machine())
        self.assertEqual(plat.tmpdir, tempfile.gettempdir())
        self.assertTrue(os.path.isdir(plat.tmpdir))


class TestLinuxPlatform(TestBase):
    """Tests for LinuxPlatform."""

    def test_os_from_lsb_release_file_with_quotes(self):
        plat = LinuxPlatform()
        lsb_txt = 'DISTRIB_ID="Ubuntu"\nDISTRIB_RELEASE=\'22.04\'\n'
        with unittest.mock.patch(
            "rez.utils.platform_.os.path.isfile",
            side_effect=lambda p: p == "/etc/lsb-release",
        ), unittest.mock.patch(
            "rez.utils.platform_.open",
            unittest.mock.mock_open(read_data=lsb_txt),
            create=True,
        ):
            self.assertEqual(plat._os(), "Ubuntu-22.04")

    def test_os_from_lsb_release_command_after_incomplete_file(self):
        plat = LinuxPlatform()
        # /etc/lsb-release has only DISTRIB_ID (no release), so _os() falls
        # through to `lsb_release -a` which supplies Release.
        lsb_txt = "DISTRIB_ID=CustomDistro\n"
        cmd_out = "Distributor ID:\tIgnored\nRelease:\t9.1\n"
        with unittest.mock.patch(
            "rez.utils.platform_.os.path.isfile",
            side_effect=lambda p: p == "/etc/lsb-release",
        ), unittest.mock.patch(
            "rez.utils.platform_.open",
            unittest.mock.mock_open(read_data=lsb_txt),
            create=True,
        ), unittest.mock.patch(
            "rez.utils.platform_.Popen",
            return_value=_make_proc(stdout=cmd_out, returncode=0),
        ):
            self.assertEqual(plat._os(), "CustomDistro-9.1")

    def test_os_from_lsb_release_command_alone(self):
        plat = LinuxPlatform()
        cmd_out = "Distributor ID:\tDebian\nRelease:\t12\n"
        with unittest.mock.patch(
            "rez.utils.platform_.os.path.isfile", return_value=False
        ), unittest.mock.patch(
            "rez.utils.platform_.Popen",
            return_value=_make_proc(stdout=cmd_out, returncode=0),
        ):
            self.assertEqual(plat._os(), "Debian-12")

    def test_os_from_lsb_release_command_incomplete_falls_through(self):
        plat = LinuxPlatform()
        cmd_out = "Distributor ID:\t\n"
        os_rel_txt = 'ID="fedora"\nVERSION_ID="39"\n'
        with unittest.mock.patch(
            "rez.utils.platform_.os.path.isfile",
            side_effect=lambda p: p == "/etc/os-release",
        ), unittest.mock.patch(
            "rez.utils.platform_.open",
            unittest.mock.mock_open(read_data=os_rel_txt),
            create=True,
        ), unittest.mock.patch(
            "rez.utils.platform_.Popen",
            return_value=_make_proc(stdout=cmd_out, returncode=0),
        ):
            self.assertEqual(plat._os(), "fedora-39")

    def test_os_from_os_release_file(self):
        plat = LinuxPlatform()
        os_rel_txt = 'NAME="Rocky Linux"\nID="rocky"\nVERSION_ID="9.3"\n'
        with unittest.mock.patch(
            "rez.utils.platform_.os.path.isfile",
            side_effect=lambda p: p == "/etc/os-release",
        ), unittest.mock.patch(
            "rez.utils.platform_.open",
            unittest.mock.mock_open(read_data=os_rel_txt),
            create=True,
        ), unittest.mock.patch(
            "rez.utils.platform_.Popen",
            return_value=_make_proc(returncode=1),
        ):
            self.assertEqual(plat._os(), "rocky-9.3")

    def test_os_from_distro_fallback(self):
        plat = LinuxPlatform()
        with unittest.mock.patch(
            "rez.utils.platform_.os.path.isfile", return_value=False
        ), unittest.mock.patch(
            "rez.utils.platform_.Popen",
            return_value=_make_proc(returncode=1),
        ), unittest.mock.patch(
            "rez.vendor.distro.distro.linux_distribution",
            return_value=("arch", "rolling", ""),
        ):
            self.assertEqual(plat._os(), "arch-rolling")

    def test_os_distro_empty_raises_rez_system_error(self):
        plat = LinuxPlatform()
        with unittest.mock.patch(
            "rez.utils.platform_.os.path.isfile", return_value=False
        ), unittest.mock.patch(
            "rez.utils.platform_.Popen",
            return_value=_make_proc(returncode=1),
        ), unittest.mock.patch(
            "rez.vendor.distro.distro.linux_distribution",
            return_value=("", "", ""),
        ):
            with self.assertRaises(RezSystemError):
                plat._os()

    def test_terminal_emulator_command(self):
        plat = LinuxPlatform()
        cases = [
            (None, None),
            ("/usr/bin/x-terminal-emulator", "x-terminal-emulator --noclose -e"),
            ("/usr/bin/konsole", "konsole --noclose -e"),
            ("/usr/bin/xterm", "xterm -hold -e"),
        ]
        for which_ret, expected in cases:
            with self.subTest(which_ret=which_ret):
                with unittest.mock.patch(
                    "rez.utils.platform_.which", return_value=which_ret
                ):
                    self.assertEqual(plat._terminal_emulator_command(), expected)

    def test_editor_with_and_without_env(self):
        plat = LinuxPlatform()
        with unittest.mock.patch.dict(os.environ, {"EDITOR": "nano"}):
            self.assertEqual(plat._editor(), "nano")

        env_without_editor = {k: v for k, v in os.environ.items() if k != "EDITOR"}
        with unittest.mock.patch.dict(os.environ, env_without_editor, clear=True), \
             unittest.mock.patch("rez.util.which", return_value="/usr/bin/vim"):
            self.assertEqual(plat._editor(), "/usr/bin/vim")

    def test_physical_cores_from_cpuinfo_missing_file(self):
        plat = LinuxPlatform()
        with unittest.mock.patch(
            "rez.utils.platform_.os.path.isfile", return_value=False
        ):
            self.assertIsNone(plat._physical_cores_from_cpuinfo())

    def test_physical_cores_from_cpuinfo_no_processors(self):
        plat = LinuxPlatform()
        with unittest.mock.patch(
            "rez.utils.platform_.os.path.isfile", return_value=True
        ), unittest.mock.patch(
            "rez.utils.platform_.open",
            unittest.mock.mock_open(read_data="Hardware\t: unknown\n"),
            create=True,
        ):
            self.assertIsNone(plat._physical_cores_from_cpuinfo())

    def test_physical_cores_from_cpuinfo_single_processor(self):
        plat = LinuxPlatform()
        cpuinfo = "processor\t: 0\nmodel name\t: Test CPU\n"
        with unittest.mock.patch(
            "rez.utils.platform_.os.path.isfile", return_value=True
        ), unittest.mock.patch(
            "rez.utils.platform_.open",
            unittest.mock.mock_open(read_data=cpuinfo),
            create=True,
        ):
            self.assertEqual(plat._physical_cores_from_cpuinfo(), 1)

    def test_physical_cores_from_cpuinfo_missing_ids(self):
        plat = LinuxPlatform()
        cpuinfo = (
            "processor\t: 0\nmodel name\t: Test\n\n"
            "processor\t: 1\nmodel name\t: Test\n"
        )
        with unittest.mock.patch(
            "rez.utils.platform_.os.path.isfile", return_value=True
        ), unittest.mock.patch(
            "rez.utils.platform_.open",
            unittest.mock.mock_open(read_data=cpuinfo),
            create=True,
        ):
            self.assertIsNone(plat._physical_cores_from_cpuinfo())

    def test_physical_cores_from_cpuinfo_hyperthreaded(self):
        plat = LinuxPlatform()
        cpuinfo = (
            "processor\t: 0\nphysical id\t: 0\ncore id\t\t: 0\n\n"
            "processor\t: 1\nphysical id\t: 0\ncore id\t\t: 0\n\n"
            "processor\t: 2\nphysical id\t: 0\ncore id\t\t: 1\n\n"
            "processor\t: 3\nphysical id\t: 0\ncore id\t\t: 1\n"
        )
        with unittest.mock.patch(
            "rez.utils.platform_.os.path.isfile", return_value=True
        ), unittest.mock.patch(
            "rez.utils.platform_.open",
            unittest.mock.mock_open(read_data=cpuinfo),
            create=True,
        ):
            self.assertEqual(plat._physical_cores_from_cpuinfo(), 2)

    def test_physical_cores_from_lscpu(self):
        plat = LinuxPlatform()
        with unittest.mock.patch(
            "rez.utils.platform_.Popen", side_effect=OSError("missing")
        ):
            self.assertIsNone(plat._physical_cores_from_lscpu())

        with unittest.mock.patch(
            "rez.utils.platform_.Popen", return_value=_make_proc(returncode=1)
        ):
            self.assertIsNone(plat._physical_cores_from_lscpu())

        lscpu_out = (
            "CPU(s):                24\n"
            "Thread(s) per core:    2\n"
            "Core(s) per socket:    6\n"
            "Socket(s):             2\n"
        )
        with unittest.mock.patch(
            "rez.utils.platform_.Popen",
            return_value=_make_proc(stdout=lscpu_out, returncode=0),
        ):
            self.assertEqual(plat._physical_cores_from_lscpu(), 12)

        lscpu_alt = "CPU socket(s): 2\nCore(s) per socket: 4\n"
        with unittest.mock.patch(
            "rez.utils.platform_.Popen",
            return_value=_make_proc(stdout=lscpu_alt, returncode=0),
        ):
            self.assertEqual(plat._physical_cores_from_lscpu(), 8)

        with unittest.mock.patch(
            "rez.utils.platform_.Popen",
            return_value=_make_proc(stdout="CPU(s): 4\n", returncode=0),
        ):
            self.assertIsNone(plat._physical_cores_from_lscpu())

        with unittest.mock.patch(
            "rez.utils.platform_.Popen",
            return_value=_make_proc(stdout="Socket(s): 2\n", returncode=0),
        ):
            self.assertIsNone(plat._physical_cores_from_lscpu())

    def test_physical_cores_falls_back_to_lscpu(self):
        plat = LinuxPlatform()
        with unittest.mock.patch.object(
            plat, "_physical_cores_from_cpuinfo", return_value=None
        ), unittest.mock.patch.object(
            plat, "_physical_cores_from_lscpu", return_value=8
        ) as mock_lscpu:
            self.assertEqual(plat._physical_cores(), 8)
            mock_lscpu.assert_called_once()


class TestOSXPlatform(TestBase):
    """Tests for OSXPlatform."""

    def test_os_and_simple_tools(self):
        plat = OSXPlatform()
        with unittest.mock.patch(
            "rez.utils.platform_.platform.mac_ver",
            return_value=("14.2.1", ("", "", ""), "arm64"),
        ):
            self.assertEqual(plat._os(), "osx-14.2.1")
        self.assertEqual(plat._image_viewer(), "open")
        self.assertEqual(plat._editor(), "open")
        with unittest.mock.patch("rez.util.which", return_value="/usr/bin/diff"):
            self.assertEqual(plat._difftool(), "/usr/bin/diff")

    def test_terminal_emulator_command(self):
        plat = OSXPlatform()
        cases = [
            (None, None),
            ("/usr/local/bin/x-terminal-emulator", "x-terminal-emulator --noclose -e"),
            ("/opt/X11/bin/xterm", "xterm -hold -e"),
        ]
        for which_ret, expected in cases:
            with self.subTest(which_ret=which_ret):
                with unittest.mock.patch(
                    "rez.utils.platform_.which", return_value=which_ret
                ):
                    self.assertEqual(plat._terminal_emulator_command(), expected)

    def test_physical_cores_from_osx_sysctl(self):
        plat = OSXPlatform()
        with unittest.mock.patch(
            "rez.utils.platform_.Popen", side_effect=OSError("missing")
        ):
            self.assertIsNone(plat._physical_cores())

        with unittest.mock.patch(
            "rez.utils.platform_.Popen", return_value=_make_proc(returncode=1)
        ):
            self.assertIsNone(plat._physical_cores())

        with unittest.mock.patch(
            "rez.utils.platform_.Popen",
            return_value=_make_proc(stdout="10\n", returncode=0),
        ):
            self.assertEqual(plat._physical_cores(), 10)


class TestWindowsPlatform(TestBase):
    """Tests for WindowsPlatform (cross-platform via boundary mocks)."""

    def test_os_with_and_without_csd(self):
        plat = WindowsPlatform()
        with unittest.mock.patch(
            "rez.utils.platform_.platform.win32_ver",
            return_value=("10", "10.0.19041", "", "Multiprocessor Free"),
        ):
            self.assertEqual(plat._os(), "windows-10.0.19041")

        with unittest.mock.patch(
            "rez.utils.platform_.platform.win32_ver",
            return_value=("7", "6.1.7601", "SP1", "Multiprocessor Free"),
        ):
            self.assertEqual(plat._os(), "windows-6.1.7601.SP1")

    def test_simple_properties(self):
        plat = WindowsPlatform()
        self.assertFalse(plat.has_case_sensitive_filesystem)
        self.assertEqual(plat._image_viewer(), "")
        self.assertEqual(plat._editor(), "")
        self.assertEqual(plat._new_session_popen_args(), {"creationflags": 0x00000010})
        self.assertEqual(plat._terminal_emulator_command(), "START")
        with unittest.mock.patch("rez.util.which", return_value="C:\\Windows\\System32\\fc.exe"):
            self.assertEqual(plat._difftool(), "C:\\Windows\\System32\\fc.exe")

    def test_symlink_uses_os_symlink_when_callable(self):
        plat = WindowsPlatform()
        with unittest.mock.patch("rez.utils.platform_.os.symlink") as mock_symlink:
            plat.symlink("C:\\src", "C:\\dst")
            mock_symlink.assert_called_once_with("C:\\src", "C:\\dst")

    def test_symlink_win10_uses_mklink(self):
        plat = WindowsPlatform()
        fake_os = types.SimpleNamespace(symlink=None, path=os.path)
        with unittest.mock.patch("rez.utils.platform_.os", fake_os), unittest.mock.patch(
            "rez.utils.platform_.platform.platform",
            return_value="Windows-10-10.0.19041-SP0",
        ), unittest.mock.patch(
            "rez.utils.platform_.subprocess.check_output"
        ) as mock_check_output:
            plat.symlink("C:\\src", "C:\\dst")
            mock_check_output.assert_called_once_with(
                "mklink C:\\dst C:\\src", shell=True
            )

    def test_symlink_ctypes_fallback_success_and_error(self):
        plat = WindowsPlatform()
        fake_os = types.SimpleNamespace(
            symlink=None,
            path=types.SimpleNamespace(isdir=lambda p: p.endswith("dir")),
        )
        csl = unittest.mock.Mock(return_value=1)
        fake_windll = types.SimpleNamespace(
            kernel32=types.SimpleNamespace(CreateSymbolicLinkW=csl)
        )

        class FakeWinError(OSError):
            pass

        with unittest.mock.patch("rez.utils.platform_.os", fake_os), unittest.mock.patch(
            "rez.utils.platform_.platform.platform",
            return_value="Windows-7-6.1.7601-SP1",
        ), unittest.mock.patch.object(
            ctypes, "windll", fake_windll, create=True
        ), unittest.mock.patch.object(
            ctypes, "WinError", FakeWinError, create=True
        ):
            plat.symlink("C:\\src_dir", "C:\\dst_dir")
            csl.assert_called_once_with("C:\\dst_dir", "C:\\src_dir", 1)

            csl.reset_mock()
            csl.return_value = 0
            with self.assertRaises(FakeWinError):
                plat.symlink("C:\\src_file", "C:\\dst_file")
            csl.assert_called_once_with("C:\\dst_file", "C:\\src_file", 0)

    def test_physical_cores_native_exception_returns_none(self):
        plat = WindowsPlatform()
        with unittest.mock.patch.object(
            ctypes, "WinDLL", side_effect=OSError("no kernel32"), create=True
        ):
            self.assertIsNone(plat._physical_cores_native())

    def test_physical_cores_native_error_branches(self):
        plat = WindowsPlatform()
        ERROR_INSUFFICIENT_BUFFER = 0x7A

        def run_with_api(api_fn, last_error=ERROR_INSUFFICIENT_BUFFER):
            kernel32 = types.SimpleNamespace(GetLogicalProcessorInformationEx=api_fn)
            with unittest.mock.patch.object(
                ctypes, "WinDLL", return_value=kernel32, create=True
            ), unittest.mock.patch.object(
                ctypes, "get_last_error", return_value=last_error, create=True
            ):
                return plat._physical_cores_native()

        # 1. First call unexpectedly succeeds -> None (line 587)
        self.assertIsNone(run_with_api(lambda rel, buf, sz: 1))

        # 2. First call fails with unexpected error -> None (line 591)
        self.assertIsNone(run_with_api(lambda rel, buf, sz: 0, last_error=0x05))

        # 3. First call sets buffer_size = 0 -> None (line 595)
        def zero_size(rel, buf, sz):
            sz._obj.value = 0
            return 0

        self.assertIsNone(run_with_api(zero_size))

        # 4. Second call fails -> None (line 605)
        def second_fails(rel, buf, sz):
            if buf is None:
                sz._obj.value = 16
                return 0
            return 0

        self.assertIsNone(run_with_api(second_fails))

    def test_physical_cores_native_parses_buffer(self):
        plat = WindowsPlatform()
        ERROR_INSUFFICIENT_BUFFER = 0x7A

        class Entry(ctypes.Structure):
            _fields_ = [
                ("Relationship", ctypes.c_int),
                ("Size", wintypes.DWORD),
            ]

        entry_size = ctypes.sizeof(Entry)
        # Two RelationProcessorCore (0) entries and one non-core (3) entry
        raw = b"".join(
            bytes(Entry(rel, entry_size)) for rel in (0, 3, 0)
        )

        def api_fn(rel, buf, sz):
            if buf is None:
                sz._obj.value = len(raw)
                return 0
            ctypes.memmove(buf, raw, len(raw))
            return 1

        kernel32 = types.SimpleNamespace(GetLogicalProcessorInformationEx=api_fn)
        with unittest.mock.patch.object(
            ctypes, "WinDLL", return_value=kernel32, create=True
        ), unittest.mock.patch.object(
            ctypes, "get_last_error", return_value=ERROR_INSUFFICIENT_BUFFER, create=True
        ):
            self.assertEqual(plat._physical_cores_native(), 2)

    def test_physical_cores_powershell_and_wmic_and_chain(self):
        plat = WindowsPlatform()
        with unittest.mock.patch(
            "rez.utils.platform_.Popen", side_effect=OSError("no ps")
        ):
            self.assertIsNone(plat._physical_cores_from_powershell())
            self.assertIsNone(plat._physical_cores_from_wmic())

        with unittest.mock.patch(
            "rez.utils.platform_.Popen", return_value=_make_proc(returncode=1)
        ):
            self.assertIsNone(plat._physical_cores_from_powershell())
            self.assertIsNone(plat._physical_cores_from_wmic())

        with unittest.mock.patch(
            "rez.utils.platform_.Popen",
            return_value=_make_proc(stdout="bad\n", returncode=0),
        ):
            self.assertIsNone(plat._physical_cores_from_powershell())
            self.assertIsNone(plat._physical_cores_from_wmic())

        with unittest.mock.patch(
            "rez.utils.platform_.Popen",
            return_value=_make_proc(stdout="4\n", returncode=0),
        ):
            self.assertEqual(plat._physical_cores_from_powershell(), 4)

        wmic_out = "NumberOfCores=6\r\n\r\nNumberOfCores=6\r\n\r\n"
        with unittest.mock.patch(
            "rez.utils.platform_.Popen",
            return_value=_make_proc(stdout=wmic_out, returncode=0),
        ):
            self.assertEqual(plat._physical_cores_from_wmic(), 12)

        with unittest.mock.patch.object(
            plat, "_physical_cores_native", return_value=None
        ), unittest.mock.patch.object(
            plat, "_physical_cores_from_powershell", return_value=None
        ), unittest.mock.patch.object(
            plat, "_physical_cores_from_wmic", return_value=8
        ):
            self.assertEqual(plat._physical_cores(), 8)
