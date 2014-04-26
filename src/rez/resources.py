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
# TODO: look into using schema.py (https://github.com/halst/schema) which is pretty
# similar to MetadataSchema class below, but is more fully-featured.
# I think the additional features could help consolidate some concepts within
# this module:
# Currently we use schemas to describe the contents of files, and we use the
# concept of a 'path pattern' to define where we will find that file
# in our directory tree.  I would like to investigate treating the directory
# structure itself as a schema, with file schemas nested within it.
#
# Two other schema validation libraries are jsonschema and pykwalify. The former
# is generic enough to validate yaml data, but might be a stretch to validate
# data coming from python files (callables, for example) and the latter supports
# both json and yaml, but we'd have to port pykwalify from python 3.x to 2.x.

from __future__ import with_statement
import yaml
import os
import sys
import inspect
import re
from collections import defaultdict
from schema import Schema, Use, And, Or, Optional
from rez.settings import settings, Settings
from rez.util import to_posixpath
from rez.exceptions import PkgMetadataError
from rez.versions import ExactVersion, VersionRange

_configs = defaultdict(list)


#------------------------------------------------------------------------------
# Exceptions
#------------------------------------------------------------------------------

class MetadataError(Exception):
    pass

class MetadataKeyError(MetadataError, KeyError):
    def __init__(self, filename, entry_id):
        self.filename = filename
        self.entry_id = entry_id

    def __str__(self):
        return "%s: missing required entry %s" % (self.filename, self.entry_id)

class MetadataTypeError(MetadataError, TypeError):
    def __init__(self, filename, entry_id, expected_type, actual_type):
        self.filename = filename
        self.entry_id = entry_id
        self.expected_type = expected_type
        self.actual_type = actual_type

    def __str__(self):
        return ("'%s': entry %r has incorrect data type: "
                "expected %s. got %s" % (self.filename, self.entry_id,
                                         self.expected_type.__name__,
                                         self.actual_type.__name__))

class MetadataValueError(MetadataError, ValueError):
    def __init__(self, filename, entry_id, value):
        self.filename = filename
        self.entry_id = entry_id
        self.value = value

    def __str__(self):
        return ("'%s': entry %r has invalid value: %r" % (self.filename,
                                                          self.entry_id,
                                                          self.value))

class MetadataUpdate(object):
    def __init__(self, old_value, new_value):
        self.old_value = old_value
        self.new_value = new_value

#------------------------------------------------------------------------------
# Internal Utilities
#------------------------------------------------------------------------------

def update_copy(source, updates):
    """Returns a copy of source_dict, updated with the new key-value
       pairs in diffs."""
    result = dict(source)
    result.update(updates)
    return result

class AttrDictYamlLoader(yaml.Loader):
    """
    A YAML loader that loads mappings into attribute dictionaries.
    """

    def __init__(self, *args, **kwargs):
        yaml.Loader.__init__(self, *args, **kwargs)

        self.add_constructor(u'tag:yaml.org,2002:map', type(self).construct_yaml_map)

    def construct_yaml_map(self, node):
        from rez.util import AttrDict
        data = AttrDict()
        yield data
        value = self.construct_mapping(node)
        data.update(value)

#------------------------------------------------------------------------------
# Base Classes and Functions
#------------------------------------------------------------------------------

def load_python(stream):
    """
    load a python module into a metadata dictionary

    - module-level attributes become root entries in the dictionary.
    - module-level functions which take no arguments will be called immediately
        and the returned value will be stored in the dictionary

    for example::

        config_version = 0
        name = 'foo'
        def requires():
            return ['bar']
    """
    # TODO: support class-based design, where the attributes and methods of the
    # class become values in the dictionary
    g = __builtins__.copy()
    exec stream in g
    result = {}
    for k, v in g.iteritems():
        if k != '__builtins__' and (k not in __builtins__ or __builtins__[k] != v):
            # module-level functions which take no arguments will be called immediately
            # FIXME: the immediate attribute is used to tell us if a function
            # should be deferred or executed immediately, but we need to work
            # out the exact syntax.  maybe a 'rex' attribute that conveys
            # the opposite meaning would be better along with a @rex decorator
            # to set the attribute.
            if inspect.isfunction(v) and getattr(v, 'immediate', False):
                v = v()
            result[k] = v
    return result

def load_yaml(stream):
    if hasattr(stream, 'read'):
        text = stream.read()
    else:
        text = stream
    try:
        return yaml.load(text) or {}
    except yaml.composer.ComposerError, err:
        if err.context == 'expected a single document in the stream':
            # automatically switch to multi-doc
            return list(yaml.load_all(text))
        raise

