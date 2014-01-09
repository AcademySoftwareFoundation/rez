"""
Access to underlying system data.

Example:
from rez.system import system
print system.arch
"""
import os
import sys
import re
import platform as plat
import socket
import subprocess as sp



class System(object):
    def __init__(self):
        self._platform = None
        self._arch = None
        self._os = None
        self._shell = None
        self._fqdn = None
        self._hostname = None
        self._domain = None
        self._exe_paths = None

    @property
    def platform(self):
        """
        Get the current platform.
        @returns The current platform. Examples:
        linux
        windows
        osx
        """
        if self._platform is None:
            self._get_platform()
        return self._platform

    @property
    def arch(self):
        """
        Get the current architecture.
        @returns The current architecture. Examples:
        x86_64
        i386
        """
        if self._arch is None:
            self._get_arch()
        return self._arch

    @property
    def shell(self):
        """
        Get the current shell.
        @returns The current shell this process is running in. Examples:
        bash
        tcsh
        """
        if self._shell is None:
            self._get_shell()
        return self._shell

    @property
    def os(self):
        """
        Get the current operating system.
        @returns The current operating system. Examples:
        Ubuntu-12.04
        CentOS-5.4
        windows-6.1.7600.sp1
        osx-10.6.2
        """
        if self._os is None:
            self._get_os()
        return self._os

    @property
    def fqdn(self):
        """
        @returns Fully qualified domain name. Example:
        somesvr.somestudio.com
        """
        if self._fqdn is None:
            self._get_fqdn()
        return self._fqdn

    @property
    def hostname(self):
        """
        @returns The machine hostname, eg 'somesvr'
        """
        if self._hostname is None:
            self._get_fqdn()
        return self._hostname

    @property
    def domain(self):
        """
        @returns The domain, eg 'somestudio.com'
        """
        if self._domain is None:
            self._get_domain()
        return self._domain

    @property
    def executable_paths(self):
        """
        @returns The list of default paths found in $PATH
        """
        if self._exe_paths is None:
            self._get_exe_paths()
        return self._exe_paths

    def _get_platform(self):
        self._platform = plat.system().lower()

    def _get_arch(self):
        # http://stackoverflow.com/questions/7164843/in-python-how-do-you-determine-whether-the-kernel-is-running-in-32-bit-or-64-bi
        if os.name == 'nt' and sys.version_info[:2] < (2, 7):
            self._arch = os.environ.get("PROCESSOR_ARCHITEW6432",
                os.environ.get('PROCESSOR_ARCHITECTURE', ''))
            if not self._arch:
                raise RuntimeError("Could not detect architecture")
        else:
            self._arch = plat.machine()

    def _get_os(self):
        if plat.system() == 'Linux':
            try:
                distname, version, codename = plat.linux_distribution()
            except AttributeError:
                distname, version, codename = plat.dist()
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
        elif plat.system() == 'Darwin':
            release, versioninfo, machine = plat.mac_ver()
            finalRelease = 'osx'
            finalVersion = release
        elif plat.system() == 'Windows':
            release, version, csd, ptype = plat.win32_ver()
            finalRelease = 'windows'
            toks = []
            for item in (version, csd):
                if item: # initial release would not have a service pack (csd)
                    toks.append(item)
            finalVersion = str('.').join(toks)
        # other
        else:
            raise RuntimeError("Could not detect operating system")

        self._os = '%s-%s' % (finalRelease, finalVersion)

    def _get_shell(self):
        shells = dict( \
            sh="bash",
            bash="bash",
            csh="tcsh",
            tcsh="tcsh")

        try:
            from psutil import Process
            proc = Process().parent
        except:
            proc = None

        shell = None
        while proc and proc.name not in shells:
            proc = proc.parent
        if proc:
            shell = proc.name
        else:
            try:
                import subprocess as sp
                proc = sp.Popen(['ps', '-o', 'args=', '-p', str(os.getppid())], stdout=sp.PIPE)
                output = proc.communicate()[0]
                shell = os.path.basename(output.strip().split()[0]).replace('-','')
            except:
                pass

            if shell not in shells:
                shell = os.getenv("SHELL")

        if shell in shells:
            self._shell = shells[shell]
        else:
            raise RuntimeError("Could not detect shell")

    def _get_fqdn(self):
        self._fqdn = socket.getfqdn()
        self._hostname, self._domain = self._fqdn.split('.', 1)

    def _get_exe_paths(self):
        paths = None
        cmd = None

        if self.shell == "bash":
            cmd = "cmd=`which bash`; unset PATH; $cmd --norc -c 'echo $PATH'"
        elif self.shell == "tcsh":
            cmd = "cmd=`which tcsh`; unset PATH; $cmd -c 'echo $PATH'"

        if cmd:
            p = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.PIPE, shell=True)
            out_ = p.communicate()[0]
            if not p.returncode:
                paths = out_.strip().split(os.pathsep)

        if paths is None:
            raise RuntimeError("Could not get executable paths")
        else:
            self._exe_paths = [x for x in paths if x]


# singleton
system = System()
