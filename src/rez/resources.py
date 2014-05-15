"""
Class for loading and verifying rez metafiles

Resources are an abstraction of rez's file and directory structure. Currently,
a resource can be a file or directory (with eventual support for other types).
A resource is given a hierarchical name and a file path pattern (like
"{name}/{version}/package.yaml") and are collected under a particular
configuration version.

If the resource is a file, an optional metadata schema can be provided to
validate the contents (e.g. enforce data types and document structure) of the
data. This validation is run after the data is deserialized, so it is decoupled
from the storage format. New resource formats can be added and share the same
validators.

The upshot is that once a resource is registered, instances of the resource can
be iterated over using `iter_resources` without the higher level code requiring
an understanding of the underlying file and folder structure.  This ensures that
the addition of new resources is localized to the registration functions
provided by this module.
"""
import os
import sys
import inspect
import re
from collections import defaultdict
from rez.settings import settings, Settings
from rez.util import to_posixpath, propertycache, Namespace
from rez.exceptions import PackageMetadataError, ResourceError
from rez.vendor.version.version import Version, VersionRange
from rez.vendor import yaml
# FIXME: handle this double-module business
from rez.vendor.schema.schema import Schema, Use, And, Or, Optional, SchemaError

_configs = defaultdict(list)

PACKAGE_NAME_REGSTR = '[a-zA-Z_][a-zA-Z0-9_]*'
VERSION_COMPONENT_REGSTR = '(?:[0-9a-zA-Z_]+)'
VERSION_REGSTR = '%(comp)s(?:[.]%(comp)s)*' % dict(comp=VERSION_COMPONENT_REGSTR)

#------------------------------------------------------------------------------
# Base Classes and Functions
#------------------------------------------------------------------------------

def _process_python_objects(data):
    """process special objects.

    Changes made:
      - functions with an `immediate` attribute that evaluates to True will be
        called immediately.
    """
    # FIXME: the `immediate` attribute is used to tell us if a function
    # should be executed immediately on load, but we need to work
    # out the exact syntax.  maybe a 'rex' attribute that conveys
    # the opposite meaning (i.e. defer execution until later) would be better.
    # We could also provide a @rex decorator to set the attribute.
    for k, v in data.iteritems():
        if inspect.isfunction(v) and getattr(v, 'immediate', False):
            data[k] = v()
        elif isinstance(v, dict):
            # because dicts are changed in place, we don't need to re-assign
            _process_python_objects(v)
    return data

def load_python(stream):
    """load a python module into a metadata dictionary.

    - module-level attributes become root entries in the dictionary.
    - module-level functions which take no arguments will be called immediately
        and the returned value will be stored in the dictionary

    Example:

        >>> load_python('''
        config_version = 0
        name = 'foo'
        def requires():
            return ['bar']''')

    Args:
        stream (string, open file object, or code object): stream of python
            code which will be passed to ``exec``

    Returns:
        dict: dictionary of non-private objects added to the globals
    """
    # TODO: support class-based design, where the attributes and methods of the
    # class become values in the dictionary
    g = __builtins__.copy()
    g['Namespace'] = Namespace
    exec stream in g
    result = {}
    for k, v in g.iteritems():
        if k != '__builtins__' and \
                (k not in __builtins__ or __builtins__[k] != v):
            result[k] = v
    # add in any namespaces used
    result.update(Namespace.get_namespace())
    result = _process_python_objects(result)
    return result

def load_yaml(stream):
    """load a yaml data into a metadata dictionary.

    Args:
        stream (string, or open file object): stream of text which will be
            passed to ``yaml.load``

    Returns:
        dict
    """

    if hasattr(stream, 'read'):
        text = stream.read()
    else:
        text = stream
    return yaml.load(text) or {}

# keep a simple dictionary of loaders for now
metadata_loaders = {}
metadata_loaders['py'] = load_python
metadata_loaders['yaml'] = load_yaml
# hack for info.txt. for now we force .txt to parse using yaml. this format
# will be going away
metadata_loaders['txt'] = metadata_loaders['yaml']

