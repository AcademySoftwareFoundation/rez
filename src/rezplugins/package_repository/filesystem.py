"""
Filesystem-based package repository
"""
from rez.package_repository import PackageRepository
from rez.package_resources_ import PackageFamilyResource, PackageResource, \
    VariantResource, help_schema, PACKAGE_NAME_REGEX
from rez.exceptions import PackageMetadataError
from rez.resources_ import ResourceHandle, cached_property, Required, schema_keys
from rez.serialise import load_from_file, FileFormat
from rez.config import config, create_config
from rez.utils.data_utils import AttributeForwardMeta, LazyAttributeMeta
from rez.util import print_warning
from rez.vendor.schema.schema import Schema, Optional, And, Or, Use, SchemaError
from rez.vendor.version.version import Version
from rez.vendor.version.requirement import Requirement
from rez.backport.lru_cache import lru_cache
import os.path
import os


# -- schemas

requirement_schema = And(basestring, Use(Requirement))


commands_schema = Or(callable,  # commands function
                     basestring,  # commands in text block
                     [basestring])  # old-style commands


package_schema_ = Schema({
    Required("name"):                   basestring,
    Optional("version"):                And(basestring, Use(Version)),
    Optional('description'):            And(basestring, Use(lambda x: x.strip())),
    Optional('authors'):                [basestring],

    Optional('requires'):               [requirement_schema],
    Optional('build_requires'):         [requirement_schema],
    Optional('private_build_requires'): [requirement_schema],
    Optional('variants'):               [[requirement_schema]],

    Optional('uuid'):                   basestring,
    Optional('config'):                 And(dict,
                                            Use(lambda x: create_config(overrides=x))),
    Optional('tools'):                  [basestring],
    Optional('help'):                   help_schema,

    Optional('pre_commands'):           commands_schema,
    Optional('commands'):               commands_schema,
    Optional('post_commands'):          commands_schema,

    Optional('custom'):                 dict
})


# -- resources

class FileSystemPackageFamilyResource(PackageFamilyResource):
    key = "filesystem.family"

    def _uri(self):
        return os.path.join(self.location, self.name)

    def iter_packages(self):
        root = self._uri()

        # check for unversioned package
        for format_ in FileFormat:
            filename = "package.%s" % format_.extension
            filepath = os.path.join(root, filename)
            if os.path.isfile(filepath):
                handle = ResourceHandle(FileSystemPackageResource.key,
                                        dict(location=self.location,
                                             name=self.name))
                package = self._repository._get_resource(handle)
                yield package
                return

        # versioned packages
        for name in os.listdir(root):
            if name.startswith('.'):
                continue
            path = os.path.join(root, name)
            if os.path.isdir(path):
                handle = ResourceHandle(FileSystemPackageResource.key,
                                        dict(location=self.location,
                                             name=self.name,
                                             version=name))
                package = self._repository._get_resource(handle)
                yield package


class FileSystemPackageResource(PackageResource):
    key = "filesystem.package"
    schema = package_schema_

    def _uri(self):
        path = os.path.join(self.location, self.name)
        ver_str = self.get("version")
        if ver_str:
            path = os.path.join(path, ver_str)
        return path

    @cached_property
    def commands(self):
        return self._convert_to_rex(self._commands)

    @cached_property
    def pre_commands(self):
        return self._convert_to_rex(self._pre_commands)

    @cached_property
    def post_commands(self):
        return self._convert_to_rex(self._post_commands)

    @cached_property
    def parent(self):
        handle = ResourceHandle(FileSystemPackageFamilyResource.key,
                                dict(location=self.location,
                                     name=self.name))
        family = self._repository._get_resource(handle)
        return family

    def iter_variants(self):
        num_variants = len(self.data.get("variants", []))
        if num_variants == 0:
            indexes = [None]
        else:
            indexes = range(num_variants)

        for index in indexes:
            handle = ResourceHandle(FileSystemVariantResource.key,
                                        dict(location=self.location,
                                             name=self.name,
                                             version=self.get("version"),
                                             index=index))
            variant = self._repository._get_resource(handle)
            yield variant

    def _load(self):
        filepath = None
        path = self._uri()
        for format_ in FileFormat:
            filename = "package.%s" % format_.extension
            filepath_ = os.path.join(path, filename)
            if os.path.isfile(filepath_):
                filepath = filepath_
                break

        if filepath is None:
            raise PackageMetadataError("Missing package definition file: %r" % self)

        data = load_from_file(filepath, format_)
        return data

    def _convert_to_rex(self, commands):
        if isinstance(commands, list):
            from rez.util import convert_old_commands
            msg = "package is using old-style commands."
            if config.disable_rez_1_compatibility or config.error_old_commands:
                raise SchemaError(None, msg)
            elif config.warn("old_commands"):
                print_warning("%r: %s" % (self, msg))
            return convert_old_commands(commands)
        else:
            return commands


