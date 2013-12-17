# TODO add blacklisting/archiving, is anyone using that though?

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

def get_platform():
    osname = os.getenv("REZ_PLATFORM")
    if osname:
        print ("Warning: REZ_PLATFORM is no longer supported. Please modify "
               "'%s' to require one of %s" % (osname,
                                              ', '.join(['platform-' + plat for plat in VALID_PLATFORMS])))
    plat = platform.system().lower()

    if plat not in VALID_PLATFORMS:
        sys.stderr.write("Rez warning: Unknown operating system '" + plat + "'\n")
    return plat

def get_arch():
    # http://stackoverflow.com/questions/7164843/in-python-how-do-you-determine-whether-the-kernel-is-running-in-32-bit-or-64-bi
    if os.name == 'nt' and sys.version_info[:2] < (2, 7):
        arch = os.environ.get("PROCESSOR_ARCHITEW6432",
                              os.environ.get('PROCESSOR_ARCHITECTURE', ''))
        if not arch:
            sys.stderr.write("Rez warning: Could not determine architecture\n")
        return arch
    else:
        return platform.machine()

_g_os_pkg = 'platform-' + get_platform()
_g_arch_pkg = 'arch-' + get_arch()

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