def get_file_loader(filename):
    scheme = os.path.splitext(filename)[1]
    try:
        return metadata_loaders[scheme]
    except KeyError:
        raise ResourceError("Unknown metadata storage scheme: %r" % scheme)

# FIXME: add lru_cache here?
def load_file(filename, loader=None):
    """Read metadata from a file.

    Determines the proper de-serialization scheme based on file extension.

    Args:
        filename (str): Path to the file from which to read metadata.
        loader (callable, optional): callable which will take an open file
            handle and return a metadata dictionary.
    Returns:
        dict: the metadata
    """
    if loader is None:
        loader = get_file_loader(filename)

    with open(filename, 'r') as f:
        try:
            return loader(f)
        except Exception as e:
            # FIXME: this stack fix is probably specific to `load_python` and
            # should be moved there.
            import traceback
            frames = traceback.extract_tb(sys.exc_traceback)
            while frames and frames[0][0] != filename:
                frames = frames[1:]
            stack = ''.join(traceback.format_list(frames)).strip()
            raise PackageMetadataError(filename, "%s\n%s" % (str(e), stack))


#------------------------------------------------------------------------------
# Resources and Configurations
#------------------------------------------------------------------------------

def register_resource(config_version, resource):
    """Register a `Resource` class.

    This informs rez where to find a resource relative to the
    rez search path, and optionally how to validate its data.

    Args:
        resource (Resource): the resource class.
    """
    version_configs = _configs[config_version]

    assert resource.key is not None, \
        "Resource must implement the 'key' attribute"
    # version_configs is a list and not a dict so that it stays ordered
    if resource.key in dict(version_configs):
        raise ResourceError("resource already exists: %r" % resource.key)

    version_configs.append((resource.key, resource))

def get_resource_by_key(config_version, key):
    """Get a `Resource` instance directly, using the name of the resource
    """
    config_resources = _configs.get(config_version)
    if config_resources:
        return dict(config_resources)[key]

def get_resource_by_filename(config_version, filename):
    """Get a `Resource` instance indirectly, by comparing a filename to a
    resource path pattern
    """
    config_resources = _configs.get(config_version)
    if config_resources:
        for resource_key, resource in config_resources:
                if resource.filename_is_match(filename):
                    return resource

def list_resource_keys(config_version):
    return [info['key'] for info in _configs[config_version]]

class ResourceIterator(object):
    """Iterates over all occurrences of a resource, given a path pattern such
    as '{name}/{version}/package.yaml'.

    For each item found, yields the path to the resource and a dictionary of
    any variables in the path pattern that were expanded.
    """
    def __init__(self, path_pattern, variables):
        self.path_pattern = path_pattern.rstrip('/')
        self.path_parts = self.path_pattern.split('/')
        self.variables = variables.copy()
        self.current_part = None
        self.next_part()

    def expand_part(self, part):
        """
        Path pattern will be split on directory separator, parts requiring
        non-constant expansion will be converted to regular expression, and
        parts with no expansion will remain string literals
        """
        for key, value in self.variables.iteritems():
            part = part.replace('{%s}' % key, '%s' % value)
        if '{' in part:
            return re.compile(Resource._expand_pattern(part))
        else:
            return part

    def copy(self):
        new = ResourceIterator(self.path_pattern, self.variables.copy())
        new.path_parts = self.path_parts[:]
        return new

    def next_part(self):
        try:
#             print self.path_pattern, "compiling:", self.path_parts[0]
            self.current_part = self.expand_part(self.path_parts.pop(0))
