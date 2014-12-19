"""
Filesystem-based package repository
"""
from rez.package_repository import PackageRepository
from rez.package_resources_ import PackageFamilyResource, PackageResource, \
    VariantResource, help_schema
from rez.exceptions import PackageMetadataError
from rez.utils.formatting import is_valid_package_name, PackageRequest
from rez.utils.resources import ResourceHandle, cached_property
from rez.utils.schema import Required, schema_keys
from rez.utils.data_utils import AttributeForwardMeta, LazyAttributeMeta, \
    SourceCode
from rez.serialise import load_from_file, FileFormat
from rez.config import config, create_config
from rez.memcache import mem_cached, DataType
from rez.utils.logging_ import print_warning
from rez.vendor.schema.schema import Schema, Optional, And, Or, Use, SchemaError
from rez.vendor.version.version import Version
from rez.backport.lru_cache import lru_cache
from textwrap import dedent
import os.path
import os


#------------------------------------------------------------------------------
# schemas
#------------------------------------------------------------------------------

package_request_schema = And(basestring, Use(PackageRequest))


commands_schema = Or(SourceCode,    # commands function
                     basestring,    # commands in text block
                     [basestring])  # old-style commands


package_schema_ = Schema({
    Required("name"):                   basestring,
    Optional("version"):                And(basestring, Use(Version)),
    Optional('description'):            And(basestring,
                                            Use(lambda x: dedent(x).strip())),
    Optional('authors'):                [basestring],

    Optional('requires'):               [package_request_schema],
    Optional('build_requires'):         [package_request_schema],
    Optional('private_build_requires'): [package_request_schema],
    Optional('variants'):               [[package_request_schema]],

    Optional('uuid'):                   basestring,
    Optional('config'):                 And(dict,
                                            Use(lambda x: create_config(overrides=x))),
    Optional('tools'):                  [basestring],
    Optional('help'):                   help_schema,

    Optional('pre_commands'):           commands_schema,
    Optional('commands'):               commands_schema,
    Optional('post_commands'):          commands_schema,

    Optional("timestamp"):              int,
    Optional('revision'):               object,
    Optional('changelog'):              basestring,
    Optional('release_message'):        Or(None, basestring),
    Optional('previous_version'):       And(basestring, Use(Version)),
    Optional('previous_revision'):      object,

    Optional('custom'):                 dict
})


#------------------------------------------------------------------------------
# utility functions
#------------------------------------------------------------------------------

def get_package_definition_file(path):
    for format_ in FileFormat:
        filename = "package.%s" % format_.extension
        filepath = os.path.join(path, filename)
        if os.path.isfile(filepath):
            return filepath, format_
    return None, None


#------------------------------------------------------------------------------
# resources
#------------------------------------------------------------------------------

class FileSystemPackageFamilyResource(PackageFamilyResource):
    key = "filesystem.family"
    repository_type = "filesystem"

    def _uri(self):
        return os.path.join(self.location, self.name)

    def get_last_release_time(self):
        # this repository makes sure to update path mtime every time a
        # variant is added to the repository [TODO: coming]
        path = os.path.join(self.location, self.name)
        try:
            return os.path.getmtime(path)
        except OSError:
            return 0

    def iter_packages(self):
        root = self.uri

        # check for unversioned package
        filepath, _ = get_package_definition_file(root)
        if filepath:
            handle = ResourceHandle(FileSystemPackageResource.key,
                                    dict(repository_type="filesystem",
                                         location=self.location,
                                         name=self.name))
            package = self._repository.get_resource(handle)
            yield package
            return

        # versioned packages
        for name in self._repository._get_version_dirs(root):
            handle = ResourceHandle(FileSystemPackageResource.key,
                                    dict(repository_type="filesystem",
                                         location=self.location,
                                         name=self.name,
                                         version=name))
            package = self._repository.get_resource(handle)
            yield package


