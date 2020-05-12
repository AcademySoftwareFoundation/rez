import os.path
from hashlib import sha1
import json

from rez.exceptions import PackageCacheError
from rez.utils.base26 import get_next_base26
from rez.vendor.lockfile import LockFile


class PackageCache(object):
    """Package cache.

    A package cache is responsible for storing copies of variant payloads into a
    location that would typically be on local disk. The intent is to avoid
    loading a package's files over shared storage.

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
                                     /variant.json

    Here, 'af8d' is the first 4 chars of the SHA1 hash of the variant's 'handle',
    which is a dict of fields that uniquely identify the variant. To avoid
    hash collisions, the variant is then stored under a subdir that is incrementally
    named ('a', 'b', ..., 'aa', 'ab', ...). The 'variant.json' file is then used
    to find the correct variant within the hash subdir. The intent is to keep
    cached paths short, and avoid having to search too many variant.json files
    for the correct variant.
    """
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
        path = self._get_hash_path(variant)
        if not os.path.exists(path):
            return None

        for name in os.listdir(path):
            rootpath = os.path.join(path, name)
            filepath = os.path.join(rootpath, "variant.json")

            if os.path.exists(filepath):
                with open(filepath) as f:
                    handle = json.load(f)
                if handle == variant.handle:
                    return rootpath

        return None

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
