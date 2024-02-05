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
from rez.utils import platform_
from rez.utils.logging_ import print_debug

if platform_.name == "windows":
    from rez.utils import uncpath
    uncpath_available = True
else:
    uncpath_available = False


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

    match = None
    start = path
    for var, sep in env_var_seps.items():
        # ${VAR}: or ${VAR};
        regex = r"(\$\{%s\})([:;])" % var
        path = re.sub(regex, "\\1%s" % sep, path, 0)
        match = re.match(regex, path)
        if match is not None:
            break

    prefix = None
    if match is not None:
        prefix = match.group()

    if prefix:
        path = path.replace(prefix, "", 1)

    if not path:
        return start

    # Convert the path based on mode.
    if mode == "unix":
        path = to_posix_path(path)
    elif mode == "mixed":
        path = to_mixed_path(path)

    if prefix and path:
        path = prefix + path

    if path != start:
        log("cygpath convert() path in: {!r}".format(start))
        log("cygpath convert() path out: {!r}".format(path))
    return path


def to_posix_path(path):
    r"""Convert (eg) 'C:\foo' to '/c/foo'

    Note: Especially for UNC paths, and as opposed mixed path conversion, this
    function will return a path that is not guaranteed to exist.

    If path is already posix, it is returned unchanged. Paths such as
    '/mingw64/bin' or '/usr/bin' are built in to gitbash and absolute paths
    such as '/' point to the root of the gitbash installation.

    Args:
        path (str): Path to convert.

    Returns:
        str: Converted path.

    Raises:
        ValueError: If the path path is malformed
    """
    # Handle Windows long paths
    if path.startswith("\\\\?\\"):
        path = path[4:]

    # Handle UNC paths
    unc, unc_path = os.path.splitdrive(path)
    if unc:
        if unc.startswith("\\\\"):
            unc_path = unc.replace("\\", "/") + slashify(unc_path)
            return unc_path
        elif unc.startswith("//"):
            return slashify(path, unc=True)

    drive = to_cygdrive(path)

    # Relative, or absolute posix path with no drive letter
    if not drive:
        return slashify(path)

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


def to_mixed_path(path, strict=False):
    r"""Convert (eg) 'C:\foo\bin' to 'C:/foo/bin'

    Note: Especially in the case of UNC paths, this function will return a path
    that is practically guaranteed to exist but it is not verified.

    Args:
        path (str): Path to convert.
        strict (bool): Raise error if UNC path is not mapped to a drive. If False,
            just return the path with slashes normalized.

    Returns:
        str: Converted path.

    Raises:
        ValueError: If the path is posix and absolute or drive letter is not mapped
            to a UNC path.
    """
    # Handle Windows long paths
    if path.startswith("\\\\?\\"):
        path = path[4:]

    # Handle UNC paths
    # Return mapped drive letter if any, else raise
    unc, unc_path = os.path.splitdrive(path)
    if unc and unc.startswith("\\\\"):
        drive = to_mapped_drive(path)
        if drive:
            return drive + slashify(unc_path)
        if strict:
            raise ValueError(
                "Cannot convert path to mixed path: {!r} "
                "Unmapped UNC paths are not supported".format(path)
            )
        return slashify(path, unc=True)

    drive, path = os.path.splitdrive(path)

    if not drive:
        path = slashify(path)
        if path.startswith("/"):
            raise ValueError(
                "Cannot convert path to mixed path: {!r} "
                "Please ensure that the path is not absolute".format(path)
            )
        # Path is relative
        return path

    if drive and not path:
        if len(drive) == 2:
            return drive + posixpath.sep
        raise ValueError(
            "Cannot convert path to mixed path: {!r} "
            "Please ensure that the path is absolute".format(path)
        )

    path = slashify(path)

    return drive + path


def slashify(path, unc=False):
    """Ensures path only contains forward slashes.

    Args:
        path (str): Path to convert.
        unc (bool): Path is a unc path

    Returns:
        str: Path with slashes normalized.
    """
    # Remove double backslashes and dots
    path = os.path.normpath(path)
    # Normalize slashes
    path = path.replace("\\", "/")
    # Remove double slashes
    if not unc:
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

    # Handle UNC paths
    # Return mapped drive letter if any, else return ""
    unc, _ = os.path.splitdrive(path)
    if unc and unc.startswith("\\\\"):
        drive = to_mapped_drive(path)
        if drive:
            return posixpath.sep + drive.lower() + posixpath.sep
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


def to_mapped_drive(path):
    r"""Convert a UNC path to an NT drive if possible.

    (eg) '\\\\server\\share\\folder' -> 'X:'

    Args:
        path (str): UNC path.

    Returns:
        str: Drive mapped to UNC, if any.
    """
    if not uncpath_available:
        return
    unc, _ = os.path.splitdrive(path)
    if unc and unc.startswith("\\\\"):
        return uncpath.to_drive(unc)
