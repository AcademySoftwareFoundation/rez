# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


import os
import re
import subprocess
from rez.utils.execution import Popen


_drive_start_regex = re.compile(r"^([A-Za-z]):\\")
_env_var_regex = re.compile(r"%([^%]*)%")


def convert_path(path, mode='unix', force_fwdslash=False):
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
        path(str): Converted path.
    """
    # expand refs like %SYSTEMROOT%, leave as-is if not in environ
    def _repl(m):
        varname = m.groups()[0]
        return os.getenv(varname, m.group())

    path = _env_var_regex.sub(_repl, path)

    # Convert the path based on mode.
    if mode == 'mixed':
        path = to_mixed_path(path)
    elif mode == 'windows':
        path = to_windows_path(path)
    else:
        path = to_posix_path(path)

    # NOTE: This would be normal cygpath behavior, but the broader
    # implications of enabling it need extensive testing.
    # Leaving it up to the user for now.
    if force_fwdslash:
        # Backslash -> fwdslash
        path = path.replace('\\', '/')

    return path


def to_posix_path(path):
    """Convert (eg) "C:\foo" to "/c/foo"

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
    path = path.replace('\\', '/')

    return path


def to_mixed_path(path):
    """Convert (eg) "C:\foo/bin" to "C:/foo/bin"

    The mixed syntax results from strings in package commands such as
    "{root}/bin" being interpreted in a windows shell.

    TODO: doesn't take into account escaped forward slashes, which would be
    weird to have in a path, but is possible.
    """
    # c:\ and C:\ -> C:/
    drive_letter_match = _drive_start_regex.match(path)
    # If converting the drive letter to posix, capitalize the drive
    # letter as per cygpath behavior.
    if drive_letter_match:
        path = _drive_start_regex.sub(
            drive_letter_match.expand("\\1:/").upper(), path
        )

    # Fwdslash -> backslash
    path = path.replace('/', '\\')

    return path


def to_windows_path(path):
    r"""Convert (eg) "C:\foo/bin" to "C:\foo\bin"

    TODO: doesn't take into account escaped forward slashes, which would be
    weird to have in a path, but is possible.
    """
    # Fwdslash -> backslash
    path = path.replace('/', '\\')

    return path


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