# keep a simple dictionary of loaders for now
metadata_loaders = {}
metadata_loaders['py'] = load_python
metadata_loaders['yaml'] = load_yaml
# hack for info.txt. for now we force .txt to parse using yaml. this format
# will be going away
metadata_loaders['txt'] = metadata_loaders['yaml']

def load(stream, scheme):
    """Read the metadata from a stream.

    Args:
        scheme: str: The serialization scheme to apply.

    Returns:
        The metadata, as a dict.
    """
    try:
        loader = metadata_loaders[scheme]
    except KeyError:
        raise MetadataError("Unknown metadata storage scheme: %r" % scheme)

    return loader(stream)

def load_file(filename):
    """Read metadata from a file.

    Determines the proper de-serialization scheme based on file extension.

    Args:
        filename: Path to the file from which to read metadata.

    Returns:
        The metadata, as a dict.
    """
    ext = os.path.splitext(filename)[1]
    with open(filename, 'r') as f:
        try:
            return load(f, ext.strip('.'))
        except Exception as e:
            import traceback
            frames = traceback.extract_tb(sys.exc_traceback)
            while frames and frames[0][0] != filename:
                frames = frames[1:]
            stack = ''.join(traceback.format_list(frames)).strip()
            raise PkgMetadataError(filename, "%s\n%s" % (str(e), stack))

def get_package_file(parent_path):
    """Return the path to package.yaml etc found under given path, or None."""
    for file in ("package.yaml", "package.py"):
        path = os.path.join(parent_path, file)
        if os.path.isfile(path):
            return path
    return None

def load_package_metadata(parent_path):
    """Load the metadata file found under parent_path.

    Returns:
        A metadata dict, or None if no package definition file found.
    """
    file = get_package_file(parent_path)
    if file:
        return (load_file(file), file)
    else:
        raise PkgMetadataError("No package definition file found in %s" % parent_path)

def load_package_settings(metadata):
    """Return rezconfig settings for this pkg (pkgs can override settings)."""
    return Settings(metadata["rezconfig"]) if "rezconfig" in metadata else settings


#------------------------------------------------------------------------------
# Resources and Configurations
#------------------------------------------------------------------------------

class ResourceInfo(object):
    """
    Stores data regarding a particular resource, including its name, where it
    should exist on disk, and how to validate its metadata.
    """
    def __init__(self, name, path_pattern=None, metadata_schemas=None):
        self.name = name
        if metadata_schemas:
            if not isinstance(metadata_schemas, list):
                metadata_schemas = [metadata_schemas]
            for i, schema in enumerate(metadata_schemas):
                if not isinstance(schema, Schema):
                    metadata_schemas[i] = Schema(schema)
        else:
            metadata_schemas = []
        self.metadata_schemas = metadata_schemas
        if path_pattern:
            self.is_dir = path_pattern.endswith('/')
            self.path_pattern = path_pattern.rstrip('/')
        else:
            self.is_dir = False
            self.path_pattern = None
        self._compiled_pattern = None

    def __repr__(self):
        return "%s(%r, %r)" % (self.__class__.__name__, self.metadata_schemas,
                               self.path_pattern)

    @staticmethod
    def _expand_pattern(pattern):
        "expand variables in a search pattern with regular expressions"
        import versions
        import packages

        pattern = re.escape(pattern)
        expansions = [('version', versions.EXACT_VERSION_REGSTR),
                      ('name', packages.PACKAGE_NAME_REGSTR),
                      ('search_path', '|'.join('(%s)' % p for p in settings.packages_path))]
        for key, value in expansions:
            pattern = pattern.replace(r'\{%s\}' % key, '(?P<%s>%s)' % (key, value))
        return pattern + '$'

    def filename_is_match(self, filename):
        "test if filename matches the configuration's path pattern"
        if not self.path_pattern:
            return False
        if self._compiled_pattern:
            regex = self._compiled_pattern
        else:
            pattern = self.path_pattern
            if not pattern.startswith('/'):
                pattern = '/' + self.path_pattern
            regex = re.compile(self._expand_pattern(pattern))
            self._compiled_pattern = regex
        return regex.search(to_posixpath(filename))

