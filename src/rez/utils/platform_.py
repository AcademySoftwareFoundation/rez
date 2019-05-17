import platform
import sys
import os
import os.path
import re
from rez.util import which
from rez.utils.system import popen
from rez.utils.data_utils import cached_property
from rez.utils.platform_mapped import platform_mapped
from rez.exceptions import RezSystemError
from tempfile import gettempdir


class Platform(object):
    """Abstraction of a platform.
    """
    name = None

    def __init__(self):
        pass

    @cached_property
    @platform_mapped
    def arch(self):
        """Returns the name of the architecture."""
        return self._arch()

    @cached_property
    @platform_mapped
    def os(self):
        """Returns the name of the operating system."""
        return self._os()

    @cached_property
    def terminal_emulator_command(self):
        """Returns the command to use to run another command in a separate
        terminal emulator.

        The command is expected to have the target command and arguments
        appended to it.

        Returns:
            List of strings, or None if the terminal emulator could not be
            determined.
        """
        return self._terminal_emulator_command()

    @cached_property
    def new_session_popen_args(self):
        """Return the arguments to pass to subprocess.Popen in order to execute
        a shell in a new process group.

        Returns:
            Dict: kwargs to pass to subprocess.Popen.
        """
        return self._new_session_popen_args()

    @cached_property
    def image_viewer(self):
        """Returns the system default image viewer.

        If None, rez will use the web browser to display images.
        """
        return self._image_viewer()

    @cached_property
    def editor(self):
        """Returns the system default text editor."""
        return self._editor()

    @cached_property
    def difftool(self):
        """Return the system default file diff tool."""
        return self._difftool()

    @cached_property
    def tmpdir(self):
        """Return system default temporary directory path."""
        return self._tmpdir()

    @cached_property
    def physical_cores(self):
        """Return the number of physical cpu cores on the system."""
        try:
            return self._physical_cores_base()
        except Exception as e:
            from rez.utils.logging_ import print_error
            print_error(
                "Error detecting physical core count, defaulting to 1: %s" % e
            )
        return 1

    @cached_property
    def logical_cores(self):
        """Return the number of cpu cores as reported to the os.

        May be different from physical_cores if, ie, intel's hyperthreading is
        enabled.
        """
        try:
            return self._logical_cores()
        except Exception as e:
            from rez.utils.logging_ import print_error
            print_error(
                "Error detecting logical core count, defaulting to 1: %s" % e
            )
        return 1

    # -- implementation

    def _arch(self):
        return platform.machine()

    def _os(self):
        raise NotImplementedError

    def _terminal_emulator_command(self):
        raise NotImplementedError

    def _new_session_popen_args(self):
        raise NotImplementedError

    def _image_viewer(self):
        raise NotImplementedError

    def _editor(self):
        raise NotImplementedError

    def _difftool(self):
        raise NotImplementedError

    def _tmpdir(self):
        return gettempdir()

    def symlink(self, source, link_name):
        """Create a symbolic link pointing to source named link_name."""
        os.symlink(source, link_name)

    def _physical_cores_base(self):
        if self.logical_cores == 1:
            # if we only have one core, we only have one core... no need to
            # bother with platform-specific stuff...

            # we do this check for all because on some platforms, the output
            # of various commands (dmesg, lscpu, /proc/cpuinfo) can be
            # very different if there's only one cpu, and don't want to have
            # to deal with that case
            return 1
        cores = self._physical_cores()
        if cores is None:
            from rez.utils.logging_ import print_warning
            print_warning("Could not determine number of physical cores - "
                          "falling back on logical cores value")
            cores = self.logical_cores
        return cores

    def _physical_cores(self):
        raise NotImplementedError

    def _logical_cores(self):
        try:
            # Favour Python 3
            return os.cpu_count()

        except AttributeError:
            import multiprocessing
            return multiprocessing.cpu_count()


