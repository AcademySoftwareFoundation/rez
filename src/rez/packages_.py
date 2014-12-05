from rez.package_repository import package_repository_manager, \
    PackageFamilyResource, PackageResource, package_family_schema, \
    package_schema
from rez.resources_ import ResourceWrapper, schema_keys
from rez.exceptions import PackageFamilyNotFoundError
from rez.config import config


class PackageFamily(ResourceWrapper):
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
            yield package


class Package(ResourceWrapper):
    """A package.

    Note:
        Do not instantiate this class directly, instead use the function
        `iter_packages` or `PackageFamily.iter_packages`.
    """
    keys = schema_keys(package_schema)

    def __init__(self, resource):
        assert isinstance(resource, PackageResource)
        super(Package, self).__init__(resource)


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
    entries = []
    for path in (paths or config.packages_path):
        repo = package_repository_manager.get_repository(path)
        family_resource = repo.get_package_family(name)
        if family_resource:
            entries.append((repo, family_resource))

    if not entries:
        raise PackageFamilyNotFoundError("No such package family %r" % name)

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
