# TODO add blacklisting/archiving, is anyone using that though?

import os
import sys
import os.path
import subprocess as sp
from versions import *
from public_enums import *
from rez_exceptions import *


_g_rez_path                 = os.getenv("REZ_PATH")
_g_local_pkgs_path          = os.getenv("REZ_LOCAL_PACKAGES_PATH")
_g_new_timestamp_behaviour  = os.getenv("REZ_NEW_TIMESTAMP_BEHAVIOUR")
_g_os_paths                 = []


# get os
_g_os_pkg = None
osname = os.getenv("REZ_PLATFORM")
if osname:
    _g_os_pkg = osname
else:
    import platform
    osname = platform.system()
    _g_os_pkg = ""

    if osname == "Linux":
        _g_os_pkg = "Linux"
    elif osname == "Darwin":
        _g_os_pkg = "Darwin"

if _g_os_pkg == "":
    sys.stderr.write("Rez warning: Unknown operating system '" + _g_os_pkg + "'\n")


# get os-specific paths
try:
    p = sp.Popen("_rez_get_PATH", stdout=sp.PIPE, stderr=sp.PIPE)
    out,err = p.communicate()
    _g_os_paths = out.strip().split(':')
except:
    pass


def get_system_package_paths():
    """
    Get the system roots for package installations. REZ_PACKAGES_PATH is a colon-
    separated string, and the paths will be searched in order of appearance.
    """
    syspathstr = os.getenv(REZ_PACKAGES_PATH_ENVVAR)
    if syspathstr:
        toks = syspathstr.split(':')
        syspaths = []
        for tok in toks:
            if tok:
                syspaths.append(tok.strip())
        return syspaths
    else:
        raise PkgSystemError(REZ_PACKAGES_PATH_ENVVAR + " is not set")

_g_syspaths = get_system_package_paths()

_g_syspaths_nolocal = _g_syspaths[:]
if _g_local_pkgs_path in _g_syspaths_nolocal:
    _g_syspaths_nolocal.remove(_g_local_pkgs_path)


def get_versions_in_directory(path, warnings):
    is_local_pkgs = path.startswith(_g_local_pkgs_path)
    vers = []

    for f in os.listdir(path):
        fullpath = os.path.join(path, f)
        if os.path.isdir(fullpath):
            try:
                ver = Version(f)
            except:
                continue

            yaml_file = os.path.join(fullpath, PKG_METADATA_FILENAME)
            if not os.path.isfile(yaml_file):
                if warnings:
                    sys.stderr.write("Warning: ignoring package with missing " + \
                        PKG_METADATA_FILENAME + ": " + fullpath + '\n')
                continue

            timestamp = 0
            if not is_local_pkgs:
                release_time_f = os.path.join(fullpath, '.metadata', 'release_time.txt')
                if os.path.isfile(release_time_f):
                    with open(release_time_f, 'r') as f:
                        timestamp = int(f.read().strip())
                elif _g_new_timestamp_behaviour:
                    s = "Warning: The package at %s is not timestamped and will be ignored. " + \
                        "To timestamp it manually, use the rez-timestamp utility."
                    print >> sys.stderr, s % fullpath
                    continue

            vers.append((ver, timestamp))

    vers.sort()
    return vers
