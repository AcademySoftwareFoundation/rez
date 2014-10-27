import os
import os.path
import re
import sys
from rez import __version__
from rez.platform_ import platform_
from rez.exceptions import RezSystemError
from rez.util import propertycache, which


class System(object):
    """Access to underlying system data.
    """
    @property
    def rez_version(self):
        """Returns the current version of Rez."""
        return __version__

    @propertycache
    def platform(self):
        """Get the current platform.
        @returns The current platform. Examples:
        linux
        windows
        osx
        """
        return platform_.name

    @propertycache
    def arch(self):
        """Get the current architecture.
        @returns The current architecture. Examples:
        x86_64
        i386
        """
        r = platform_.arch
        return self._make_safe_version_string(r)

    @propertycache
    def os(self):
        """Get the current operating system.
        @returns The current operating system. Examples:
        Ubuntu-12.04
        CentOS-5.4
        windows-6.1.7600.sp1
        osx-10.6.2
        """
        r = platform_.os
        return self._make_safe_version_string(r)

    @propertycache
    def variant(self):
        """Returns a list of the form ["platform-X", "arch-X", "os-X"] suitable
        for use as a variant in a system-dependent package."""
        return ["platform-%s" % self.platform,
                "arch-%s" % self.arch,
                "os-%s" % self.os]

    # TODO move shell detection into shell plugins
    @propertycache
    def shell(self):
        """Get the current shell.
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
                proc = sp.Popen(args, stdout=sp.PIPE)
                output = proc.communicate()[0]
                shell = os.path.basename(output.strip().split()[0]).replace('-', '')
            except Exception as e:
                pass

            # check $SHELL
            if shell not in shells:
                shell = os.path.basename(os.getenv("SHELL", ''))

            # traverse parent procs via /proc/(pid)/status
            if shell not in shells:
                pid = str(os.getppid())
                found = False

                while not found:
                    try:
                        file = os.path.join(os.sep, "proc", pid, "status")
                        with open(file) as f:
                            loc = f.read().split('\n')

                        for line in loc:
                            line = line.strip()
                            toks = line.split()
                            if len(toks) == 2:
                                if toks[0] == "Name:":
                                    name = toks[1]
                                    if name in shells:
                                        shell = name
                                        found = True
                                        break
                                elif toks[0] == "PPid:":
                                    pid = toks[1]
                    except Exception as e:
                        break

            if (shell not in shells) and ("sh" in shells):
                shell = "sh"  # failed detection, fall back on 'sh'
            elif (shell not in shells) and ("bash" in shells):
                shell = "bash"  # failed detection, fall back on 'bash'
            elif shell not in shells:
                shell = iter(shells).next()  # give up - just choose a shell

            # sh has to be handled as a special case
            if shell == "sh":
                if os.path.islink("/bin/sh"):
                    path = os.readlink("/bin/sh")
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
                            if "bash" in shells:
                                shell = "bash"  # fall back on bash
                            else:
                                shell = iter(shells).next()  # give up - just choose a shell
            return shell

    @propertycache
    def user(self):
        """Get the current user."""
        import getpass
        return getpass.getuser()

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

    @propertycache
    def rez_bin_path(self):
        """Get path containing rez binaries, or None if no binaries are
        available, or Rez is not a production install.
        """
        binpath = None
        if sys.argv and sys.argv[0]:
            executable = sys.argv[0]
            path = os.path.dirname(executable)
            rezolve_exe = os.path.join(path, "rezolve")
            if os.path.exists(rezolve_exe):
                binpath = path

        # TODO improve this, could still pick up non-production 'rezolve'
        if not binpath:
            path = which("rezolve")
            if path:
                binpath = os.path.dirname(path)

        if binpath:
            validation_file = os.path.join(binpath, ".rez_production_install")
            if os.path.exists(validation_file):
                return os.path.realpath(binpath)

        return None

    @property
    def is_production_rez_install(self):
        """Return True if this is a production rez install."""
        return bool(self.rez_bin_path)

    @classmethod
    def _make_safe_version_string(cls, s):
        from rez.vendor.version.version import Version

        sep_regex = re.compile("[\.\-]")
        char_regex = re.compile("[a-zA-Z0-9_]")

        s = s.strip('.').strip('-')
        toks = sep_regex.split(s)
        seps = sep_regex.findall(s)
        valid_toks = []
        b = True

        while toks or seps:
            if b:
                tok = toks[0]
                toks = toks[1:]
                if tok:
                    valid_tok = ''
                    for ch in tok:
                        if char_regex.match(ch):
                            valid_tok += ch
                        else:
                            valid_tok += '_'
                    valid_toks.append(valid_tok)
                else:
                    seps = seps[1:]  # skip empty string between seps
                    b = not b
            else:
                sep = seps[0]
                seps = seps[1:]
                valid_toks.append(sep)
            b = not b

        return ''.join(valid_toks)


# singleton
system = System()
