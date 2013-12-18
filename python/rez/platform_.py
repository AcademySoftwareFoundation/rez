"""
Access to underlying platform's identifying data. Like python's platform builtin, but gives a
more unified interface across platforms.
"""
import os
import sys
import re
import platform
import socket
import subprocess as sp
from rez.exceptions import PkgSystemError



_platform = None
_arch = None
_os = None
_fqdn = None
_hostname = None
_domain = None


def get_platform():
    """
    Get the current platform.
    @returns The current platform. Examples:
    linux
    windows
    osx
    """
    if _platform is None:
        _get_platform()
    return _platform

def get_arch():
    """
    Get the current architecture.
    @returns The current architecture. Examples:
    x86_64
    i386
    """
    if _arch is None:
        _get_arch()
    return _arch

def get_os():
    """
    Get the current operating system.
    @returns The current operating system. Examples:
    Ubuntu-12.04
    CentOS-5.4
    windows-6.1.7600.sp1
    osx-10.6.2
    """
    if _os is None:
        _get_os()
    return _os

def get_fqdn():
    """
    @returns Fully qualified domain name. Example:
    somesvr.somestudio.com
    """
    if _fqdn is None:
        _get_fqdn()
    return _fqdn

def get_hostname():
    """
    @returns The machine hostname, eg 'somesvr'
    """
    if _hostname is None:
        _get_fqdn()
    return _hostname

def get_domain():
    """
    @returns The domain, eg 'somestudio.com'
    """
    if _domain is None:
        _get_domain()
    return _domain


class Platform(object):
    """
    Exposes functions in this file as object properties.
    """
    @property
    def arch(self):
        return get_arch()

    @property
    def os(self):
        return get_os()

    @property
    def platform(self):
        return get_platform()

    @property
    def hostname(self):
        return get_hostname()

    @property
    def fqdn(self):
        return get_fqdn()

    @property
    def domain(self):
        return get_domain()


def _get_platform():
    global _platform
    _platform = platform.system().lower()

def _get_arch():
    # http://stackoverflow.com/questions/7164843/in-python-how-do-you-determine-whether-the-kernel-is-running-in-32-bit-or-64-bi
    global _arch
    if os.name == 'nt' and sys.version_info[:2] < (2, 7):
        arch = os.environ.get("PROCESSOR_ARCHITEW6432",
            os.environ.get('PROCESSOR_ARCHITECTURE', ''))
        if not arch:
            raise PkgSystemError("Could not detect architecture")
    else:
        _arch = platform.machine()

def _get_os():
    global _os
    if platform.system() == 'Linux':
        try:
            distname, version, codename = platform.linux_distribution()
        except AttributeError:
            distname, version, codename = platform.dist()
            try:
                proc = sp.Popen(['/usr/bin/env', 'lsb_release', '-i'], stdout=sp.PIPE, stderr=sp.PIPE)
                out_,err_ = proc.communicate()
                if proc.returncode:
                    print >> sys.stderr, ("Warning: lsb_release failed when detecting OS: " + \
                        "[errorcode %d] %s") % (proc.returncode, err_)
                else:
                    m = re.search(r'^Distributor ID:\s*(\w+)\s*$', str(out_).strip())
                    if m is not None:
                        distname = m.group(1)
            except Exception:
                pass # not an lsb compliant distro?
        finalRelease = distname
        finalVersion = version
    elif platform.system() == 'Darwin':
        release, versioninfo, machine = platform.mac_ver()
        finalRelease = 'osx'
        finalVersion = release
    elif platform.system() == 'Windows':
        release, version, csd, ptype = platform.win32_ver()
        finalRelease = 'windows'
        toks = []
        for item in (version, csd):
            if item: # initial release would not have a service pack (csd)
                toks.append(item)
        finalVersion = str('.').join(toks)
    # other
    else:
        raise PkgSystemError("Could not detect operating system")

    _os = '%s-%s' % (finalRelease, finalVersion)

def _get_fqdn():
    global _fqdn, _domain, _hostname
    _fqdn = socket.getfqdn()
    _hostname, _domain = _fqdn.split('.', 1)
