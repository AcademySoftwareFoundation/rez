"""
Class for loading and verifying rez metafiles.

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
import string
from collections import defaultdict
from fnmatch import fnmatch
from rez.settings import settings, Settings
from rez.util import to_posixpath, propertycache, print_warning_once, Namespace
from rez.exceptions import PackageMetadataError, ResourceError
from rez.vendor.version.version import Version, VersionRange
from rez.vendor.version.requirement import Requirement
from rez.backport.lru_cache import lru_cache
from rez.vendor import yaml
# FIXME: handle this double-module business
from rez.vendor.schema.schema import Schema, Use, And, Or, Optional, SchemaError


# list of resource classes, keyed by config_version
_configs = defaultdict(list)

PACKAGE_NAME_REGSTR = '[a-zA-Z_][a-zA-Z0-9_]*'
VERSION_COMPONENT_REGSTR = '(?:[0-9a-zA-Z_]+)'
VERSION_REGSTR = '%(comp)s(?:[.-]%(comp)s)*' % dict(comp=VERSION_COMPONENT_REGSTR)
UUID_REGEX = re.compile("^[a-f0-9]{8}-?[a-f0-9]{4}-?4[a-f0-9]{3}-?[a-f0-9]{4}-?[a-f0-9]{12}\Z")


#------------------------------------------------------------------------------
# Base Classes and Functions
#------------------------------------------------------------------------------

def _or_regex(strlist):
    return '|'.join('(%s)' % e for e in strlist)


def _updated_schema(schema, items=None, rm_keys=None):
    """Get an updated copy of a schema."""
    items = items or ()
    rm_keys = rm_keys or ()
    items_ = dict((x[0]._schema, x) for x in items)
    schema_ = {}

    for key, value in schema._schema.iteritems():
        k = key._schema
        if k not in rm_keys:
            item = items_.get(k)
            if item is not None:
                del items_[k]
                key, value = item
            schema_[key] = value

    schema_.update(dict(items_.itervalues()))
    return Schema(schema_)


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
    excludes = set(['Namespace', '__builtins__'])
    exec stream in g
    result = {}
    for k, v in g.iteritems():
        if k not in excludes and \
                (k not in __builtins__ or __builtins__[k] != v):
            result[k] = v
    # add in any namespaces used
    result.update(Namespace.get_namespace())
    result = _process_python_objects(result)
    return result


def load_yaml(stream):
    """load a yaml stream into a metadata dictionary.

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


def get_file_loader(filepath):
    scheme = os.path.splitext(filepath)[1][1:]
    try:
        return metadata_loaders[scheme]
    except KeyError:
        raise ResourceError("Unknown metadata storage scheme: %r" % scheme)


# FIXME: add lru_cache here?
def load_file(filepath, loader=None):
    """Read metadata from a file.

    Determines the proper de-serialization scheme based on file extension.

    Args:
        filepath (str): Path to the file from which to read metadata.
        loader (callable or str, optional): callable which will take an open
            file handle and return a metadata dictionary. Can also be a key
            to the `metadata_loaders` dictionary.
    Returns:
        dict: the metadata
    """
    if loader is None:
        loader = get_file_loader(filepath)
    elif isinstance(loader, basestring):
        loader = metadata_loaders[loader]

    with open(filepath, 'r') as f:
        try:
            return loader(f)
        except Exception as e:
            # FIXME: this stack fix is probably specific to `load_python` and
            # should be moved there.
            import traceback
            frames = traceback.extract_tb(sys.exc_traceback)
            while frames and frames[0][0] != filepath:
                frames = frames[1:]
            stack = ''.join(traceback.format_list(frames)).strip()
            raise PackageMetadataError(filepath, "%s\n%s" % (str(e), stack))


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
    # TODO why is order important?
    if resource.key in set(r.key for r in version_configs):
        raise ResourceError("resource already exists: %r" % resource.key)

    version_configs.append(resource)

    if resource.parent_resource:
        Resource._children[resource.parent_resource].append(resource)