class FileSystemPackageResource(PackageResource):
    key = "filesystem.package"
    repository_type = "filesystem"
    schema = package_schema_

    def _uri(self):
        return self.filepath

    @property
    def base(self):
        return self._path()

    @cached_property
    def parent(self):
        handle = ResourceHandle(FileSystemPackageFamilyResource.key,
                                dict(repository_type="filesystem",
                                     location=self.location,
                                     name=self.name))
        family = self._repository.get_resource(handle)
        return family

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
    def state_handle(self):
        if self.filepath:
            return os.path.getmtime(self.filepath)
        return None

    def iter_variants(self):
        # this is called by the repository
        num_variants = len(self.data.get("variants", []))
        if num_variants == 0:
            indexes = [None]
        else:
            indexes = range(num_variants)

        for index in indexes:
            handle = ResourceHandle(FileSystemVariantResource.key,
                                        dict(repository_type="filesystem",
                                             location=self.location,
                                             name=self.name,
                                             version=self.get("version"),
                                             index=index))
            variant = self._repository.get_resource(handle)
            yield variant

    def _path(self):
        path = os.path.join(self.location, self.name)
        ver_str = self.get("version")
        if ver_str:
            path = os.path.join(path, ver_str)
        return path

    @cached_property
    def filepath(self):
        return self._filepath_and_format[0]

    @cached_property
    def file_format(self):
        return self._filepath_and_format[1]

    @cached_property
    def _filepath_and_format(self):
        path = self._path()
        return get_package_definition_file(path)

    def _load(self):
        if self.filepath is None:
            raise PackageMetadataError("Missing package definition file: %r" % self)

        data = load_from_file(self.filepath, self.file_format,
                              recursive_attributes=("config",))

        if "timestamp" not in data:  # old format support
            data_ = self._load_old_formats()
            if data_:
                data.update(data_)

        return data

    def _load_old_formats(self):
        data = None
        path = self.uri

        filepath = os.path.join(path, "release.yaml")
        if os.path.isfile(filepath):
            # rez<2.0.BETA.16
            data = load_from_file(filepath, FileFormat.yaml,
                                  update_data_callback=self._update_changelog)
        else:
            path_ = os.path.join(path, ".metadata")
            if os.path.isdir(path_):
                # rez-1
                data = {}
                filepath = os.path.join(path_, "changelog.txt")
                if os.path.isfile(filepath):
                    data["changelog"] = load_from_file(
                        filepath, FileFormat.txt,
                        update_data_callback=self._update_changelog)

                filepath = os.path.join(path_, "release_time.txt")
                if os.path.isfile(filepath):
                    value = load_from_file(filepath, FileFormat.txt)
                    try:
                        data["timestamp"] = int(value.strip())
                    except:
                        pass
        return data

    def _convert_to_rex(self, commands):
        if isinstance(commands, list):
            from rez.util import convert_old_commands
            msg = "package is using old-style commands."
            if config.disable_rez_1_compatibility or config.error_old_commands:
                raise SchemaError(None, msg)
            elif config.warn("old_commands"):
                print_warning("%r: %s" % (self, msg))
            commands = convert_old_commands(commands)

        if isinstance(commands, basestring):
            return SourceCode(commands)
        else:
            return commands

    def _update_changelog(self, file_format, data):
        # this is to deal with older package releases. They can contain long
        # changelogs (more recent rez versions truncate before release), and
        # release.yaml files can contain a list-of-str changelog.
        maxlen = config.max_package_changelog_chars

        if file_format == FileFormat.yaml:
            changelog = data.get("changelog")
            if changelog:
                changed = False
                if isinstance(changelog, list):
                    changelog = '\n'.join(changelog)
                    changed = True
                if len(changelog) > (maxlen + 3):
                    changelog = changelog[:maxlen] + "..."
                    changed = True
                if changed:
                    data["changelog"] = changelog
        else:
            assert isinstance(data, basestring)
            if len(data) > (maxlen + 3):
                data = data[:maxlen] + "..."

        return data


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
    repository_type = "filesystem"

    # forward Package attributes onto ourself
    unused_package_keys = frozenset(["requires", "variants"])
    keys = schema_keys(package_schema_) - unused_package_keys

    def _uri(self):
        index = self.index
        idxstr = '' if index is None else str(index)
        return "%s[%s]" % (self.parent.uri, idxstr)

    @property
    def base(self):
        return self.parent.base

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
                                dict(repository_type="filesystem",
                                     location=self.location,
                                     name=self.name,
                                     version=self.get("version")))
        package = self._repository.get_resource(handle)
        return package

    @property
    def wrapped(self):  # forward Package attributes onto ourself
        return self.parent


