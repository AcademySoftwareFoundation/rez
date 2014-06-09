from rez.resources import _or_regex, _updated_schema, register_resource, \
	Resource, SearchPath, ArbitraryPath, FolderResource, FileResource, \
	Required, metadata_loaders, load_resource
from rez.settings import settings, Settings
from rez.exceptions import ResourceError
from rez.util import propertycache
from rez.vendor.schema.schema import Schema, Use, And, Or, Optional
from rez.vendor.version.version import Version, VersionRange
from rez.vendor.version.requirement import Requirement
import string
import re


PACKAGE_NAME_REGSTR = '[a-zA-Z_][a-zA-Z0-9_]*'
VERSION_COMPONENT_REGSTR = '(?:[0-9a-zA-Z_]+)'
VERSION_REGSTR = '%(comp)s(?:[.-]%(comp)s)*' % dict(comp=VERSION_COMPONENT_REGSTR)
UUID_REGEX = re.compile("^[a-f0-9]{8}-?[a-f0-9]{4}-?[a-f0-9]{4}-?[a-f0-9]{4}-?[a-f0-9]{12}\Z")


#------------------------------------------------------------------------------
# MetadataSchema Implementations
#------------------------------------------------------------------------------

# TODO: inspect arguments of the function to confirm proper number?
rex_command = Or(callable,     # python function
                 basestring,   # new-style rex
                 )

def is_uuid(s):
    if not UUID_REGEX.match(s):
        import uuid
        u = uuid.uuid4()
        raise ValueError("Not a valid identifier. Try: '%s'" % u.hex)
    return True

# The master package schema.  All resources delivering metadata to the Package
# class must ultimately validate against this master schema. This schema
# intentionally does no casting of types: that should happen on the resource
# schemas.
# TODO should this be here? It's only used in packages.py
"""
package_schema = Schema({
    Required('config_version'):         int,
    Optional('uuid'):                   basestring,
    Optional('description'):            basestring,
    Required('name'):                   basestring,
    Required('version'):                Version,
    Optional('authors'):                [basestring],
    Required('timestamp'):              int,
    Optional('config'):                 Settings,
    Optional('help'):                   Or(basestring,
                                           [[basestring]]),
    Optional('tools'):                  [basestring],
    Optional('requires'):               [package_requirement],
    Optional('build_requires'):         [package_requirement],
    Optional('private_build_requires'): [package_requirement],
    Optional('variants'):               [[package_requirement]],
    Optional('commands'):               rex_command,
    # swap-comment these 2 lines if we decide to allow arbitrary root metadata
    Optional('custom'):                 object,
    # Optional(object):                   object
})
"""


#------------------------------------------------------------------------------
# Package Resources
#------------------------------------------------------------------------------

class PackagesRoot(SearchPath):
    """Represents a package searchpath, typically in Settings.packages_path."""
    key = 'folder.packages_root'

    @classmethod
    def _default_search_paths(cls, path=None):
        return settings.packages_path


class NameFolder(FolderResource):
    """Represents a folder with the name of a package."""
    key = 'folder.name'
    path_pattern = '{name}'
    parent_resource = PackagesRoot
    variable_keys = ["name"]
    variable_regex = dict(name=PACKAGE_NAME_REGSTR)


class VersionFolder(FolderResource):
    """Represents a folder whos name is the version of a package."""
    key = 'folder.version'
    path_pattern = '{version}'
    parent_resource = NameFolder
    variable_keys = ["version"]
    variable_regex = dict(version=VERSION_REGSTR)


# -- deprecated

class MetadataFolder(FolderResource):
    key = 'folder.metadata'
    path_pattern = '.metadata'
    parent_resource = VersionFolder


class ReleaseTimestampResource(FileResource):
    # Deprecated
    key = 'release.timestamp'
    path_pattern = 'release_time.txt'
    parent_resource = MetadataFolder
    schema = Use(int)


class ReleaseInfoResource(FileResource):
    # Deprecated
    key = 'release.info'
    path_pattern = 'info.txt'
    parent_resource = MetadataFolder
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
    parent_resource = VersionFolder

    schema = Schema({
        Required('timestamp'): int,
        Required('revision'): object,
        Required('changelog'): basestring,
        Required('release_message'): basestring,
        Optional('previous_version'): Use(Version),
        Optional('previous_revision'): object
    })


class BasePackageResource(FileResource):
    """Abstract class providing the standard set of package metadata.
    """
    def convert_to_rex(self, commands):
        from rez.util import convert_old_commands, print_warning_once
        if settings.warn("old_commands"):
            print_warning_once("%s is using old-style commands." % self.path)
        return convert_old_commands(commands)

    @propertycache
    def schema(self):
        return Schema({
            Required('config_version'):         0,  # this will only match 0
            Optional('uuid'):                   is_uuid,
            Optional('description'):            And(basestring,
                                                    Use(string.strip)),
            Required('name'):                   self.variables.get('name'),
            Optional('authors'):                [basestring],
            Optional('config'):                 And(dict,
                                                    Use(lambda x:
                                                        Settings(overrides=x))),
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
            # swap-comment these 2 lines if we decide to allow arbitrary root metadata
            Optional('custom'):                 object,
            # basestring: object
        })

    # TODO deprecate, will move into VariantResource
    def load_timestamp(self):
        timestamp = 0
        try:
            release_data = load_resource(
                0,
                resource_keys='release.data',
                search_path=self.variables['search_path'],
                variables=self.variables)
            timestamp = release_data.get('timestamp', 0)
        except ResourceError:
            try:
                timestamp = load_resource(
                    0,
                    resource_keys='release.timestamp',
                    search_path=self.variables['search_path'],
                    variables=self.variables)
            except ResourceError:
                pass
        if not timestamp:
            # FIXME: should we deal with is_local here or in rez.packages?
            if not timestamp and settings.warn("untimestamped"):
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

        # TODO we need to move away from indexes
        idx = self.variables["index"]
        if idx is not None:
            try:
                requires = data.get("requires", []) + variants[idx]
                data["requires"] = requires
            except IndexError:
                raise ResourceError("variant not found in parent package "
                                    "resource")
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
    parent_resource = NameFolder
    variable_keys = ["ext"]
    variable_regex = dict(ext=_or_regex(metadata_loaders.keys()))

    @Resource.cached
    def load(self):
        data = super(VersionlessPackageResource, self).load().copy()
        data['timestamp'] = self.load_timestamp()
        data['version'] = Version()
        return data