#------------------------------------------------------------------------------
# MetadataSchema Implementations
#------------------------------------------------------------------------------

#package_requirement = Requirement

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

# make an alias which just so happens to be the same number of characters as
# 'Optional'  so that our schema are easier to read
Required = Schema

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
# Utility Classes
#------------------------------------------------------------------------------

class _ResourcePathParser(object):
    @classmethod
    def parse_filepath(cls, resource_class, filepath, search_paths,
                       parse_all=True):
        """parse `filepath` against the joined `path_pattern` of this resource
        and all of its parents, extracting the resource variables.

        Args:
            filepath (str): path to parse.
        Returns:
            str: part of `filepath` that matched
            dict: dictionary of variables
        """
        pattern = resource_class._path_pattern()
        return cls._parse_pattern(resource_class, filepath, pattern,
                                  search_paths, parse_all)

    @classmethod
    def parse_filepart(cls, resource_class, filename):
        """parse `filename` against the resource's `path_pattern`.

        Args:
            filename (str): filename to parse.
        Returns:
            str: part of `filename` that matched
            dict: dictionary of variables
        """
        if not resource_class.path_pattern:
            return None
        return cls._parse_pattern(resource_class, filename,
                                  resource_class.path_pattern)

    @classmethod
    def _parse_pattern(cls, resource_class, filepath, pattern,
                       search_paths=None, parse_all=True):
        """
        Returns:
            str: the part of `filepath` that matches `pattern`
            dict: the variables in `pattern` that matched
        """
        reg = cls._get_regex(resource_class, pattern,
                             tuple(search_paths or ()), parse_all)
        m = reg.match(to_posixpath(filepath))
        if m:
            return m.group(0), m.groupdict()

    @classmethod
    def _expand_pattern(cls, resource_class, pattern, search_paths):
        """expand variables in a search pattern with regular expressions"""
        # escape literals:
        #   '{package}.{ext}' --> '\{package\}\.\{ext\}'
        pattern = re.escape(pattern)
        expansions = dict(search_path=_or_regex(search_paths)) \
            if search_paths else {}
        expansions.update(resource_class._variable_regex())
        for key, value in expansions.iteritems():
            # escape key so it matches escaped pattern:
            #   'search_path' --> 'search\_path'
            pattern = pattern.replace(r'\{%s\}' % re.escape(key),
                                      '(?P<%s>%s)' % (key, value))
        return pattern

    @classmethod
    @lru_cache()
    def _get_regex(cls, resource_class, pattern, search_paths, parse_all):
        pattern = cls._expand_pattern(resource_class, pattern, search_paths)
        pattern = r'^' + pattern
        if parse_all:
            pattern += '$'
        else:
            # assertion lookaehead so '/foo/ba' matches 'foo/ba' and 
            # /foo/ba/whee', but not '/foo/barry'
            pattern += "(?=$|%s)" % re.escape(os.path.sep)
        reg = re.compile(pattern)
        return reg


#------------------------------------------------------------------------------
# Resource Implementations
#------------------------------------------------------------------------------