#             print self.path_pattern, "result:", self.current_part
        except IndexError:
            pass

    def is_final_part(self):
        return len(self.path_parts) == 0

    def list_matches(self, path):
        if isinstance(self.current_part, basestring):
            fullpath = os.path.join(path, self.current_part)
            # TODO: check file vs dir here
            if os.path.exists(fullpath):
                yield fullpath
        else:
            for name in os.listdir(path):
                match = self.current_part.match(name)
                if match:
                    # TODO: add match to variables
                    self.variables.update(match.groupdict())
                    yield os.path.join(path, name)

    def walk(self, root):
        for fullpath in self.list_matches(root):
            if self.is_final_part():
                yield fullpath, self.variables
            else:
                child = self.copy()
                child.next_part()
                for res in child.walk(fullpath):
                    yield res

def iter_resources(config_version, resource_keys, search_paths,
                   **expansion_variables):
    # convenience:
    for k, v in expansion_variables.items():
        if v is None:
            expansion_variables.pop(k)
    resources = [get_resource_by_key(config_version, key)
                 for key in resource_keys]
    for search_path in search_paths:
        for resource in resources:
            if resource.path_patterns:
                for pattern in resource.path_patterns:
                    it = ResourceIterator(pattern, expansion_variables)
                    for path, variables in it.walk(search_path):
                        yield resource(path, variables, search_path)

def load_resource(config_version, resource_keys, search_paths,
                  **expansion_variables):
    it = iter_resources(config_version, resource_keys, search_paths,
                        **expansion_variables)
    result = list(it)
    if not result:
        raise ResourceError("Could not find resource")
    if len(result) != 1:
        raise ResourceError("Found more than one matching resource")
    return result[0].load()

#------------------------------------------------------------------------------
# MetadataSchema Implementations
#------------------------------------------------------------------------------
# TODO: check for valid package names
# (or do we want to defer to the package class?)

# 'name'
package_name = basestring

# 'name-1.2'
package_requirement = basestring

# TODO: inspect arguments of the function to confirm proper number?
rex_command = Or(callable,     # python function
                 basestring,   # new-style rex
                 )

# make an alias which just so happens to be the same number of characters as
# 'Optional'  so that our schema are easier to read
Required = Schema

# The master package schema.  All resources delivering metadata to the Package
# class must validate against this master schema
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
    Optional('requires'):               [package_requirement],
    Optional('build_requires'):         [package_requirement],
    Optional('private_build_requires'): [package_requirement],
    Optional('variants'):               [[package_requirement]],
    Optional('commands'):               rex_command
})

class Resource(object):
    """Stores data regarding a particular resource.

    This includes its name, where it should exist on disk, and how to validate
    its metadata.
    """
    key = None
    schema = None
    path_patterns = None

    def __init__(self, path, variables, search_path=None):
        super(Resource, self).__init__()
        # the search path is here so that we can load sub-resources
        if search_path:
            self.search_path = [search_path]
        else:
            self.search_path = settings.packages_path

        self.path = path
        self.variables = variables

    def __repr__(self):
        return "%s(%r, %r)" % (self.__class__.__name__, self.path,
                               self.variables)

    @staticmethod
    def _expand_pattern(pattern):
        "expand variables in a search pattern with regular expressions"
        pattern = re.escape(pattern)
        expansions = [('version', VERSION_REGSTR),
                      ('name', PACKAGE_NAME_REGSTR),
                      ('search_path', '|'.join('(%s)' % p
                       for p in settings.packages_path))]
        for key, value in expansions:
            pattern = pattern.replace(r'\{%s\}' % key,
                                      '(?P<%s>%s)' % (key, value))
        return pattern + '$'

    def filename_is_match(cls, filename):
        "test if `filename` matches the resource's `path_patterns`"
        if not cls.path_pattern:
            return False
        if not hasattr(cls, '_compiled_pattern'):
            patterns = cls.path_patterns
            if isinstance(patterns, basestring):
                patterns = [patterns]

            patterns = [('/' + p) if not p.startswith('/') else p
                        for p in patterns]

            pattern = '|'.join('(%s)' % cls._expand_pattern(p)
                               for p in patterns)
            cls._compiled_pattern = re.compile(pattern)
        return cls._compiled_pattern.search(to_posixpath(filename))

    def load(self):
        """load the resource data.

        For a file this means use `load_file` to deserialize the data, and then
        validate it against the `Schema` instance provided by the resource's
        `schema` attribute.

        This gives the resource a chance to do further modifications to the
        loaded metadata (beyond what is possible or practical to do with the
        schema), for example, changing the name of keys, or grafting on data
        loaded from other reources.
        """
        if os.path.isfile(self.path):
            data = load_file(self.path)
            if self.schema:
                try:
                    return self.schema.validate(data)
                except SchemaError, err:
                    raise PackageMetadataError(self.path, str(err))
            else:
                return data

