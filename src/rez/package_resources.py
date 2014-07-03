from rez.resources import _or_regex, _updated_schema, register_resource, \
    Resource, SearchPath, ArbitraryPath, FolderResource, FileResource, \
    Required, metadata_loaders, load_resource, load_yaml
from rez.config import config, Config, create_config
from rez.exceptions import ResourceError, ResourceNotFoundError, \
    PackageMetadataError
from rez.util import propertycache, deep_update, print_warning_once
from rez.vendor.schema.schema import Schema, SchemaError, Use, And, Or, \
    Optional
from rez.vendor.version.version import Version, VersionRange
from rez.vendor.version.requirement import Requirement
import os.path
import string
import re


PACKAGE_NAME_REGSTR = '[a-zA-Z_](\.?[a-zA-Z0-9_]+)*'
PACKAGE_NAME_REGEX = re.compile(r"^%s\Z" % PACKAGE_NAME_REGSTR)
VERSION_COMPONENT_REGSTR = '(?:[0-9a-zA-Z_]+)'
VERSION_REGSTR = ('%(comp)s(?:[.-]%(comp)s)*'
                  % dict(comp=VERSION_COMPONENT_REGSTR))


# -----------------------------------------------------------------------------
# Schema Implementations
# -----------------------------------------------------------------------------

# TODO: inspect arguments of the function to confirm proper number?
rex_command = Or(callable,  # python function
                 basestring  # new-style rex
                 )


# The master package schema.  All resources delivering metadata to the Package
# class must ultimately validate against this master schema. This schema
# intentionally does no casting of types: that should happen on the resource
# schemas.
package_schema = Schema({
    Optional('config_version'):         int,  # deprecated

    Optional('uuid'):                   basestring,
    Optional('description'):            basestring,
    Required('name'):                   basestring,
    Optional('version'):                Version,
    Optional('authors'):                [basestring],
    # TODO timestamp is going to become per-variant
    Optional('timestamp'):              int,
    # Required('timestamp'):              int,
    Optional('config'):                 Config,
    Optional('help'):                   Or(basestring,
                                           [[basestring]]),
    Optional('tools'):                  [basestring],
    Optional('requires'):               [Requirement],
    Optional('build_requires'):         [Requirement],
    Optional('private_build_requires'): [Requirement],
    Optional('variants'):               [[Requirement]],
    Optional('commands'):               rex_command,

    # custom keys
    Optional('custom'):                 object,
    Optional(basestring):               object,

    # a dict for internal use
    Optional('_internal'):              dict,

    # release data
    Optional('revision'):               object,
    Optional('changelog'):              basestring,
    Optional('release_message'):        Or(None, basestring),
    Optional('previous_version'):       Version,
    Optional('previous_revision'):      object,

    # rez-1 rez-egg-install properties
    Optional('unsafe_name'):            object,
    Optional('unsafe_version'):         object,
    Optional('EGG-INFO'):               object,
})


# -----------------------------------------------------------------------------
# Package Resources
# -----------------------------------------------------------------------------

class PackagesRoot(SearchPath):
    """Represents a package searchpath, typically in config.packages_path."""
    key = 'folder.packages_root'

    @classmethod
    def _default_search_paths(cls, path=None):
        return config.packages_path

    @classmethod
    def _contents_exception_type(cls):
        return PackageMetadataError


class PackageFamilyFolder(FolderResource):
    """Represents a folder with the name of a package."""
    key = 'package_family.folder'
    path_pattern = '{name}'
    parent_resource = PackagesRoot
    variable_keys = ["name"]
    variable_regex = dict(name=PACKAGE_NAME_REGSTR)


class PackageVersionFolder(FolderResource):
    """Represents a folder whos name is the version of a package."""
    key = 'version.folder'
    path_pattern = '{version}'
    parent_resource = PackageFamilyFolder
    variable_keys = ["version"]
    variable_regex = dict(version=VERSION_REGSTR)


# -- deprecated

class MetadataFolder(FolderResource):
    key = 'folder.metadata'
    path_pattern = '.metadata'
    parent_resource = PackageVersionFolder


class ReleaseTimestampResource(FileResource):
    # Deprecated
    key = 'release.timestamp'
    path_pattern = 'release_time.txt'
    parent_resource = MetadataFolder
    schema = Use(int)


class ChangelogResource(FileResource):
    # Deprecated
    key = 'release.changelog'
    path_pattern = 'changelog.txt'
    parent_resource = MetadataFolder
    schema = Use(str)


