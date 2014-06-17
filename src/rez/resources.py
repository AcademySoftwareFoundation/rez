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
an understanding of the underlying file and folder structure.  This ensures
that the addition of new resources is localized to the registration functions
provided by this module.
"""
import os
import sys
import inspect
import re
import string
from collections import defaultdict
from fnmatch import fnmatch
from rez.util import to_posixpath, ScopeContext, is_dict_subset, \
    propertycache, convert_to_user_dict, RO_AttrDictWrapper, dicts_conflicting
from rez.settings import settings
from rez.exceptions import PackageMetadataError, ResourceError, \
    ResourceNotFoundError
from rez.backport.lru_cache import lru_cache
from rez.vendor import yaml
# FIXME: handle this double-module business
from rez.vendor.schema.schema import Schema, SchemaError, Optional


# list of resource classes, keyed by config_version
_configs = defaultdict(list)

# make an alias which just so happens to be the same number of characters as
# 'Optional'  so that our schema are easier to read
Required = Schema


# -----------------------------------------------------------------------------
# Misc Functions
# -----------------------------------------------------------------------------

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


# -----------------------------------------------------------------------------
# File Loading
# -----------------------------------------------------------------------------

@settings.lru_cache("resource_caching", "resource_caching_maxsize")
def _listdir(path, is_file=None):
    names = []
    for name in os.listdir(path):
        filepath = os.path.join(path, name)
        if is_file is None or os.path.isfile(filepath) == is_file:
            names.append(name)
    return names


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
    scopes = ScopeContext()
    g['scope'] = scopes
    excludes = set(['scope', '__builtins__'])
    exec stream in g
    result = {}
    for k, v in g.iteritems():
        if k not in excludes and \
                (k not in __builtins__ or __builtins__[k] != v):
            result[k] = v
    # add in any namespaces used
    result.update(scopes.to_dict())
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


def load_text(stream):
    """Load a text file.

    Args:
        stream (string, or open file object): stream of text to load.

    Returns:
        str
    """
    if hasattr(stream, 'read'):
        text = stream.read()
    else:
        text = stream
    return text


# TODO pluggize
metadata_loaders = {}
metadata_loaders['py'] = load_python
metadata_loaders['yaml'] = load_yaml
metadata_loaders['txt'] = load_text


def get_file_loader(filepath):
    scheme = os.path.splitext(filepath)[1][1:]
    try:
        return metadata_loaders[scheme]
    except KeyError:
        raise ResourceError("Unknown metadata storage scheme: %r" % scheme)


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


# -----------------------------------------------------------------------------
# Resource Registration
# -----------------------------------------------------------------------------

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


# -----------------------------------------------------------------------------
# Utility Classes
# -----------------------------------------------------------------------------

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


# -----------------------------------------------------------------------------
# Resource Implementations
# -----------------------------------------------------------------------------

class ResourceHandle(object):
    """A `Resource` handle.

    A handle uniquely identifies a resource. A handle can be stored and used
    to recreate the same resource at a later date.

    Do not create a resource handle directly, instead use the `Resource`
    property 'handle' to get a resource handle.
    """
    def __init__(self, key, path, variables):
        self.key = key
        self.path = path
        self.variables = variables

    def get_resource(self):
        """Get a resource instance from the resource handle."""
        clss = list_resource_classes(0, self.key)
        if not clss:
            raise ResourceError("Unknown resource type %s" % self.key)
        assert len(clss) == 1
        return clss[0](self.path, self.variables)

    def to_dict(self):
        return dict(key=self.key,
                    path=self.path,
                    variables=self.variables)

    @classmethod
    def from_dict(cls, d):
        return ResourceHandle(**d)

    def __str__(self):
        return "%s(%s)" % (self.key, self.path)

    def __repr__(self):
        return "%s(%r, %r, %r)" % (self.__class__.__name__, self.key,
                                   self.path, self.variables)

    def __eq__(self, other):
        return (self.key == other.key) \
            and (self.path == other.path) \
            and (self.variables == other.variables)

    def __hash__(self):
        return hash((self.key,
                     self.path,
                     frozenset(self.variables.items())))


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

    @property
    def handle(self):
        """Get the resource handle."""
        return ResourceHandle(self.key, self.path, self.variables)

    def __repr__(self):
        return "%s(%r, %r)" % (self.__class__.__name__, self.path,
                               self.variables)

    def __hash__(self):
        return hash((self.__class__, self.handle))

    def __eq__(self, other):
        return (self.handle == other.handle)

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

    # --- instantiation

    def load(self):
        """load the resource's data.

        Returns:
            The resource data as a dict. The implementation should validate the
            data against the schema, if any. If no data is associated with this
            resource, None is returned.
        """
        return None

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

    # -- caching

    @staticmethod
    @settings.lru_cache("resource_caching", "resource_caching_maxsize")
    def _cached(fn, instance):
        return fn(instance)

    @classmethod
    def cached(cls, f):
        """load() implementations should be decorated with @Resource.cached."""
        def decorated(instance):
            return Resource._cached(f, instance)
        return decorated


class FileSystemResource(Resource):
    """A resource that resides on disk.

    Attributes:
        is_file (bool): True if the resources is stored in a file, False if not
            (the resource may be a directory).
    """
    is_file = None

    @classmethod
    def from_path(cls, path, search_paths=None):
        if not os.path.exists(path):
            raise ResourceNotFoundError("File or directory does not exist: %s"
                                        % path)
        return super(FileSystemResource, cls).from_path(path, search_paths)

    @classmethod
    def iter_instances(cls, parent_resource):
        for name in _listdir(parent_resource.path, cls.is_file):
            match = _ResourcePathParser.parse_filepart(cls, name)
            if match is not None:
                variables = match[1]
                variables.update(parent_resource.variables)
                filepath = os.path.join(parent_resource.path, name)
                yield cls(filepath, variables)


class FolderResource(FileSystemResource):
    """A resource representing a directory on disk"""
    is_file = False


class FileResource(FileSystemResource):
    """A resource representing a file on disk"""
    is_file = True
    loader = None

    @Resource.cached
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
        else:
            msg = "not a file" if os.path.exists(self.path) \
                else "file does not exist"
            raise ResourceError("Could not load %s from %s: %s"
                                % (self.key, self.path, msg))


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


# -----------------------------------------------------------------------------
# Resource Wrapper
# -----------------------------------------------------------------------------

class _WithDataAccessors(type):
    """Metaclass for adding properties to a class for accessing top-level keys
    in its metadata dictionary.

    Property names are derived from the keys of the class's `schema` object.
    If a schema key is optional, then the class property will evaluate to None
    if the key is not present in the resource.
    """
    def __new__(cls, name, parents, members):
        schema = members.get('schema')
        if schema:
            schema_dict = schema._schema
            for key in schema_dict.keys():
                optional = isinstance(key, Optional)
                while isinstance(key, Schema):
                    key = key._schema
                if key not in members and \
                        not any(hasattr(x, key) for x in parents):
                    members[key] = cls._make_getter(key, optional)
        return super(_WithDataAccessors, cls).__new__(cls, name, parents,
                                                      members)

    @classmethod
    def _make_getter(cls, key, optional):
        def getter(self):
            if optional:
                return getattr(self.metadata, key, None)
            else:
                return getattr(self.metadata, key)
        return property(getter)


class ResourceWrapper(object):
    """Base class for implementing a class that wraps a resource.
    """
    __metaclass__ = _WithDataAccessors
    schema = None

    def __init__(self, resource):
        self._resource = resource

    @property
    def path(self):
        return self._resource.path

    @property
    def resource_handle(self):
        return self._resource.handle

    def validate(self):
        """Check that the resource's contents are valid."""
        _ = self._data

    @propertycache
    def _data(self):
        """Dictionary of data loaded from the package's resource.

        This is private because it is preferred for users to go through the
        `metadata` property.  This is here to preserve the original dictionary
        loaded directly from the package's resource.

        Returns:
            Resource data as a dict, or None if the resource has no data.
        """
        data = self._resource.load()
        if data and self.schema:
            data = self.schema.validate(data)
        return data

    @propertycache
    def metadata(self):
        """Read-only dictionary of metadata for this package with nested,
        attribute-based access for the keys in the dictionary.

        All of the dictionaries in `_data` have are replaced with custom
        `UserDicts` to provide the attribute-lookups.  If you need the raw
        dictionary, use `_data`.

        Note that the `UserDict` references the dictionaries in `_data`, so
        the data is not copied, and thus the two will always be in sync.

        Returns:
            `RO_AttrDictWrapper` instance, or None if the resource has no data.
        """
        if self._data is None:
            return None
        else:
            return convert_to_user_dict(self._data, RO_AttrDictWrapper)

    def format(self, s, pretty=False):
        """Format a string.

        Args:
            s (str): String to format, eg "hello {name}"
            pretty: If True, references to non-string attributes such as lists
                are converted to basic form, with characters such as brackets
                and parenthesis removed.

        Returns:
            The formatting string.
        """
        f = ResourceWrapperStringFormatter(self, pretty=pretty)
        return f.format(s)

    def __eq__(self, other):
        return (self._resource == other._resource)

    def __repr__(self):
        return "%s(%r)" % (self.__class__.__name__, self._resource)

    def __hash__(self):
        return hash((self.__class__, self._resource))


