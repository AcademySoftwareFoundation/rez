"""
rez packages
"""
from __future__ import with_statement
import os.path
import re
import sys
from rez.util import print_warning_once
from rez.resources import iter_resources, load_metadata
from rez.settings import settings
from rez.exceptions import PkgSystemError
from rez.versions import Version_, ExactVersion, VersionRange_, ExactVersionSet, VersionError
from rez.version import Version, VersionRange


PACKAGE_NAME_REGSTR = '[a-zA-Z_][a-zA-Z0-9_]*'
PACKAGE_NAME_REGEX = re.compile(PACKAGE_NAME_REGSTR + '$')
PACKAGE_NAME_SEP_REGEX = re.compile(r'[-@#]')
PACKAGE_REQ_SEP_REGEX = re.compile(r'[-@#=<>]')



class PackageStatement(object):
    """Parse a package string, eg "foo-1.0".

    Note that '-', '@' or '#' can be used as the seperator between package name
    and version, however this is purely cosmetic - "foo-1" is the same as "foo@1".
    """
    def __init__(self, s):
        self.name_ = None
        self.sep_ = '-'
        self.version_ = None

        m = PACKAGE_NAME_SEP_REGEX.search(s)
        if m:
            i = m.start()
            self.name_ = s[:i]
            self.sep_ = s[i]
            ver_str = s[i+1:]
            self.version_ = Version(ver_str)
        else:
            self.name_ = s
            self.version_ = Version()

        if not PACKAGE_NAME_REGEX.match(self.name_):
            raise PkgSystemError("Invalid package name: '%s'" % self.name_)

    @property
    def name(self):
        return self.name_

    @property
    def version(self):
        return self.version_

    def __eq__(self, other):
        return (self.name_ == other.name_) and (self.version_ == other.version_)

    def __ne__(self, other):
        return not (self == other)

    def __hash__(self):
        return hash((self.name_, str(self.version_)))

    def __str__(self):
        sep_str = ''
        ver_str = ''
        if self.version_:
            sep_str = self.sep_
            ver_str = str(self.version_)
        return self.name_ + sep_str + ver_str

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, str(self))



class PackageRangeStatement(object):
    """Parse a package range string, eg 'foo-1.5+<2'.
    """
    def __init__(self, s):
        self.name_ = None
        self.sep_ = '-'
        self.range_ = None
        self.negate_ = False
        self.conflict_ = s.startswith('!')

        if self.conflict_:
            s = s[1:]
        elif s.startswith('~'):
            s = s[1:]
            self.negate_ = True
            self.conflict_ = True

        m = PACKAGE_REQ_SEP_REGEX.search(s)
        if m:
            i = m.start()
            self.name_ = s[:i]
            req_str = s[i:]
            if req_str[0] in ('-','@','#'):
                self.sep_ = req_str[0]
                req_str = req_str[1:]

            self.range_ = VersionRange(req_str)
            if self.negate_:
                self.range_ = ~self.range_
        elif self.negate_:
            self.name_ = s
            self.range_ = None
        else:
            self.name_ = s
            self.range_ = VersionRange()

        if not PACKAGE_NAME_REGEX.match(self.name_):
            raise PkgSystemError("Invalid package name: '%s'" % self.name_)

    @property
    def name(self):
        return self.name_

    @property
    def range(self):
        return self.range_

    @property
    def conflict(self):
        return self.conflict_

    def __eq__(self, other):
        return (self.name_ == other.name_) \
            and (self.range_ == other.range_) \
            and (self.conflict_ == other.conflict_)

    def __ne__(self, other):
        return not (self == other)

    def __hash__(self):
        return hash((self.name_, str(self.range_), self.conflict_))

    def __str__(self):
        pre_str = '~' if self.negate_ else ('!' if self.conflict_ else '')
        range_str = ''
        sep_str = ''

        range = self.range_
        if self.negate_:
            range = ~range if range else VersionRange()

        if not range.is_any():
            range_str = str(range)
            if range_str[0] not in ('=','<','>'):
                sep_str = self.sep_

        return pre_str + self.name_ + sep_str + range_str

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, str(self))



