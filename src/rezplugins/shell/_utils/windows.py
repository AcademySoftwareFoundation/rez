# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


import os
import re
import subprocess
from rez.utils.execution import Popen


_drive_start_regex = re.compile(r"^([A-Za-z]):\\")
_env_var_regex = re.compile(r"%([^%]*)%")


def to_posix_path(path):
    """Convert (eg) "C:\foo" to "/c/foo"

    TODO: doesn't take into account escaped bask slashes, which would be
    weird to have in a path, but is possible.
    """

    # expand refs like %SYSTEMROOT%, leave as-is if not in environ
    def _repl(m):
        varname = m.groups()[0]
        return os.getenv(varname, m.group())

    path = _env_var_regex.sub(_repl, path)

    # C:\ ==> /C/
    path = _drive_start_regex.sub("/\\1/", path)

    # backslash ==> fwdslash
    path = path.replace('\\', '/')

    return path


def to_windows_path(path):
    """Convert (eg) "C:\foo/bin" to "C:\foo\bin"

    The mixed syntax results from strings in package commands such as
    "{root}/bin" being interpreted in a windows shell.

    TODO: doesn't take into account escaped forward slashes, which would be
    weird to have in a path, but is possible.
    """
    return path.replace('/', '\\')


def get_syspaths_from_registry():

    def gen_expected_regex(parts):
        whitespace = r"[\s]+"
        return whitespace.join(parts)

    entries = (
        # local machine
        dict(
            cmd=[
                "REG",
                "QUERY",
                "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment",
                "/v",
                "PATH"
            ],
            expected=gen_expected_regex([
                "HKEY_LOCAL_MACHINE\\\\SYSTEM\\\\CurrentControlSet\\\\Control\\\\Session Manager\\\\Environment",
                "PATH",
                "REG_(EXPAND_)?SZ",
                "(.*)"
            ])
        ),
        # current user
        dict(
            cmd=[
                "REG",
                "QUERY",
                "HKCU\\Environment",
                "/v",
                "PATH"
            ],
            expected=gen_expected_regex([
                "HKEY_CURRENT_USER\\\\Environment",
                "PATH",
                "REG_(EXPAND_)?SZ",
                "(.*)"
            ])
        )
    )

    paths = []

    for entry in entries:
        p = Popen(
            entry["cmd"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
            text=True
        )

        out_, _ = p.communicate()
        out_ = out_.strip()

        if p.returncode == 0:
            match = re.match(entry["expected"], out_)
            if match:
                paths.extend(match.group(2).split(os.pathsep))

    return [x for x in paths if x]
