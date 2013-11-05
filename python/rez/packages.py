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

    @property
    def metadata(self):
        # bypass the memcache so that non-essentials are not stripped
        if self._metadata is None:
            import yaml
            self._metadata = yaml.load(open(self.metafile, 'r'))
        return self._metadata

    @property
    def core_metadata(self):
        pass

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
        self.root = root
        self.commands = commands
        self._core_metadata = metadata # original (stripped) yaml data

    def strip(self):
        # remove data that we don't want to cache
        self.commands = None
        self._metadata = None

    def __str__(self):
        return str([self.name, self.version, self.root])

    def __repr__(self):
        return "%s(%r, %r, %r)" % (self.__class__.__name__, self.name,
                                   self.version, self.root)
