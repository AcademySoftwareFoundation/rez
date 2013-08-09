import os
import sys
import yaml
import os.path
import subprocess as sp
from versions import *
from public_enums import *
from rez_exceptions import *
from version_compare import version_compare


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


def get_versions_in_directory(path, warnings=False, ignore_archived=True, ignore_blacklisted=True):
    is_local_pkgs = path.startswith(_g_local_pkgs_path)
    vers = []

    archive = []
    blacklist = []
    if ignore_archived or ignore_blacklisted:
        packages_f = os.path.join(path, 'packages.yaml')
        with open(packages_f, 'r') as f:
            cfg = '\n'.join(f.readlines())
            data = (yaml.load(cfg))
            if 'archive' in data:
                for each in data['archive']:
                    archive.append(Version(each))
            if 'blacklist' in data:
                for each in data['blacklist']:
                    blacklist.append(Version(each))

    for f in os.listdir(path):
        fullpath = os.path.join(path, f)
        if os.path.isdir(fullpath) and is_package_version_dir(fullpath):
            ver = Version(f)
            if ignore_archived and [x for x in archive if ver.get_intersection(x)]:
                continue
            if ignore_blacklisted and [x for x in blacklist if ver.get_intersection(x)]:
                continue
            timestamp = 0
            if not is_local_pkgs:
                release_time_f = fullpath + '/.metadata/release_time.txt'
                if os.path.isfile(release_time_f):
                    with open(release_time_f, 'r') as f:
                        timestamp = int(f.read().strip())
                elif _g_new_timestamp_behaviour:
                    s = "Warning: The package at %s is not timestamped and will be ignored. " + \
                        "To timestamp it manually, use the rez-timestamp utility."
                    print >> sys.stderr, s % fullpath
                    continue

            vers.append((ver, timestamp))

    if (not vers) and warnings and os.path.basename(path) != _g_os_pkg: # The os packages may be unversioned (?)'
        sys.stderr.write("Warning: no valid versions (i.e., no subdirs with files found with name '%s') under '%s'\n" %
             (PKG_METADATA_FILENAME, path)
        )

    tmp = {}
    for ver in vers:
        tmp[ver[0].original_version_str] = ver
    sorted_vers = sort_versions(tmp.keys())
    vers = [tmp[x] for x in sorted_vers]
    return vers

def is_package_version_dir(root):
    result = False
    for root, dirs, files in os.walk(root, topdown=False):
        if PKG_METADATA_FILENAME in files:
            result = True
    return result

def sort_versions(versions):
    return sorted(versions, cmp=version_compare)