class Resource(object):
    """Abstract base class for data resources.

    The `Package` class expects its metadata to match a specific schema, but
    each individual resource may have its own schema specific to the file it
    loads, and that schema is able to modify the data on validation so that it
    conforms to the Package's master schema.

    As an additional conform layer, each resource implements a `load` method,
    which is the main entry point for loading that resource's metadata. By
    default, this method loads the contents of the resource file and validates
    its contents using the Resource's schema, however, this method can also
    be used to mutate the metadata and graft other resources into it.

    In this paradigm, the responsibility for handling variability is shifted
    from the package to the resource. This makes it easier to implement
    different resources that present the same metatada interface to the
    `Package` class.  As long as the `Package` class gets metadata that matches
    its expected schema, it doesn't care how it gets there. The end result is
    that it is much easier to add new file and folder structures to rez
    without the need to modify the `Package` class, which remains a fairly
    static public interface.

    Attributes:
        key (str): The name of the resource. Used with the resource utilty
            functions `iter_resources`, `get_resource`, and `load_resource`
            when the type of resource desired is known. This attribute must be
            overridden by `Resource` subclasses.
        schema (Schema, optional): schema defining the structure of the data
            which will be loaded
        parent_resource (Resource class): the resource above this one in the
            tree.  An instance of this type is passed to `iter_instances`
            on this class to allow this resource to determine which instances
            of itself exist under an instance of its parent resource.
        path_pattern (str, optional): a string containing variable tokens such
            as ``{name}``.  This is used to determine if a resource is
            compatible with a given path.
        variable_keys (list of str): The variables required by this resource.
        variable_regex ((str, str) dict): The names of the tokens which can be
            expanded within the `path_pattern` and their corresponding regular
            expressions.
        sub_resource (bool): A sub-resource is a resource that can only be
            extracted from another resource. For example,
            `CombinedPackageResource` is a sub-resource - in this case multiple
            packages are contained within a single file, which is represented
            by the parent `CombinedPackageFamilyResource` class.
    """
    key = None
    schema = None
    parent_resource = None
    sub_resource = False
    path_pattern = None
    variable_keys = []
    variable_regex = {}

    _children = defaultdict(list)  # gets filled by register_resource

    # TODO promote search_path to first-class member?
    def __init__(self, path, variables=None):
        """
        Args:
            path (str): path of the file to be loaded.
            variables (dict): variables that define this resource. For example,
                a package has a name and a version. Some of these variables may
                have been used to construct `path`.
        """
        super(Resource, self).__init__()
        self.variables = variables or {}
        self.path = path

    def get(self, key, default=None):
        """Get the value of a resource variable."""
        return self.variables.get(key, default)

    @propertycache
    def handle(self):
        """Get the resource handle."""
        return dict(config_version=0,
                    resource_key=self.key,
                    path=self.path,
                    variables=self.variables.copy())

    def __repr__(self):
        return "%s(%r, %r)" % (self.__class__.__name__, self.path,
                               self.variables)

    # --- info

    @classmethod
    def children(cls):
        """Get a tuple of the resource classes which consider this class its
        parent"""
        return tuple(cls._children[cls])

    @classmethod
    def _iter_ancestors(cls):
        if cls.parent_resource:
            for parent in cls.parent_resource.ancestors():
                yield parent
            yield cls.parent_resource

    @classmethod
    def ancestors(cls):
        """Get a tuple of all the resources above this one, in descending order
        """
        return tuple(cls._iter_ancestors())

    @classmethod
    def topmost(cls):
        """Get the root resource type in this hierarchy."""
        if cls.parent_resource:
            return cls._iter_ancestors().next()
        else:
            return cls

    @classmethod
    def has_ancestor(cls, other_cls):
        """Returns True if other_cls is an ancestor of cls."""
        return (other_cls in cls._iter_ancestors())

    @classmethod
    def _default_search_paths(cls, path=None):
        """Get the default search paths for this resource type.

        Only topmost resource types (such as PackageRoot) need to implement
        this method.

        Args:
            path (str): The path of a resource being loaded, if any. In some
                cases (such as floating resource types, ie those with no strict
                filesystem hierarchy) the search path is derived from the
                filepath of the resource.

        Returns:
            List of str paths.
        """
        topmost_cls = cls.topmost()
        if cls == topmost_cls:
            raise NotImplemented
        else:
            return topmost_cls._default_search_paths(path)

    @classmethod
    def _path_pattern(cls):
        hierarchy = cls.ancestors() + (cls,)
        parts = [r.path_pattern for r in hierarchy if r]
        return os.path.sep.join(parts)

    @classmethod
    def _variable_keys(cls):
        hierarchy = cls.ancestors() + (cls,)
        keys = set()
        for r in hierarchy:
            keys |= set(r.variable_keys)
        return keys

    @classmethod
    def _variable_regex(cls):
        hierarchy = cls.ancestors() + (cls,)
        keys = {}
        for r in hierarchy:
            keys.update(r.variable_regex)
        return keys

    def __eq__(self, other):
        return (self.path == other.path) \
            and (self.variables == other.variables)

    # --- instantiation

    def load(self):
        """load the resource's data.

        Returns:
            The resource data as a dict. The implementation should validate the
            data against the schema, if any.
        """
        raise NotImplemented

    @classmethod
    def from_handle(cls, handle):
        """Get a resource instance from a resource handle."""
        key = handle["resource_key"]
        clss = list_resource_classes(handle["config_version"], key)
        if not clss:
            raise ResourceError("Unknown resource type %s" % key)
        return clss[0](handle["path"], handle["variables"])

    @classmethod
    def from_path(cls, path, search_paths=None):
        """Create a resource from a path.

        Args:
            path (str): Path or filepath representing the resource.
            search_paths (list of str): Search path(s) that was used to create
                the resource. This is used to decode the path to extract
                variables such as package name and version.

        Returns:
            `Resource` instance.
        """
        if cls.sub_resource:
            raise ResourceError("A sub-resource cannot be loaded from only "
                                "a path")

        filepath = os.path.abspath(path)
        if not cls.path_pattern:
            raise ResourceError("Cannot create resource %r from %r: "
                                "does not have path patterns" %
                                (cls.key, filepath))

        search_paths = search_paths or cls._default_search_paths(path)
        result = _ResourcePathParser.parse_filepath(cls, filepath,
                                                    search_paths)
        if result is None:
            raise ResourceError("Cannot create resource %r from %r: "
                                "file did not match path patterns" %
                                (cls.key, filepath))
        variables = result[1]
        return cls(filepath, variables)

    @classmethod
    def iter_instances(cls, parent_resource):
        """Iterate over instances of this class which reside under the given
        parent resource.

        Args:
            parent_resource (Resource): resource instance of the type specified
                by this class's `parent_resource` attribute

        Returns:
            iterator of `Resource` instances
        """
        raise NotImplementedError

    def _ancestor_instance(self, ancestor_cls):
        path, _ = _ResourcePathParser.parse_filepath(ancestor_cls,
            filepath=self.path, search_paths=[self.variables["search_path"]],
            parse_all=False)
        var_keys = ancestor_cls._variable_keys()
        variables = dict((k,v) for k,v in self.variables.iteritems()
                         if k in var_keys)
        return ancestor_cls(path, variables)

    def ancestor_instance(self, ancestor_cls):
        """Get an instance of a resource type higher in the hierarchy."""
        if not self.has_ancestor(ancestor_cls):
            raise ResourceError("%s is not a resource ancestor of %s"
                        % (ancestor_cls.__name__, self.__class__.__name__))
        return self._ancestor_instance(ancestor_cls)

    def parent_instance(self):
        """Get an instance of the parent resource type."""
        return self._ancestor_instance(self.parent_resource)