class ReleaseTimestampResource(Resource):
    # Deprecated
    key = 'release.timestamp'
    path_patterns = ['{name}/{version}/.metadata/release_time.txt']
    schema = Use(int)

class ReleaseInfoResource(Resource):
    # Deprecated
    key = 'release.info'
    path_patterns = ['{name}/{version}/.metadata/info.txt']
    schema = Schema({
        Required('ACTUAL_BUILD_TIME'): int,
        Required('BUILD_TIME'): int,
        Required('USER'): basestring,
        Optional('SVN'): basestring
    })

class ReleaseResource(Resource):
    key = 'release.data'
    path_patterns = ['{name}/{version}/release.yaml']
    schema = Schema({
        Required('timestamp'): int,
        Required('revision'): basestring,
        Required('changelog'): basestring,
        Required('release_message'): basestring,
        Required('previous_version'): basestring,
        Required('previous_revision'): basestring
    })

class VersionlessPackageResource(Resource):
    """
    The standard set of package metadata
    """
    key = 'package.versionless'
    # TODO: look into creating an {ext} token
    path_patterns = ['{name}/package.yaml', '{name}/package.py']

    def convert_to_rex(self, commands):
        from rez.util import convert_old_commands, print_warning_once
        if settings.warn("old_commands"):
            print_warning_once("%s is using old-style commands."
                               % self.path)

        return convert_old_commands(commands)

    @propertycache
    def schema(self):
        return Schema({
            Required('config_version'):         0,  # this will only match 0
            Optional('uuid'):                   basestring,
            Optional('description'):            basestring,
            Required('name'):                   self.variables['name'],
            Optional('authors'):                [basestring],
            Optional('config'):                 And(dict,
                                                    Use(lambda x:
                                                        Settings(overrides=x))),
            Optional('help'):                   Or(basestring,
                                                   [[basestring]]),
            Optional('requires'):               [package_requirement],
            Optional('build_requires'):         [package_requirement],
            Optional('private_build_requires'): [package_requirement],
            Optional('variants'):               [[package_requirement]],
            Optional('commands'):               Or(rex_command,
                                                   And([basestring],
                                                       Use(self.convert_to_rex)))
        })

    def load(self):
        data = super(VersionlessPackageResource, self).load()
        try:
            release_data = load_resource(0, 'release.data',
                                         [self.search_path], **self.variables)
            timestamp = release_data.get('timestamp', 0)
        except ResourceError:
            timestamp = load_resource(0, 'release.timestamp',
                                      [self.search_path], **self.variables)
        data['timestamp'] = timestamp
        data['version'] = Version()
        # # TODO: handle warning.  should we deal is_local here or in rez.packages?
        # if (not timestamp) and (not self.is_local) and settings.warn("untimestamped"):
        #     print_warning_once("Package is not timestamped: %s" % str(self))

        return data

class VersionedPackageResource(VersionlessPackageResource):
    key = 'package.versioned'
    path_patterns = ['{name}/{version}/package.yaml',
                     '{name}/{version}/package.py']

    @propertycache
    def schema(self):
        schema = super(VersionedPackageResource, self).schema._schema
        schema = schema.copy()
        schema.update({
            Required('version'): And(self.variables['version'],
                                     Use(Version))
        })
        return Schema(schema)

class PackageFamilyResource(Resource):
    key = 'package_family.folder'
    path_patterns = ['{name}/']