class FileSystemVariantResource(VariantResource):
    """
    Note:
        Since a variant overlaps so much with a package, here we use the
        forwarding metaclass to forward our parent package's attributes onto
        ourself (with some exceptions - eg 'variants', 'requires').
    """
    class _Metas(AttributeForwardMeta, LazyAttributeMeta): pass
    __metaclass__ = _Metas

    key = "filesystem.variant"

    # forward Package attributes onto ourself
    unused_package_keys = frozenset(["requires", "variants"])
    keys = schema_keys(package_schema_) - unused_package_keys

    def _uri(self):
        index = self.index
        idxstr = '' if index is None else str(index)
        return "%s[%s]" % (self.parent.uri, idxstr)

    @cached_property
    def base(self):
        return self.parent.uri

    @cached_property
    def root(self):
        index = self.index
        if index is None:
            return self.base
        else:
            reqs = self.parent.variants[index]
            dirs = [x.safe_str() for x in reqs]
            subpath = os.path.join(*dirs)
            return os.path.join(self.base, subpath)

    @cached_property
    def requires(self):
        reqs = self.parent.requires or []
        index = self.index
        if index is not None:
            reqs = reqs + (self.parent.variants[index] or [])
        return reqs

    @cached_property
    def parent(self):
        handle = ResourceHandle(FileSystemPackageResource.key,
                                dict(location=self.location,
                                     name=self.name,
                                     version=self.get("version")))
        package = self._repository._get_resource(handle)
        return package

    @property
    def wrapped(self):  # forward Package attributes onto ourself
        return self.parent


# -- repository

class FileSystemPackageRepository(PackageRepository):
    """A filesystem-based package repository.

    Packages are stored on disk, in either 'package.yaml' or 'package.py' files.
    These files are stored into an organised directory structure like so:

        /LOCATION/pkgA/1.0.0/package.py
                      /1.0.1/package.py
                 /pkgB/2.1/package.py
                      /2.2/package.py
    """
    @classmethod
    def name(cls):
        return "filesystem"

    def __init__(self, location, resource_pool):
        """Create a filesystem package repository.

        Args:
            location (str): Path containing the package repository.
            resource_pool (`ResourcePool`): Pool to manage all resources from
                this repository.
        """
        super(FileSystemPackageRepository, self).__init__(location, resource_pool)
        self.pool.register_resource(FileSystemPackageFamilyResource)
        self.pool.register_resource(FileSystemPackageResource)
        self.pool.register_resource(FileSystemVariantResource)

    def get_package_family(self, name):
        return self._get_family(name)

    def iter_package_families(self):
        for family in self._get_families():
            yield family

    def iter_packages(self, package_family_resource):
        for package in self._get_packages(package_family_resource):
            yield package

    def iter_variants(self, package_resource):
        for variant in self._get_variants(package_resource):
            yield variant

    def get_parent_package_family(self, package_resource):
        return package_resource.parent

    def get_parent_package(self, variant_resource):
        return variant_resource.parent

    # -- internal

    @lru_cache(maxsize=None)
    def _get_families(self):
        families = []
        for name in os.listdir(self.location):
            family = self._get_family(name)
            if family:
                families.append(family)
        return families

    @lru_cache(maxsize=None)
    def _get_family(self, name):
        if PACKAGE_NAME_REGEX.match(name)  \
                and os.path.isdir(os.path.join(self.location, name)):
            handle = ResourceHandle(FileSystemPackageFamilyResource.key,
                                    dict(location=self.location,
                                         name=name))
            family = self._get_resource(handle)
            return family
        return None

    @lru_cache(maxsize=None)
    def _get_packages(self, package_family_resource):
        return [x for x in package_family_resource.iter_packages()]

    @lru_cache(maxsize=None)
    def _get_variants(self, package_resource):
        return [x for x in package_resource.iter_variants()]


def register_plugin():
    return FileSystemPackageRepository
