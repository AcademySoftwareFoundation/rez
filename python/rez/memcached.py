import sys
import os
from collections import defaultdict
import rez.filesys as filesys
import rez.resources as resources
from rez.packages import Package
from rez.public_enums import *
from rez.exceptions import *

_g_caching_enabled = True
_g_memcached_server = os.getenv("REZ_MEMCACHED_SERVER") or "127.0.0.1:11211"


def _create_client():
    if not _g_caching_enabled:
        return None
    return memcache.Client([_g_memcached_server], cache_cas=True)


def print_cache_warning(msg):
    print >> sys.stderr, "Cache Warning: %s" % msg

# init
_g_caching_enabled = not os.getenv("REZ_DISABLE_CACHING")
if _g_caching_enabled:
    try:
        import memcache
        from memcached_client import *
    except:
        _g_caching_enabled = False
if _g_caching_enabled:
    mc = _create_client()
    if not mc.set("test_set", "success"):
        _g_caching_enabled = False
    mc = None

_memcache = None

def get_memcache():
    global _memcache
    if not _memcache:
        _memcache = RezMemCache()
        # raise RezError("Memcache does not exist. use memcaching() context manager to create")
    return _memcache

def cached_path(key, default=None, postfilter=None, local_only=False):
    """
    A decorator to aid in automatically caching functions that take a path as
    an argument.

    key : str
        unique key used to identify the data to cache with the memcache client
    default : any
        value to return if the path does not exist
    postfilter : function
        filter function to apply to data after retrieving it from the memcache client.
        should take the data and an instance of the RezMemCache as arguments and
        return a modified copy of data.
    local_only : bool
        if True, only store the results in the local instance cache. this is useful
        for data that is too big to store in the remote memcache.
    """
    def decorator(func):
        def wrapped_func(self, path, *args, **kwargs):
            # get the cache for this key.
            # self.cache is a defaultdict, so this will always return a dict
            cache = self.cache[key]

            # FIXME: allow None to be cached.
            data = cache.get(path)
            if data is not None:
                return data

            try:
                path_modtime = os.path.getmtime(path)
            except OSError:
                if default is not None:
                    return default
                raise

            k = (key, path)
            # get memcached data if it exists
            if self.mc:
                # FIXME: allow None to be cached.
                t = self.mc.get(k)
                if t is not None:
                    mtime, d = t
                    if path_modtime == mtime:
                        data = d

            if not data:
                # cached data does not exist or is stale: get the data
                data = func(self, path, *args, **kwargs)

            assert data is not None, "Cached function must not return None"

            # cache result to memcache
            if self.mc:
                self.mc.set(k, (path_modtime, data))

            if postfilter:
                data = postfilter(data, self)

            # cache result to local instance cache
            cache[path] = data
            return data

        wrapped_func.__name__ = func.__name__
        wrapped_func.__doc__ = func.__doc__
        wrapped_func.__module__ = func.__module__
        return wrapped_func
    return decorator

class RezMemCache(object):
    """
    Cache for filesystem access and resolves.
    """
    def __init__(self, use_caching=True):
        self.cache = defaultdict(dict)
        self.families = set()
        self.mc = None
        if use_caching and _g_caching_enabled:
            mc = _create_client()
            self.mc = MemCacheClient(mc)

    def caching_enabled(self):
        """
        whether the memcache client is being used
        """
        return bool(self.mc)

    @cached_path("PKGYAML")
    def get_metadata(self, path):
        """
        Load the *essential* metadata in the given file.
        """
        return resources.load_metadata(path)

    @cached_path("VERSIONS", default=())
    def get_versions_in_directory(self, path, warnings=True):
        """
        For a given directory, return a list of (Version,epoch), which match version directories
        found in the given directory.
        """
        return filesys.get_versions_in_directory(path, warnings)

    @cached_path("LISTDIR", default=())
    def list_directory(self, path, warnings=True):
        """
        For a given directory, return the list of files and dirs within.
        """
        return os.listdir(path)

    def package_family_exists(self, family_name, paths=None):
        """
        Determines if the package family exists. This involves only quite light file system
        access, so isn't memcached.
        """
        if family_name in self.families:
            return True

        if paths is None:
            paths = filesys._g_syspaths

        for path in paths:
            if os.path.isdir(os.path.join(path, family_name)):
                self.families.add(family_name)
                return True

        return False

    def package_fam_modified_during(self, paths, family_name, start_epoch, end_epoch):
        for path in paths:
            famp = os.path.join(path, family_name)
            if os.path.isdir(famp):
                mtime = int(os.path.getmtime(famp))
                if mtime >= start_epoch and mtime <= end_epoch:
                    return famp

    # --- direct memcache usage

    def store_resolve(self, paths, pkg_reqs, result, timestamp):
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
        self.mc.set(k_timestamped, (timestamp, result))

    def get_resolve(self, paths, pkg_reqs, timestamp):
        """
        Return a cached resolve, or None if the resolve is not found or possibly stale.
        """
        if not self.mc:
            return None, None

        k_base = (paths, pkg_reqs)

        # get most recent cache of this resolve that is < current resolve time
        k_no_timestamp = ("RESOLVE-NO-TS", k_base)
        timestamps = self.mc.get(k_no_timestamp)
        if not timestamps:
            return None, None

        if timestamp:
            timestamps = [x for x in timestamps if x < timestamp]
            if not timestamps:
                return None, None

        cache_timestamp = sorted(timestamps)[-1]
        k_timestamped = ("RESOLVE", cache_timestamp, k_base)
        t = self.mc.get(k_timestamped)
        if not t:
            return None, None

        # trim down list of resolve pkgs to those that may invalidate the cache
        result_epoch, result = t

        # cache cannot be stale in this case
        if self.epoch <= result_epoch:
            return result, cache_timestamp

        pkg_res_list = result[0]
        pkgs = {}
        for pkg_res in pkg_res_list:
            pkgs[pkg_res.name] = pkg_res

        # check for new package versions released before the current resolve time, but after the
        # cache resolve time. These may invalidate the cache.
        for pkg_name, pkg in pkgs.items():
            if not self.package_fam_modified_during(paths, pkg_name, result_epoch, self.epoch):
                del pkgs[pkg_name]

        if not pkgs:
            return result, result_epoch

        # remove pkgs where new versions have been released after the cache was written, but none
        # of these versions fall within the 'max bounds' of that pkg. This can be simplified to
        # checking only the earliest version in this set.
        # TODO NOT YET IMPLEMENTED
        # for pkg_name,pkg in pkgs.items():
        #    pass

        if pkgs:
            print_cache_warning("Newer released package(s) caused cache miss: %s" %
                                str(", ").join(pkgs.keys()))
            return None, None
        else:
            return result, cache_timestamp

        """
        # check if there are any versions of the resolved packages that are newer than the resolved
        # version, but older than the current time - if so, this resolve may be out of date, and
        # must be discarded.
        print "checking for newer versions..."

        pkg_res_list = result[0]
        for pkg_res in pkg_res_list:
            pkg_res_ver = Version(pkg_res.version)
            fam_path,ver,pkg_epoch = self.find_package2(paths, pkg_res.name, VersionRange(""))
            if ver is not None and ver > pkg_res_ver and pkg_epoch <= self.epoch:
                print fam_path
                print "newer pkg: " + str(ver)
                print "existing pkg: " + str(pkg_res_ver)
                return None,None

        return result, cache_timestamp
        """