class ResourceWrapperStringFormatter(string.Formatter):
    """String formatter for resource wrappers.

    This formatter will expand any reference to a resource wrapper's
    attributes.
    """
    def __init__(self, resource_wrapper, pretty=False):
        """Create a formatter.

        Args:
            resource_wrapper: The resource to format with.
            pretty: If True, references to non-string attributes such as lists
                are converted to basic form, with characters such as brackets
                and parenthesis removed.
        """
        self.instance = resource_wrapper
        self.pretty = pretty

    def convert_field(self, value, conversion):
        if self.pretty:
            if value is None:
                return ''
            elif isinstance(value, list):
                return ' '.join(str(x) for x in value)
        return string.Formatter.convert_field(self, value, conversion)

    def get_value(self, key, args, kwds):
        if isinstance(key, basestring):
            attr = getattr(self.instance, key, '')
            return '' if callable(attr) else attr
        else:
            return string.Formatter.get_value(self, key, args, kwds)


# -----------------------------------------------------------------------------
# Main Entry Points
# -----------------------------------------------------------------------------

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
        keys (str or tuple of str, optional): Name(s) of the type of
            `Resources` to list. If None, all resource types in the hierarchy
            are listed.

    Returns:
        `Resource` class: Root resource type.
        list of `Resource` classes: Matching subclass types.
    """
    if root_key is None and not keys:
        raise ResourceError("Most provide root key or resource key(s)")

    if root_key:
        clss = list_resource_classes(config_version, root_key)
        if len(clss) > 1:
            raise ResourceError("Specified multiple resource roots: %s"
                                % root_key)
        elif not clss:
            raise ResourceError("Unknown root resource type %s" % root_key)
        root_class = clss[0]
        # if keys is none, will return all resource classes
        clss = list_resource_classes(config_version, keys)
        return root_class, [c for c in clss if c.topmost() == root_class]
    else:
        resource_classes = set()
        clss = list_resource_classes(config_version, keys)
        if not clss:
            if isinstance(keys, basestring):
                keys = [keys]
            msg = "no such resource type(s) %s" % ", ".join(keys)
            if root_key:
                msg += " in resource hierarchy %s" % root_key
            raise ResourceError(msg)

        # all root classes must match
        root_class = clss[0].topmost()
        for cls in clss:
            if root_class != cls.topmost():
                raise ResourceError(
                    "Resources from different "
                    "hierarchies were requested: %s, %s"
                    % (list(resource_classes)[-1].key, cls.key))
            resource_classes.add(cls)
        return root_class, list(resource_classes)


def _iter_resources(parent_resource, child_resource_classes=None,
                    variables=None):
    """Iterate over child resources of the given parent.

    If `child_resource_classes` is supplied, this prunes the search so that
    only ancestor-or-equal resource types are iterated over.

    If `variables` is supplied, this prunes the search so that any resource
    with clashing variable values is not iterated over.

    If supplied, both `child_resource_classes` and `variables` can greatly
    increase the speed of resource iteration.
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
            if not dicts_conflicting(variables or {}, child.variables):
                yield child
                for grand_child in _iter_resources(child,
                                                   child_resource_classes,
                                                   variables):
                    yield grand_child


def _iter_filtered_resources(parent_resource, resource_classes, variables):
    for child in _iter_resources(parent_resource, resource_classes, variables):
        if isinstance(child, tuple(resource_classes)) \
                and is_dict_subset(variables or {}, child.variables):
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
    root_cls, resource_classes = list_common_resource_classes(
        config_version, root_resource_key, resource_keys)
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


def iter_child_resources(parent_resource, resource_keys=None, variables=None):
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
            toks.append("variables: %r" % variables)
        raise ResourceNotFoundError("Could not find resource: %s"
                                    % "; ".join(toks))

    if filepath:
        def _match_resource(resource_classes):
            for resource_class in resource_classes:
                try:
                    return resource_class.from_path(filepath, search_path)
                except ResourceError:
                    pass

        # first try to find a matching resource that is not a sub-resource
        _, resource_classes = list_common_resource_classes(
            config_version, root_resource_key, resource_keys)
        if not resource_classes:
            _err()

        resource_classes_1 = set(r for r in resource_classes
                                 if not r.sub_resource)
        resource = _match_resource(resource_classes_1)
        if resource is not None and \
                is_dict_subset(variables or {}, resource.variables):
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