class ExternalPackageFamilyResource(VersionlessPackageResource):
    """
    A single package containing settings for multiple versions.

    An external package does not have a directory in which to put package
    resources.
    """
    key = 'package_family.external'
    path_patterns = ['{name}.yaml', '{name}.py']

    @propertycache
    def schema(self):
        schema = super(ExternalPackageFamilyResource, self).schema._schema
        schema = schema.copy()
        schema.update({
            Optional('versions'): [Use(Version)],
            Optional('version_overrides'): {
                Use(VersionRange): {
                    Optional('help'):                   Or(basestring,
                                                           [[basestring]]),
                    Optional('requires'):               [package_requirement],
                    Optional('build_requires'):         [package_requirement],
                    Optional('private_build_requires'): [package_requirement],
                    Optional('variants'):               [[package_requirement]],
                    Optional('commands'):               Or(rex_command,
                                                           And([basestring],
                                                               Use(self.convert_to_rex)))
                }
            }
        })
        return Schema(schema)

    def load(self):
        # do not use super because VersionlessPackageResource loads the
        # the timestamp from file
        data = Resource.load(self)

        # convert 'versions' from a list of `Version` to a list of complete
        # package data
        versions = data.pop('versions', [])
        overrides = self.metadata.pop('version_overrides', {})
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

class BuiltPackageResource(VersionedPackageResource):
    """A package that is built with the intention to release.

    Same as `VersionedPackageResource`, but stricter about the existence of
    certain metadata.
    """
    key = 'package.built'

    @property
    def schema(self):
        schema = super(BuiltPackageResource, self).schema._schema
        # we only need to copy here if we change property to propertycache
        # schema = schema.copy()
        # swap optional to required:
        for key, value in schema.iteritems():
            if key._schema in ('uuid', 'description', 'authors'):
                newkey = Required(key._schema)
                schema[newkey] = schema.pop(key)
        return Schema(schema)

register_resource(0, VersionedPackageResource)

register_resource(0, VersionlessPackageResource)

register_resource(0, BuiltPackageResource)

register_resource(0, ReleaseInfoResource)

register_resource(0, ReleaseTimestampResource)

register_resource(0, PackageFamilyResource)

register_resource(0, ExternalPackageFamilyResource)

#------------------------------------------------------------------------------
# Main Entry Point
#------------------------------------------------------------------------------

def load_metadata(filename, variables, resource_key=None, min_config_version=0,
                  force_config_version=None):
    """Return the metadata stored in a file and validate it against a metadata
    configuration.

    Args:
        filename (str): path to the file from which to load the metadata
        resource_key (str, optional): explicitly set the resource used to
            validate the loaded metadata instead of trying to determine it from
            `filename`
        min_config_version (int, optional): the minimum config version required
        force_config_version (int, optional): used for legacy config files that
            do not store a configuration version
    """
    # metadata = load_file(filename)
    # if isinstance(metadata, list):
    #     config_version = metadata[0].get('config_version', None)
    # elif isinstance(metadata, dict):
    #     config_version = metadata.get('config_version', None)
    # else:
    #     raise MetadataError("Unknown type at metadata root")

    # if config_version is None:
    #     if force_config_version is not None:
    #         config_version = force_config_version
    #     else:
    #         raise MetadataKeyError(filename, 'config_version')
    # else:
    #     if config_version < min_config_version:
    #         raise MetadataError('configuration version %d '
    #                             'is less than minimum requested: %d' % (config_version,
    #                                                                     min_config_version))

    # FIXME:!!!
    config_version = 0

    if resource_key:
        resource = get_resource_by_key(config_version, resource_key)
    else:
        resource = get_resource_by_filename(config_version, filename)

    if resource is None:
        raise MetadataValueError(filename, 'config_version', config_version)

    return resource(filename, variables).load()


#    Copyright 2008-2012 Dr D Studios Pty Limited (ACN 127 184 954) (Dr. D Studios)
#
#    This file is part of Rez.
#
#    Rez is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Rez is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public License
#    along with Rez.  If not, see <http://www.gnu.org/licenses/>.
