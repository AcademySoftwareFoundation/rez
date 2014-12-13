from rez.package_repository import package_repository_manager
from rez.package_resources_ import PackageFamilyResource, PackageResource, \
    VariantResource, package_family_schema, package_schema, variant_schema
from rez.utils.data_utils import cached_property
from rez.utils.formatting import StringFormatMixin
from rez.utils.filesystem import is_subdirectory
from rez.utils.schema import schema_keys
from rez.utils.resources import ResourceHandle, ResourceWrapper
from rez.exceptions import PackageFamilyNotFoundError, PackageRequestError
from rez.vendor.version.requirement import VersionedObject
from rez.config import config
import sys


#------------------------------------------------------------------------------
# package-related classes
#------------------------------------------------------------------------------

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


class PackageBaseResourceWrapper(PackageRepositoryResourceWrapper):
    """Abstract base class for `Package` and `Variant`.
    """
    def print_info(self, buf=None, skip_attributes=None):
        """Print the contents of the object, in yaml format."""
        from rez.utils.yaml import dump_package_yaml
        data = self.validated_data().copy()
        data = dict((k, v) for k, v in data.iteritems()
                    if v is not None and not k.startswith('_'))

        # attributes we don't want to see
        if "config_version" in data:
            del data["config_version"]
        if "config" in data:
            del data["config"]

        for attr in (skip_attributes or []):
            if attr in data:
                del data[attr]

        txt = dump_package_yaml(data)
        buf = buf or sys.stdout
        print >> buf, txt


class Package(PackageBaseResourceWrapper):
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

    @cached_property
    def num_variants(self):
        return len(self.data.get("variants", []))

    def iter_variants(self):
        """Iterate over the variants within this package, in index order.

        Returns:
            `Variant` iterator.
        """
        repo = self.resource._repository
        for variant in repo.iter_variants(self.resource):
            yield Variant(variant)


class Variant(PackageBaseResourceWrapper):
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


#------------------------------------------------------------------------------
# resource aquisition functions
#------------------------------------------------------------------------------

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


def get_completions(prefix, paths=None, family_only=False):
    """Get autocompletion options given a prefix string.

    Args:
        prefix (str): Prefix to match.
        paths (list of str): paths to search for packages, defaults to
            `config.packages_path`.
        family_only (bool): If True, only match package names, do not include
            version component.

    Returns:
        Set of strings, may be empty.
    """
    op = None
    if prefix:
        if prefix[0] in ('!', '~'):
            if family_only:
                return set()
            op = prefix[0]
            prefix = prefix[1:]

    fam = None
    for ch in ('-', '@', '#'):
        if ch in prefix:
            if family_only:
                return set()
            fam = prefix.split(ch)[0]
            break

    words = set()
    if not fam:
        words = set(x.name for x in iter_package_families(paths=paths)
                    if x.name.startswith(prefix))
        if len(words) == 1:
            fam = iter(words).next()

    if family_only:
        return words

    if fam:
        it = iter_packages(fam, paths=paths)
        words.update(x.qualified_name for x in it
                     if x.qualified_name.startswith(prefix))

    if op:
        words = set(op + x for x in words)
    return words


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
