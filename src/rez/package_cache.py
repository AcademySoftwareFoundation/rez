import os.path
import errno
from hashlib import sha1
import shutil
import json

from rez.exceptions import PackageCacheError
from rez.utils.filesystem import safe_listdir


class PackageCache(object):
    """Package cache.

    A package cache is responsible for storing copies of variant payloads into a
    location that would typically be on local disk. The intent is to avoid
    fetching a package's files over shared storage at runtime.

    A package cache is used like so:

    * A rez-env is performed;
    * The context is resolved;
    * For each variant in the context, we check to see if it's present in the
      current package cache;
    * If it is, the variant's root is remapped to this location.

    A package cache is _not_ a package repository. It just stores copies of
    variant payloads - no package definitions are stored.

    Payloads are stored into the following structure:

        /<cache_dir>/foo/1.0.0/af8d/a/<payload>
                                   /a.json

    Here, 'af8d' is the first 4 chars of the SHA1 hash of the variant's 'handle',
    which is a dict of fields that uniquely identify the variant. To avoid
    hash collisions, the variant is then stored under a subdir that is incrementally
    named ('a', 'b', ..., 'aa', 'ab', ...). The 'a.json' file is used to find the
    correct variant within the hash subdir. The intent is to keep cached paths
    short, and avoid having to search too many variant.json files to find the
    matching variant.
    """

    # See add_variant()
    VARIANT_NOT_FOUND = 0
    VARIANT_FOUND = 1
    VARIANT_CREATED = 2
    VARIANT_COPYING = 3

    def __init__(self, path):
        """Create a package cache.

        Args:
            path (str): Path on disk, must exist.
        """
        if not os.path.isdir(path):
            raise PackageCacheError("Not a directory: %s" % path)

        self.path = path

    def get_cached_root(self, variant):
        """Get location of variant payload copy.

        Args:
            variant (`Variant`): Variant to search for.

        Returns:
            str: Cached variant root path, or None if not found.
        """
        status, rootpath = self._get_cached_root(variant)
        if status != self.VARIANT_FOUND:
            return None

        # touch the root path so we know when it was last used
        try:
            os.utime(rootpath, None)
        except OSError as e:
            if e.errno == errno.ENOENT:
                # maybe got cleaned up by other process
                return None
            else:
                raise

        return rootpath

    def add_variant(self, variant, follow_symlinks=False, force=False):
        """Copy a variant's payload into the cache.

        The following steps are taken to ensure muti-thread/proc safety, and to
        guarantee that a partially-copied variant payload is never able to be
        used:

        1. The hash dir (eg '/<cache_dir>/foo/1.0.0/af8d') is created;
        2. A file lock mutex ('/<cache_dir>/foo/1.0.0/af8d/.lock') is acquired;
        3. The file '/<cache_dir>/foo/1.0.0/af8d/.copying-a' (or -b, -c etc) is
           created. This tells rez that this variant is being copied and cannot
           be used yet;
        4. The file '/<cache_dir>/foo/1.0.0/af8d/a.json' is created. Now
           another proc/thread can't create the same local variant;
        5. The file lock is released;
        6. The variant payload is copied to '/<cache_dir>/foo/1.0.0/af8d/a';
        7. The '.copying-a' file is removed.

        Args:
            force (bool): Copy the variant regardless of its cachable attribute.
                Use at your own risk (there is no guarantee the resulting variant
                payload will be functional).
            follow_symlinks (bool): Follow symlinks when copying variant payload,
                rather than copying the symlinks themselves.

        Returns:
            2-tuple:
            - str: Path to cached payload
            - int: One of:
              - VARIANT_FOUND: Variant already exists in cache
              - VARIANT_CREATED: Variant was successfully created in cache
              - VARIANT_COPYING: Another thread/proc is already in the process
                of creating the variant.
        """
        from rez.utils.base26 import get_next_base26
        from rez.utils.filesystem import safe_makedirs
        from rez.vendor.lockfile import LockFile, NotLocked

        # do some sanity checking on variant to cache
        variant_root = getattr(variant, "root", None)

        if not variant_root:
            raise PackageCacheError(
                "Cannot cache variant %s - it is a type of variant that "
                "does not have a root." % variant.uri
            )

        if not os.path.isdir(variant_root):
            raise PackageCacheError(
                "Cannot cache variant %s - its root does not appear to "
                "be present on disk (%s)." % variant.uri, variant_root
            )

        # variant already exists, or is being copied to cache by another thread/proc
        status, rootpath = self._get_cached_root(variant)
        if status in (self.VARIANT_FOUND, self.VARIANT_COPYING):
            return (rootpath, status)

        # 1.
        path = self._get_hash_path(variant)
        safe_makedirs(path)

        # construct data to store to json file
        data = {
            "handle": variant.handle.to_dict()
        }

        if variant.index is not None:
            # just added for debugging purposes
            data["data"] = variant.parent.data["variants"][variant.index]

        lock_filepath = os.path.join(path, ".lock")
        lock = LockFile(lock_filepath)

        try:
            # 2.
            lock.acquire(timeout=10)

            # Check if variant exists again, another proc could have created it
            # just before lock acquire
            #
            status, rootpath = self._get_cached_root(variant)
            if status in (self.VARIANT_FOUND, self.VARIANT_COPYING):
                return (rootpath, status)

            # determine next increment name ('a', 'b' etc)
            names = os.listdir(path)
            names = [x for x in names if x.endswith(".json")]

            if names:
                prev = os.path.splitext(max(names))[0]
            else:
                prev = None

            incname = get_next_base26(prev)

            # 3.
            copying_filepath = os.path.join(path, ".copying-" + incname)
            with open(copying_filepath, 'w'):
                pass

            # 4.
            json_filepath = os.path.join(path, incname + ".json")
            with open(json_filepath, 'w') as f:
                json.dump(data, f, indent=2)

        finally:
            # 5.
            try:
                lock.release()
            except NotLocked:
                pass

        # 6.
        rootpath = os.path.join(path, incname)
        shutil.copytree(variant_root, rootpath, symlinks=follow_symlinks)

        # 7.
        os.remove(copying_filepath)

        return (rootpath, self.VARIANT_CREATED)

    def iter_variants(self):
        """
        Yields:
            2-tuple:
            - `Variant`: The cached variant
            - str: Local cache path for variant
        """
        from rez.packages import get_variant

        for pkg_name in safe_listdir(self.path):
            path1 = os.path.join(self.path, pkg_name)

            for ver_str in safe_listdir(path1):
                path2 = os.path.join(path1, ver_str)

                for hash_str in safe_listdir(path2):
                    path3 = os.path.join(path2, hash_str)

                    for name in safe_listdir(path3):
                        if name.endswith(".json"):
                            with open(os.path.join(path3, name)) as f:
                                data = json.load(f)

                            handle = data["handle"]
                            variant = get_variant(handle)

                            incname = os.path.splitext(name)[0]
                            rootpath = os.path.join(path3, incname)
                            yield (variant, rootpath)

    def _get_cached_root(self, variant):
        path = self._get_hash_path(variant)
        if not os.path.exists(path):
            return (self.VARIANT_NOT_FOUND, '')

        handle_dict = variant.handle.to_dict()

        for name in os.listdir(path):
            if name.endswith(".json"):
                incname = os.path.splitext(name)[0]
                json_filepath = os.path.join(path, name)
                rootpath = os.path.join(path, incname)
                copying_filepath = os.path.join(path, ".copying-" + incname)

                try:
                    with open(json_filepath) as f:
                        data = json.load(f)
                except IOError as e:
                    if e.errno == errno.ENOENT:
                        # maybe got cleaned up by other process
                        continue
                    else:
                        raise

                if data.get("handle") == handle_dict:
                    if os.path.exists(copying_filepath):
                        return (self.VARIANT_COPYING, rootpath)
                    else:
                        return (self.VARIANT_FOUND, rootpath)

        return (self.VARIANT_NOT_FOUND, '')

    def _get_hash_path(self, variant):
        dirs = [self.path, variant.name]

        if variant.version:
            dirs.append(str(variant.version))
        else:
            dirs.append("_NO_VERSION")

        h = sha1(str(variant.handle._hashable_repr()).encode('utf-8'))
        hash_dirname = h.hexdigest()[:4]
        dirs.append(hash_dirname)

        return os.path.join(*dirs)
