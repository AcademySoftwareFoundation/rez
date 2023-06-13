# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
This module provides a simple emulation of the cygpath command that is available
in gitbash is used to convert between Windows and Unix styles. It provides
implementations of cygpath behavior to avoid complexities of adding cygpath as a
dependency such as compiling or relying on a system installation.
"""
import os
import re

from rez.utils.logging_ import print_debug

_drive_start_regex = re.compile(r"^([A-Za-z]):\\")
_drive_regex_mixed = re.compile(r"([a-z]):/")
_env_var_regex = re.compile(r"%([^%]*)%")


def convert(path, mode=None, env_var_seps=None, force_fwdslash=False):
    r"""Convert a path to unix style or windows style as per cygpath rules.

    Args:
        path (str): Path to convert.
        mode (str|Optional): Cygpath-style mode to use:
            unix (default): Unix style path (c:\ and C:\ -> /c/)
            mixed: Windows style drives with forward slashes
                (c:\ and C:\ -> C:/)
            windows: Windows style paths (C:\)
        force_fwdslash (bool|Optional): Return a path containing only
            forward slashes regardless of mode. Default is False.

    Returns:
        str: Converted path.
    """
    mode = mode or "unix"
    if mode not in ("unix", "mixed", "windows"):
        raise ValueError("Unsupported mode: %s" % mode)

    # expand refs like %SYSTEMROOT%, leave as-is if not in environ
    def _repl(m):
        varname = m.groups()[0]
        return os.getenv(varname, m.group())

    path = _env_var_regex.sub(_repl, path)

    env_var_seps = env_var_seps or {}
    for var, sep in env_var_seps.items():
        start = path
        regex = r"(\$\{%s\})([:;])" % var
        path = re.sub(regex, "\\1%s" % sep, path, 0)
        if path != start:
            print_debug("cygpath convert_path() path in: {!r}".format(start))
            print_debug("cygpath convert_path() path out: {!r}".format(path))

    # Convert the path based on mode.
    if mode == "unix":
        new_path = to_posix_path(path)
    elif mode == "mixed":
        new_path = to_mixed_path(path)
    elif mode == "windows":
        new_path = to_windows_path(path)

    # NOTE: This would be normal cygpath behavior, but the broader
    # implications of enabling it need extensive testing.
    # Leaving it up to the user for now.
    if force_fwdslash:
        # Backslash -> fwdslash
        new_path = new_path.replace('\\', '/')

    return new_path


def to_posix_path(path):
    r"""Convert (eg) "C:\foo" to "/c/foo"

    TODO: doesn't take into account escaped bask slashes, which would be
    weird to have in a path, but is possible.

    Args:
        path (str): Path to convert.
    """
    # c:\ and C:\ -> /c/
    drive_letter_match = _drive_start_regex.match(path)
    # If converting the drive letter to posix, capitalize the drive
    # letter as per cygpath behavior.
    if drive_letter_match:
        path = _drive_start_regex.sub(
            drive_letter_match.expand("/\\1/").lower(), path
        )

    # Backslash -> fwdslash
    # TODO: probably use filesystem.to_posixpath() intead
    path = path.replace('\\', '/')

    return path


def to_mixed_path(path):
    r"""Convert (eg) "C:\foo/bin" to "C:/foo/bin"

    The mixed syntax results from strings in package commands such as
    "{root}/bin" being interpreted in a windows shell.

    TODO: doesn't take into account escaped forward slashes, which would be
    weird to have in a path, but is possible.
    """
    def uprepl(match):
        if match:
            return '{}:/'.format(match.group(1).upper())

    # c:\ and C:\ -> C:/
    drive_letter_match = _drive_start_regex.match(path)
    # If converting the drive letter to posix, capitalize the drive
    # letter as per cygpath behavior.
    if drive_letter_match:
        path = _drive_start_regex.sub(
            drive_letter_match.expand("\\1:/").upper(), path
        )

    # Fwdslash -> backslash
    # TODO: probably use filesystem.to_ntpath() instead
    path = path.replace('\\', '/')

    # ${XYZ};c:/ -> C:/
    if _drive_regex_mixed.match(path):
        path = _drive_regex_mixed.sub(uprepl, path)

    return path


def to_windows_path(path):
    r"""Convert (eg) "C:\foo/bin" to "C:\foo\bin"

    TODO: doesn't take into account escaped forward slashes, which would be
    weird to have in a path, but is possible.
    """
    # Fwdslash -> backslash
    path = path.replace('/', '\\')

    return path
