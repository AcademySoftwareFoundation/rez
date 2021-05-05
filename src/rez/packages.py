from rez.package_repository import package_repository_manager
from rez.package_resources import PackageFamilyResource, PackageResource, \
    VariantResource, package_family_schema, package_schema, variant_schema, \
    package_release_keys, late_requires_schema
from rez.package_serialise import dump_package_data
from rez.utils import reraise
from rez.utils.sourcecode import SourceCode
from rez.utils.data_utils import cached_property
from rez.utils.formatting import StringFormatMixin, StringFormatType
from rez.utils.schema import schema_keys
from rez.utils.resources import ResourceHandle, ResourceWrapper
from rez.exceptions import PackageFamilyNotFoundError, ResourceError
from rez.vendor.version.version import Version, VersionRange
from rez.vendor.version.requirement import VersionedObject
from rez.vendor.six import six
from rez.serialise import FileFormat
from rez.config import config

import os
import sys


basestring = six.string_types[0]

# ------------------------------------------------------------------------------
# package-related classes
# ------------------------------------------------------------------------------


class PackageRepositoryResourceWrapper(ResourceWrapper, StringFormatMixin):
    format_expand = StringFormatType.unchanged

    def validated_data(self):
        data = ResourceWrapper.validated_data(self)
        data = dict((k, v) for k, v in data.items() if v is not None)
        return data

    @property
    def repository(self):
        """The package repository this resource comes from.

        Returns:
            `PackageRepository`.
        """
        return self.resource._repository


class PackageFamily(PackageRepositoryResourceWrapper):
    """A package family.

    Note:
        Do not instantiate this class directly, instead use the function
        `iter_package_families`.
    """
    keys = schema_keys(package_family_schema)

    def __init__(self, resource):
        _check_class(resource, PackageFamilyResource)
        super(PackageFamily, self).__init__(resource)

    def iter_packages(self):
        """Iterate over the packages within this family, in no particular order.

        Returns:
            `Package` iterator.
        """
        for package in self.repository.iter_packages(self.resource):
            yield Package(package)


class PackageBaseResourceWrapper(PackageRepositoryResourceWrapper):
    """Abstract base class for `Package` and `Variant`.
    """
    late_bind_schemas = {
        "requires": late_requires_schema
    }

    def __init__(self, resource, context=None):
        super(PackageBaseResourceWrapper, self).__init__(resource)
        self.context = context

        # cached results of late-bound funcs
        self._late_binding_returnvalues = {}

    def set_context(self, context):
        self.context = context

    def arbitrary_keys(self):
        raise NotImplementedError

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

        if not include_release:
            skip_attributes = list(skip_attributes or []) + list(package_release_keys)

        buf = buf or sys.stdout
        dump_package_data(data, buf=buf, format_=format_,
                          skip_attributes=skip_attributes)

    def _wrap_forwarded(self, key, value):
        if isinstance(value, SourceCode) and value.late_binding:
            # get cached return value if present
            value_ = self._late_binding_returnvalues.get(key, KeyError)

            if value_ is KeyError:
                # evaluate the late-bound function
                value_ = self._eval_late_binding(value)

                schema = self.late_bind_schemas.get(key)
                if schema is not None:
                    value_ = schema.validate(value_)

                # cache result of late bound func
                self._late_binding_returnvalues[key] = value_

            return value_
        else:
            return value

    def _eval_late_binding(self, sourcecode):
        g = {}

        if self.context is None:
            g["in_context"] = lambda: False
        else:
            g["in_context"] = lambda: True
            g["context"] = self.context

            # 'request', 'system' etc
            bindings = self.context._get_pre_resolve_bindings()
            g.update(bindings)

        # Note that 'this' could be a `Package` or `Variant` instance. This is
        # intentional; it just depends on how the package is accessed.
        #
        g["this"] = self

        # evaluate the late-bound function
        sourcecode.set_package(self)
        return sourcecode.exec_(globals_=g)


