import os.path
from rez.util import Common, propertycache, is_subdirectory, \
    convert_to_user_dict, RO_AttrDictWrapper
from rez.resources import iter_resources, package_schema, Schema
from rez.vendor.version.version import Version, VersionRange
from rez.vendor.version.requirement import VersionedObject, Requirement
from rez.exceptions import PackageNotFoundError


"""
PACKAGE_NAME_REGSTR = '[a-zA-Z_][a-zA-Z0-9_]*'
PACKAGE_NAME_REGEX = re.compile(PACKAGE_NAME_REGSTR + '$')
PACKAGE_NAME_SEP_REGEX = re.compile(r'[-@#]')
PACKAGE_REQ_SEP_REGEX = re.compile(r'[-@#=<>]')
"""

resource_classes = {}


def _iter_packages(name=None, paths=None):
    """Iterate over `Package` instances."""
    pkg_iter = iter_resources(0,  # configuration version
                              ['package.*'],
                              paths,
                              name=name)

    for resource in pkg_iter:
        if name is None or name in resource.variables.get('name', None):
            yield Package(resource=resource)

def iter_packages(name=None, range=None, timestamp=None, paths=None,
                  descending=False):
    """Iterate over `Package` instances, sorted by version.

    Packages of the same name and version earlier in the search path take
    precedence - equivalent packages later in the paths are ignored.

    Args:
        name (str): Name of the package, eg 'maya'.
        range (VersionRange, optional): If provided, limits the versions
            returned.
        timestamp (int, optional): Any package newer than this time epoch is
            ignored.
        paths (list of str): paths to search for pkgs, defaults to
            `settings.packages_path`.
        descending (bool): If True, return packages in descending order.

    Returns:
        Package object iterator.
    """
    packages = []
    consumed = set()
    for pkg in _iter_packages(name, paths):
        pkgname = pkg.qualified_name
        if pkgname not in consumed:
            if (timestamp and pkg.timestamp > timestamp) \
                    or (range and pkg.version not in range):
                continue

            consumed.add(pkgname)
            packages.append(pkg)

    packages = sorted(packages, key=lambda x: (x.name, x.version),
                      reverse=descending)
    return iter(packages)


class WithDataAccessors(type):
    """Metaclass for adding properties to a class for accessing top-level keys
    in its metadata dictionary.

    The property names are derived from the keys of the class's `schema`
    object.
    """
    def __new__(cls, name, parents, members):
        schema_dict = members['schema']._schema
        for key in schema_dict.keys():
            while isinstance(key, Schema):
                key = key._schema
            if key not in members:
                members[key] = cls.make_getter(key)
        return super(WithDataAccessors, cls).__new__(cls, name, parents,
                                                     members)

    @classmethod
    def make_getter(cls, key):
        def getter(self):
            return getattr(self.metadata, key)
        return property(getter)

class PackageBase(Common):
    """Abstract base class for Package and Variant."""

    schema = None

    def __init__(self, resource):
        self.metafile = resource.path
        self.base = os.path.dirname(self.metafile)
        self._resource = resource

    @propertycache
    def qualified_name(self):
        o = VersionedObject.construct(self.name, self.version)
        return str(o)

    @propertycache
    def _data(self):
        """Dictionary of data loaded from the package's resource.

        This is private because it is preferred for users to go through the
        `metadata` property.  This is here to preserve the original dictionary
        loaded directly from the package's resource.
        """
        data = self._resource.load()
        if self.schema:
            data = self.schema.validate(data)
        return data

    @propertycache
    def metadata(self):
        """Read-only dictionary of metadata for this package with nested,
        attribute-based access for the keys in the dictionary.

        All of the dictionaries in `_data` have are replaced with custom
        `UserDicts` to provide the attribute-lookups.  If you need the raw
        dictionary, use `_data`.

        Note that the `UserDict` references the dictionaries in `_data`, so
        the data is not copied, and thus the two will always be in sync.

        Returns:
            RO_AttrDictWrapper
        """
        return convert_to_user_dict(self._data, RO_AttrDictWrapper)

    @propertycache
    def is_local(self):
        """Returns True if this package is in the local packages path."""
        return is_subdirectory(self.metafile,
                               self.settings.local_packages_path)

    def _base_path(self):
        path = os.path.dirname(self.base)
        if not self.version:
            path = os.path.dirname(path)
        return os.path.dirname(path)

    def __str__(self):
        return "%s@%s" % (self.qualified_name, self._base_path())