# -----------------------------------------------------------------------------
# Unix (Linux and OSX)
# -----------------------------------------------------------------------------

class _UnixPlatform(Platform):
    def _new_session_popen_args(self):
        return dict(preexec_fn=os.setpgrp)


# -----------------------------------------------------------------------------
# Linux
# -----------------------------------------------------------------------------

class LinuxPlatform(_UnixPlatform):
    name = "linux"

    def _os(self):
        distributor = None
        release = None

        def _str(s):
            if (s.startswith("'") and s.endswith("'")) \
                    or (s.startswith('"') and s.endswith('"')):
                return s[1:-1]
            else:
                return s

        def _os():
            if distributor and release:
                return "%s-%s" % (distributor, release)
            else:
                return None

        def _parse(txt, distributor_key, release_key):
            distributor_ = None
            release_ = None
            lines = txt.strip().split('\n')
            for line in lines:
                if line.startswith(distributor_key):
                    s = line[len(distributor_key):].strip()
                    distributor_ = _str(s)
                elif line.startswith(release_key):
                    s = line[len(release_key):].strip()
                    release_ = _str(s)
            return distributor_, release_

        # first try parsing the /etc/lsb-release file
        file = "/etc/lsb-release"
        if os.path.isfile(file):
            with open(file) as f:
                txt = f.read()
            distributor, release = _parse(txt,
                                          "DISTRIB_ID=",
                                          "DISTRIB_RELEASE=")
            result = _os()
            if result:
                return result

        # next, try getting the output of the lsb_release program
        import subprocess

        p = popen(['/usr/bin/env', 'lsb_release', '-a'],
                  universal_newlines=True,
                  stdout=subprocess.PIPE,
                  stderr=subprocess.PIPE)
        txt = p.communicate()[0]

        if not p.returncode:
            distributor_, release_ = _parse(txt,
                                            "Distributor ID:",
                                            "Release:")
            if distributor_ and not distributor:
                distributor = distributor_
            if release_ and not release:
                release = release_

            result = _os()
            if result:
                return result

        # try to read the /etc/os-release file
        # this file contains OS specific data on linux
        # distributions
        # see https://www.freedesktop.org/software/systemd/man/os-release.html
        os_release = '/etc/os-release'
        if os.path.isfile(os_release):
            with open(os_release, 'r') as f:
                txt = f.read()
            distributor_, release_ = _parse(txt,
                                            "ID=",
                                            "VERSION_ID=")
            if distributor_ and not distributor:
                distributor = distributor_
            if release_ and not release:
                release = release_

            result = _os()
            if result:
                return result

        # last, use python's dist detection. It is known to return incorrect
        # info on some systems though
        try:
            distributor_, release_, _ = platform.linux_distribution()
        except:
            distributor_, release_, _ = platform.dist()

        if distributor_ and not distributor:
            distributor = distributor_
        if release_ and not release:
            release = release_

        result = _os()
        if result:
            return result

        # last resort, accept missing release
        if distributor:
            return distributor

        # give up
        raise RezSystemError("cannot detect operating system")

    def _terminal_emulator_command(self):
        term = which("x-terminal-emulator", "xterm", "konsole")
        if term is None:
            return None

        term = os.path.basename(term)
        if term in ("x-terminal-emulator", "konsole"):
            return "%s --noclose -e" % term
        else:
            return "%s -hold -e" % term

    def _image_viewer(self):
        return which("xdg-open", "eog", "kview")

    def _editor(self):
        ed = os.getenv("EDITOR")
        if ed is None:
            ed = which("xdg-open", "vim", "vi")
        return ed

    def _difftool(self):
        return which("kdiff3", "meld", "diff")

    @classmethod
    def _parse_colon_table_to_dict(cls, table_text):
        '''Given a simple text output where each line gives a key-value pair
      of the form "key: value", parse and return a dict'''
        lines = [l.strip() for l in table_text.splitlines()]
        lines = [l for l in lines if l]
        pairs = [l.split(':', 1) for l in lines]
        pairs = [(k.strip(), v.strip()) for k, v in pairs]
        data = dict(pairs)
        assert len(data) == len(pairs)
        return data

    def _physical_cores_from_cpuinfo(self):
        cpuinfo = '/proc/cpuinfo'
        if not os.path.isfile(cpuinfo):
            return None

        with open(cpuinfo) as f:
            contents = f.read()

        known_ids = set()

        proc_re = re.compile('^processor\s*:\s+[0-9]+\s*$', re.MULTILINE)
        procsplit = proc_re.split(contents)

        if len(procsplit) <= 1:
            # no procs found... give up
            return None
        elif len(procsplit) == 2:
            # if there's only two entries - the first is the stuff before the
            # processor, and can be ingored... which means there's only one
            # proc

            # besides, if there's only one proc, the output changes - ie, no
            # "core id", etc
            return 1

        # the first result is the stuff before the first processor line -
        # ignore it...
        for proc in procsplit[1:]:
            proc = self._parse_colon_table_to_dict(proc)
            # physical id corresponds to the socket, and core id to the
            # physical core number on that socket
            p_id = proc.get('physical id')
            c_id = proc.get('core id')
            if p_id is None or c_id is None:
                # something is screwy, we weren't able to parse correctly...
                return None

            # hyperthreaded procs will share the same physical_id + core id...
            # so if we just throw them all in a set, duplicates will be
            # ignored, and we'll know the total number of "real" cores
            known_ids.add((int(p_id), int(c_id)))
        return len(known_ids)

    def _physical_cores_from_lscpu(self):
        import subprocess
        try:
            p = popen(['lscpu'],
                      universal_newlines=True,
                      stdout=subprocess.PIPE,
                      stderr=subprocess.PIPE)
        except (OSError, IOError):
            return None

        stdout, stderr = p.communicate()
        if p.returncode:
            return None

        data = self._parse_colon_table_to_dict(stdout)

        # lscpu gives output like this:
        #
        # CPU(s):                24
        # On-line CPU(s) list:   0-23
        # Thread(s) per core:    2
        # Core(s) per socket:    6
        # Socket(s):             2

        # we want to take sockets * cores, and ignore threads...

        # some versions of lscpu format the sockets line differently...
        sockets = data.get('Socket(s)', data.get('CPU socket(s)'))
        if not sockets:
            return None
        cores = data.get('Core(s) per socket')
        if not cores:
            return None
        return int(sockets) * int(cores)

    def _physical_cores(self):
        cores = self._physical_cores_from_cpuinfo()
        if cores is not None:
            return cores
        return self._physical_cores_from_lscpu()