class ReleaseInfoResource(FileResource):
    # Deprecated
    key = 'release.info'
    path_pattern = 'info.txt'
    parent_resource = MetadataFolder
    loader = 'yaml'
    schema = Schema({
        Required('ACTUAL_BUILD_TIME'): int,
        Required('BUILD_TIME'): int,
        Required('USER'): basestring,
        Optional('SVN'): basestring
    })

# -- END deprecated


class ReleaseDataResource(FileResource):
    key = 'release.data'
    path_pattern = 'release.yaml'
    parent_resource = PackageVersionFolder

    def load_changelog(v):
        if v is None:
            return ""
        elif isinstance(v, basestring):
            return v
        else:
            return '\n'.join(v)

    schema = Schema({
        # TODO this is going to move to per-variant
        Optional('timestamp'): int,
        # Required('timestamp'): int,
        Required('revision'): object,
        Required('changelog'): And(Or(basestring,
                                      [basestring]),
                                   Use(load_changelog)),
        Optional('release_message'): Or(None, basestring),
        Optional('previous_version'): Use(Version),
        Optional('previous_revision'): object,
        Optional(basestring): object
    })


class BasePackageResource(FileResource):
    """Abstract class providing the standard set of package metadata.
    """
    versioned = None

    def convert_to_rex(self, commands):
        from rez.util import convert_old_commands
        msg = "package is using old-style commands."
        if config.disable_rez_1_compatibility or config.error_old_commands:
            raise SchemaError(None, msg)
        elif config.warn("old_commands"):
            print_warning_once("%s: %s" % (self.path, msg))
        return convert_old_commands(commands)

    def convert_name(self, value):
        """Deals with case where package name in a package.yaml does not match
        package name in directory structure. This error will be handled as a
        warning if the relevant backwards compatibility setting is turned on.
        """
        name = self.variables.get("name")
        if value != name:
            msg = "name %r does not match %r" % (value, name)
            if config.disable_rez_1_compatibility \
                    or config.error_package_name_mismatch:
                raise SchemaError(None, msg)
            elif config.warn("package_name_mismatch"):
                print_warning_once("%s: %s" % (self.path, msg))
        return name

    def custom_key(self, value):
        msg = "custom key in root of package definition."
        if config.disable_rez_1_compatibility or config.error_root_custom_key:
            raise SchemaError(None, msg)
        elif config.warn("root_custom_key"):
            print_warning_once("%s: %s" % (self.path, msg))
        return True

    def new_rex_command(self, value):
        msg = "'commands2' section in package definition"
        if config.disable_rez_1_compatibility or config.error_commands2:
            raise SchemaError(None, msg)
        elif config.warn("commands2"):
            print_warning_once("%s: %s" % (self.path, msg))
        return True

    @propertycache
    def schema(self):
        return Schema({
            Optional('config_version'):         0,  # this will only match 0

            Optional('uuid'):                   basestring,
            Optional('description'):            And(basestring,
                                                    Use(string.strip)),
            Required('name'):                   And(basestring,
                                                    Use(self.convert_name)),
            Optional('authors'):                [basestring],
            Optional('config'):                 And(dict,
                                                    Use(lambda x:
                                                        create_config(overrides=x))),
            Optional('help'):                   Or(basestring,
                                                   [[basestring]]),
            Optional('tools'):                  [basestring],
            Optional('requires'):               [Use(Requirement)],
            Optional('variants'):               [[Use(Requirement)]],
            Optional('build_requires'):         [Use(Requirement)],
            Optional('private_build_requires'): [Use(Requirement)],
            Optional('commands'):               Or(rex_command,
                                                   And([basestring],
                                                       Use(self.convert_to_rex))),
            Optional('commands2'):              And(rex_command,
                                                    self.new_rex_command),

            # backwards compatibility for rez-egg-install- generated packages
            Optional('unsafe_name'):            object,
            Optional('unsafe_version'):         object,
            Optional('EGG-INFO'):               object,

            # custom keys
            Optional('custom'):                 dict,
            Optional(basestring):               self.custom_key,

            # a dict for internal use
            Optional('_internal'):              dict,
        })

    @Resource.cached
    def load(self):
        data = super(BasePackageResource, self).load().copy()

        # commands2 support
        if "commands2" in data:
            data["commands"] = data.pop("commands2")

        # graft release info onto resource
        release_data = self._load_component("release.data")
        if release_data:
            data.update(release_data)
        timestamp = self._load_timestamp()
        if timestamp:
            data['timestamp'] = timestamp

        # graft on old-style changelog, if necessary
        if "changelog" not in data:
            changelog = self._load_component("release.changelog")
            if changelog:
                data["changelog"] = changelog
        return data

    # TODO just load the handle rather than the resource data, and add lazy
    # loading mechanism
    def _load_component(self, resource_key):
        variables = dict((k, v) for k, v in self.variables.iteritems()
                         if k in ("name", "version"))
        try:
            data = load_resource(
                resource_keys=resource_key,
                search_path=self.variables['search_path'],
                variables=variables)
        except ResourceNotFoundError:
            data = None
        return data

    # TODO move into variant
    def _load_timestamp(self):
        release_data = self._load_component("release.data")
        timestamp = (release_data or {}).get("timestamp", 0)
        if not timestamp:
            timestamp = self._load_component("release.timestamp") or 0
        if not timestamp:
            # FIXME: should we deal with is_local here or in rez.packages?
            if config.warn("untimestamped"):
                print_warning_once("Package is not timestamped: %s" %
                                   self.path)
        return timestamp


