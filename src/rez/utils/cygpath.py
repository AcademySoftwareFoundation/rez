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
import shlex

from rez.config import config
from rez.utils.logging_ import print_debug

_drive_start_regex = re.compile(r"^([A-Za-z]):[\\/]")
_drive_regex_mixed = re.compile(r"([a-z]):/")


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
    """Convert (eg) "C:\foo" to "/c/foo"

    Args:
        path (str): Path to convert.

    Returns:
        str: Converted path.
    """
    drive = to_cygdrive(path)
    _, path = os.path.splitdrive(path)
    path = path.replace("\\", "", 1)
    path = drive + path.replace("\\", "/")

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


def to_cygdrive(path):
    """Convert an NT drive to a cygwin-style drive.

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

    # Split the path into tokens using shlex
    tokens = shlex.split(path) or path  # no tokens

    # Empty paths are invalid
    if not tokens:
        return ""

    # Extract the drive letter from the first token
    drive, _ = os.path.splitdrive(tokens[0])

    if drive:
        # Check if the drive letter is valid
        drive_letter = drive[0].lower()
        if drive_letter.isalpha():
            # Valid drive letter format
            return posixpath.sep + drive_letter + posixpath.sep

    return ""
