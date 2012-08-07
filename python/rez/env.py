"""
Simple API to extract information about the current rez-configured environment.
"""

import os


class RezError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return str(self.value)


def get_request(as_dict=False):
    """
    @param as_dict If True, return value is in form { UPPER_PKG_NAME: (pkg-family, pkg-version) }
    @return the rez package request.
    """
    s = _get_rez_env_var("REZ_REQUEST")
    pkgs = s.strip().split()
    if as_dict:     return _get_pkg_dict(pkgs)
    else:           return pkgs


def get_resolve(as_dict=False):
    """
    @param as_dict If True, return value is in form { UPPER_PKG_NAME: (pkg-family, pkg-version) }
    @return the rez package resolve.
    """
    s = _get_rez_env_var("REZ_RESOLVE")
    pkgs = s.strip().split()
    if as_dict:     return _get_pkg_dict(pkgs)
    else:           return pkgs


def get_resolve_timestamp():
    """
    @return the rez resolve timestamp.
    """
    s = _get_rez_env_var("REZ_REQUEST_TIME")
    return int(s)


def get_context_path():
    """
    @return Filepath of the context file for the current environment.
    """
    return _get_rez_env_var("REZ_CONTEXT_FILE")


def get_context_dot_path():
    """
    @return Filepath of the context resolve graph dot-file for the current environment.
    """
    return get_context_path() + ".dot"


def _get_rez_env_var(var):
    val = os.getenv(var)
    if val is None:
        raise RezError("Not in a correctly-configured Rez environment")
    return val


def _get_pkg_dict(pkgs):
    d = {}
    for pkg in pkgs:
        toks = pkg.split('-',1)
        fam = toks[0]
        ver = ""
        if len(toks) > 1:
            ver = toks[1]
        d[fam.upper()] = (fam, ver)
    return d
