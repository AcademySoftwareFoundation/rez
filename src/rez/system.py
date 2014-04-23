"""
Access to underlying system data.

Example:
from rez.system import system
print system.arch
"""
import os
import os.path
import sys
import re
import platform as plat
from rez.util import propertycache


class System(object):

    @propertycache
    def platform(self):
        """
        Get the current platform.
        @returns The current platform. Examples:
        linux
        windows
        osx
        """
        return plat.system().lower()

    @propertycache
    def arch(self):
        """
        Get the current architecture.
        @returns The current architecture. Examples:
        x86_64
        i386
        """
        # http://stackoverflow.com/questions/7164843/in-python-how-do-you-determine-whether-the-kernel-is-running-in-32-bit-or-64-bi
        if os.name == 'nt' and sys.version_info[:2] < (2, 7):
            arch = os.environ.get("PROCESSOR_ARCHITEW6432",
                                  os.environ.get('PROCESSOR_ARCHITECTURE', ''))
            if not arch:
                raise RuntimeError("Could not detect architecture")
            return arch
        else:
            return plat.machine()

    # TODO remove, this belongs in shells.py and should use the plugins
    @propertycache
    def shell(self):
        """
        Get the current shell.
        @returns The current shell this process is running in. Examples:
        bash
        tcsh
        """
        from rez.shells import get_shell_types
        shells = get_shell_types()

        shell = None
        try:
            import subprocess as sp
            proc = sp.Popen(['ps', '-o', 'args=', '-p',
                             str(os.getppid())], stdout=sp.PIPE)
            output = proc.communicate()[0]
            shell = os.path.basename(output.strip().split()[0]).replace('-', '')
        except:
            pass

        if shell not in shells:
            shell = os.path.basename(os.getenv("SHELL", ''))

        if shell in shells:
            return shell
        else:
            raise RuntimeError("Could not detect shell")

    @propertycache
    def os(self):
        """
        Get the current operating system.
        @returns The current operating system. Examples:
        Ubuntu-12.04
        CentOS-5.4
        windows-6.1.7600.sp1
        osx-10.6.2
        """
        if plat.system() == 'Linux':
            try:
                distname, version, codename = plat.linux_distribution()
            except AttributeError:
                distname, version, codename = plat.dist()
                try:
                    import subprocess as sp
                    proc = sp.Popen(['/usr/bin/env', 'lsb_release', '-i'],
                                    stdout=sp.PIPE, stderr=sp.PIPE)
                    out_, err_ = proc.communicate()
                    if proc.returncode:
                        print >> sys.stderr, ("Warning: lsb_release failed when detecting OS: " + \
                            "[errorcode %d] %s") % (proc.returncode, err_)
                    else:
                        m = re.search(r'^Distributor ID:\s*(\w+)\s*$',
                                      str(out_).strip())
                        if m is not None:
                            distname = m.group(1)
                except Exception:
                    pass  # not an lsb compliant distro?
            final_release = distname
            final_version = version
        elif plat.system() == 'Darwin':
            release, versioninfo, machine = plat.mac_ver()
            final_release = 'osx'
            final_version = release
        elif plat.system() == 'Windows':
            release, version, csd, ptype = plat.win32_ver()
            final_release = 'windows'
            toks = []
            for item in (version, csd):
                if item:  # initial release would not have a service pack (csd)
                    toks.append(item)
            final_version = str('.').join(toks)
        # other
        else:
            raise RuntimeError("Could not detect operating system")

        return '%s-%s' % (final_release, final_version)

    @propertycache
    def fqdn(self):
        """
        @returns Fully qualified domain name. Example:
        somesvr.somestudio.com
        """
        import socket
        return socket.getfqdn()

    @propertycache
    def hostname(self):
        """
        @returns The machine hostname, eg 'somesvr'
        """
        return self.fqdn.split('.', 1)[0]

    @propertycache
    def domain(self):
        """
        @returns The domain, eg 'somestudio.com'
        """
        return self.fqdn.split('.', 1)[1]

# singleton
system = System()
