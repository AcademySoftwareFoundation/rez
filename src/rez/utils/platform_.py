import platform
import sys
import os
import os.path
from rez.util import which
from rez.utils.data_utils import cached_property
from rez.exceptions import RezSystemError


class Platform(object):
    """Abstraction of a platform.
    """
    name = None

    def __init__(self):
        pass

    @cached_property
    def arch(self):
        """Returns the name of the architecture."""
        return self._arch()

    @cached_property
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
    def tmpdir(self):
        """Return system default temporary directory path."""
        return self._tmpdir()

    # -- implementation

    def _arch(self):
        return platform.machine()

    def _os(self):
        raise NotImplementedError

    def _terminal_emulator_command(self):
        raise NotImplementedError

    def _image_viewer(self):
        raise NotImplementedError

    def _editor(self):
        raise NotImplementedError

    def _tmpdir(self):
        raise NotImplementedError

    def symlink(self, source, link_name):
        """Create a symbolic link pointing to source named link_name."""
        os.symlink(source, link_name)


# -----------------------------------------------------------------------------
# Unix (Linux and OSX)
# -----------------------------------------------------------------------------

class _UnixPlatform(Platform):
    def _tmpdir(self):
        return "/tmp"


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
        p = subprocess.Popen(['/usr/bin/env', 'lsb_release', '-a'],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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
            return [term, "--noclose", "-e"]
        else:
            return [term, "-hold", "-e"]

    def _image_viewer(self):
        from rez.util import which
        return which("xdg-open", "eog", "kview")

    def _editor(self):
        ed = os.getenv("EDITOR")
        if ed is None:
            from rez.util import which
            ed = which("xdg-open", "vim", "vi")
        return ed


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
            return [term, "--noclose", "-e"]
        else:
            return [term, "-hold", "-e"]

    def _image_viewer(self):
        return "open"

    def _editor(self):
        return "open"


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

    def _tmpdir(self):
        path = os.getenv("TEMP")
        if path and os.path.isdir(path):
            return path
        return "C:/temp"

    def _image_viewer(self):
        # os.system("file.jpg") will open default viewer on windows
        return ''

    def _editor(self):
        # os.system("file.txt") will open default editor on windows
        return ''

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
        return ["CMD.exe", "/Q", "/K"]


# singleton
platform_ = None
name = platform.system().lower()
if name == "linux":
    platform_ = LinuxPlatform()
elif name == "darwin":
    platform_ = OSXPlatform()
elif name == "windows":
    platform_ = WindowsPlatform()
