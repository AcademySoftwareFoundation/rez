# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


import os
import re


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