# -----------------------------------------------------------------------------
# OSX
# -----------------------------------------------------------------------------

class OSXPlatform(_UnixPlatform):
    name = "osx"

    def _os(self):
        release = platform.mac_ver()[0]
        return "osx-%s" % release

    def _terminal_emulator_command(self):
        term = which("x-terminal-emulator", "xterm")
        if term is None:
            return None

        term = os.path.basename(term)
        if term == "x-terminal-emulator":
            return "%s --noclose -e" % term
        else:
            return "%s -hold -e" % term

    def _image_viewer(self):
        return "open"

    def _editor(self):
        return "open"

    def _physical_cores_from_osx_sysctl(self):
        import subprocess
        try:
            p = popen(['sysctl', '-n', 'hw.physicalcpu'],
                      universal_newlines=True,
                      stdout=subprocess.PIPE,
                      stderr=subprocess.PIPE)
        except (OSError, IOError):
            return None

        stdout, stderr = p.communicate()
        if p.returncode:
            return None

        return int(stdout.strip())

    def _physical_cores(self):
        return self._physical_cores_from_osx_sysctl()

    def _difftool(self):
        return which("kdiff3", "meld", "diff")

    def _new_session_popen_args(self):
        return dict(preexec_fn=os.setpgrp)

# -----------------------------------------------------------------------------
# Windows
# -----------------------------------------------------------------------------

