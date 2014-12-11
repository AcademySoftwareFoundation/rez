from rez.package_repository import package_repository_manager
from rez.package_resources_ import PackageFamilyResource, PackageResource, \
    VariantResource, package_family_schema, package_schema, variant_schema
from rez.utils.data_utils import cached_property, StringFormatMixin
from rez.util import is_subdirectory
from rez.utils.resources import ResourceHandle, ResourceWrapper, schema_keys
from rez.exceptions import PackageFamilyNotFoundError
from rez.config import config
from rez.vendor.version.requirement import VersionedObject


class PackageRepositoryResourceWrapper(ResourceWrapper, StringFormatMixin):
    pass


class PackageFamily(PackageRepositoryResourceWrapper):
    """A package family.

    Note:
        Do not instantiate this class directly, instead use the function
        `iter_package_families`.
    """
    keys = schema_keys(package_family_schema)

    def __init__(self, resource):
        assert isinstance(resource, PackageFamilyResource)
        super(PackageFamily, self).__init__(resource)

    def iter_packages(self):
        """Iterate over the packages within this family, in no particular order.

        Returns:
            `Package` iterator.
        """
        repo = self.resource._repository
        for package in repo.iter_packages(self.resource):
            yield Package(package)


class Package(PackageRepositoryResourceWrapper):
    """A package.

    Note:
        Do not instantiate this class directly, instead use the function
        `iter_packages` or `PackageFamily.iter_packages`.
    """
    keys = schema_keys(package_schema)

    def __init__(self, resource):
        assert isinstance(resource, PackageResource)
        super(Package, self).__init__(resource)

    @cached_property
    def qualified_name(self):
        """Get the qualified name of the package.

        Returns:
            str: Name of the package with version, eg "maya-2016.1".
        """
        o = VersionedObject.construct(self.name, self.version)
        return str(o)

    @cached_property
    def parent(self):
        repo = self.resource._repository
        family = repo.get_parent_package_family(self.resource)
        return PackageFamily(family)

    def iter_variants(self):
        """Iterate over the variants within this package, in index order.

        Returns:
            `Variant` iterator.
        """
        repo = self.resource._repository
        for variant in repo.iter_variants(self.resource):
            yield Variant(variant)


class Variant(PackageRepositoryResourceWrapper):
    """A package variant.

    Note:
        Do not instantiate this class directly, instead use the function
        `Package.iter_variants`.
    """
    keys = schema_keys(variant_schema)

    def __init__(self, resource):
        assert isinstance(resource, VariantResource)
        super(Variant, self).__init__(resource)

    @cached_property
    def qualified_package_name(self):
        o = VersionedObject.construct(self.name, self.version)
        return str(o)

    @cached_property
    def qualified_name(self):
        """Get the qualified name of the variant.

        Returns:
            str: Name of the variant with version and index, eg "maya-2016.1[1]".
        """
        idxstr = '' if self.index is None else str(self.index)
        return "%s[%s]" % (self.qualified_package_name, idxstr)

    @cached_property
    def parent(self):
        repo = self.resource._repository
        package = repo.get_parent_package(self.resource)
        return Package(package)

    @property
    def config(self):
        """Returns the config for this package.

        Defaults to global config if this package did not provide a 'config'
        section.
        """
        return self.resource.config or config

    @cached_property
    def is_local(self):
        """Returns True if the variant is from a local package"""
        return is_subdirectory(self.base, config.local_packages_path)

    def get_requires(self, build_requires=False, private_build_requires=False):
        """Get the requirements of the variant.

        Args:
            build_requires (bool): If True, include build requirements.
            private_build_requires (bool): If True, include private build
                requirements.

        Returns:
            List of `Requirement` objects.
        """
        requires = self.requires or []
        if build_requires:
            requires = requires + (self.build_requires or [])
        if private_build_requires:
            requires = requires + (self.private_build_requires or [])
        return requires


def iter_package_families(paths=None):
    """Iterate over package families, in no particular order.

    Note that multiple package families with the same name can be returned.
    Unlike packages, families later in the searchpath are not hidden by earlier
    families.

    Args:
        paths (list of str, optional): paths to search for package families,
            defaults to `config.packages_path`.

    Returns:
        `PackageFamily` iterator.
    """
    for path in (paths or config.packages_path):
        repo = package_repository_manager.get_repository(path)
        for resource in repo.iter_package_families():
            yield PackageFamily(resource)


def iter_packages(name, range_=None, paths=None):
    """Iterate over `Package` instances, in no particular order.

    Packages of the same name and version earlier in the search path take
    precedence - equivalent packages later in the paths are ignored. Packages
    are not returned in any specific order.

    Args:
        name (str): Name of the package, eg 'maya'.
        range_ (VersionRange, optional): If provided, limits the versions
            returned to those in `range_`.
        paths (list of str, optional): paths to search for packages, defaults
            to `config.packages_path`.

    Returns:
        `Package` iterator.
    """
    entries = _get_families(name, paths)

    seen = set()
    for repo, family_resource in entries:
        for package_resource in repo.iter_packages(family_resource):
            key = (package_resource.name, package_resource.version)
            if key in seen:
                continue

            seen.add(key)
            if range_ and package_resource.version not in range_:
                continue

            yield Package(package_resource)


def get_variant(variant_handle):
    """Create a variant given its handle.

    Args:
        variant_handle (`ResourceHandle` or dict): Resource handle, or
            equivalent dict.

    Returns:
        `Variant`.
    """
    if isinstance(variant_handle, dict):
        variant_handle = ResourceHandle.from_dict(variant_handle)

    resource = package_repository_manager.get_resource(variant_handle)
    variant = Variant(resource)
    return variant


def get_last_release_time(name, paths=None):
    """Returns the most recent time this package was released.

    Note that releasing a variant into an already-released package is also
    considered a package release.

    Returns:
        int: Epoch time of last package release, or zero if this cannot be
        determined.
    """
    entries = _get_families(name, paths)
    max_time = 0

    for repo, family_resource in entries:
        time_ = repo.get_last_release_time(family_resource)
        if time_ == 0:
            return 0
        max_time = max(max_time, time_)
    return max_time


def _get_families(name, paths=None):
    entries = []
    for path in (paths or config.packages_path):
        repo = package_repository_manager.get_repository(path)
        family_resource = repo.get_package_family(name)
        if family_resource:
            entries.append((repo, family_resource))

    if not entries:
        raise PackageFamilyNotFoundError("No such package family %r" % name)
    return entries
