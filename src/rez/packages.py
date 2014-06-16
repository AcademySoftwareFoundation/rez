import os.path
from rez.util import Common, propertycache
from rez.resources import iter_resources, iter_child_resources, \
    ResourceWrapper
from rez.package_resources import package_schema
from rez.settings import Settings
from rez.vendor.schema.schema import Schema, Optional
from rez.vendor.version.version import Version, VersionRange
from rez.vendor.version.requirement import VersionedObject, Requirement


def iter_package_families(paths=None):
    """Iterate over package families.

    Note that multiple package families with the same name can be returned.
    Unlike packages, families later in the searchpath are not hidden by earlier
    families.

    Args:
        paths (list of str): paths to search for package families, defaults to
            `settings.packages_path`.

    Returns:
        `PackageFamily` iterator.
    """
    for resource in iter_resources(
            0,
            resource_keys='package_family.*',
            search_path=paths,
            root_resource_key="folder.packages_root"):
        yield PackageFamily(resource)


def _iter_packages(name=None, paths=None):
    variables = {}
    if name is not None:
        variables["name"] = name
    for resource in iter_resources(
            0,
            resource_keys='package.*',
            search_path=paths,
            root_resource_key="folder.packages_root",
            variables=variables):
        yield Package(resource)


def iter_packages(name=None, range=None, timestamp=None, paths=None):
    """Iterate over `Package` instances.

    Packages of the same name and version earlier in the search path take
    precedence - equivalent packages later in the paths are ignored. Packages
    are not returned in any specific order.

    Args:
        name (str): Name of the package, eg 'maya'.
        range (VersionRange, optional): If provided, limits the versions
            returned.
        timestamp (int, optional): Any package newer than this time epoch is
            ignored.
        paths (list of str): paths to search for packages, defaults to
            `settings.packages_path`.

    Returns:
        `Package` object iterator.
    """
    consumed = set()
    for pkg in _iter_packages(name, paths):
        if pkg not in consumed:
            if (timestamp and pkg.timestamp > timestamp) \
                    or (range and pkg.version not in range):
                continue
            consumed.add(pkg)
            yield pkg


class PackageFamily(ResourceWrapper):
    """Class representing a package family.

    You should not instantiate this class directly - instead, call
    `iter_package_families`.
    """
    @propertycache
    def name(self):
        return self._resource.get("name")

    @propertycache
    def search_path(self):
        return self._resource.get("search_path")

    def __str__(self):
        return "%s@%s" % (self.name, self.search_path)


class _PackageBase(ResourceWrapper):
    """Abstract base class for Package and Variant."""
    @propertycache
    def name(self):
        return self._resource.get("name")

    @propertycache
    def search_path(self):
        return self._resource.get("search_path")

    @propertycache
    def version(self):
        ver_str = self._resource.get("version")
        return None if ver_str is None else Version(ver_str)

    @propertycache
    def qualified_name(self):
        o = VersionedObject.construct(self.name, self.version)
        return str(o)

    @propertycache
    def is_local(self):
        """Returns True if this package is in the local packages path."""
        return (self.search_path == self.settings.local_packages_path)

    def __str__(self):
        return "%s@%s" % (self.qualified_name, self.search_path)


class Package(_PackageBase):
    """Class representing a package definition, as read from a package.* file
    or similar.

    You should not instantiate this class directly - instead, call
    `iter_packages` or `load_development_package`.
    """
    schema = package_schema

    @property
    def num_variants(self):
        """Return the number of variants in this package. Returns zero if there
        are no variants."""
        return len(self.variants or [])

    def get_variant(self, index=None):
        """Return a variant from the package definition.

        Note that even a package that does not contain variants will return a
        Variant object with index=None.
        """
        n = self.num_variants
        if index is None:
            if n:
                raise IndexError("there are variants, index must be non-None")
        elif index not in range(n):
            raise IndexError("variant index out of range")

        it = iter_child_resources(parent_resource=self._resource,
                                  resource_keys="variant.*",
                                  variables=dict(index=index))
        try:
            resource = it.next()
        except StopIteration:
            raise ResourceNotFoundError("variant not found in package")

    def iter_variants(self):
        """Returns an iterator over the variants in this package."""
        for resource in iter_child_resources(parent_resource=self._resource,
                                             resource_keys="variant.*"):
            yield Variant(resource)


class Variant(_PackageBase):
    """Class representing a variant of a package.

    Note that Variant is also used in packages that don't have a variant - in
    this case, index is None. This helps give a consistent interface.
    """
    schema = package_schema

    @property
    def qualified_package_name(self):
        return super(Variant, self).qualified_name

    @property
    def qualified_name(self):
        s = super(Variant, self).qualified_name
        index = self._resource.get("index")
        if index is not None:
            s += "[%d]" % index
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
