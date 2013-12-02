"""
Simple API to extract information about the current rez-configured environment.
"""

import os
from rez_exceptions import PkgFamilyNotFoundError


class RezError(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return str(self.value)


def get_request(as_dict=False, parent_env=False):
    """
    @param as_dict If True, return value is in form { UPPER_PKG_NAME: (pkg-family, pkg-version) }
    @parent_env If true, return the request of the previous (parent) env. This is sometimes useful
        when a wrapped program needs to know information about the calling environment.
    @return the rez package request.
    """
    evar = "REZ_REQUEST"
    if parent_env:
        evar = "REZ_PREV_REQUEST"
    s = _get_rez_env_var(evar)
    pkgs = s.strip().split()
    if as_dict:
        return _get_pkg_dict(pkgs)
    else:
        return pkgs


def in_wrapper_env():
    """
    @returns True if the current environment is actually a wrapper, false otherwise.
    """
    return os.getenv("REZ_IN_WRAPPER") == "1"


def get_resolve(as_dict=False):
    """
    @param as_dict If True, return value is in form { UPPER_PKG_NAME: (pkg-family, pkg-version) }
    @return the rez package resolve.
    """
    s = _get_rez_env_var("REZ_RESOLVE")
    pkgs = s.strip().split()
    if as_dict:
        return _get_pkg_dict(pkgs)
    else:
        return pkgs


def get_resolve_timestamp():
    """
    @return the rez resolve timestamp.
    """
    s = _get_rez_env_var("REZ_REQUEST_TIME")
    return int(s)


def get_package_root(package_name):
    """
    @return Install path of the given package.
    """
    evar = "REZ_%s_ROOT" % package_name.upper()
    pkg_root = os.getenv(evar)
    if not pkg_root:
        raise PkgFamilyNotFoundError(package_name)
    return pkg_root


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
        toks = pkg.split('-', 1)
        fam = toks[0]
        ver = ""
        if len(toks) > 1:
            ver = toks[1]
        d[fam.upper()] = (fam, ver)
    return d
