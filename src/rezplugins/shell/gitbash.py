# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Git Bash (for Windows) shell
"""
import os
import re
import os.path
import subprocess
from rez.config import config
from rezplugins.shell.bash import Bash
from rez.utils.execution import Popen
from rez.utils.platform_ import platform_
from rez.utils.logging_ import print_warning
from rez.util import dedup

if platform_.name == "windows":
    from ._utils.windows import get_syspaths_from_registry, to_posix_path


class GitBash(Bash):
    """Git Bash shell plugin.
    """
    pathsep = ':'

    _drive_regex = re.compile(r"([A-Za-z]):\\")

    @classmethod
    def name(cls):
        return "gitbash"

    @classmethod
    def executable_name(cls):
        return "bash"

    @classmethod
    def find_executable(cls, name, check_syspaths=False):
        exepath = Bash.find_executable(name, check_syspaths=check_syspaths)

        if exepath and "system32" in exepath.lower():
            print_warning(
                "Git-bash executable has been detected at %s, but this is "
                "probably not correct (google Windows Subsystem for Linux). "
                "Consider adjusting your searchpath, or use rez config setting "
                "plugins.shell.gitbash.executable_fullpath."
            )

        return exepath

    @classmethod
    def get_syspaths(cls):
        if cls.syspaths is not None:
            return cls.syspaths

        if config.standard_system_paths:
            cls.syspaths = config.standard_system_paths
            return cls.syspaths

        # get default PATH from bash
        exepath = cls.executable_filepath()
        environ = os.environ.copy()
        environ.pop("PATH", None)
        p = Popen(
            [exepath, cls.norc_arg, cls.command_arg, 'echo __PATHS_ $PATH'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environ,
            text=True
        )

        out_, _ = p.communicate()
        if p.returncode == 0:
            lines = out_.split('\n')
            line = [x for x in lines if "__PATHS_" in x.split()][0]
            # note that we're on windows, but pathsep in bash is ':'
            paths = line.strip().split()[-1].split(':')
        else:
            paths = []

        # combine with paths from registry
        paths = get_syspaths_from_registry() + paths

        paths = dedup(paths)
        paths = [x for x in paths if x]

        cls.syspaths = paths
        return cls.syspaths

    def normalize_path(self, path):
        return to_posix_path(path)

    def normalize_paths(self, value):
        """
        This is a bit tricky in the case of gitbash. The problem we hit is that
        our pathsep is ':', _but_ pre-normalised paths also contain ':' (eg
        C:\foo). In other words we have to deal with values like  'C:\foo:C:\bah'.

        To get around this, we do the drive-colon replace here instead of in
        normalize_path(), so we can then split the paths correctly. Note that
        normalize_path() still does drive-colon replace also - it needs to
        behave correctly if passed a string like C:\foo.
        """

        # C:\ ==> /c/
        value2 = self._drive_regex.sub("/\\1/", value)

        return super(GitBash, self).normalize_paths(value2)


def register_plugin():
    if platform_.name == "windows":
        return GitBash