class VersionlessVariantResource(BaseVariantResource):
    """A variant within a `VersionlessPackageResource`."""
    key = 'variant.versionless'
    parent_resource = VersionlessPackageResource
    variable_keys = ["index"]
    sub_resource = True
    schema = None


class VersionedPackageResource(BasePackageResource):
    """A versioned package from a single file."""
    key = 'package.versioned'
    path_pattern = 'package.{ext}'
    parent_resource = VersionFolder
    variable_keys = ["ext"]
    variable_regex = dict(ext=_or_regex(metadata_loaders.keys()))

    @propertycache
    def schema(self):
        schema = super(VersionedPackageResource, self).schema
        return _updated_schema(schema,
            [(Required('version'), 
                And(self.variables['version'], Use(Version)))])

    @Resource.cached
    def load(self):
        data = super(VersionedPackageResource, self).load().copy()
        data['timestamp'] = self.load_timestamp()
        return data


class VersionedVariantResource(BaseVariantResource):
    """A variant within a `VersionedPackageResource`."""
    key = 'variant.versioned'
    parent_resource = VersionedPackageResource
    variable_keys = ["index"]
    sub_resource = True
    schema = None


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
        return _updated_schema(schema,
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
                    # swap-comment these 2 lines if we decide to allow arbitrary root metadata
                    Optional('custom'):                 object,
                    # basestring:                         object
                }
            })])
	
	# TODO delete this, it's going to cause NVARIANT* storage of each package
	# in the cache, which won't even get used
    @Resource.cached
    def load(self):
        data = super(CombinedPackageFamilyResource, self).load().copy()
        # convert 'versions' from a list of `Version` to a list of complete
        # package data
        versions = data.pop('versions', [Version()])
        overrides = data.pop('version_overrides', {})
        if versions:
            new_versions = []
            for version in versions:
                # FIXME: order matters here: use OrderedDict or make
                # version_overrides a list instead of a dict?
                ver_data = data.copy()
                for ver_range in sorted(overrides.keys()):
                    if version in ver_range:
                        ver_data.update(overrides[ver_range])
                        break
                ver_data['version'] = version
                new_versions.append(ver_data)

            data['versions'] = new_versions
        return data


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
        data = parent.load()
        this_version = Version(self.variables["version"])
        for ver_data in data['versions']:
            if ver_data['version'] == this_version:
                return ver_data

        raise ResourceError("resource couldn't find itself in parent "
                            "resource data")

    @classmethod
    def iter_instances(cls, parent_resource):
        data = parent_resource.load()
        for ver_data in data['versions']:
            variables = parent_resource.variables.copy()
            variables['version'] = str(ver_data['version'])
            yield cls(parent_resource.path, variables)


#------------------------------------------------------------------------------
# Developer Package Resources
#------------------------------------------------------------------------------

class DeveloperPackagesRoot(ArbitraryPath):
    """Represents a path containing a developer package resource."""
    key = "folder.dev_packages_root"
    pass


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

    @propertycache
    def schema(self):
        schema = super(DeveloperPackageResource, self).schema
        return _updated_schema(schema,
                               [(Required('name'), basestring),
                                (Required('version'), Use(Version)),
                                (Required('description'), And(basestring,
                                                            Use(string.strip))),
                                (Required('authors'), [basestring]),
                                (Required('uuid'), is_uuid)])


class DeveloperVariantResource(BaseVariantResource):
    """A variant within a `DeveloperPackageResource`."""
    key = 'variant.dev'
    parent_resource = DeveloperPackageResource
    variable_keys = ["index"]
    sub_resource = True
    schema = None


#------------------------------------------------------------------------------
# Resource Registration
#------------------------------------------------------------------------------

# -- deployed packages

register_resource(0, PackagesRoot)

register_resource(0, NameFolder)

register_resource(0, VersionFolder)

register_resource(0, VersionedPackageResource)

register_resource(0, VersionedVariantResource)

register_resource(0, VersionlessPackageResource)

register_resource(0, VersionlessVariantResource)

register_resource(0, ReleaseInfoResource)

register_resource(0, ReleaseTimestampResource)

register_resource(0, ReleaseDataResource)

register_resource(0, CombinedPackageFamilyResource)

register_resource(0, CombinedPackageResource)


# -- development packages

register_resource(0, DeveloperPackagesRoot)

register_resource(0, DeveloperPackageResource)

register_resource(0, DeveloperVariantResource)
