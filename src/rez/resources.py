"""
Class for loading and verifying rez metafiles

Resources are an abstraction of rez's file and directory structure. Currently,
a resource can be a file or directory (with eventual support for other types).
A resource is given a hierarchical name and a file path pattern (like
"{name}/{version}/package.yaml") and are collected under a particular
configuration version.

If the resource is a file, an optional metadata validator can be provided to
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
from rez.util import to_posixpath
from rez.exceptions import PkgMetadataError
from rez.contrib.version.version import Version
from rez.contrib import yaml

_configs = defaultdict(list)

PACKAGE_NAME_REGSTR = '[a-zA-Z_][a-zA-Z0-9_]*'
VERSION_COMPONENT_REGSTR = '(?:[0-9a-zA-Z_]+)'
VERSION_REGSTR = '%(comp)s(?:[.]%(comp)s)*' % dict(comp=VERSION_COMPONENT_REGSTR)


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
# Base Classes and Functions
#------------------------------------------------------------------------------

class MetadataLoader(object):
    def load(self):
        raise NotImplementedError

class PythonLoader(MetadataLoader):
    def load(self, stream):
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

class YAMLLoader(MetadataLoader):
    def load(self, stream):
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
metadata_loaders['py'] = PythonLoader()
metadata_loaders['yaml'] = YAMLLoader()
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

    return loader.load(stream)

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

# TODO move into PackageDefinition class
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

# TODO move into PackageDefinition class
def load_package_settings(metadata):
    """Return rezconfig settings for this pkg (pkgs can override settings)."""
    return Settings(overrides=metadata["rezconfig"]) \
        if "rezconfig" in metadata else settings


#------------------------------------------------------------------------------
# Resources and Configurations
#------------------------------------------------------------------------------

class ResourceInfo(object):
    """
    Stores data regarding a particular resource, including its name, where it
    should exist on disk, and how to validate its metadata.
    """
    def __init__(self, name, path_pattern=None, metadata_validators=None):
        self.name = name
        if metadata_validators:
            if not isinstance(metadata_validators, list):
                metadata_validators = [metadata_validators]
            for cls in metadata_validators:
                assert issubclass(cls, MetadataValidator)
        else:
            metadata_validators = []
        self.metadata_validators = metadata_validators
        if path_pattern:
            self.is_dir = path_pattern.endswith('/')
            self.path_pattern = path_pattern.rstrip('/')
        else:
            self.is_dir = False
            self.path_pattern = None
        self._compiled_pattern = None

    def __repr__(self):
        return "%s(%r, %r)" % (self.__class__.__name__, self.metadata_validators,
                               self.path_pattern)

    @staticmethod
    def _expand_pattern(pattern):
        "expand variables in a search pattern with regular expressions"
        import versions
        import packages

        pattern = re.escape(pattern)
        expansions = [('version', VERSION_REGSTR),
                      ('name', PACKAGE_NAME_REGSTR),
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
                      metadata_validators=None):
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
    metadata_validators : MetadataValidator class or list of MetadataValidator classes
        used to validate metadata
    """
    version_configs = _configs[config_version]

    # version_configs is a list and not a dict so that it stays ordered
    if resource_key in dict(version_configs):
        raise MetadataError("resource already exists: %r" % resource_key)

    if path_patterns:
        if isinstance(path_patterns, basestring):
            path_patterns = [path_patterns]
        resources = [ResourceInfo(resource_key, path, metadata_validators) for path in path_patterns]
    else:
        resources = [ResourceInfo(resource_key, metadata_validators=metadata_validators)]
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

def get_metadata_validators(config_version, filename, key=None):
    """
    find any resources whose path pattern matches the given filename and yield
    a list of MetadataValidator instances.
    """
    resources = get_resources(config_version, key)
    if resources is None:
        raise MetadataValueError(filename, 'config_version', config_version)

    for resource in resources:
        if (key and not resource.path_pattern) or resource.filename_is_match(filename):
            for cls in resource.metadata_validators:
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
# Base MetadataValidator
#------------------------------------------------------------------------------

