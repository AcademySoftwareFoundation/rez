import os.path
from rez.util import Common, propertycache, dedup
from rez.resources import iter_resources, iter_child_resources, \
    get_resource, ResourceWrapper
from rez.exceptions import PackageMetadataError, PackageRequestError
from rez.package_resources import package_schema, PACKAGE_NAME_REGEX
from rez.config import config
from rez.vendor.schema.schema import Schema, Optional
from rez.vendor.version.version import Version, VersionRange
from rez.vendor.version.requirement import VersionedObject, Requirement


def validate_package_name(pkg_name):
    """Raise an error if the value is not a valid package name."""
    if not PACKAGE_NAME_REGEX.match(pkg_name):
        raise PackageRequestError("Not a valid package name: %r" % pkg_name)


def iter_package_families(paths=None):
    """Iterate over package families.

    Note that multiple package families with the same name can be returned.
    Unlike packages, families later in the searchpath are not hidden by earlier
    families.

    Args:
        paths (list of str): paths to search for package families, defaults to
            `config.packages_path`.

    Returns:
        `PackageFamily` iterator.
    """
    for resource in iter_resources(
            resource_keys='package_family.*',
            search_path=paths,
            root_resource_key="folder.packages_root"):
        yield PackageFamily(resource)


def _iter_packages(name=None, paths=None):
    variables = {}
    if name is not None:
        variables["name"] = name
    for resource in iter_resources(
            resource_keys='package.*',
            search_path=paths,
            root_resource_key="folder.packages_root",
            variables=variables):
        yield Package(resource)


def iter_packages(name=None, range=None, paths=None):
    """Iterate over `Package` instances, in no particular order.

    Packages of the same name and version earlier in the search path take
    precedence - equivalent packages later in the paths are ignored. Packages
    are not returned in any specific order.

    Args:
        name (str): Name of the package, eg 'maya'.
        range (VersionRange, optional): If provided, limits the versions
            returned.
        paths (list of str): paths to search for packages, defaults to
            `config.packages_path`.

    Returns:
        `Package` object iterator.
    """
    consumed = set()
    for pkg in _iter_packages(name, paths):
        handle = (pkg.name, pkg.version)
        if handle not in consumed:
            if range and pkg.version not in range:
                continue
            consumed.add(handle)
            yield pkg


def load_developer_package(path):
    """Load a developer package.

    A developer package may for example be a package.yaml or package.py in a
    user's source directory.

    Args:
        path: Directory containing the package definition file.

    Returns:
        `Package` object.
    """
    it = iter_resources(
        resource_keys='package.*',
        search_path=path,
        root_resource_key="folder.dev_packages_root")
    resources = list(it)
    if not resources:
        raise ResourceError("No package definition file found under %s" % path)
    elif len(resources) > 1:
        files = [os.path.basename(x.path) for x in resources]
        raise ResourceError("Multiple package definition files found under "
                            "%s: %s" % (path, ", ".join(files)))

    package = Package(resources[0])
    package.validate_data()
    return package


def get_completions(prefix, paths=None, family_only=False):
    """Get autocompletion options given a prefix string.

    Args:
        prefix (str): Prefix to match.
        paths (list of str): paths to search for packages, defaults to
            `config.packages_path`.
        family_only (bool): If True, only match package names, do not include
            version component.

    Returns:
        List of strings, may be empty.
    """
    op = None
    if prefix:
        if prefix[0] in ('!', '~'):
            if family_only:
                return []
            op = prefix[0]
            prefix = prefix[1:]

    fam = None
    for ch in ('-', '@', '#'):
        if ch in prefix:
            if family_only:
                return []
            fam = prefix.split(ch)[0]
            break

    words = []
    if not fam:
        words = sorted(x.name for x in iter_package_families(paths=paths)
                       if x.name.startswith(prefix))
        words = list(dedup(words))
        if len(words) == 1:
            fam = words[0]

    if family_only:
        return words

    if fam:
        it = iter_packages(name=fam, paths=paths)
        pkgs = sorted(it, key=lambda x: x.version)
        words.extend(x.qualified_name for x in pkgs
                     if x.qualified_name.startswith(prefix))

    if op:
        words = [op + x for x in words]
    return words


