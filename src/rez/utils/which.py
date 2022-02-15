# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


import os
import sys


_default_pathext = '.COM;.EXE;.BAT;.CMD;.VBS;.VBE;.JS;.JSE;.WSF;.WSH;.MSC'


def which(cmd, mode=os.F_OK | os.X_OK, path=None, env=None):
    """A replacement for shutil.which.

    Things we do that shutil.which does not:

        * Support specifying `env`
        * Take into account '%systemroot%' possible presence in `path` (windows)
        * Take into account symlinks to executables (windows)
    """
    iswin = (sys.platform == "win32")
    pathext = []
    if env is None:
        env = os.environ

    # Check that a given file can be accessed with the correct mode.
    # Additionally check that `file` is not a directory, as on Windows
    # directories pass the os.access check.
    #
    def _access_check(fn, mode):
        return (os.path.exists(fn) and os.access(fn, mode)
                and not os.path.isdir(fn))

    # If we're given a path with a directory part, look it up directly rather
    # than referring to PATH directories. This includes checking relative to the
    # current directory, e.g. ./script. Note that `path` is ignored in this case.
    #
    dirname, filename = os.path.split(cmd)
    if dirname:
        path = dirname
        cmd = filename

    if path is None:
        path = env.get("PATH", os.defpath)
    if not path:
        return None
    path = path.split(os.pathsep)

    if iswin:
        # The current directory takes precedence on Windows
        if not dirname and os.curdir not in path:
            path.insert(0, os.curdir)

        # PATHEXT is necessary to check on Windows
        pathext = env.get("PATHEXT", _default_pathext).split(os.pathsep)
        pathext = [x.lower() for x in pathext]

    # iterate over paths
    seen = set()
    for dir_ in path:
        normdir = os.path.normcase(dir_)

        # On windows the system paths might contain %systemroot%
        normdir = os.path.expandvars(normdir)

        if normdir in seen:
            continue
        seen.add(normdir)

        # search for matching cmd
        if iswin:
            # Account for cmd possibly being a symlink. A symlink can be an
            # executable on windows without an extension. If it is, see if its
            # target's extension matches any of the expected path extensions.
            #
            realfile = os.path.realpath(os.path.join(normdir, cmd)).lower()
            if any(realfile.endswith(x) for x in pathext):
                files = [cmd]
            else:
                files = [(cmd + ext) for ext in pathext]
        else:
            files = [cmd]

        for thefile in files:
            name = os.path.join(normdir, thefile)
            if _access_check(name, mode):
                return name

    return None
