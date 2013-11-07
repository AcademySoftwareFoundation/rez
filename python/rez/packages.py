"""
rez packages
"""
import os.path
import re
from public_enums import PKG_METADATA_FILENAME
import rez_metafile
import rez_filesys
from rez_exceptions import PkgSystemError
from versions import Version

PACKAGE_NAME_REGSTR = '[a-zA-Z][a-zA-Z0-9_]*'
PACKAGE_NAME_REGEX = re.compile(PACKAGE_NAME_REGSTR + '$')

def split_name(pkg_str):
    strs = pkg_str.split('-')
    if len(strs) > 2:
        PkgSystemError("Invalid package string '" + pkg_str + "'")
    name = strs[0]
    if len(strs) == 1:
        verrange = ""
    else:
        verrange = strs[1]
    return name, verrange

def pkg_name(pkg_str):
    return split_name(pkg_str)[0]

# TODO: move this to RezMemCache
def get_family_paths(path):
    return [(x, os.path.join(path, x)) for x in os.listdir(path) \
            if not PACKAGE_NAME_REGEX.match(x) and x not in ['rez']]

def iter_package_families(name=None, paths=None):
    """
    Iterate through top-level `PackageFamily` instances.
    """
    if paths is None:
        paths = rez_filesys._g_syspaths
    elif isinstance(paths, basestring):
        paths = [paths]

    for pkg_path in paths:
        if name is not None:
            family_path = os.path.join(pkg_path, name)
            if os.path.isdir(family_path):
                yield PackageFamily(name, family_path)
        else:
            # FIXME: (?) this is not cached:
            for family_name, family_path in get_family_paths(pkg_path):
                yield PackageFamily(family_name, family_path)

def iter_version_packages(name=None, paths=None):
    for pkg_fam in iter_package_families(name, paths):
        for pkg in pkg_fam.iter_version_pacakges():
            yield pkg

def package_family(name, paths=None):
    """
    Return the first `FamilyPackage` found on the search path.
    """
    result = iter_package_families(name, paths)
    if result is not None:
        return next(result)

class VersionString(str):
    LABELS = {'major': 1,
              'minor': 2,
              'patch': 3}

    @property
    def major(self):
        return self.part(self.LABELS['major'])

    @property
    def minor(self):
        return self.part(self.LABELS['minor'])

    @property
    def patch(self):
        return self.part(self.LABELS['patch'])

    def part(self, num):
        num = int(num)
        if num == 0:
            print "warning: version.part() got index 0: converting to 1"
            num = 1
        try:
            return self.split('.')[num - 1]
        except IndexError:
            return ''

    def thru(self, num):
        try:
            num = int(num)
        except ValueError:
            if isinstance(num, basestring):
                try:
                    num = self.LABELS[num]
                except KeyError:
                    # allow to specify '3' as 'x.x.x'
                    num = len(num.split('.'))
            else:
                raise
        if num == 0:
            print "warning: version.thru() got index 0: converting to 1"
            num = 1
        try:
            return '.'.join(self.split('.')[:num])
        except IndexError:
            return ''

class PackageFamily(object):
    """
    A package family contains versioned packages of the same name.

    A package family has a single root directory, and there may be multiple
    package families on the rez search path with the same name.
    """
    def __init__(self, name, path):
        self.name = name
        self.path = path

    def iter_version_packages(self):
        from rez_memcached import get_memcache
        vers = get_memcache().get_versions_in_directory(self.path)
        if vers:
            for ver, timestamp in vers:
                metafile = os.path.join(self.path, str(ver), PKG_METADATA_FILENAME)
                # no need to check if metafile is exists, already done in `get_versions_in_directory`
                yield Package(self.name, ver, metafile, timestamp)
        else:
            metafile = os.path.join(self.path, PKG_METADATA_FILENAME)
            if os.path.isfile(metafile):
                # check for special case - unversioned package.
                # only allowed when no versioned packages exist.
                yield Package(self.name, Version(""), metafile, 0)

#     def iter_version_packages(self, paths=None):
#         from rez_memcached import get_memcache
#         return get_memcache().iter_packages(self.name, paths)
# 
#     def find_package_in_range(self, ver_range, latest=True, exact=False,
#                               paths=None, timestamp=0):
#         from rez_memcached import get_memcache
#         get_memcache().find_package_in_range(self.name, ver_range, latest, exact,
#                               paths, timestamp)

    def version_package(self, ver_range, latest=True, exact=False, timestamp=0):
        """
        Given a a `VersionRange`, return a `Package` instance, or None if no
        matches are found.
        """
        # store the generator. no paths have been walked yet
        results = self.iter_version_packages()

        if timestamp:
            results = [x for x in results if x.timestamp <= timestamp]
        # sort 
        if latest:
            results = sorted(results, key=lambda x: x.version, reverse=True)
        else:
            results = sorted(results, key=lambda x: x.version, reverse=False)

        # find the best match
        for result in results:
            if ver_range.matches_version(result.version, allow_inexact=not exact):
                return result

        return None

class Package(object):
    """
    an unresolved package.

    An unresolved package has a version, but may have inexplicit or "variant"
    requirements, which can only be determined once its co-packages
    are known. When the exact list of requirements is determined, the package
    is considered resolved and the full path to the package root is known.
    """
    def __init__(self, name, version, base, timestamp):
        self.name = name
        self.version = version
        # for convenience, base may be a path or a metafile
        if base.endswith('.yaml'):
            self.base = os.path.dirname(base)
            self.metafile = base
        else:
            self.base = base
            self.metafile = os.path.join(self.base, PKG_METADATA_FILENAME)
        self.timestamp = timestamp
        self._metadata = None
        self._stripped_metdata = None

    @property
    def metadata(self):
        # bypass the memcache so that non-essentials are not stripped
        if self._metadata is None:
            self._metadata = rez_metafile.load_metadata(self.metafile)
        return self._metadata

    @property
    def stripped_metadata(self):
        """
        only the essential metadata
        """
        if self._stripped_metdata is None:
            from rez_memcached import get_memcache
            self._stripped_metdata = get_memcache().get_metafile(self.metafile)
        return self._stripped_metdata

    def short_name(self):
        if (len(self.version) == 0):
            return self.name
        else:
            return self.name + '-' + str(self.version)

    def __str__(self):
        return str([self.name, self.version, self.base])

    def __repr__(self):
        return "%s(%r, %r)" % (self.__class__.__name__, self.name,
                               self.version)

class ResolvedPackage(Package):
    """
    A resolved package.

    An unresolved package has a version, but may have inexplicit or "variant"
    requirements, which can only be determined once its co-packages
    are known. When the exact list of requirements is determined, the package
    is considered resolved and the full path to the package root is known.
    """
    def __init__(self, name, version, base, root, commands, metadata, timestamp):
        Package.__init__(self, name, version, base, timestamp)
        # FIXME: this is primarily here for rex. i don't like the fact that
        # Package.version is a Version, and ResolvedPackage.version is a VersionString.
        # look into moving functionality of VersionString onto Version
        self.version = VersionString(version)
        self.root = root
        self.raw_commands = commands
        self.commands = None
        self._core_metadata = metadata # original (stripped) ConfigMetadata

    def strip(self):
        # remove data that we don't want to cache
        self.commands = None
        self.raw_commands = None
        self._metadata = None

    def __str__(self):
        return str([self.name, self.version, self.root])

    def __repr__(self):
        return "%s(%r, %r, %r)" % (self.__class__.__name__, self.name,
                                   self.version, self.root)