class BaseVariantResource(BasePackageResource):
    """Abstract base class for all package variants."""
    @Resource.cached
    def load(self):
        parent = self.parent_instance()
        data = parent.load()
        variants = data.get("variants")
        if "variants" in data:
            data = data.copy()
            del data["variants"]

        idx = self.variables["index"]
        if idx is not None:
            try:
                variant_requires = variants[idx]
                data["_internal"] = dict(variant_requires=variant_requires)
                requires = data.get("requires", []) + variant_requires
                data["requires"] = requires
            except IndexError:
                raise ResourceNotFoundError("variant not found in parent "
                                            "package resource")
        return data

    @classmethod
    def iter_instances(cls, parent_resource):
        data = parent_resource.load()
        variants = data.get("variants")
        if variants:
            for i in range(len(variants)):
                variables = parent_resource.variables.copy()
                variables["index"] = i
                yield cls(parent_resource.path, variables)
        else:
            variables = parent_resource.variables.copy()
            variables['index'] = None
            yield cls(parent_resource.path, variables)


class VersionlessPackageResource(BasePackageResource):
    """A versionless package from a single file."""
    key = 'package.versionless'
    path_pattern = 'package.{ext}'
    parent_resource = PackageFamilyFolder
    variable_keys = ["ext"]
    variable_regex = dict(ext=_or_regex(metadata_loaders.keys()))
    versioned = False

    @Resource.cached
    def load(self):
        data = super(VersionlessPackageResource, self).load().copy()
        data['version'] = Version()
        return data


class VersionlessVariantResource(BaseVariantResource):
    """A variant within a `VersionlessPackageResource`."""
    key = 'variant.versionless'
    parent_resource = VersionlessPackageResource
    variable_keys = ["index"]
    sub_resource = True
    schema = None
    versioned = False


class VersionedPackageResource(BasePackageResource):
    """A versioned package from a single file."""
    key = 'package.versioned'
    path_pattern = 'package.{ext}'
    parent_resource = PackageVersionFolder
    variable_keys = ["ext"]
    variable_regex = dict(ext=_or_regex(metadata_loaders.keys()))
    versioned = True

    def convert_version(self, value):
        """Deals with two errors:
        1) 'version' is a number (it should be a string);
        2) 'version' does not match the version specified in the directory
           structure.
        These errors will be handled as warnings if the relevant backwards
        compatibility settings are turned on.
        """
        version_str = self.variables.get('version')
        if isinstance(value, basestring):
            if value != version_str:
                msg = "version %r does not match %r" % (value, version_str)
                if config.disable_rez_1_compatibility \
                        or config.error_version_mismatch:
                    raise SchemaError(None, msg)
                elif config.warn("version_mismatch"):
                    print_warning_once("%s: %s" % (self.path, msg))
        else:
            msg = "version must be a string"
            if config.disable_rez_1_compatibility \
                    or config.error_nonstring_version:
                raise SchemaError(None, msg)
            elif config.warn("nonstring_version"):
                print_warning_once("%s: %s" % (self.path, msg))
        return Version(version_str)

    @propertycache
    def schema(self):
        schema = super(VersionedPackageResource, self).schema
        return _updated_schema(schema,
                               [(Required('version'),
                                 Use(self.convert_version))])


class VersionedVariantResource(BaseVariantResource):
    """A variant within a `VersionedPackageResource`."""
    key = 'variant.versioned'
    parent_resource = VersionedPackageResource
    variable_keys = ["index"]
    sub_resource = True
    schema = None
    versioned = True


