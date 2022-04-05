# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project

import re


def to_posix_path(path):
    """Convert (eg) "C:\foo" to "/c/foo"
    TODO: doesn't take into account escaped bask slashes, which would be
    weird to have in a path, but is possible.
    """
    if re.match("[A-Z]:", path):
        path = '/' + path[0].lower() + path[2:]
    return path.replace('\\', '/')


def to_windows_path(path):
    """Convert (eg) "C:\foo/bin" to "C:\foo\bin"
    The mixed syntax results from strings in package commands such as
    "{root}/bin" being interpreted in a windows shell.
    TODO: doesn't take into account escaped forward slashes, which would be
    weird to have in a path, but is possible.
    """
    return path.replace('/', '\\')
