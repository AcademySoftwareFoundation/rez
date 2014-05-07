import os.path
from rez.backport.lru_cache import lru_cache
from rez.util import print_warning_once, Common, encode_filesystem_name
from rez.resources import iter_resources, load_metadata
from rez.contrib.version.version import Version, VersionRange
from rez.contrib.version.requirement import VersionedObject
from rez.settings import settings


"""
PACKAGE_NAME_REGSTR = '[a-zA-Z_][a-zA-Z0-9_]*'
PACKAGE_NAME_REGEX = re.compile(PACKAGE_NAME_REGSTR + '$')
PACKAGE_NAME_SEP_REGEX = re.compile(r'[-@#]')
PACKAGE_REQ_SEP_REGEX = re.compile(r'[-@#=<>]')
"""


# cached package.* file reads
@lru_cache(maxsize=1024)
def _load_metadata(path):
    return load_metadata(path)


def iter_package_families(name=None, paths=None):
    """Iterate through top-level `PackageFamily` instances."""
    if paths is None:
        paths = settings.packages_path
    elif isinstance(paths, basestring):
        paths = [paths]

    pkg_iter = iter_resources(0,  # configuration version
                              ['package_family.folder'],
                              paths,
                              name=name)
    for path, variables, resource_info in pkg_iter:
        if os.path.isdir(path):
            yield PackageFamily(variables['name'], path)


def _iter_packages(family_name, paths=None):
    """
    Iterate through all packages in UNSORTED order.
    """
    done = set()
    for pkg_fam in iter_package_families(family_name, paths):
        for pkg in pkg_fam.iter_version_packages():
            pkgname = pkg.qualified_name
            if pkgname not in done:
                done.add(pkgname)
                yield pkg

# TODO simplify this
def iter_packages_in_range(family_name, ver_range=None, latest=True,
                           timestamp=0, exact=False, paths=None):
    """
    Iterate over `Package` instances, sorted by version.

    Parameters
    ----------
    family_name : str
        name of the package without a version
    ver_range : VersionRange
        range of versions in package to iterate over, or all if None
    latest : bool
        whether to sort by latest version first (default) or earliest
    timestamp : int
        time since epoch: any packages newer than this will be ignored. 0 means
        no effect.
    exact : bool
        only match if ver_range represents an exact version
    paths : list of str
        search path. defaults to settings.package_path

    If two versions in two different paths are the same, then the package in
    the first path is returned in preference.
    """
    if (ver_range is not None) and (not isinstance(ver_range, VersionRange)):
        ver_range = VersionRange(ver_range)

    # store the generator. no paths have been walked yet
    results = _iter_packages(family_name, paths)

    if timestamp:
        results = [x for x in results if x.timestamp <= timestamp]
    # sort
    results = sorted(results, key=lambda x: x.version, reverse=latest)

    # yield versions only inside range
    for result in results:
        if ver_range is None or result.version in ver_range:
            yield result


def find_package(name, version, timestamp=None, paths=None):
    """Find the given package.

    Args:
        name: package name.
        version: package version (Version object).
        timestamp: integer time since epoch - any packages newer than this
            will be ignored. If None, no packages are ignored.
        paths: List of paths to search for packages, defaults to
            settings.packages_path.

    Returns:
        Package object, or None if the package was not found.
    """
    range = VersionRange.from_version(version)
    result = iter_packages_in_range(name,
                                    ver_range=range,
                                    latest=True,
                                    timestamp=timestamp or 0,
                                    paths=paths)
    try:
        return result.next()
    except StopIteration:
        return None


class PackageFamily(Common):
    """A package family has a single root directory, with a sub-directory for
    each version.
    """
    def __init__(self, name, path):
        self.name = name
        self.path = path

    def __str__(self):
        return "%s@%s" % (self.name, os.path.dirname(self.path))

    def iter_version_packages(self):
        pkg_iter = iter_resources(0,  # configuration version
                                  ['package.versionless', 'package.versioned'],
                                  [os.path.dirname(self.path)],
                                  name=self.name)
        for metafile, variables, resource_info in pkg_iter:
            version = Version(variables.get('version', ''))
            yield Package(self.name, version, metafile)


class PackageBase(Common):
    """Abstract base class for Package and Variant."""
    def __init__(self, name, version, metafile):
        self.name = name
        self.version = version
        self.metafile = metafile
        self.base = os.path.dirname(metafile)
        self._metadata = None

    @property
    def qualified_name(self):
        o = VersionedObject.construct(self.name, self.version)
        return str(o)

    @property
    def metadata(self):
        if self._metadata is None:
            self._metadata = _load_metadata(self.metafile)
        return self._metadata

    def _base_path(self):
        path = os.path.dirname(self.base)
        if not self.version:
            path = os.path.dirname(path)
        return os.path.dirname(path)


class Package(PackageBase):
    """Class representing a package definition, as read from a package.* file.
    """
    def __init__(self, name, version, metafile):
        super(Package,self).__init__(name, version, metafile)

    @property
    def num_variants(self):
        """Return the number of variants in this package."""
        variants = self.metadata["variants"] or []
        return len(variants)

    def get_variant(self, index=None):
        """Return a variant from the definition.

        Note that even a package that does not contain variants will return a
        Variant object with index=None.
        """
        n = self.num_variants
        if index is None:
            if n:
                raise IndexError("there are variants, index must be non-None")
        elif index not in range(n):
            raise IndexError("variant doesn't exist at this index")

        return Variant(self.name, self.version, self.metafile, index)

    def iter_variants(self):
        n = self.num_variants
        if n:
            for i in range(n):
                yield self.get_variant(i)
        else:
            yield self.get_variant()

    def __str__(self):
        return "%s@%s" % (self.qualified_name, self._base_path())


class Variant(PackageBase):
    """Class representing a variant of a package.

    Note that Variant is also used in packages that don't have a variant - in
    this case, index is None. This helps give a consistent interface.
    """
    def __init__(self, name, version, metafile, index=None):
        super(Variant,self).__init__(name, version, metafile)
        self.index = index
        self.root = self.base

        metadata = self.metadata
        self.requires = metadata["requires"] or []

        if self.index is not None:
            var_requires = metadata["variants"][self.index]
            self.requires = self.requires + var_requires

            dirs = [encode_filesystem_name(x) for x in var_requires]
            self.root = os.path.join(self.base, os.path.join(*dirs))

            # backwards compatibility with rez-1
            if (not os.path.exists(self.root)) and (dirs != var_requires):
                root = os.path.join(self.base, os.path.join(*var_requires))
                if os.path.exists(root):
                    self.root = root

    @property
    def qualified_package_name(self):
        return super(Variant,self).qualified_name

    @property
    def qualified_name(self):
        s = super(Variant,self).qualified_name
        if self.index is not None:
            s += "[%d]" % self.index
        return s

    @property
    def subpath(self):
        if self.index is None:
            return ''
        else:
            path = os.path.relpath(self.root, self.base)
            return os.path.normpath(path)

    def to_dict(self):
        return dict(
            name=self.name,
            version=str(self.version),
            metafile=self.metafile,
            index=self.index)

    @classmethod
    def from_dict(cls, d):
        return Variant(name=d["name"],
                       version=Version(d["version"]),
                       metafile=d["metafile"],
                       index=d["index"])

    def __str__(self):
        return "%s@%s,%s" % (self.qualified_name, self._base_path(), self.subpath)