# TODO deprecate
def split_name(pkg_str, exact=False):
    strs = pkg_str.split('-')
    if len(strs) > 2:
        PkgSystemError("Invalid package string '" + pkg_str + "'")
    name = strs[0]
    if len(strs) == 1:
        verrange = ""
    else:
        verrange = strs[1]
    if exact:
        verrange = ExactVersion(verrange)
    else:
        try:
            verrange = VersionRange_(verrange)
        except VersionError:
            verrange = ExactVersionSet(verrange)
    return name, verrange

def pkg_name(pkg_str):
    return pkg_str.split('-')[0]

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
                pkgname = pkg.short_name()
                if pkgname not in done:
                    done.add(pkgname)
                    yield pkg
            else:
                yield pkg

def iter_packages_in_range(family_name, ver_range=None, latest=True, timestamp=0,
                           exact=False, paths=None):
    """
    Iterate over `Package` instances, sorted by version.

    Parameters
    ----------
    family_name : str
        name of the package without a version
    ver_range : VersionRange_
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
    if (ver_range is not None) and (not isinstance(ver_range, VersionRange_)):
        ver_range = VersionRange_(ver_range)

    # store the generator. no paths have been walked yet
    results = _iter_packages(family_name, paths)

    if timestamp:
        results = [x for x in results if x.timestamp <= timestamp]
    # sort
    results = sorted(results, key=lambda x: x.version, reverse=latest)

    # yield versions only inside range
    for result in results:
        if ver_range is None or \
                ver_range.matches_version(result.version, allow_inexact=not exact):
            yield result

def package_in_range(family_name, ver_range=None, latest=True, timestamp=0,
                     exact=False, paths=None):
    """
    Return the first `Package` found on the search path.

    Parameters
    ----------
    family_name : str
        name of the package without a version
    ver_range : VersionRange_
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


class PackageFamily(object):
    """A package family has a single root directory, with a sub-directory for
    each version.
    """
    def __init__(self, name, path):
        self.name = name
        self.path = path

    def __repr__(self):
        return "%s(%r, %r)" % (self.__class__.__name__, self.name,
                               self.path)

    def iter_version_packages(self):
        pkg_iter = iter_resources(0,  # configuration version
                                  ['package.versionless', 'package.versioned'],
                                  [os.path.dirname(self.path)],
                                  name=self.name)
        for metafile, variables, resource_info in pkg_iter:
            yield Package(self.name, ExactVersion(variables.get('version', '')),
                          metafile)


class BasePackage(object):
    def __init__(self, name, version, timestamp):
        self.name = name
        self.version = version
        self._timestamp = timestamp

    def __repr__(self):
        return "%s(%r, %r)" % (self.__class__.__name__, self.name,
                               self.version)

    @property
    def timestamp(self):
        return self._timestamp

    def short_name(self):
        if (len(str(self.version)) == 0):
            return self.name
        else:
            return self.name + '-' + str(self.version)


class Package(BasePackage):
    """An unresolved package.

    An unresolved package has a version, but may have inexplicit or "variant"
    requirements, which can only be determined once its co-packages
    are known. When the exact list of requirements is determined, the package
    is considered resolved and the full path to the package root is known.
    """
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
            from rez.memcached import get_memcache
            self._metadata = get_memcache().get_metadata(self.metafile)
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
    """
    A resolved package.

    An unresolved package has a version, but may have inexplicit or "variant"
    requirements, which can only be determined once its co-packages
    are known. When the exact list of requirements is determined, the package
    is considered resolved and the full path to the package root is known.
    """
    def __init__(self, name, version, metafile, timestamp, metadata, base, root):
        Package.__init__(self, name, version, metafile, timestamp, metadata=metadata)
        self.version = ExactVersion(version)
        self.base = base
        self.root = root

    def __str__(self):
        return str([self.name, self.version, self.root])

    def __repr__(self):
        return "%s(%r, %r, %r)" % (self.__class__.__name__, self.name,
                                   self.version, self.root)
