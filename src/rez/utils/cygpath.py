# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
This module provides a simple emulation of the cygpath command that is available
in gitbash is used to convert between Windows and Unix styles. It provides
implementations of cygpath behavior to avoid complexities of adding cygpath as a
dependency such as compiling or relying on a system installation.
"""
import os
import posixpath
import re

from rez.config import config
from rez.utils.logging_ import print_debug


def log(*msg):
    if config.debug("cygpath"):
        print_debug(*msg)


def convert(path, mode=None, env_var_seps=None):
    r"""Convert a path to unix style or windows style as per cygpath rules.

    A "windows" mode is absent due to the fact that converting from unix to
    windows style is not necessary for rez or gitbash in rez to function and
    gitbash is the primary consumer of this function. Other shells may need to
    do their own normalization, and should not use this function for that purpose.

    Args:
        path (str): Path to convert.
        mode (str|Optional): Cygpath-style mode to use:
            unix (default): Unix style path (c:\ and C:\ -> /c/)
            mixed: Windows style drives with forward slashes
                (c:\ and C:\ -> C:/)

    Returns:
        str: Converted path.
    """
    mode = mode or "unix"
    if mode not in ("unix", "mixed", "windows"):
        raise ValueError("Unsupported mode: %s" % mode)

    env_var_seps = env_var_seps or {}
    matches = None
    for var, sep in env_var_seps.items():
        start = path
        regex = r"(\$\{%s\})([:;])" % var
        path = re.sub(regex, "\\1%s" % sep, path, 0)
        if path != start:
            log("cygpath convert_path() path in: {!r}".format(start))
            log("cygpath convert_path() path out: {!r}".format(path))
        matches = re.finditer(regex, path)

    prefix = None
    if matches:
        match = next(matches, None)
        if match is not None:
            prefix = match.group()

    if prefix:
        path = path.replace(prefix, "", 1)

    # Convert the path based on mode.
    if mode == "unix":
        path = to_posix_path(path)
    elif mode == "mixed":
        path = to_mixed_path(path)

    if prefix and path:
        path = prefix + path

    return path


def to_posix_path(path):
    r"""Convert (eg) 'C:\foo' to '/c/foo'

    Args:
        path (str): Path to convert.

    Returns:
        str: Converted path.
    """
    # Handle Windows long paths
    if path.startswith("\\\\?\\"):
        path = path[4:]

    unc, path = os.path.splitunc(path)
    if unc:
        path = unc.replace("\\", "/") + path.replace("\\", "/")
        return path

    drive = to_cygdrive(path)

    # Relative, or already in posix format (but missing a drive!)
    if not drive:
        raise ValueError(
            "Cannot convert path to posix path: {!r} "
            "Please ensure that the path is absolute".format(path)
        )

    _, path = os.path.splitdrive(path)

    # Already posix style
    if path.startswith(drive):
        path = path[len(drive):]

    # Remove leading slashes
    path = re.sub(r"^[\\/]+", "", path)
    path = slashify(path)

    # Drive and path will concatenate into an unexpected result
    if drive and path[0] == ".":
        raise ValueError(
            "Cannot convert path to posix path: {!r} "
            "This is most likely due to a malformed path".format(path)
        )

    return drive + path


def to_mixed_path(path):
    r"""Convert (eg) 'C:\foo\bin' to 'C:/foo/bin'

    Args:
        path (str): Path to convert.

    Returns:
        str: Converted path.
    """
    drive, path = os.path.splitdrive(path)

    if not drive:
        raise ValueError(
            "Cannot convert path to mixed path: {!r} "
            "Please ensure that the path is absolute".format(path)
        )
    if drive and not path:
        if len(drive) == 2:
            return drive + posixpath.sep
        raise ValueError(
            "Cannot convert path to mixed path: {!r} "
            "Please ensure that the path is absolute".format(path)
        )

    path = slashify(path)

    return drive + path


def slashify(path):
    # Remove double backslashes and dots
    path = os.path.normpath(path)
    # Normalize slashes
    path = path.replace("\\", "/")
    # Remove double slashes
    path = re.sub(r'/{2,}', '/', path)
    return path


def to_cygdrive(path):
    r"""Convert an NT drive to a cygwin-style drive.

    (eg) 'C:\' -> '/c/'

    Args:
        path (str): Path to convert.

    Returns:
        str: Converted path.
    """
    # Handle Windows long paths
    if path.startswith("\\\\?\\"):
        path = path[4:]

    # Normalize forward backslashes to slashes
    path = path.replace("\\", "/")

    # UNC paths are not supported
    unc, _ = os.path.splitunc(path)
    if unc:
        return ""

    if (
        path.startswith(posixpath.sep)
        and len(path) >= 2
        and path[1].isalpha()
        and path[2] == posixpath.sep
    ):
        drive = path[1]
    else:
        # Extract the drive letter from the first token
        drive, _ = os.path.splitdrive(path)

    if drive:
        # Check if the drive letter is valid
        drive_letter = drive[0].lower()
        if drive_letter.isalpha():
            # Valid drive letter format
            return posixpath.sep + drive_letter + posixpath.sep

    # Most likely a relative path
    return ""