class CombinedPackageFamilyResource(BasePackageResource):
    """A single file containing multiple versioned packages.

    A combined package consists of a single file and thus does not have a
    directory in which to put package resources.
    """
    key = 'package_family.combined'
    path_pattern = '{name}.{ext}'
    parent_resource = PackagesRoot
    variable_keys = ["name", "ext"]
    variable_regex = dict(name=PACKAGE_NAME_REGSTR,
                          ext=_or_regex(metadata_loaders.keys()))

    @propertycache
    def schema(self):
        schema = super(CombinedPackageFamilyResource, self).schema
        return _updated_schema(
            schema,
            [(Optional('versions'), [Use(Version)]),
             (Optional('version_overrides'), {
                Use(VersionRange): {
                    Optional('help'):                   Or(basestring,
                                                           [[basestring]]),
                    Optional('tools'):                  [basestring],
                    Optional('requires'):               [Use(Requirement)],
                    Optional('build_requires'):         [Use(Requirement)],
                    Optional('private_build_requires'): [Use(Requirement)],
                    Optional('variants'):               [[Use(Requirement)]],
                    Optional('commands'):               Or(rex_command,
                                                           And([basestring],
                                                               Use(self.convert_to_rex))),
                    Optional('custom'):                 object,
                    Optional(basestring):               self.custom_key
                }
            })])


class CombinedPackageResource(BasePackageResource):
    """A versioned package that is contained within a
    `CombinedPackageFamilyResource`.
    """
    key = 'package.combined'
    sub_resource = True
    schema = None
    parent_resource = CombinedPackageFamilyResource
    variable_keys = ["version"]

    @Resource.cached
    def load(self):
        parent = self.parent_instance()
        parent_data = parent.load()
        data = parent_data.copy()
        version = Version(self.variables["version"])
        data["version"] = version
        versions = data.pop("versions", [Version()])
        if version not in versions:
            raise ResourceNotFoundError("version '%s' not present in %s"
                                        % (str(version), self.path))

        overrides = data.pop("version_overrides", {})
        for ver_range, doc in overrides.iteritems():
            if version in ver_range:
                deep_update(data, doc)
        return data

    @classmethod
    def iter_instances(cls, parent_resource):
        data = parent_resource.load()
        for version in data.get('versions', [Version()]):
            variables = parent_resource.variables.copy()
            variables['version'] = str(version)
            yield cls(parent_resource.path, variables)


# -----------------------------------------------------------------------------
# Developer Package Resources
# -----------------------------------------------------------------------------

class DeveloperPackagesRoot(ArbitraryPath):
    """Represents a path containing a developer package resource."""
    key = "folder.dev_packages_root"

    @classmethod
    def _contents_exception_type(cls):
        return PackageMetadataError


class DeveloperPackageResource(BasePackageResource):
    """A package that is created with the intention to release.

    A development package must be versioned.

    This resource belongs to its own resource hierarchy, because a development
    package has not yet been deployed and is stored in an arbitrary location in
    the filesystem (typically under a developer's home directory).
    """
    key = 'package.dev'
    path_pattern = 'package.{ext}'
    parent_resource = DeveloperPackagesRoot
    variable_keys = ["ext"]
    variable_regex = dict(ext=_or_regex(metadata_loaders.keys()))
    versioned = True

    @propertycache
    def schema(self):
        schema = super(DeveloperPackageResource, self).schema
        return _updated_schema(schema,
                               [(Required('name'), basestring),
                                (Required('version'), Use(Version)),
                                (Required('description'),
                                    And(basestring, Use(string.strip))),
                                (Required('authors'), [basestring]),
                                (Required('uuid'), basestring)])


class DeveloperVariantResource(BaseVariantResource):
    """A variant within a `DeveloperPackageResource`."""
    key = 'variant.dev'
    parent_resource = DeveloperPackageResource
    variable_keys = ["index"]
    sub_resource = True
    schema = None
    versioned = True


# -----------------------------------------------------------------------------
# Resource Registration
# -----------------------------------------------------------------------------

# -- deployed packages

register_resource(PackagesRoot)
register_resource(PackageFamilyFolder)
register_resource(PackageVersionFolder)
register_resource(VersionedPackageResource)
register_resource(VersionedVariantResource)
register_resource(VersionlessPackageResource)
register_resource(VersionlessVariantResource)
register_resource(ReleaseDataResource)
register_resource(CombinedPackageFamilyResource)
register_resource(CombinedPackageResource)
# deprecated
register_resource(MetadataFolder)
register_resource(ReleaseTimestampResource)
register_resource(ReleaseInfoResource)
register_resource(ChangelogResource)


# -- development packages

register_resource(DeveloperPackagesRoot)
register_resource(DeveloperPackageResource)
register_resource(DeveloperVariantResource)