class Package(PackageBaseResourceWrapper):
    """A package.

    Note:
        Do not instantiate this class directly, instead use the function
        `iter_packages` or `PackageFamily.iter_packages`.
    """
    keys = schema_keys(package_schema)

    # This is to allow for a simple check like 'this.is_package' in late-bound
    # funcs, where 'this' may be a package or variant.
    #
    is_package = True
    is_variant = False

    def __init__(self, resource, context=None):
        _check_class(resource, PackageResource)
        super(Package, self).__init__(resource, context)

    # arbitrary keys
    def __getattr__(self, name):
        if name in self.data:
            value = self.data[name]
            return self._wrap_forwarded(name, value)
        else:
            raise AttributeError("Package instance has no attribute '%s'" % name)

    def arbitrary_keys(self):
        """Get the arbitrary keys present in this package.

        These are any keys not in the standard list ('name', 'version' etc).

        Returns:
            set of str: Arbitrary keys.
        """
        return set(self.data.keys()) - set(self.keys)

    @cached_property
    def qualified_name(self):
        """Get the qualified name of the package.

        Returns:
            str: Name of the package with version, eg "maya-2016.1".
        """
        o = VersionedObject.construct(self.name, self.version)
        return str(o)

    def as_exact_requirement(self):
        """Get the package, as an exact requirement string.

        Returns:
            Equivalent requirement string, eg "maya==2016.1"
        """
        o = VersionedObject.construct(self.name, self.version)
        return o.as_exact_requirement()

    @cached_property
    def parent(self):
        """Get the parent package family.

        Returns:
            `PackageFamily`.
        """
        family = self.repository.get_parent_package_family(self.resource)
        return PackageFamily(family) if family else None

    @cached_property
    def num_variants(self):
        return len(self.data.get("variants", []))

    @property
    def is_relocatable(self):
        """True if the package and its payload is safe to copy.
        """
        if self.relocatable is not None:
            return self.relocatable

        if config.default_relocatable_per_repository:
            value = config.default_relocatable_per_repository.get(
                self.repository.location)
            if value is not None:
                return value

        if config.default_relocatable_per_package:
            value = config.default_relocatable_per_package.get(self.name)
            if value is not None:
                return value

        return config.default_relocatable

    @property
    def is_cachable(self):
        """True if the package and its payload is safe to cache locally.
        """
        if self.cachable is not None:
            return self.cachable

        if config.default_cachable_per_repository:
            # TODO: The location of filesystem repository is canonical path,
            #   so if the path in `default_cachable_per_repository` isn't
            #   canonical, this may return false value e.g. on Windows.
            value = config.default_cachable_per_repository.get(
                self.repository.location)
            if value is not None:
                return value

        if config.default_cachable_per_package:
            value = config.default_cachable_per_package.get(self.name)
            if value is not None:
                return value

        if config.default_cachable is not None:
            return config.default_cachable

        return self.is_relocatable

    def iter_variants(self):
        """Iterate over the variants within this package, in index order.

        Returns:
            `Variant` iterator.
        """
        for variant in self.repository.iter_variants(self.resource):
            yield Variant(variant, context=self.context, parent=self)

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

    # See comment in `Package`
    is_package = False
    is_variant = True

    def __init__(self, resource, context=None, parent=None):
        _check_class(resource, VariantResource)
        super(Variant, self).__init__(resource, context)
        self._parent = parent

    # arbitrary keys
    def __getattr__(self, name):
        try:
            return self.parent.__getattr__(name)
        except AttributeError:
            raise AttributeError("Variant instance has no attribute '%s'" % name)

    def arbitrary_keys(self):
        return self.parent.arbitrary_keys()

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
        if self._parent is not None:
            return self._parent

        try:
            package = self.repository.get_parent_package(self.resource)
            self._parent = Package(package, context=self.context)
        except AttributeError as e:
            reraise(e, ValueError)

        return self._parent

    @property
    def variant_requires(self):
        """Get the subset of requirements specific to this variant.

        Returns:
            List of `Requirement` objects.
        """
        if self.index is None:
            return []
        else:
            return self.parent.variants[self.index] or []

    @property
    def requires(self):
        """Get variant requirements.

        This is a concatenation of the package requirements and those of this
        specific variant.

        Returns:
            List of `Requirement` objects.
        """
        return (
            (self.parent.requires or []) + self.variant_requires
        )

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

    @property
    def _non_shortlinked_subpath(self):
        return self.resource._subpath(ignore_shortlinks=True)