class Package(PackageBase):
    """Class representing a package definition, as read from a package.* file.
    """
    __metaclass__ = WithDataAccessors

    schema = package_schema

    def __init__(self, resource):
        """Create a package.

        Args:
            path (str): Either a filepath to a package definition file, or a
                path to the directory containing the definition file.
            resource (Resource):
        """
        super(Package, self).__init__(resource)

    @property
    def num_variants(self):
        """Return the number of variants in this package. Returns zero if there
        are no variants."""
        # FIXME: move default to resources
        variants = self.metadata.get("variants", [])
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
            raise IndexError("variant index out of range")

        return Variant(index=index,
                       resource=self._resource)

    def iter_variants(self):
        """Returns an iterator over the variants in this package."""
        n = self.num_variants
        if n:
            for i in range(n):
                yield self.get_variant(i)
        else:
            yield self.get_variant()

    def __eq__(self, other):
        return (self.name == other.name) \
            and (self.version == other.version) \
            and (self.metafile == other.metafile)


class Variant(PackageBase):
    """Class representing a variant of a package.

    Note that Variant is also used in packages that don't have a variant - in
    this case, index is None. This helps give a consistent interface.
    """

    # FIXME: move to PackageBase?
    __metaclass__ = WithDataAccessors

    schema = package_schema

    def __init__(self, index=None, resource=None):
        """Create a package variant.

        Args:
            path (str): Either a filepath to a package definition file, or a
                path to the directory containing the definition file.
            index (int): Zero-based variant index. If the package does not
                contain variants, index should be set to None.
        """
        super(Variant, self).__init__(resource)
        self.index = index
        self.root = self.base

        metadata = self.metadata
        # FIXME: move default to schema
        requires = metadata.get("requires", [])

        if self.index is not None:
            try:
                var_requires = metadata["variants"][self.index]
            except IndexError:
                raise IndexError("variant index out of range")

            requires = requires + var_requires
            dirs = [Requirement(x).safe_str() for x in var_requires]
            self.root = os.path.join(self.base, os.path.join(*dirs))

        self._all_requires = [Requirement(x) for x in requires]

    @property
    def qualified_package_name(self):
        return super(Variant, self).qualified_name

    @property
    def qualified_name(self):
        s = super(Variant, self).qualified_name
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

    # FIXME: rename to get_requires or requirements to avoid conflict with
    # requires property
    def requires(self, build_requires=False, private_build_requires=False):
        """Get the requirements of the variant.

        Args:
            build_requires (bool): If True, include build requirements.
            private_build_requires (bool): If True, include private build
                requirements.

        Returns:
            List of `Requirement` objects.
        """
        requires = self._all_requires
        if build_requires:
            reqs = self.metadata["build_requires"]
            if reqs:
                requires = requires + [Requirement(x) for x in reqs]

        if private_build_requires:
            reqs = self.metadata["private_build_requires"]
            if reqs:
                requires = requires + [Requirement(x) for x in reqs]

        return requires

    def to_dict(self):
        return dict(
            name=self.name,
            version=str(self.version),
            metafile=self.metafile,
            index=self.index)

    @classmethod
    def from_dict(cls, d):
        return Variant(path=d["metafile"],
                       name=d["name"],
                       version=Version(d["version"]),
                       index=d["index"])

    def __eq__(self, other):
        return (self.name == other.name) \
            and (self.version == other.version) \
            and (self.metafile == other.metafile) \
            and (self.index == other.index)

    def __str__(self):
        return "%s@%s,%s" % (self.qualified_name, self._base_path(),
                             self.subpath)
