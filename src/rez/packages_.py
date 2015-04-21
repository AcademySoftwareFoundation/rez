from rez.package_repository import package_repository_manager
from rez.package_resources_ import PackageFamilyResource, PackageResource, \
    VariantResource, package_family_schema, package_schema, variant_schema, \
    package_release_keys
from rez.package_serialise import dump_package_data
from rez.utils.data_utils import cached_property
from rez.utils.formatting import StringFormatMixin, StringFormatType
from rez.utils.filesystem import is_subdirectory
from rez.utils.schema import schema_keys
from rez.utils.resources import ResourceHandle, ResourceWrapper
from rez.exceptions import PackageMetadataError, PackageFamilyNotFoundError
from rez.vendor.version.version import VersionRange
from rez.vendor.version.requirement import VersionedObject
from rez.serialise import load_from_file, FileFormat
from rez.config import config
from rez.system import system
import os.path
import sys


#------------------------------------------------------------------------------
# package-related classes
#------------------------------------------------------------------------------

class PackageRepositoryResourceWrapper(ResourceWrapper, StringFormatMixin):
    format_expand = StringFormatType.unchanged

    def validated_data(self):
        data = ResourceWrapper.validated_data(self)
        data = dict((k, v) for k, v in data.iteritems() if v is not None)
        return data


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
    @property
    def uri(self):
        return self.resource.uri

    @property
    def config(self):
        """Returns the config for this package.

        Defaults to global config if this package did not provide a 'config'
        section.
        """
        return self.resource.config or config

    @cached_property
    def is_local(self):
        """Returns True if the package is in the local package repository"""
        local_repo = package_repository_manager.get_repository(
            self.config.local_packages_path)
        return (self.resource._repository.uid == local_repo.uid)

    def print_info(self, buf=None, format_=FileFormat.yaml,
                   skip_attributes=None, include_release=False):
        """Print the contents of the package.

        Args:
            buf (file-like object): Stream to write to.
            format_ (`FileFormat`): Format to write in.
            skip_attributes (list of str): List of attributes to not print.
            include_release (bool): If True, include release-related attributes,
                such as 'timestamp' and 'changelog'
        """
        data = self.validated_data().copy()

        # config is a special case. We only really want to show any config settings
        # that were in the package.py, not the entire Config contents that get
        # grafted onto the Package/Variant instance. However Variant has an empy
        # 'data' dict property, since it forwards data from its parent package.
        data.pop("config", None)
        if self.config:
            if isinstance(self, Package):
                config_dict = self.data.get("config")
            else:
                config_dict = self.parent.data.get("config")
            data["config"] = config_dict

        """
        if self.data:
            data["config"] = self.data.get("config")
        if "base" in data:
            del data["base"]
        """

        if not include_release:
            skip_attributes = list(skip_attributes or []) + list(package_release_keys)

        buf = buf or sys.stdout
        dump_package_data(data, buf=buf, format_=format_,
                          skip_attributes=skip_attributes)


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
        """Get the parent package family.

        Returns:
            `PackageFamily`.
        """
        repo = self.resource._repository
        family = repo.get_parent_package_family(self.resource)
        return PackageFamily(family) if family else None

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

    def get_variant(self, index=None):
        """Get the variant with the associated index.

        Returns:
            `Variant` object, or None if no variant with the given index exists.
        """
        for variant in self.iter_variants():
            if variant.index == index:
                return variant


class Variant(PackageBaseResourceWrapper):
    """A package variant.

    Note:
        Do not instantiate this class directly, instead use the function
        `Package.iter_variants`.
    """
    keys = schema_keys(variant_schema)
    keys.update(["index", "root", "subpath"])

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
        """Get the parent package.

        Returns:
            `Package`.
        """
        repo = self.resource._repository
        package = repo.get_parent_package(self.resource)
        return Package(package)

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

    def install(self, path, dry_run=False, overrides=None):
        """Install this variant into another package repository.

        If the package already exists, this variant will be correctly merged
        into the package. If the variant already exists in this package, the
        existing variant is returned.

        Args:
            path (str): Path to destination package repository.
            dry_run (bool): If True, do not actually install the variant. In this
                mode, a `Variant` instance is only returned if the equivalent
                variant already exists in this repository; otherwise, None is
                returned.
            overrides (dict): Use this to change or add attributes to the
                installed variant.

        Returns:
            `Variant` object - the (existing or newly created) variant in the
            specified repository. If `dry_run` is True, None may be returned.
        """
        repo = package_repository_manager.get_repository(path)
        resource = repo.install_variant(self.resource,
                                        dry_run=dry_run,
                                        overrides=overrides)
        if resource is None:
            return None
        elif resource is self.resource:
            return self
        else:
            return Variant(resource)