class PackageFamily(ResourceWrapper):
    """Class representing a package family.

    You should not instantiate this class directly - instead, call
    `iter_package_families`.
    """
    schema_error = PackageMetadataError

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
    schema_error = PackageMetadataError

    @propertycache
    def name(self):
        value = self._resource.get("name")
        if value is None:
            value = self._name  # loads data
        return value

    @propertycache
    def search_path(self):
        return self._resource.get("search_path")

    @propertycache
    def version(self):
        if self._resource.versioned is False:
            return Version()
        else:
            ver_str = self._resource.get("version")
            if ver_str is None:
                return self._version  # loads data
            return Version(ver_str)

    @propertycache
    def qualified_name(self):
        o = VersionedObject.construct(self.name, self.version)
        return str(o)

    @property
    def config(self):
        """Returns the config for this package.

        Defaults to global config if this package did not provide a 'config'
        section.
        """
        return self._config or config

    @property
    def is_local(self):
        """Returns True if this package is in the local packages path."""
        return (self.search_path == config.local_packages_path)

    def validate_data(self):
        # TODO move compilation into per-key data validation
        super(_PackageBase, self).validate_data()
        if self.commands and isinstance(self.commands, basestring):
            from rez.rex import RexExecutor
            try:
                RexExecutor.compile_code(self.commands)
            except Exception as e:
                raise PackageMetadataError(value=str(e),
                                           path=self.path,
                                           resource_key=self._resource.key)

    def print_info(self, buf=None):
        """Print the contents of the package, in yaml format."""
        from rez.yaml import dump_package_yaml
        data = self.validated_data.copy()
        data = dict((k, v) for k, v in data.iteritems()
                    if v is not None and not k.startswith('_'))

        if "config_version" in data:
            del data["config_version"]
        # TODO
        if "config" in data:
            del data["config"]
        txt = dump_package_yaml(data)
        print >> buf, txt

    def __str__(self):
        return "%s@%s" % (self.qualified_name, self.search_path)


class Package(_PackageBase):
    """Class representing a package definition, as read from a package.* file
    or similar.

    You should not instantiate this class directly - instead, call
    `iter_packages` or `load_developer_package`.
    """
    schema = package_schema

    @property
    def num_variants(self):
        """Return the number of variants in this package."""
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
        return Variant(resource)

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

    @propertycache
    def index(self):
        return self._resource.get("index")

    @property
    def qualified_package_name(self):
        return super(Variant, self).qualified_name

    @property
    def qualified_name(self):
        idxstr = '' if self.index is None else ("%d" % self.index)
        return "%s[%s]" % (self.qualified_package_name, idxstr)

    @property
    def base(self):
        return os.path.dirname(self.path)

    @propertycache
    def root(self):
        return (os.path.join(self.base, self.subpath)
                if self.subpath else self.base)

    @propertycache
    def subpath(self):
        if self.index is None:
            return ''
        else:
            dirs = [x.safe_str() for x in self.variant_requires()]
            return os.path.join(*dirs) if dirs else ''

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

    def variant_requires(self):
        """Get the requirements that have come from the variant part of the
        package only."""
        if self.index is None:
            return []
        else:
            return self._internal.get("variant_requires", [])

    @propertycache
    def parent(self):
        """Get the parent `Package` object."""
        variables = self._resource.variables.copy()
        del variables["index"]
        resource = get_resource(resource_keys=self._resource.parent_resource.key,
                                search_path=self.search_path,
                                variables=variables)
        return Package(resource)

    def __str__(self):
        s = "%s@%s" % (self.qualified_name, self.search_path)
        if self.subpath:
            s += "(%s)" % self.subpath
        return s