class FileSystemResource(Resource):
    """A resource that resides on disk.

    Attributes:
        is_file (bool): True if the resources is stored in a file, False if not
            (the resource may be a directory, not a file).
    """
    is_file = None

    @classmethod
    def from_path(cls, path, search_paths=None):
        if not os.path.exists(path):
            raise ResourceError("File or directory does not exist: %s" % path)
        return super(FileSystemResource, cls).from_path(path, search_paths)

    @classmethod
    def iter_instances(cls, parent_resource):
        # FIXME: cache these disk crawls
        for name in os.listdir(parent_resource.path):
            fullpath = os.path.join(parent_resource.path, name)
            if os.path.isfile(fullpath) == cls.is_file:
                match = _ResourcePathParser.parse_filepart(cls, name)
                if match is not None:
                    variables = match[1]
                    variables.update(parent_resource.variables)
                    yield cls(fullpath, variables)


class FolderResource(FileSystemResource):
    """A resource representing a directory on disk"""
    is_file = False


class FileResource(FileSystemResource):
    """A resource representing a file on disk"""
    is_file = True
    loader = None

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
            data = load_file(self.path, self.loader)
            if self.schema:
                try:
                    return self.schema.validate(data)
                except SchemaError, err:
                    raise PackageMetadataError(self.path, str(err))
            else:
                return data