class WindowsPlatform(Platform):
    name = "windows"

    def _arch(self):
        # http://stackoverflow.com/questions/7164843/in-python-how-do-you-determine-whether-the-kernel-is-running-in-32-bit-or-64-bi
        if os.name == 'nt' and sys.version_info[:2] < (2, 7):
            arch = os.environ.get("PROCESSOR_ARCHITEW6432",
                                  os.environ.get('PROCESSOR_ARCHITECTURE'))
            if arch:
                return arch
        return super(WindowsPlatform, self)._arch()

    def _os(self):
        release, version, csd, ptype = platform.win32_ver()
        toks = []
        for item in (version, csd):
            if item:  # initial release would not have a service pack (csd)
                toks.append(item)
        final_version = str('.').join(toks)
        return "windows-%s" % final_version

    def _image_viewer(self):
        # os.system("file.jpg") will open default viewer on windows
        return ''

    def _editor(self):
        # os.system("file.txt") will open default editor on windows
        return ''

    def _new_session_popen_args(self):
        # https://msdn.microsoft.com/en-us/library/windows/desktop/ms684863%28v=vs.85%29.aspx
        return dict(creationflags=0x00000010)

    def symlink(self, source, link_name):
        # If we are already in a version of python that supports symlinks then
        # just use the os module, otherwise fall back on ctypes.  It requires
        # administrator privileges to run or the correct group policy to be set.
        # This implementation is taken from
        # http://stackoverflow.com/questions/6260149/os-symlink-support-in-windows
        if callable(getattr(os, "symlink", None)):
            os.symlink(source, link_name)
        else:
            import ctypes
            csl = ctypes.windll.kernel32.CreateSymbolicLinkW
            csl.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32)
            csl.restype = ctypes.c_ubyte
            flags = 1 if os.path.isdir(source) else 0
            if csl(link_name, source, flags) == 0:
                raise ctypes.WinError()

    def _terminal_emulator_command(self):
        return "START"

    def _physical_cores_from_wmic(self):
        # windows
        import subprocess
        try:
            p = popen('wmic cpu get NumberOfCores /value'.split(),
                      universal_newlines=True,
                      stdout=subprocess.PIPE,
                      stderr=subprocess.PIPE)
        except (OSError, IOError):
            return None

        stdout, stderr = p.communicate()
        if p.returncode:
            return None

        # a Windows machine with 1 installed CPU will return "NumberOfCores=N" where N is
        # the number of physical cores on that CPU chip. If more than one CPU is installed
        # there will be one "NumberOfCores=N" line listed per actual CPU, so the sum of all
        # N is the number of physical cores in the machine: this will be exactly one half the
        # number of logical cores (ie from multiprocessing.cpu_count) if HyperThreading is
        # enabled on the CPU(s)
        result = re.findall(r'NumberOfCores=(\d+)', stdout.strip())

        if not result:
            # don't know what's wrong... should get back a result like:
            # NumberOfCores=2
            return None

        return sum(map(int, result))

    def _physical_cores(self):
        return self._physical_cores_from_wmic()

    def _difftool(self):
        # although meld would be preferred, fc ships with all Windows versions back to DOS
        from rez.util import which
        return which("meld", "fc")

    def _difftool(self):
        return "C:\\Program Files\\Microsoft SDKs\\Windows\\v7.1\\Bin\\x64\\WinDiff.Exe"


# singleton
platform_ = None
name = platform.system().lower()
if name == "linux":
    platform_ = LinuxPlatform()
elif name == "darwin":
    platform_ = OSXPlatform()
elif name == "windows":
    platform_ = WindowsPlatform()


# Copyright 2013-2016 Allan Johns.
#
# This library is free software: you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.
