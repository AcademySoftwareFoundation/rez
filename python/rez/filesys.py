# TODO add blacklisting/archiving, is anyone using that though?
# TODO DEPRECATE this file.

import os
import sys
import os.path
import platform
import subprocess as sp
from rez.versions import ExactVersion
from rez.public_enums import REZ_PACKAGES_PATH_ENVVAR, PKG_METADATA_FILENAME
from rez.exceptions import *

VALID_PLATFORMS = ['darwin', 'linux', 'windows']

_g_rez_path = os.getenv("REZ_PATH")
_g_local_pkgs_path = os.getenv("REZ_LOCAL_PACKAGES_PATH")
_g_new_timestamp_behaviour = os.getenv("REZ_NEW_TIMESTAMP_BEHAVIOUR")
_g_os_paths = []

# TODO move elsewhere
from rez.system import system
_g_platform_pkg = 'platform-' + system.platform
_g_arch_pkg = 'arch-' + system.arch


# get os-specific paths
try:
    p = sp.Popen("_rez_get_PATH", stdout=sp.PIPE, stderr=sp.PIPE)
    out, err = p.communicate()
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
        return [tok.strip() for tok in syspathstr.split(':') if tok]
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
        if f.startswith('.'):
            continue
        fullpath = os.path.join(path, f)
        if os.path.isdir(fullpath):
            try:
                ver = ExactVersion(f)
            except:
                continue

            yaml_file = os.path.join(fullpath, PKG_METADATA_FILENAME)
            if not os.path.isfile(yaml_file):
                if warnings:
                    sys.stderr.write("Warning: ignoring package with missing " +
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