class SearchPath(FolderResource):
    """Represents a path in a searchpath."""
    path_pattern = '{search_path}'
    variable_keys = ["search_path"]


class ArbitraryPath(SearchPath):
    """Represents an arbitrary path in the filesystem."""
    @classmethod
    def _default_search_paths(cls, path=None):
        if path:
            return [os.path.dirname(path)]
        else:
            raise ResourceError("This type of resources requires explicit "
                                "search path(s)")


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

    def load(self):
        data = super(VersionlessPackageResource, self).load()
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

    def load(self):
        data = super(VersionedPackageResource, self).load()
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

    def load(self):
        data = super(CombinedPackageFamilyResource, self).load()

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
# Resource Hierarchies
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


#------------------------------------------------------------------------------
# Main Entry Points
#------------------------------------------------------------------------------

def list_resource_classes(config_version, keys=None):
    """List resource classes matching the search criteria.

    Args:
        keys (str or list of str, optional): Name(s) of the type of `Resources`
            to list. If None, all resource types are listed.

    Returns:
        List of `Resource` subclass types.
    """
    resource_classes = _configs.get(config_version)
    if keys:
        if isinstance(keys, basestring):
            keys = [keys]
        resource_classes = [r for r in resource_classes if
                            any(fnmatch(r.key, k) for k in keys)]
    return resource_classes


def list_common_resource_classes(config_version, root_key=None, keys=None):
    """List resource classes belonging to a common resource hierarchy.

    Must provide `root_key` or `keys`. If the keys are not common to a
    hierarchy, an error is raised. If both `keys` and `root_key` is provided,
    any keys outside of root_key's hierarchy are discarded.

    Args:
        root_key (str, optional): Root type in the hierarchy.
        keys (str or list of str, optional): Name(s) of the type of `Resources`
            to list. If None, all resource types in the hierarchy are listed.

    Returns:
        `Resource` class: Root resource type.
        list of `Resource` classes: Matching subclass types.
    """
    if root_key is None and not keys:
        raise ResourceError("Most provide root key or resource key(s)")

    root_class = None
    if root_key:
        clss = list_resource_classes(config_version, root_key)
        if len(clss) > 1:
            raise ResourceError("Specified multiple resource roots: %s"
                                % root_key)
        elif not clss:
            raise ResourceError("Unknown root resource type %s" % root_key)
        root_class = iter(clss).next()

    if keys is None:
        clss = list_resource_classes(config_version)
        return root_class, [c for c in clss if c.topmost() == root_class]
    else:
        if isinstance(keys, basestring):
            keys = [keys]

        resource_classes = set()
        root_classes = set()
        keys_ = set()

        for key in keys:
            clss = list_resource_classes(config_version, keys)
            for cls in clss:
                if root_class:
                    if cls.topmost() == root_class:
                        resource_classes.add(cls)
                else:
                    root_classes.add(cls.topmost())
                    if len(root_classes) > 1:
                        raise ResourceError("Resources from different "
                            "hierarchies were requested: %s, %s"
                            % (iter(keys_).next(), cls.key))
                    resource_classes.add(cls)
                    keys_.add(cls.key)

        if root_class is None:
            root_class = iter(root_classes).next()
        return root_class, list(resource_classes)


def _iter_resources(parent_resource, child_resource_classes=None):
    """Iterate over child resources of the given parent.

    If `child_resource_classes` is supplied, this prunes the search so that 
    only ancestor-or-equal resource types are iterated over.
    """
    if child_resource_classes is not None:
        child_resource_classes = [x for x in child_resource_classes
                                  if x.has_ancestor(parent_resource.__class__)]
        if not child_resource_classes:
            return

    for child_class in parent_resource.children():
        if child_resource_classes and \
                not any((child_class is x or x.has_ancestor(child_class)) 
                        for x in child_resource_classes):
            continue
        for child in child_class.iter_instances(parent_resource):
            yield child
            for grand_child in _iter_resources(child, child_resource_classes):
                yield grand_child


