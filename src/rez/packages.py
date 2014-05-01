import os.path
from rez.util import print_warning_once, Common
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

def package_family(name, paths=None):
    """
    Return the first `FamilyPackage` found on the search path.
    """
    result = iter_package_families(name, paths)
    try:
        # return first item in generator
        return result.next()
    except StopIteration:
        return None

def _iter_packages(family_name, paths=None, skip_dupes=True):
    """
    Iterate through all packages in UNSORTED order.
    """
    done = set()
    for pkg_fam in iter_package_families(family_name, paths):
        for pkg in pkg_fam.iter_version_packages():
            if skip_dupes:
                pkgname = pkg.qualified_name
                if pkgname not in done:
                    done.add(pkgname)
                    yield pkg
            else:
                yield pkg

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


def package_in_range(family_name, ver_range=None, latest=True, timestamp=0,
                     exact=False, paths=None):
    """
    Return the first `Package` found on the search path.

    Parameters
    ----------
    family_name : str
        name of the package without a version
    ver_range : VersionRange
        range of versions in package to iterate over, or all if None
    latest : bool
        whether to sort by latest (default) or earliest
    timestamp : int
        time since epoch: any packages newer than this will be ignored. 0 means
        no effect.
    exact : bool
        only match if ver_range represents an exact version
    paths : list of str
        search path. defaults to settings.packages_path

    """
    result = iter_packages_in_range(family_name, ver_range, latest, timestamp,
                                    exact, paths)
    try:
        # return first item in generator
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
            yield PackageDefinition(self.name, version, metafile)


class PackageDefinition(Common):
    """Class representing a package definition, as read from a package.* file.
    """
    def __init__(self, name, version, metafile):
        self.name = name
        self.version = version
        self.metafile = metafile
        self.root = os.path.dirname(metafile)
        self._metadata = None

    @property
    def qualified_name(self):
        o = VersionedObject.construct(self.name, self.version)
        return str(o)

    @property
    def metadata(self):
        if self._metadata is None:
            self._metadata = load_metadata(self.metafile)
        return self._metadata

    @property
    def num_variants(self):
        """Return the number of variants in this package."""
        variants = self.metadata["variants"] or []
        return len(variants)

    def get_variant(self, index=None):
        """Return a variant from the definition.

        Note that even a package that does not contain variants will return a
        VariantDefinition object with index=None.
        """
        n = self.num_variants
        if index is None:
            if n:
                raise ValueError("there are variants, index must be non-None")
        elif index not in range(n):
            raise IndexError("variant doesn't exist at this index")

        return VariantDefinition(self, index)

    def iter_variants(self):
        n = self.num_variants
        if n:
            for i in range(n):
                yield self.get_variant(i)
        else:
            yield self.get_variant()

    def _base_path(self):
        path = os.path.dirname(self.root)
        if not self.version:
            path = os.path.dirname(path)
        return path

    def __str__(self):
        return "%s@%s" % (self.qualified_name, self._base_path())


class VariantDefinition(Common):
    """Class representing a variant of a package.

    Note that VariantDefinition is also used in packages that don't have a
    variant - in this case index is None.
    """
    def __init__(self, pkg, index=None):
        self.pkg = pkg
        self.index = index
        self.root = pkg.root
        metadata = self.pkg.metadata
        self.requires = metadata["requires"] or []

        if self.index is not None:
            var_requires = metadata["variants"][self.index]
            self.requires = self.requires + var_requires

    @property
    def name(self):
        return self.pkg.name

    @property
    def version(self):
        return self.pkg.version

    def __str__(self):
        if self.index is None:
            return str(self.pkg)
        else:
            o = VersionedObject.construct(self.pkg.name, self.pkg.version)
            base_path = self._base_path()
            var_path = os.path.relpath(self.root, base_path)
            var_path = os.path.normpath(var_path)
            return "%s[%d]@%s:%s" % (str(o), self.index, base_path, var_path)





"""
class BasePackage(object):
    def __init__(self, name, version, timestamp):
        self.name = name
        assert(isinstance(version, Version)) # TODO remove check after version porting
        self.version = version
        self._timestamp = timestamp

    def __repr__(self):
        return "%s(%r, %r)" % (self.__class__.__name__, self.name, self.version)

    @property
    def timestamp(self):
        return self._timestamp

    def short_name(self):
        if (len(str(self.version)) == 0):
            return self.name
        else:
            return self.name + '-' + str(self.version)


class Package(BasePackage):
    def __init__(self, name, version, metafile, timestamp=None, metadata=None):
        BasePackage.__init__(self, name, version, timestamp)
        assert os.path.splitext(metafile)[1], "%s: %s" % (self.name, metafile)
        self.base = os.path.dirname(metafile)
        self.metafile = metafile
        self._metadata = metadata

    def __getstate__(self):
        d = self.__dict__.copy()
        # metadata is never pickled!
        d["_metadata"] = None
        return d

    @property
    def metadata(self):
        if self._metadata is None:
            self._metadata = load_metadata(self.metafile)
        return self._metadata

    @property
    def timestamp(self):
        if self._timestamp is None:
            self._timestamp = 0
            if not self.is_local():
                # TODO: replace this with package resources
                release_time_f = os.path.join(self.base, '.metadata', 'release_time.txt')
                if os.path.isfile(release_time_f):
                    with open(release_time_f, 'r') as f:
                        self._timestamp = int(f.read().strip())
                elif settings.warn_untimestamped:
                    print_warning_once(("%s is not timestamped. To timestamp it " + \
                                       "manually, use the rez-timestamp utility.") % self.base)
        return self._timestamp

    def is_local(self):
        # FIXME: this is not completely safe since '/foo/barf'.startswith('/foo/bar')
        # is True and yet '/foo/barf' is not a sub-directory of '/foo/bar'
        return self.base.startswith(settings.local_packages_path)

    def __str__(self):
        return str([self.name, self.version, self.base])


class ResolvedPackage(Package):
    def __init__(self, name, version, metafile, timestamp, metadata, base, root):
        Package.__init__(self, name, version, metafile, timestamp, metadata=metadata)
        #self.version = ExactVersion(version)
        self.base = base
        self.root = root

    def __str__(self):
        return str([self.name, self.version, self.root])

    def __repr__(self):
        return "%s(%r, %r, %r)" % (self.__class__.__name__, self.name,
                                   self.version, self.root)
"""
