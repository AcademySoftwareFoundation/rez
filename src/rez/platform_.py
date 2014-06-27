import platform
import sys
import os
import os.path
from rez.exceptions import RezSystemError


# class matching the current platform
current_platform = None


class Platform(object):
    """Abstraction of a platform.
    """
    @classmethod
    def name(cls):
        """Returns the name of the platform."""
        raise NotImplemented

    @classmethod
    def arch(cls):
        """Returns the name of the architecture."""
        return platform.machine()

    @classmethod
    def os(cls):
        """Returns the name of the operating system."""
        raise NotImplemented

    @classmethod
    def symlink(cls, source, link_name):
        """Create a symbolic link pointing to source named link_name."""
        os.symlink(source, link_name)


# -----------------------------------------------------------------------------
# Linux
# -----------------------------------------------------------------------------
class LinuxPlatform(Platform):
    @classmethod
    def name(cls):
        return "linux"

    @classmethod
    def os(cls):
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
        txt = proc.communicate()[0]
        if not proc.returncode:
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


# -----------------------------------------------------------------------------
# OSX
# -----------------------------------------------------------------------------
class OSXPlatform(Platform):
    @classmethod
    def name(cls):
        return "osx"

    @classmethod
    def os(cls):
        release = platform.mac_ver()[0]
        return "osx-%s" % release


# -----------------------------------------------------------------------------
# Windows
# -----------------------------------------------------------------------------
class WindowsPlatform(Platform):
    @classmethod
    def name(cls):
        return "windows"

    @classmethod
    def arch(cls):
        # http://stackoverflow.com/questions/7164843/in-python-how-do-you-determine-whether-the-kernel-is-running-in-32-bit-or-64-bi
        if os.name == 'nt' and sys.version_info[:2] < (2, 7):
            arch = os.environ.get("PROCESSOR_ARCHITEW6432",
                                  os.environ.get('PROCESSOR_ARCHITECTURE'))
            if arch:
                return arch
        return super(WindowsPlatform, cls).arch()

    @classmethod
    def os(cls):
        release, version, csd, ptype = platform.win32_ver()
        toks = []
        for item in (version, csd):
            if item:  # initial release would not have a service pack (csd)
                toks.append(item)
        final_version = str('.').join(toks)
        return "windows-%s" % final_version


name = platform.system().lower()
if name == "linux":
    current_platform = LinuxPlatform
elif name == "darwin":
    current_platform = OSXPlatform
elif name == "windows":
    current_platform = WindowsPlatform