class FileSystemDeveloperPackageResource(FileSystemPackageResource):
    key = "filesystem.package.developer"

    def _uri(self):
        return "%s(developer)" % self.location

    @property
    def base(self):
        return self.uri

    @cached_property
    def name(self):
        return self._name

    @cached_property
    def version(self):
        return self._version

    @property
    def parent(self):
        return None

    def iter_variants(self):
        num_variants = len(self.data.get("variants", []))
        if num_variants == 0:
            indexes = [None]
        else:
            indexes = range(num_variants)

        for index in indexes:
            handle = ResourceHandle(FileSystemDeveloperVariantResource.key,
                                        dict(repository_type="filesystem",
                                             location=self.location,
                                             index=index))
            variant = self._repository.get_resource(handle)
            yield variant

    def _path(self):
        return self.location

    def _load(self):
        if self.filepath is None:
            raise PackageMetadataError("Missing package definition file: %r" % self)

        data = load_from_file(self.filepath, self.file_format)
        return data


class FileSystemDeveloperVariantResource(FileSystemVariantResource):
    key = "filesystem.variant.developer"

    @cached_property
    def name(self):
        return self.parent.name

    @cached_property
    def version(self):
        return self.parent.version

    @cached_property
    def parent(self):
        handle = ResourceHandle(FileSystemDeveloperPackageResource.key,
                                dict(repository_type="filesystem",
                                     location=self.location))
        package = self._repository.get_resource(handle)
        return package


#------------------------------------------------------------------------------
# repository
#------------------------------------------------------------------------------

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
        """
        super(FileSystemPackageRepository, self).__init__(location, resource_pool)
        self.register_resource(FileSystemPackageFamilyResource)
        self.register_resource(FileSystemPackageResource)
        self.register_resource(FileSystemVariantResource)
        self.register_resource(FileSystemDeveloperPackageResource)
        self.register_resource(FileSystemDeveloperVariantResource)

    def _uid(self):
        st = os.stat(self.location)
        return ("filesystem", self.location, st.st_ino)

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

    def get_developer_package(self):
        filepath, _ = get_package_definition_file(self.location)
        if not filepath:
            return None

        handle = ResourceHandle(FileSystemDeveloperPackageResource.key,
                                dict(repository_type="filesystem",
                                     location=self.location))
        package = self.get_resource(handle)
        return package

    def get_variant_state_handle(self, variant_resource):
        package_resource = variant_resource.parent
        return package_resource.state_handle

    def get_last_release_time(self, package_family_resource):
        return package_family_resource.get_last_release_time()

    # -- internal

    def _get_family_dirs__key(self):
        st = os.stat(self.location)
        return (self.location, st.st_ino, st.st_mtime)

    @mem_cached(DataType.listdir, key_func=_get_family_dirs__key)
    def _get_family_dirs(self):
        dirs = []
        for name in os.listdir(self.location):
            path = os.path.join(self.location, name)
            if is_valid_package_name(name) and os.path.isdir(path):
                dirs.append(name)
        return dirs

    def _get_version_dirs__key(self, root):
        st = os.stat(root)
        return (root, st.st_ino, st.st_mtime)

    @mem_cached(DataType.listdir, key_func=_get_version_dirs__key)
    def _get_version_dirs(self, root):
        dirs = []
        for name in os.listdir(root):
            if name.startswith('.'):
                continue
            path = os.path.join(root, name)
            if os.path.isdir(path):
                dirs.append(name)
        return dirs

    @lru_cache(maxsize=None)
    def _get_families(self):
        families = []
        for name in self._get_family_dirs():
            handle = ResourceHandle(FileSystemPackageFamilyResource.key,
                                    dict(repository_type="filesystem",
                                         location=self.location,
                                         name=name))
            family = self.get_resource(handle)
            families.append(family)
        return families

    @lru_cache(maxsize=None)
    def _get_family(self, name):
        is_valid_package_name(name, raise_error=True)
        if os.path.isdir(os.path.join(self.location, name)):
            handle = ResourceHandle(FileSystemPackageFamilyResource.key,
                                    dict(repository_type="filesystem",
                                         location=self.location,
                                         name=name))
            family = self.get_resource(handle)
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
