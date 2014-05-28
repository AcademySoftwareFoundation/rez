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
from rez.exceptions import RezSystemError
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
                raise RezSystemError("Could not detect architecture")
        else:
            arch = plat.machine()

        arch = self._make_safe_version(arch)
        return arch

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
                self._pr("detecting os: trying platform.linux_distribution...")
                distname,version,_ = plat.linux_distribution()
            except AttributeError:
                self._pr("detecting os: trying platform.dist...")
                distname,version,_ = plat.dist()
                try:
                    import subprocess as sp
                    proc = sp.Popen(['/usr/bin/env', 'lsb_release', '-i'],
                                    stdout=sp.PIPE, stderr=sp.PIPE)
                    out_, err_ = proc.communicate()
                    if proc.returncode:
                        self._pr(("lsb_release failed when detecting OS: "
                                 "[errorcode %d] %s") % (proc.returncode, err_))
                    else:
                        m = re.search(r'^Distributor ID:\s*(\w+)\s*$',
                                      str(out_).strip())
                        if m is not None:
                            distname = m.group(1)
                except Exception as e:
                    self._pr("")
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
            raise RezSystemError("Could not detect operating system")

        toks = []
        if final_release:
            toks.append(final_release)
        if final_version:
            toks.append(final_version)
        return '-'.join(self._make_safe_version(x) for x in toks)

    @propertycache
    def variant(self):
        """Returns a list of the form ["platform-X", "arch-X", "os-X"] suitable
        for use as a variant in a system-dependent package."""
        return ["platform-%s" % self.platform,
                "arch-%s" % self.arch,
                "os-%s" % self.os]

    @propertycache
    def shell(self):
        """
        Get the current shell.
        @returns The current shell this process is running in. Examples:
        bash
        tcsh
        """
        from rez.shells import get_shell_types
        shells = set(get_shell_types())
        if not shells:
            raise RezSystemError("no shells available")

        if self.platform == "windows":
            raise NotImplemented
        else:
            import subprocess as sp
            shell = None

            # check parent process via ps
            try:
                args = ['ps', '-o', 'args=', '-p', str(os.getppid())]
                self._pr("detecting shell: running %s..." % ' '.join(args))
                proc = sp.Popen(args, stdout=sp.PIPE)
                output = proc.communicate()[0]
                shell = os.path.basename(output.strip().split()[0]).replace('-', '')
            except Exception as e:
                self._pr("ps failed: %s" % str(e))

            # check $SHELL
            if shell not in shells:
                self._pr("detecting shell: testing $SHELL...")
                shell = os.path.basename(os.getenv("SHELL", ''))

            # traverse parent procs via /proc/(pid)/status
            if shell not in shells:
                self._pr("detecting shell: traversing /proc/{pid}/status...")
                pid = str(os.getppid())
                found = False

                while not found:
                    try:
                        file = os.path.join(os.sep, "proc", pid, "status")
                        self._pr("reading %s..." % file)
                        with open(file) as f:
                            loc = f.read().split('\n')

                        for line in loc:
                            line = line.strip()
                            toks = line.split()
                            if len(toks) == 2:
                                if toks[0] == "Name:":
                                    self._pr(line)
                                    name = toks[1]
                                    if name in shells:
                                        shell = name
                                        found = True
                                        break
                                elif toks[0] == "PPid:":
                                    self._pr(line)
                                    pid = toks[1]
                    except Exception as e:
                        self._pr("traversal ended: %s" % str(e))
                        break

            if (shell not in shells) and ("sh" in shells):
                shell = "sh"  # failed detection, fall back on 'sh'
            elif (shell not in shells) and ("bash" in shells):
                shell = "bash"  # failed detection, fall back on 'bash'
            elif shell not in shells:
                shell = iter(shells).next()  # give up - just choose a shell
                self._pr("could not detect shell, chose '%s'") % shell

            # sh has to be handled as a special case
            if shell == "sh":
                if os.path.islink("/bin/sh"):
                    path = os.readlink("/bin/sh")
                    self._pr("detected: /bin/sh -> %s" % path)
                    shell2 = os.path.split(path)[-1]

                    if shell2 == "bash":
                        # bash switches to sh-like shell when invoked as sh,
                        # so we want to use the sh shell plugin
                        pass
                    elif shell2 == "dash":
                        # dash doesn't have an sh emulation mode, so we have
                        # to use the dash shell plugin
                        if "dash" in shells:
                            shell = "dash"
                        else:
                            # this isn't good!
                            self._pr("dash is the current shell, but the "
                                     "plugin is not available.")

                            if "bash" in shells:
                                shell = "bash"  # fall back on bash
                            else:
                                shell = iter(shells).next()  # give up - just choose a shell

                            self._pr("fell back to %s" % shell)

            self._pr("selected shell: %s" % shell)
            return shell

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

    def _make_safe_version(self, s):
        from rez.vendor.version.version import Version
        def _test(verstr):
            try:
                Version(verstr)
                return True
            except:
                return False

        def _reduce(verstr, pattern):
            import re
            r = re.compile(pattern)
            return ''.join(x for x in verstr if r.match(x))

        if _test(s):
            return s

        # remove invalid chars
        s_ = _reduce(s, r"[a-zA-Z0-9_.-]")
        if _test(s_):
            return s_

        # remove token seperators
        return _reduce(s, r"[a-zA-Z0-9_]")

    # TODO deprecate once shell detection is removed from here - it needs to go
    # into shell plugins
    def _pr(self, s):
        # remove for now, allows us to make a smaller get-rez.py - settings not
        # being imported means vendor/schema not needed
        pass
        #from rez.settings import settings
        #if settings.debug("system"):
        #    print s

# singleton
system = System()