class MetadataValidator(object):
    """
    The MetadataValidator class provides a means to validate the structure of hierarchical
    metadata.

    The STRUCTURE attribute defines a reference document which is compared
    against the metadata document passed to `validate()`. The reference document
    provided by the STRUCTURE attribute can either be a single document or a
    list of documents. If it is a list, the additional documents provide
    a subset of the original with alternate types for particular items.
    """
    REFERENCE = None
    # list of required nodes:
    REQUIRED = ()
    # list of optional nodes which should not be stripped
    # when producing lightweight copy:
    PROTECTED = ()

    _refdocs = None

    def __init__(self, filename):
        self.filename = filename

    @staticmethod
    def _get_map_id(parent_id, key):
        return (parent_id + '.' if parent_id else '') + key

    @staticmethod
    def _get_list_id(parent_id, i):
        return '%s[%s]' % (parent_id, i)

    @staticmethod
    def _id_match(id, match_id):
        if id == match_id:
            return True

        match_parts = re.findall('\[(\d*:\d*)\]', match_id)
        parts = re.findall('\[(\d+)\]', id)
        if not len(parts) or (len(parts) != len(match_parts)):
            return False
        for part, match_part in zip(parts, match_parts):
            i = int(part)
            start, stop = match_part.split(':')
            if start and i < int(start):
                return False
            if stop and i >= int(stop):
                return False
        return True

    def check_node(self, node, refnode, id=''):
        """
        check a node against the reference node. checks type and existence.
        """
        if isinstance(refnode, OneOf):
            for option in refnode.options:
                for res in self.check_node(node, option, id=id):
                    yield res
        else:
            if type(node) != type(refnode):
                if node is None:
                    yield (id, None)
                # disable this until we sort out how commands() works
#                 elif inspect.isfunction(node) and not any(inspect.getargspec(node)):
#                     new_node = node()
#                     yield (id, MetadataUpdate(node, new_node))
#                     for res in self.check_node(new_node, refnode, id=id):
#                         yield res
                elif type(refnode).__module__ != '__builtin__':
                    # refnode requested a custom type. we use this opportunity to attempt
                    # to cast node to this type.
                    try:
                        new_node = type(refnode)(node)
                    except:
                        yield (id, MetadataTypeError(self.filename, id, type(refnode), type(node)))
                    else:
                        yield (id, MetadataUpdate(node, new_node))
                        for res in self.check_node(new_node, refnode, id=id):
                            yield res
                else:
                    yield (id, MetadataTypeError(self.filename, id, type(refnode), type(node)))
            else:
                if isinstance(refnode, dict):
                    for key in refnode:
                        key_id = self._get_map_id(id, key)
                        if key in node.keys():
                            for res in self.check_node(node[key],
                                                       refnode[key],
                                                       id=key_id):
                                if isinstance(res[1], MetadataUpdate):
                                    node[key] = res[1].new_value
                                else:
                                    yield res
                        elif any([self._id_match(key_id, m) for m in self.REQUIRED]):
                            yield (id, MetadataKeyError(self.filename, key))
                        else:
                            # add it to the dictionary
                            node[key] = None
                elif isinstance(refnode, list):
                    if len(refnode):
                        for i, item in enumerate(node):
                            try:
                                refitem = refnode[i]
                            except IndexError:
                                # repeat the last found reference item
                                pass
                            for res in self.check_node(item,
                                                       refitem,
                                                       id=self._get_list_id(id, i)):
                                if isinstance(res[1], MetadataUpdate):
                                    node[i] = res[1].new_value
                                else:
                                    yield res
                yield (id, None)

    def validate_document_structure(self, doc, refdoc):
        prev_results = {}
        # OneOf instance means an id fails only if all runs fail.
        for id, value in self.check_node(doc, refdoc):
            if id not in prev_results:
                prev_results[id] = value
            elif value is not None and prev_results[id] is not None:
                # failure
                prev_results[id] = value
            else:
                prev_results[id] = None
        failures = [val for id, val in prev_results.items() if val is not None]
        if failures:
            # TODO: either raise error immediately when first encountered, or devise
            # a way to raise a failure here that provides feedback on a list of failures
            raise failures[0]

    def validate(self, metadata):
        "validate the metadata"
        self.validate_document_structure(metadata, self.REFERENCE)

    def strip(self, metadata):
        """
        remove non-protected data
        """
        remove = set(metadata.keys()).difference(self.REQUIRED + self.PROTECTED)
        for key in remove:
            metadata.pop(key, None)

