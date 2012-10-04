import sys
import os
import time
import rez_filesys
import rez_metafile
from versions import *
from public_enums import *
from rez_exceptions import *
from memcached_client import *



_g_caching_enabled = True
_g_memcached_server = os.getenv("REZ_MEMCACHED_SERVER") or "127.0.0.1:11211"


def _create_client():
    if not _g_caching_enabled:
        return None
    return memcache.Client([_g_memcached_server], cache_cas=True)


# init
_g_caching_enabled = not os.getenv("REZ_DISABLE_CACHING")
if _g_caching_enabled:
    try:
        import memcache
    except:
        _g_caching_enabled = False
if _g_caching_enabled:
    mc = _create_client()
    if not mc.set("test_set", "success"):
        _g_caching_enabled = False
    mc = None


class RezMemCache():
    """
    Cache for filesystem access and resolves.
    """
    def __init__(self, time_epoch=0, use_caching=True):
        self.epoch = time_epoch or int(time.time())
        self.families = set()
        self.versions = {} # (path,order): [versions]
        self.metafiles = {} # path, ConfigMetadata
        self.mc = None
        if use_caching and _g_caching_enabled:
            mc = _create_client()
            self.mc = MemCacheClient(mc)

    def get_metafile(self, path):
        """
        Load the yaml metadata in the given file.
        """
        d = self.metafiles.get(path)
        if d is not None:
            return d

        k = ("PKGYAML", path)
        path_modtime = os.path.getmtime(path)

        if self.mc:
            t = self.mc.get(k)
            if t is not None:
                mtime,d = t
                if path_modtime == mtime:
                    self.metafiles[path] = d
                    return d

        d = rez_metafile.ConfigMetadata(path)
        d.delete_nonessentials()

        if self.mc:
            self.mc.set(k, (path_modtime, d))
        self.metafiles[path] = d
        return d

    def get_versions_in_directory(self, path, warnings=True):
        """
        For a given directory, return a list of (Version,epoch), which match version directories 
        found in the given directory.
        """
        vers = self.versions.get(path)
        if vers is not None:
            return vers

        if not os.path.isdir(path):
            return []

        k = ("VERSIONS", path)
        path_modtime = os.path.getmtime(path)

        if self.mc:
            t = self.mc.get(k)
            if t is not None:
                mtime,tvers = t
                if path_modtime == mtime:
                    vers = [x for x in tvers if x[1] <= self.epoch]
                    self.versions[path] = vers
                    return vers

        tvers = rez_filesys.get_versions_in_directory(path, warnings)
        if self.mc:
            self.mc.set(k, (path_modtime, tvers))
        vers = [x for x in tvers if x[1] <= self.epoch]
        self.versions[path] = vers
        return vers

    def find_package(self, path, ver_range, latest=True, exact=False):
        """
        Given a path to a package family and a version range, return (resolved version, epoch)
        or None if not found.
        """
        vers = self.get_versions_in_directory(path)

        # check for special case - unversioned package
        # todo subtle bug here, unversioned pkg's timestamp not taken into account. In practice
        # though this should not cause any problems.
        if not vers and ver_range.is_any() and os.path.isfile(os.path.join(path, PKG_METADATA_FILENAME)):
            return (Version(""), 0)

        if not ver_range.is_inexact():
            exact_ver = [x for x in vers if x[0] == ver_range.versions[0]]
            if exact_ver:
                return exact_ver[0]

        if exact:
            return None

        # find the earliest/latest version on disk that falls within ver
        if latest:
            vers = reversed(vers)
        for ver in vers:
            if ver_range.contains_version(ver[0].ge):
                return ver

        return None

    def find_package2(self, paths, family_name, ver_range, latest=True, exact=False):
        """
        Given a list of package paths, a family name and a version range, return (family path,
        resolved version, epoch), or (None,None,None) if not found. If two versions in two different 
        paths are the same, then the package in the first path is returned in preference.
        """
        maxminver = None
        fpath = None

        for pkg_path in paths:
            family_path = os.path.join(pkg_path, family_name)
            ver2 = self.find_package(family_path, ver_range, latest, exact)
            if ver2:
                if exact:
                    return family_path, ver2[0], ver2[1]
                elif latest:
                    if maxminver:
                        if (maxminver[0].ge < ver2[0].ge):
                            maxminver = ver2
                            fpath = family_path
                    else:
                        maxminver = ver2
                        fpath = family_path
                else:   # earliest
                    if maxminver:
                        if (maxminver[0].ge > ver2[0].ge):
                            maxminver = ver2
                            fpath = family_path
                    else:
                        maxminver = ver2
                        fpath = family_path

        if maxminver:
            return fpath, maxminver[0], maxminver[1]
        else:
            return (None,None,None)

    def package_family_exists(self, paths, family_name):
        """
        Determines if the package family exists. This involves only quite light file system 
        access, so isn't memcached.
        """
        if family_name in self.families:
            return True

        for path in paths:
            if os.path.isdir(os.path.join(path, family_name)):
                self.families.add(family_name)
                return True

        return False

    def store_resolve(self, paths, pkg_reqs, result):
        """
        Store a resolve in the cache.
        """
        if not self.mc:
            return

        pkg_res_list = result[0]

        # find most recent pkg timestamp, we store the cache entry on this
        max_epoch = 0
        for pkg_res in pkg_res_list:
            max_epoch = max(pkg_res.timestamp, max_epoch)

        # construct cache keys
        k_base = (paths, pkg_reqs)
        k_no_timestamp = ("RESOLVE-NO-TS", k_base)
        k_timestamped = ("RESOLVE", max_epoch, k_base)

        # store
        self.mc.update_add_to_set(k_no_timestamp, max_epoch)
        self.mc.set(k_timestamped, result)

    def get_resolve(self, paths, pkg_reqs):
        """
        Return a cached resolve, or None if the resolve is not found or possible outdated.
        """
        if not self.mc:
            return None,None

        k_base = (paths, pkg_reqs)

        # get most recent cache of this resolve that is < current time
        k_no_timestamp = ("RESOLVE-NO-TS", k_base)
        timestamps = self.mc.get(k_no_timestamp)
        if not timestamps:
            return None,None

        older_timestamps = [x for x in timestamps if x < self.epoch]
        if not older_timestamps:
            return None,None

        cache_timestamp = sorted(older_timestamps)[-1]
        k_timestamped = ("RESOLVE", cache_timestamp, k_base)
        result = self.mc.get(k_timestamped)
        if not result:
            return None,None

        # check if there are any versions of the resolved packages that are newer than the resolved
        # version, but older than the current time - if so, this resolve may be out of date, and
        # must be discarded.
        pkg_res_list = result[0]
        for pkg_res in pkg_res_list:
            pkg_res_ver = Version(pkg_res.version)
            fam_path,ver,pkg_epoch = self.find_package2(paths, pkg_res.name, VersionRange(""))
            if ver is not None and ver > pkg_res_ver and pkg_epoch <= self.epoch:
                return None,None

        return result, cache_timestamp
