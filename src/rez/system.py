# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


import os
import os.path
import re
import platform

from rez import __version__
from rez.utils.platform_ import platform_
from rez.exceptions import RezSystemError
from rez.utils.data_utils import cached_property


class System(object):
    """Access to underlying system data.
    """
    @property
    def rez_version(self):
        """Returns the current version of Rez."""
        return __version__

    @cached_property
    def platform(self):
        """Get the current platform.
        @returns The current platform. Examples:

            linux
            windows
            osx
        """
        return platform_.name

    @cached_property
    def arch(self):
        """Get the current architecture.
        @returns The current architecture. Examples:

            x86_64
            i386
        """
        r = platform_.arch
        return self._make_safe_version_string(r)

    @cached_property
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

    @cached_property
    def variant(self):
        """Returns a list of the form ["platform-X", "arch-X", "os-X"] suitable
        for use as a variant in a system-dependent package."""
        return ["platform-%s" % self.platform,
                "arch-%s" % self.arch,
                "os-%s" % self.os]

    # TODO: move shell detection into shell plugins
    @cached_property
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
            return "cmd"
        else:
            import subprocess as sp
            shell = None

            # check parent process via ps
            try:
                args = ['ps', '-o', 'args=', '-p', str(os.getppid())]
                proc = sp.Popen(args, stdout=sp.PIPE)
                output = proc.communicate()[0]
                shell = os.path.basename(output.strip().split()[0]).replace('-', '')
            except Exception:
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
                    except Exception:
                        break

            if (shell not in shells) and ("sh" in shells):
                shell = "sh"  # failed detection, fall back on 'sh'
            elif (shell not in shells) and ("bash" in shells):
                shell = "bash"  # failed detection, fall back on 'bash'
            elif shell not in shells:
                shell = next(iter(shells))  # give up - just choose a shell

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
                                shell = next(iter(shells))  # give up - just choose a shell

            # TODO: remove this when/if dash support added
            if shell == "dash":
                shell = "bash"

            return shell

    @cached_property
    def user(self):
        """Get the current user."""
        import getpass
        return getpass.getuser()

    @cached_property
    def home(self):
        """Get the home directory for the current user."""
        return os.path.expanduser("~")

    @cached_property
    def fqdn(self):
        """
        @returns Fully qualified domain name, eg 'somesvr.somestudio.com'
        """
        import socket
        return socket.getfqdn()

    @cached_property
    def hostname(self):
        """
        @returns The machine hostname, eg 'somesvr'
        """
        import socket
        return socket.gethostname()

    @cached_property
    def domain(self):
        """
        @returns The domain, eg 'somestudio.com'
        """
        try:
            return self.fqdn.split('.', 1)[1]
        except IndexError:
            return ""

    @cached_property
    def rez_bin_path(self):
        """Get path containing rez binaries, or None if no binaries are
        available, or Rez is not a production install.
        """

        # Rez install layout will be like:
        #
        # /<install>/lib/python2.7/site-packages/rez  <- module path
        # /<install>/(bin or Scripts)/rez/rez  <- rez executable
        #
        import rez
        module_path = rez.__path__[0]

        parts = module_path.split(os.path.sep)
        parts_lower = module_path.lower().split(os.path.sep)

        # find last 'lib' or 'lib64' dir in rez module path
        # Note: On Windows it can be 'Lib' (hence lowercase check).
        # Note: Occasionally a rez install will use the python lib stored in
        # lib64 instead of lib, I don't know why.
        #
        rev_parts = list(reversed(parts_lower))
        try:
            i = rev_parts.index("lib")
        except ValueError:
            try:
                i = rev_parts.index("lib64")
            except ValueError:
                return None

        i = len(parts) - 1 - i  # unreverse the index

        # find rez bin path and look for the production install marker file
        if platform.system() == "Windows":
            bin_dirname = "Scripts"
        else:
            bin_dirname = "bin"

        binpath = os.path.sep.join(parts[:i] + [bin_dirname, "rez"])

        validation_file = os.path.join(binpath, ".rez_production_install")
        if os.path.exists(validation_file):
            return os.path.realpath(binpath)

        return None

    @property
    def is_production_rez_install(self):
        """Return True if this is a production rez install."""
        return bool(self.rez_bin_path)

    @property
    def selftest_is_running(self):
        """Return True if tests are running via rez-selftest tool."""
        return os.getenv("__REZ_SELFTEST_RUNNING") == "1"

    def get_summary_string(self):
        """Get a string summarising the state of Rez as a whole.

        Returns:
            String.
        """
        from rez.plugin_managers import plugin_manager

        txt = "Rez %s" % __version__
        txt += "\n\n%s" % plugin_manager.get_summary_string()
        return txt

    def clear_caches(self, hard=False):
        """Clear all caches in Rez.

        Rez caches package contents and iteration during a python session. Thus
        newly released packages, and changes to existing packages, may not be
        picked up. You need to clear the cache for these changes to become
        visible.

        Args:
            hard (bool): Perform a 'hard' cache clear. This just means that the
                memcached cache is also cleared. Generally this is not needed -
                this option is for debugging purposes.
        """
        from rez.package_repository import package_repository_manager
        from rez.utils.memcached import memcached_client

        package_repository_manager.clear_caches()
        if hard:
            with memcached_client() as client:
                client.flush()

    @classmethod
    def _make_safe_version_string(cls, s):
        sep_regex = re.compile(r"[\.\-]")
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