class OneOf(object):
    '''
    Utility class for storing optional types in a reference document
    '''
    def __init__(self, *options):
        self.options = options

#------------------------------------------------------------------------------
# MetadataValidator Implementations
#------------------------------------------------------------------------------

# FIXME: come up with something better than this. Seems like legacy a format.
# Why is the release_time in a different file than the release info?
# Does it store something meaningfully different than ACTUAL_BUILD_TIME and BUILD_TIME?
# Why isn't the name of the release metadata more informative than info.txt?
# Why does it assume SVN?
# Why is it all caps whereas other metadata files use lowercase?
# Why is it using .txt with custom parsing instead of YAML?
class ReleaseInfo(MetadataValidator):
    REFERENCE = {
        'ACTUAL_BUILD_TIME': 0,
        'BUILD_TIME': 0,
        'USER': 'str',
        'SVN': 'str'
    }
    REQUIRED = ('ACTUAL_BUILD_TIME', 'BUILD_TIME', 'USER')

class BasePackageConfig_0(MetadataValidator):
    REFERENCE = {
        'config_version': 0,
        'uuid': 'str',
        'description': 'str',
        'name': 'str',
        'help': OneOf('str', [['str']]),
        'authors': ['str'],
        'requires': ['name-1.2'],
        'build_requires': ['name-1.2'],
        'variants': [['name-1.2']],
        'commands': OneOf(lambda: None, 'str', ['str'])
    }

    REQUIRED = ('config_version', 'name')
    PROTECTED = ('requires', 'build_requires', 'variants', 'commands')

class VersionPackageConfig_0(BasePackageConfig_0):
    REFERENCE = {
        'config_version': 0,
        'uuid': 'str',
        'description': 'str',
        'name': 'str',
        'version': Version('1.2'),
        'help': OneOf('str', [['str']]),
        'authors': ['str'],
        'requires': ['name-1.2'],
        'build_requires': ['name-1.2'],
        'variants': [['name-1.2']],
        'commands': OneOf(lambda: None, 'str', ['str'])
    }
    REQUIRED = ('config_version', 'name', 'version')

class PackageBuildConfig_0(VersionPackageConfig_0):
    """
    A package that is built with the intention to release is stricter about
    the existence of certain metadata values
    """
    REQUIRED = ('config_version', 'name', 'version', 'uuid', 'description', 'authors')

# TODO: look into creating an {ext} token
register_resource(0,
                  'package.versioned',
                  ['{name}/{version}/package.yaml', '{name}/{version}/package.py'],
                  [VersionPackageConfig_0])

register_resource(0,
                  'package.versionless',
                  ['{name}/package.yaml', '{name}/package.py'],
                  [BasePackageConfig_0])

register_resource(0,
                  'package.built',
                  metadata_validators=[PackageBuildConfig_0])

register_resource(0,
                  'release.info',
                  ['{name}/{version}/.metadata/info.txt'],
                  [ReleaseInfo])

register_resource(0,
                  'package_family.folder',
                  ['{name}/'])

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
    for validator in get_metadata_validators(config_version, filename, resource_key):
        try:
            validator.validate(metadata)
        except MetadataError, err:
            errors.append((validator, err))
            continue
        if strip:
            validator.strip(metadata)
        return metadata

    msg = "Could not find registered metadata configuration for %r" % filename
    for val,err in errors:
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
