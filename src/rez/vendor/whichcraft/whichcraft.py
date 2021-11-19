# -*- coding: utf-8 -*-

__author__ = "Daniel Roy Greenfeld"
__email__ = "pydanny@gmail.com"
__version__ = "0.6.1"

import os
import sys


_default_pathext = '.COM;.EXE;.BAT;.CMD;.VBS;.VBE;.JS;.JSE;.WSF;.WSH;.MSC'


def which(cmd, mode=os.F_OK | os.X_OK, path=None, env=None):
    """Given a command, mode, and a PATH string, return the path which
    conforms to the given mode on the PATH, or None if there is no such
    file.
    `mode` defaults to os.F_OK | os.X_OK. `path` defaults to the result
    of os.environ.get("PATH"), or can be overridden with a custom search
    path.
    Note: This function was backported from the Python 3 source code.
    """
    # Check that a given file can be accessed with the correct mode.
    # Additionally check that `file` is not a directory, as on Windows
    # directories pass the os.access check.

    # NOTE: Modified for rez, original code in commit:
    # https://github.com/nerdvegas/rez/commit/f5b0ea07ea2a8d9dae691b0768f63a9239ca7c91

    def _access_check(fn, mode):
        return os.path.exists(fn) and os.access(fn, mode) and not os.path.isdir(fn)

    # If we're given a path with a directory part, look it up directly
    # rather than referring to PATH directories. This includes checking
    # relative to the current directory, e.g. ./script
    if os.path.dirname(cmd):
        if _access_check(cmd, mode):
            return cmd

        return None

    if env is None:
        env = os.environ

    if path is None:
        path = env.get("PATH", os.defpath)
    if not path:
        return None

    path = path.split(os.pathsep)

    if sys.platform == "win32":
        # The current directory takes precedence on Windows.
        if os.curdir not in path:
            path.insert(0, os.curdir)

        # PATHEXT is necessary to check on Windows.
        pathext = os.environ.get("PATHEXT", _default_pathext).split(os.pathsep)
        # See if the given file matches any of the expected path
        # extensions. This will allow us to short circuit when given
        # "python.exe". If it does match, only test that one, otherwise we
        # have to try others.
        if any(cmd.lower().endswith(ext.lower()) for ext in pathext):
            files = [cmd]
        else:
            files = [cmd + ext.lower() for ext in pathext]
    else:
        # On other platforms you don't have things like PATHEXT to tell you
        # what file suffixes are executable, so just pass on cmd as-is.
        files = [cmd]

    seen = set()
    for dir in path:
        normdir = os.path.normcase(dir)
        if normdir not in seen:
            seen.add(normdir)
            for thefile in files:
                name = os.path.join(dir, thefile)

                # On windows the system paths might have %systemroot%
                name = os.path.expandvars(name)

                if _access_check(name, mode):
                    return name

    return None