def register_resource(config_version, resource_key, path_patterns=None,
                      metadata_schemas=None):
    """
    register a resource. this informs rez where to find it relative to the
    rez search path, and optionally how to validate its data.

    resource_key : str
        unique name used to identify the resource. when retrieving metadata from
        a file, the resource type can be automatically determined from the
        optional path string, or explicitly using the resource_key.
    path_patterns : str or list of str
        a string pattern identifying where the resource file resides relative to
        the rez search path
    metadata_schemas : Schema class or list of Schema classes
        used to validate metadata
    """
    version_configs = _configs[config_version]

    # version_configs is a list and not a dict so that it stays ordered
    if resource_key in dict(version_configs):
        raise MetadataError("resource already exists: %r" % resource_key)

    if path_patterns:
        if isinstance(path_patterns, basestring):
            path_patterns = [path_patterns]
        resources = [ResourceInfo(resource_key, path, metadata_schemas) for path in path_patterns]
    else:
        resources = [ResourceInfo(resource_key, metadata_schemas=metadata_schemas)]
    version_configs.append((resource_key, resources))

def get_resources(config_version, key=None):
    """
    Get a list of ResourceInfo instances.
    """
    config_resources = _configs.get(config_version)
    if config_resources:
        if key:
            if isinstance(key, basestring):
                keys = set([key])
            else:
                keys = set(key)
        # narrow the search
        result = []
        for resource_key, resources in config_resources:
            if not key or resource_key in keys:
                result.extend(resources)
        return result

def get_metadata_schemas(config_version, filename, key=None):
    """
    find any resources whose path pattern matches the given filename and yield
    a list of MetadataSchema instances.
    """
    resources = get_resources(config_version, key)
    if resources is None:
        raise MetadataValueError(filename, 'config_version', config_version)

    for resource in resources:
        if (key and not resource.path_pattern) or resource.filename_is_match(filename):
            for cls in resource.metadata_schemas:
                yield cls(filename)

def list_resource_keys(config_version):
    return [info['key'] for info in _configs[config_version]]

class ResourceIterator(object):
    """
    Iterates over all occurrences of a resource, given a path pattern such as
    '{name}/{version}/package.yaml'.

    For each item found, yields the path to the resource and a dictionary of any
    variables in the path pattern that were expanded.
    """
    def __init__(self, path_pattern, variables):
        self.path_pattern = path_pattern
        self.path_parts = self.path_pattern.split('/')
        self.variables = variables.copy()
        self.current_part = None
        self.next_part()

    def expand_part(self, part):
        """
        Path pattern will be split on directory separator, parts requiring
        non-constant expansion will be converted to regular expression, and parts with no
        expansion will remain string literals
        """
        for key, value in self.variables.iteritems():
            part = part.replace('{%s}' % key, '%s' % value)
        if '{' in part:
            return re.compile(ResourceInfo._expand_pattern(part))
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
        import rez.memcached
        if isinstance(self.current_part, basestring):
            fullpath = os.path.join(path, self.current_part)
            # TODO: check file vs dir here
            if os.path.exists(fullpath):
                yield fullpath
        else:
            for name in rez.memcached.get_memcache().list_directory(path):
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

def iter_resources(config_version, resource_keys, search_paths, **expansion_variables):
    # convenience:
    for k, v in expansion_variables.items():
        if v is None:
            expansion_variables.pop(k)
    resources = get_resources(config_version, key=resource_keys)
    for search_path in search_paths:
        for resource in resources:
            if resource.path_pattern:
                pattern = ResourceIterator(resource.path_pattern, expansion_variables)
                for path, variables in pattern.walk(search_path):
                    yield path, variables, resource

#------------------------------------------------------------------------------
# MetadataSchema Implementations
#------------------------------------------------------------------------------
# TODO: check for valid package names (or do we want to defer to the package class?)

# 'name'
package_name = basestring

# 'name-1.2'
package_requirement = basestring

# 'Use' means cast to this type. If it fails to cast, then validation also fails
exact_version = Use(ExactVersion)

# TODO: inspect arguments of the function to confirm proper number?
rex_command = Or(callable,     # python function
                 basestring,   # new-style rex
                 [basestring]  # old-style rex
                               # to automatically convert to new-style we could replace with
                               #   And([basestring], Use(convert_old_commands))
                               # but would need to figure out how to get the package name/path for warning message)
                 )

# make an alias which just so happens to be the same number of characters as 'Optional'
# so that our schema are easier to read
Required = Schema


# FIXME: come up with something better than this. Seems like legacy a format.
# Why is the release_time in a different file than the release info?
# Does it store something meaningfully different than ACTUAL_BUILD_TIME and BUILD_TIME?
# Why isn't the name of the release metadata more informative than info.txt?
# Why does it assume SVN?
# Why is it all caps whereas other metadata files use lowercase?
# Why is it using .txt with custom parsing instead of YAML?
ReleaseInfo = {
    Required('ACTUAL_BUILD_TIME'): int,
    Required('BUILD_TIME'): int,
    Required('USER'): basestring,
    Optional('SVN'): basestring
}