def _iter_filtered_resources(parent_resource, resource_classes, variables):
    for child in _iter_resources(parent_resource, resource_classes):
        if isinstance(child, tuple(resource_classes)) and \
                set((variables or {}).items()).issubset(child.variables.items()):
            yield child


def iter_resources(config_version, resource_keys=None, search_path=None,
                   variables=None, root_resource_key=None):
    """Iterate over `Resource` instances.

    Must provide `resource_keys` or `root_resource_key`.

    Args:
        resource_keys (str or list of str): Name(s) of the type of `Resources`
            to find. If None, all resource types are searched.
        search_path (str or list of str, optional): List of root paths under
            which to search for resources.  These typically correspond to the
            rez packages path. Default depends on `root_resource_key`.
        variables (dict, optional): variables that identify the resource. Some
            of these variables may be used to expand the resource path pattern,
            eg '{name}/{version}/package.{ext}'.
        root_resource_key (str): The root of the resource type hierarchy to
            search. If None, is determined from resource_keys.

    Returns:
        A `Resource` iterator.
    """
    root_cls, resource_classes = list_common_resource_classes(config_version,
        root_resource_key, resource_keys)
    if not resource_classes:
        return

    if search_path is None:
        search_path = root_cls._default_search_paths()
    elif isinstance(search_path, basestring):
        search_path = [search_path]

    for path in search_path:
        resource = root_cls(path, {'search_path': path})
        for child in _iter_filtered_resources(resource, resource_classes,
                                              variables):
            yield child


def iter_descendant_resources(parent_resource, resource_keys=None, 
                              variables=None):
    """Iterate over all descendant `Resource` instances of the given resource.

    Args:
        parent_resource (`Resource`): The resource to search under.
        resource_keys (str or list of str): Name(s) of the type of `Resources`
            to find. If None, all descendant resource types are searched.
        variables (dict, optional): variables that identify the resource. Some
            of these variables may be used to expand the resource path pattern,
            eg '{name}/{version}/package.{ext}'.

    Returns:
        A `Resource` iterator.
    """
    root_resource_key = parent_resource.topmost().key
    _, resource_classes = list_common_resource_classes(0, root_resource_key, 
                                                       resource_keys)
    if not resource_classes:
        return

    for child in _iter_filtered_resources(parent_resource, resource_classes,
                                          variables):
        yield child


def iter_child_resources(parent_resource, resource_keys=None, 
                              variables=None):
    """Iterate over all child `Resource` instances of the given resource.

    Args:
        parent_resource (`Resource`): The resource to search under.
        resource_keys (str or list of str): Name(s) of the type of `Resources`
            to find. If None, all child resource types are searched.
        variables (dict, optional): variables that identify the resource. Some
            of these variables may be used to expand the resource path pattern,
            eg '{name}/{version}/package.{ext}'.

    Returns:
        A `Resource` iterator.
    """
    root_resource_key = parent_resource.topmost().key
    _, resource_classes = list_common_resource_classes(0, root_resource_key, 
                                                       resource_keys)
    resource_classes = set(resource_classes) & set(parent_resource.children())
    if not resource_classes:
        return

    for child in _iter_filtered_resources(parent_resource, resource_classes,
                                          variables):
        yield child


