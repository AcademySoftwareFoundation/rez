import os.path
from public_enums import PKG_METADATA_FILENAME
import rez_metafile as metafile
from rez_exceptions import PkgSystemError

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

class Package(object):
    """
    Class that represents an unresolved package.

    An unresolved package may contain a list of variant requirements, which,
    once resolved to an individual variant based on a given context, gives the
    full path to the package root.
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
        self._core_metdata = None

    @property
    def metadata(self):
        # bypass the memcache so that non-essentials are not stripped
        if self._metadata is None:
            import yaml
            self._metadata = yaml.load(open(self.metafile, 'r'))
        return self._metadata

    @property
    def core_metadata(self):
        if self._core_metdata is None:
            from rez_memcached import get_memcache
            self._core_metdata = get_memcache().get_metafile(self.metafile)
        return self._core_metdata

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
    A resolved package
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
