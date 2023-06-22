# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Git Bash (for Windows) shell.
"""
import os
import re
import os.path
import subprocess

from rez.config import config
from rez.shells import log
from rezplugins.shell.bash import Bash
from rez.utils import cygpath
from rez.utils.execution import Popen
from rez.utils.platform_ import platform_
from rez.utils.logging_ import print_error, print_warning
from rez.util import dedup
from ._utils.windows import get_syspaths_from_registry


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
        # If WSL is installed, it's probably safest to assume System32 bash is
        # on the path and the default bash location for gitbash is on the path
        # and appears after System32. In this scenario, we don't want to get the
        # executable path from the parent class because it is configured
        # differently and it seems like the best option to get the executable is
        # through configuration, unless there's a way to get the gitbash executable
        # using the registry.
        settings = config.plugins.shell[cls.name()]
        if settings.executable_fullpath:
            if not os.path.exists(settings.executable_fullpath):
                raise RuntimeError(
                    "Couldn't find executable '%s'." % settings.executable_fullpath
                )
            else:
                return settings.executable_fullpath

        exepath = Bash.find_executable(name, check_syspaths=check_syspaths)

        if exepath and "system32" in exepath.lower():
            print_warning(
                "Git-bash executable has been detected at %s, but this is "
                "probably not correct (google Windows Subsystem for Linux). "
                "Consider adjusting your searchpath, or use rez config setting "
                "plugins.shell.gitbash.executable_fullpath.",
                exepath
            )

        exepath = exepath.replace("\\", "\\\\")

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

    def validate_env_sep_map(self):
        # Return early if validation is disabled.
        if not config.warn("shell_startup"):
            return

        env_var_seps = self.env_sep_map
        shell = self.name()
        shell_setting = self.shell_env_sep_map_setting
        py_path_var, py_path_sep = ("PYTHONPATH", ";")

        # Begin validation, check special case for PYTHONPATH in gitbash
        if env_var_seps:
            if py_path_var not in env_var_seps:
                print_error(
                    "'%s' is not configured in '%s'. This is required for "
                    "python to work correctly. Please add '%s' to %s['%s'] and "
                    "set it to '%s' for the best experience working with  %s ",
                    py_path_var,
                    shell_setting,
                    py_path_var,
                    shell_setting,
                    shell,
                    py_path_sep,
                    shell,
                )
        else:
            print_error(
                "'%s' is improperly configured! '%s' must be configured and "
                "contain '%s' and set to '%s' for python to function and rez "
                "in %s to work as expected.",
                shell,
                shell_setting,
                py_path_var,
                py_path_sep,
                shell,
            )

        env_seps = self._global_env_seps()
        shell_env_seps = self._shell_env_seps()
        setting = self.env_sep_map_setting

        is_configured = (env_seps and py_path_var in env_seps)
        shell_is_configured = (shell_env_seps and py_path_var in shell_env_seps)

        # If `shell_path_vars` is not configured for `PYTHONPATH`
        # ensure `env_var_separators` is configured with `PYTHONPATH` set to `;`
        # Otherwise communicate to the user that there's a configuration error.
        if is_configured and not shell_is_configured:
            if env_seps[py_path_var] != py_path_sep:
                print_error(
                    "'%s' is configured in '%s' but is not configured in '%s'. "
                    "This is required for python to work correctly. Please add "
                    "'%s' to %s['%s'] and set it to '%s' for the best "
                    "experience working with  %s",
                    py_path_var,
                    setting,
                    shell_setting,
                    py_path_var,
                    shell_setting,
                    shell,
                    py_path_sep,
                    shell,
                )
            else:
                print_warning(
                    "'%s' is configured in '%s' but is not configured in '%s'. "
                    "Using rez with gitbash will probably still work but "
                    "configuration is technically incorrect and may cause "
                    "problems. Please add '%s' to %s['%s'] "
                    "and set it to '%s' for %s to ensure the best experience.",
                    py_path_var,
                    setting,
                    shell_setting,
                    py_path_var,
                    shell_setting,
                    shell,
                    py_path_sep,
                    shell,
                )

    def as_path(self, path):
        """Return the given path as a system path.
        Used if the path needs to be reformatted to suit a specific case.
        Args:
            path (str): File path.

        Returns:
            (str): Transformed file path.
        """
        return path

    def as_shell_path(self, path):
        """Return the given path as a shell path.
        Used if the shell requires a different pathing structure.

        Args:
            path (str): File path.

        Returns:
            (str): Transformed file path.
        """
        # Prevent path conversion if normalization is disabled in the config.
        if not config.enable_path_normalization:
            return path

        normalized_path = cygpath.convert(
            path, env_var_seps=self.env_sep_map, mode="mixed"
        )

        if path != normalized_path:
            log("GitBash as_shell_path()")
            log("path normalized: {!r} -> {!r}".format(path, normalized_path))
            self._addline(
                "# path normalized: {!r} -> {!r}".format(path, normalized_path)
            )
        return normalized_path

    def normalize_path(self, path):
        """Normalize the path to fit the environment.
        For example, POSIX paths, Windows path, etc. If no transformation is
        necessary, just return the path.

        Args:
            path (str): File path.

        Returns:
            (str): Normalized file path.
        """
        # Prevent path conversion if normalization is disabled in the config.
        if not config.enable_path_normalization:
            return path

        normalized_path = cygpath.convert(path, mode="unix")
        if path != normalized_path:
            log("GitBash normalize_path()")
            log("path normalized: {!r} -> {!r}".format(path, normalized_path))
            self._addline(
                "# path normalized: {!r} -> {!r}".format(path, normalized_path)
            )

        return normalized_path

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
        if not config.enable_path_normalization:
            return value

        def lowrepl(match):
            if match:
                return "/{}/".format(match.group(1).lower())

        # C:\ ==> /c/
        normalized = self._drive_regex.sub(lowrepl, value).replace("\\", "/")

        if value != normalized:
            log("GitBash normalize_path[s]()")
            log("path normalized: {!r} -> {!r}".format(value, normalized))
            self._addline(
                "# path normalized: {!r} -> {!r}".format(value, normalized)
            )

        return normalized

    def shebang(self):
        self._addline("#!/usr/bin/env bash")


def register_plugin():
    if platform_.name == "windows":
        return GitBash