#------------------------------------------------------------------------------
# resource acquisition functions
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
        range_ (VersionRange or str): If provided, limits the versions returned
            to those in `range_`.
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
            if range_:
                if isinstance(range_, basestring):
                    range_ = VersionRange(range_)
                if package_resource.version not in range_:
                    continue

            yield Package(package_resource)


def get_package(name, version, paths=None):
    """Get an exact version of a package.

    Args:
        name (str): Name of the package, eg 'maya'.
        version (Version or str): Version of the package, eg '1.0.0'
        paths (list of str, optional): paths to search for package, defaults
            to `config.packages_path`.

    Returns:
        `Package` object, or None if the package was not found.
    """
    if isinstance(version, basestring):
        range_ = VersionRange("==%s" % version)
    else:
        range_ = VersionRange.from_version(version, "==")

    it = iter_packages(name, range_, paths)
    try:
        return it.next()
    except StopIteration:
        return None


def get_developer_package(path):
    """Load a developer package.

    A developer package may for example be a package.yaml or package.py in a
    user's source directory.

    Note:
        The resulting package has a 'filepath' attribute added to it, that does
        not normally appear on a `Package` object. A developer package is the
        only case where we know we can directly associate a 'package.*' file
        with a package - other packages can come from any kind of package repo,
        which may or may not associate a single file with a single package (or
        any file for that matter - it may come from a database).

    Args:
        path: Directory containing the package definition file.

    Returns:
        `Package` object.
    """
    data = None
    for format_ in (FileFormat.py, FileFormat.yaml):
        filepath = os.path.join(path, "package.%s" % format_.extension)
        if os.path.isfile(filepath):
            data = load_from_file(filepath, format_)
            break

    if data is None:
        raise PackageMetadataError("No package definition file found at %s" % path)

    name = data.get("name")
    if name is None or not isinstance(name, basestring):
        raise PackageMetadataError(
            "Error in %r - missing or non-string field 'name'" % filepath)

    package = create_package(name, data)
    setattr(package, "filepath", filepath)
    return package


def create_package(name, data):
    """Create a package given package data.

    Args:
        name (str): Package name.
        data (dict): Package data. Must conform to `package_maker.package_schema`.

    Returns:
        `Package` object.
    """
    from rez.package_maker__ import PackageMaker
    maker = PackageMaker(name, data)
    return maker.get_package()


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

    variant_resource = package_repository_manager.get_resource(variant_handle)
    variant = Variant(variant_resource)
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

    Example:

        >>> get_completions("may")
        set(["maya", "maya_utils"])
        >>> get_completions("maya-")
        set(["maya-2013.1", "maya-2015.0.sp1"])

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


def get_latest_package(name, range_=None, paths=None, error=False):
    """Get the latest package for a given package name.

    Args:
        name (str): Package name.
        range_ (`VersionRange`): Version range to search within.
        paths (list of str, optional): paths to search for package families,
            defaults to `config.packages_path`.
        error (bool): If True, raise an error if no package is found.

    Returns:
        `Package` object, or None if no package is found.
    """
    it = iter_packages(name, range_=range_, paths=paths)
    try:
        return max(it, key=lambda x: x.version)
    except ValueError:  # empty sequence
        if error:
            raise PackageFamilyNotFoundError("No such package family %r" % name)
        return None


def _get_families(name, paths=None):
    entries = []
    for path in (paths or config.packages_path):
        repo = package_repository_manager.get_repository(path)
        family_resource = repo.get_package_family(name)
        if family_resource:
            entries.append((repo, family_resource))

    return entries