class PackageSearchPath(object):
    """A list of package repositories.

    For example, $REZ_PACKAGES_PATH refers to a list of repositories.
    """
    def __init__(self, packages_path):
        """Create a package repository list.

        Args:
            packages_path (list of str): List of package repositories.
        """
        self.paths = packages_path

    def iter_packages(self, name, range_=None):
        """See `iter_packages`.

        Returns:
            `Package` iterator.
        """
        for package in iter_packages(name=name, range_=range_, paths=self.paths):
            yield package

    def __contains__(self, package):
        """See if a package is in this list of repositories.

        Note:
            This does not verify the existance of the resource, only that the
            resource's repository is in this list.

        Args:
            package (`Package` or `Variant`): Package to search for.

        Returns:
            bool: True if the resource is in the list of repositories, False
            otherwise.
        """
        return (package.resource._repository.uid in self._repository_uids)

    @cached_property
    def _repository_uids(self):
        uids = set()
        for path in self.paths:
            repo = package_repository_manager.get_repository(path)
            uids.add(repo.uid)
        return uids


# ------------------------------------------------------------------------------
# resource acquisition functions
# ------------------------------------------------------------------------------

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
    """Get a package by searching a list of repositories.

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
        return next(it)
    except StopIteration:
        return None


def get_package_from_repository(name, version, path):
    """Get a package from a repository.

    Args:
        name (str): Name of the package, eg 'maya'.
        version (Version or str): Version of the package, eg '1.0.0'

    Returns:
        `Package` object, or None if the package was not found.
    """
    repo = package_repository_manager.get_repository(path)

    if isinstance(version, basestring):
        version = Version(version)

    package_resource = repo.get_package(name, version)
    if package_resource is None:
        return None

    return Package(package_resource)


def get_package_from_handle(package_handle):
    """Create a package given its handle (or serialized dict equivalent)

    Args:
        package_handle (`ResourceHandle` or dict): Resource handle, or
            equivalent serialized dict representation from
            ResourceHandle.to_dict

    Returns:
        `Package`.
    """
    if isinstance(package_handle, dict):
        package_handle = ResourceHandle.from_dict(package_handle)
    package_resource = package_repository_manager.get_resource_from_handle(package_handle)
    package = Package(package_resource)
    return package


def get_package_from_string(txt, paths=None):
    """Get a package given a string.

    Args:
        txt (str): String such as 'foo', 'bah-1.3'.
        paths (list of str, optional): paths to search for package, defaults
            to `config.packages_path`.

    Returns:
        `Package` instance, or None if no package was found.
    """
    o = VersionedObject(txt)
    return get_package(o.name, o.version, paths=paths)


def get_developer_package(path, format=None):
    """Create a developer package.

    Args:
        path (str): Path to dir containing package definition file.
        format (str): Package definition file format, detected if None.

    Returns:
        `DeveloperPackage`.
    """
    from rez.developer_package import DeveloperPackage
    return DeveloperPackage.from_path(path, format=format)


def create_package(name, data, package_cls=None):
    """Create a package given package data.

    Args:
        name (str): Package name.
        data (dict): Package data. Must conform to `package_maker.package_schema`.

    Returns:
        `Package` object.
    """
    from rez.package_maker import PackageMaker
    maker = PackageMaker(name, data, package_cls=package_cls)
    return maker.get_package()


def get_variant(variant_handle, context=None):
    """Create a variant given its handle (or serialized dict equivalent)

    Args:
        variant_handle (`ResourceHandle` or dict): Resource handle, or
            equivalent serialized dict representation from
            ResourceHandle.to_dict
        context (`ResolvedContext`): The context this variant is associated
            with, if any.

    Returns:
        `Variant`.
    """
    if isinstance(variant_handle, dict):
        variant_handle = ResourceHandle.from_dict(variant_handle)

    variant_resource = package_repository_manager.get_resource_from_handle(variant_handle)
    variant = Variant(variant_resource, context=context)
    return variant


def get_package_from_uri(uri, paths=None):
    """Get a package given its URI.

    Args:
        uri (str): Variant URI
        paths (list of str): paths to search for packages, defaults to
            `config.packages_path`. If None, attempts to find a package that
            may have come from any package repo.

    Returns:
        `Package`, or None if the package could not be found.
    """
    def _find_in_path(path):
        repo = package_repository_manager.get_repository(path)
        pkg_resource = repo.get_package_from_uri(uri)
        if pkg_resource is not None:
            return Package(pkg_resource)
        else:
            return None

    for path in (paths or config.packages_path):
        pkg = _find_in_path(path)
        if pkg is not None:
            return pkg

    if paths:
        return None

    # same deal as in get_variant_from_uri, see there for comments

    parts = os.path.split(uri)

    # assume form /{pkg-repo-path}/{pkg-name}/{pkg-version}/package.py
    if '<' not in uri:
        path = os.path.sep.join(parts[:-3])
        pkg = _find_in_path(path)
        if pkg is not None:
            return pkg

    # assume unversioned OR 'combined'-type package, ie:
    # /{pkg-repo-path}/{pkg-name}/package.py OR
    # /{pkg-repo-path}/{pkg-name}/package.py<{version}>
    #
    path = os.path.sep.join(parts[:-2])
    return _find_in_path(path)


def get_variant_from_uri(uri, paths=None):
    """Get a variant given its URI.

    Args:
        uri (str): Variant URI
        paths (list of str): paths to search for variants, defaults to
            `config.packages_path`. If None, attempts to find a variant that
            may have come from any package repo.

    Returns:
        `Variant`, or None if the variant could not be found.
    """
    def _find_in_path(path):
        repo = package_repository_manager.get_repository(path)
        variant_resource = repo.get_variant_from_uri(uri)
        if variant_resource is not None:
            return Variant(variant_resource)
        else:
            return None

    for path in (paths or config.packages_path):
        variant = _find_in_path(path)
        if variant is not None:
            return variant

    if paths:
        return None

    # If we got here, `uri` may be valid, but for a variant that is not in the
    # current packages_path. Variant URIs are determined by package repos, and
    # there is no guarantee that you can determine the repo from any given URI
    # (ie, they are unidirectional). The following has to be considered a hack,
    # as it will only work for filesystem-type package repos.
    #
    # TODO make variant URIs bidirectional (ie, package repo can be determined
    # from URI).
    #
    parts = os.path.split(uri)

    # assume form /{pkg-repo-path}/{pkg-name}/{pkg-version}/package.py[{index}]
    if '<' not in uri:
        path = os.path.sep.join(parts[:-3])
        variant = _find_in_path(path)
        if variant is not None:
            return variant

    # assume unversioned OR 'combined'-type package, ie:
    # /{pkg-repo-path}/{pkg-name}/package.py[{index}] OR
    # /{pkg-repo-path}/{pkg-name}/package.py<{version}>[{index}]
    #
    path = os.path.sep.join(parts[:-2])
    return _find_in_path(path)


def get_last_release_time(name, paths=None):
    """Returns the most recent time this package was released.

    Note that releasing a variant into an already-released package is also
    considered a package release.

    Args:
        name (str): Package family name.
        paths (list of str): paths to search for packages, defaults to
            `config.packages_path`.

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
            fam = next(iter(words))

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
            # FIXME this isn't correct, since the pkg fam may exist but a pkg
            # in the range does not.
            raise PackageFamilyNotFoundError("No such package family %r" % name)
        return None


def get_latest_package_from_string(txt, paths=None, error=False):
    """Get the latest package found within the given request string.

    Args:
        txt (str): Request, eg 'foo-1.2+'
        paths (list of str, optional): paths to search for packages, defaults
            to `config.packages_path`.
        error (bool): If True, raise an error if no package is found.

    Returns:
        `Package` object, or None if no package is found.
    """
    from rez.utils.formatting import PackageRequest

    req = PackageRequest(txt)
    return get_latest_package(name=req.name,
                              range_=req.range_,
                              paths=paths,
                              error=error)


def _get_families(name, paths=None):
    entries = []
    for path in (paths or config.packages_path):
        repo = package_repository_manager.get_repository(path)
        family_resource = repo.get_package_family(name)
        if family_resource:
            entries.append((repo, family_resource))

    return entries


def _check_class(resource, cls):
    if not isinstance(resource, cls):
        raise ResourceError("Expected %s, got %s"
                            % (cls.__name__, resource.__class__.__name__))


# Copyright 2013-2016 Allan Johns.
#
# This library is free software: you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.