# Base Package:
#    The standard set of metadata
BasePackageSchema_0 = {
    Required('config_version'): 0,  # this will only match 0
    Optional('uuid'):           basestring,
    Optional('description'):    basestring,
    Required('name'):           package_name,
    Optional('help'):           Or(basestring,
                                   [[basestring]]),
    Optional('authors'):        [basestring],
    Optional('requires'):       [package_requirement],
    Optional('build_requires'): [package_requirement],
    Optional('variants'):       [[package_requirement]],
    Optional('commands'):       rex_command
}

# Version Package:
#    Same as Base Package, but with a version
VersionPackageSchema_0 = BasePackageSchema_0.copy()
VersionPackageSchema_0.update({
    Required('version'): exact_version
})

# Built Package:
#    A package that is built with the intention to release.
#    Same as Version Package, but stricter about the existence of certain metadata
PackageBuildSchema_0 = VersionPackageSchema_0.copy()
# swap optional to required:
for key, value in PackageBuildSchema_0.iteritems():
    if key._schema in ('uuid', 'description', 'authors'):
        newkey = Required(key._schema)
        PackageBuildSchema_0[newkey] = PackageBuildSchema_0.pop(key)


# TODO: look into creating an {ext} token
register_resource(0,
                  'package.versioned',
                  ['{name}/{version}/package.yaml', '{name}/{version}/package.py'],
                  [VersionPackageSchema_0])

register_resource(0,
                  'package.versionless',
                  ['{name}/package.yaml', '{name}/package.py'],
                  [BasePackageSchema_0])

register_resource(0,
                  'package.built',
                  metadata_schemas=[PackageBuildSchema_0])

register_resource(0,
                  'release.info',
                  ['{name}/{version}/.metadata/info.txt'],
                  [ReleaseInfo])

register_resource(0,
                  'package_family.folder',
                  ['{name}/'])

# --- Experimenting with how to represent our directory tree as a Schema 
# 
# PackageVersionedFolderSchema = {
#     And(package_name, Use(PackageFamily)): {
#         exact_version: Or(File('package.yaml', VersionPackageSchema_0),
#                           File('package.py',)),
#     }
# }
# 
# {
#     Optional('package.py'): And(Use(PythonLoader), VersionPackageSchema_0),
#     Optional('package.yaml'): And(Use(YAMLLoader), VersionPackageSchema_0)
# }


# this actually works, but you must first cd to a directory with a package file
_test1 = And(
             Or('package.py', 'package.yaml'),  # confirm the file is properly named
             Use(load_file),                    # load the file
             VersionPackageSchema_0)            # validate its contents


# PackageVersionedFolderSchema = {
#     'folders' : {
#         package_name : Use(PackageFamily)
#         
#         : {
#         exact_version: Or(File('package.yaml', VersionPackageSchema_0),
#                           File('package.py',)),
#     }
#                                 Use(PythonLoader)
# }

#------------------------------------------------------------------------------
# Main Entry Point
#------------------------------------------------------------------------------

def load_metadata(filename, strip=False, resource_key=None, min_config_version=0,
                  force_config_version=None):
    """
    Return the metadata stored in a file and validate it against a metadata
    configuration.

    Parameters
    ----------
    filename : str
        path to the file from which to load the metadata
    resource_key : str or None
        if set, determine validation of the metadata based on this key instead
        of based on the file path
    min_config_version : int
        the minimum config version required
    force_config_version : int or None
        used for legacy config files that do not store a configuration version
    """
    metadata = load_file(filename)
    if isinstance(metadata, list):
        config_version = metadata[0].get('config_version', None)
    elif isinstance(metadata, dict):
        config_version = metadata.get('config_version', None)
    else:
        raise MetadataError("Unknown type at metadata root")

    if config_version is None:
        if force_config_version is not None:
            config_version = force_config_version
        else:
            raise MetadataKeyError(filename, 'config_version')
    else:
        if config_version < min_config_version:
            raise MetadataError('configuration version %d '
                                'is less than minimum requested: %d' % (config_version,
                                                                        min_config_version))

    errors = []
    for schema in get_metadata_schemas(config_version, filename, resource_key):
        try:
            schema.validate(metadata)
        except MetadataError, err:
            errors.append((schema, err))
            continue
#         if strip:
#             schema.strip(metadata)
        return metadata

    msg = "Could not find registered metadata configuration for %r" % filename
    for val, err in errors:
        msg += "\n%s: %s" % (val.__class__.__name__, str(err))
    raise MetadataError(msg)



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