def get_resource(config_version, filepath=None, resource_keys=None,
                 search_path=None, variables=None, root_resource_key=None):
    """Find and instantiate a `Resource` instance.

    Returns the first match.

    Must provide `resource_keys` or `root_resource_key`

    Args:
        resource_keys (str or list of str, optional): Name(s) of the type of
            `Resources` to find. If None, all resource types are searched.
        search_path (str or list of str, optional): List of root paths under 
            which to search for resources. These typically correspond to the 
            rez packages path. Default depends on `root_resource_key`.
        filepath (str, optional): file that contains the resource - either the
            resource is the entire file, or the resource is a 'sub-resource',
            meaning it is one of possibly several resources contained in the
            file.
        variables (dict, optional): variables that identify the resource. Some
            of these variables may be used to expand the resource path pattern,
            eg '{name}/{version}/package.{ext}'. If a resource's variables are
            not a superset of these, the resource is not matched.
        root_resource_key (str): The root of the resource type hierarchy to
            search. If None, is determined from resource_keys.

    Returns:
        A `Resource` instance.
    """
    if isinstance(search_path, basestring):
        search_path = [search_path]
    if isinstance(resource_keys, basestring):
        resource_keys = [resource_keys]

    def _err():
        toks = []
        if filepath:
            toks.append("filepath: %s" % filepath)
        if resource_keys:
            kstr = ', '.join('%s' % str(r) for r in (resource_keys or []))
            toks.append("resource types: %s" % kstr)
        if variables:
            vstr = ', '.join('%s=%r' % r for r in (variables or {}).iteritems())
            toks.append("variables: %s" % vstr)
        raise ResourceError("Could not find resource: %s" % "; ".join(toks))

    if filepath:
        def _match_resource(resource_classes):
            for resource_class in resource_classes:
                try:
                    return resource_class.from_path(filepath, search_path)
                except ResourceError, err:
                    pass

        # first try to find a matching resource that is not a sub-resource
        _, resource_classes = list_common_resource_classes(config_version,
            root_resource_key, resource_keys)
        if not resource_classes:
            _err()

        resource_classes_1 = set(r for r in resource_classes
                                 if not r.sub_resource)
        resource = _match_resource(resource_classes_1)
        if resource is not None and \
                set((variables or {}).items()).issubset(resource.variables.items()):
            return resource

        # find all parents of sub-resource classes in the requested resource
        # keys. Note that even classes already tested are tested again, this
        # time without the variable check
        resource_classes_2 = [r for r in resource_classes if r.sub_resource]
        resource_classes_3 = set()
        for resource_class in resource_classes_2:
            resource_classes_3 |= set(resource_class.ancestors())
        resource_classes_3 = set(r for r in resource_classes_3
                                 if not r.sub_resource)

        resource = _match_resource(resource_classes_3)
        if resource is None:
            _err()

        # the resource we want is is a sub- (sub-sub- etc) resource of the one
        # we've found, switch to iteration to find it
        it = _iter_filtered_resources(resource, resource_classes_2, variables)
    else:
        # a search with no filepath is just the first result of an iteration
        it = iter_resources(config_version, resource_keys, search_path,
                            variables, root_resource_key)

    try:
        return it.next()
    except StopIteration:
        _err()


def load_resource(config_version, filepath=None, resource_keys=None,
                  search_path=None, variables=None, root_resource_key=None):
    """Find a resource and load its metadata.

    Returns the first match.

    Must provide `resource_keys` or `root_resource_key`

    Args:
        resource_keys (str or list of str, optional): Name(s) of the type of
            `Resources` to find. If None, all resource types are searched.
        search_path (str or list of str, optional): List of root paths under 
            which to search for resources. These typically correspond to the 
            rez packages path. Default depends on the resource hierarchy.
        filepath (str, optional): file that contains the resource - either the
            resource is the entire file, or the resource is a 'sub-resource',
            meaning it is one of possibly several resources contained in the
            file.
        variables (dict, optional): variables that identify the resource. Some
            of these variables may be used to expand the resource path pattern,
            eg '{name}/{version}/package.{ext}'. If a resource's variables are
            not a superset of these, the resource is not matched.
        root_resource_key (str): The root of the resource type hierarchy to
            search. If None, is determined from resource_keys. If both are None,
            defaults to 'folder.packages_root'.

    Returns:
        The resource metadata, as a dict.
    """
    return get_resource(config_version, filepath, resource_keys, search_path,
                        variables, root_resource_key).load()





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
