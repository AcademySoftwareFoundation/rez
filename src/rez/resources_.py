"""
A general resource system.

Use the classes in this file to create a resource system that supports
registering of resource classes, lazy validation of resource attributes, and
resource caching. You would not typically have users create `Resource` instances
directly; instead, some factory would be responsible for creating resources,
and would probably contain a `ResourcePool` to manage the resource instances.

Resources have attributes whos names match the entries in `Resource.schema`.
When a resource attribute is accessed for the first time, data validation (and
possibly conversion) is applied and cached. Resource data is also loaded lazily
- when the first attribute is accessed.

Resources themselves are also cached, according to the `cache_size` argument of
`ResourcePool`.

Use the `ResourceWrapper` class to implement classes that provide a public API
for a resource. This extra layer is useful because the same resource type may
be available from several sources or in different formats. In this situation
you can implement multiple `Resource` subclasses, but wrap them with a single
`ResourceWrapper` class.

Another reason to use `ResourceWrapper` is when you have attributes on your
`Resource` that don't require its data to be loaded - instead, some attributes
can be derived directly from the resource's variables. If you provide properties
in your resource wrapper for these attributes, then the unnecessary resource
data load is avoided.

See the 'pets' unit test in tests/test_resources.py for a complete example.
"""
from rez.exceptions import ResourceError
from rez.vendor.schema.schema import Schema, Optional
from rez.backport.lru_cache import lru_cache


# make an alias which just so happens to be the same number of characters as
# 'Optional' so that our schema are easier to read
Required = Schema


class cached_property(object):
    """simple property caching decorator."""
    def __init__(self, func, name=None):
        self.func = func
        self.name = name or func.__name__

    def __get__(self, instance, owner=None):
        result = self.func(instance)
        setattr(instance, self.name, result)
        return result


class LazyAttributeMeta(type):
    """Metaclass for adding properties to a class for accessing top-level keys
    in its `data` dictionary, and validating them on first reference.

    Property names are derived from the keys of the class's `schema` object.
    If a schema key is optional, then the class property will evaluate to None
    if the key is not present in `data`.

    The attribute getters created by this metaclass will perform lazy data
    validation, OR, if the class has a `_validate_key` method, will call this
    method, passing the key, key value and key schema.

    This metaclass creates the following attributes:
        - for each key in cls.schema, creates an attribute of the same name,
          unless that attribute already exists;
        - for each key in cls.schema, if the attribute already exists on cls,
          then creates an attribute with the same name but prefixed with '_';
        - 'validate_data' (function): A method that validates all keys;
        - 'validated_data' (function): A method that returns the entire
          validated dict, or None if there is no schema;
        - '_validate_key_impl' (function): Validation function used when
          '_validate_key' is not provided, it is here so you can use it in
          your own '_validate_key'.
        - '_schema_keys' (frozenset): Keys in the schema.
    """
    def __new__(cls, name, parents, members):
        schema = members.get('schema')
        keys = set()

        def _defined(x):
            return x in members or any(hasattr(p, x) for p in parents)

        if schema:
            schema_dict = schema._schema
            for key, key_schema in schema_dict.iteritems():
                optional = isinstance(key, Optional)
                while isinstance(key, Schema):
                    key = key._schema
                if isinstance(key, basestring):
                    keys.add(key)
                    if _defined(key):
                        attr = "_%s" % key
                        if _defined(attr):
                            raise Exception("Couldn't make fallback attribute "
                                            "%r, already defined" % attr)
                    else:
                        attr = key
                    members[attr] = cls._make_getter(key, optional, key_schema)

        if schema or not _defined("schema"):
            members["validate_data"] = cls._make_validate_data()
            members["validated_data"] = cls._make_validated_data()
            members["_validate_key_impl"] = cls._make_validate_key_impl()
            members["_schema_keys"] = frozenset(keys)

        return super(LazyAttributeMeta, cls).__new__(cls, name, parents, members)

    @classmethod
    def _make_validate_data(cls):
        def func(self):
            getattr(self, "validated_data")
        return func

    @classmethod
    def _make_validated_data(cls):
        def func(self):
            if self.schema:
                d = {}
                for key in self._schema_keys:
                    d[key] = getattr(self, key)
                return d
            else:
                return None
        return func

    @classmethod
    def _make_validate_key_impl(cls):
        def func(self, key, attr, schema):
            schema_ = schema if isinstance(schema, Schema) else Schema(schema)
            try:
                return schema_.validate(attr)
            except Exception as e:
                raise self.schema_error("Validation of key %r failed: "
                                        "%s" % (key, str(e)))
        return func

    @classmethod
    def _make_getter(cls, key, optional, key_schema):
        def getter(self):
            if key not in self.data:
                if optional:
                    return None
                raise self.schema_error("Required key is missing: %r" % key)

            attr = self.data[key]
            if hasattr(self, "_validate_key"):
                return self._validate_key(key, attr, key_schema)
            else:
                return self._validate_key_impl(key, attr, key_schema)

        return cached_property(getter, name=key)


class Resource(object):
    """Abstract base class for a data resource.

    A resource is an object uniquely identified by a 'key' (the resource type),
    and a dict of variables. For example, a very simple banking system might
    have a resource type with key 'account.checking', and a single variable
    'account_owner' that uniquely identifies each checking account.

    Resources may have a schema, which describes the data associated with the
    resource. For example, a checking account might have a current balance (an
    integer) and a social security number (also an integer).

    Keys in a resource's schema are mapped onto the resource class. So a
    checking account instance 'account' would have attributes 'account.balance',
    'account.ssn' etc. Attributes are lazily validated, using the schema, on
    first access.

    A resource's data is loaded lazily, on first attribute access. This,
    combined with lazy attribute validation, means that many resources can be
    iterated, while potentially expensive operations (data loading, attribute
    validation) are put off as long as possible.

    Note:
        You can access the entire validated resource data dict using the
        `validated_data` function, and test full validation using `validate_data`.

    Attributes:
        key (str): Unique identifier of the resource type.
        schema (Schema): Schema for the resource data. Must validate a dict.
            Can be None, in which case the resource does not load any data.
        schema_error (Exception): The exception type to raise on key
            validation failure.
    """
    __metaclass__ = LazyAttributeMeta
    key = None
    schema = None
    schema_error = Exception

    def __init__(self, variables=None):
        self.variables = variables or {}

    @cached_property
    def handle(self):
        """Get the resource handle."""
        return ResourceHandle(self.key, self.variables)

    @cached_property
    def data(self):
        return self._load()

    def _load(self):
        """Load the data associated with the resource.

        You are not expected to cache this data - the resource system does this
        for you.

        If `schema` is None, this signifies that the resource does not load any
        data. In this case you don't need to implement this function - it will
        never be called.

        Returns:
            dict.
        """
        raise NotImplementedError


class ResourceHandle(object):
    """A `Resource` handle.

    A handle uniquely identifies a resource. A handle can be stored and used
    with a `ResourcePool` to retrieve the same resource at a later date.
    """
    def __init__(self, key, variables=None):
        self.key = key
        self.variables = variables or {}

    def to_dict(self):
        return dict(key=self.key, variables=self.variables)

    @classmethod
    def from_dict(cls, d):
        return ResourceHandle(**d)

    def __str__(self):
        return "%s%r" % (self.key, self.variables)

    def __repr__(self):
        return "%s(%r, %r)" % (self.__class__.__name__, self.key, self.variables)

    def __eq__(self, other):
        return (self.key == other.key) and (self.variables == other.variables)

    def __hash__(self):
        return hash((self.key, frozenset(self.variables.items())))


class ResourcePool(object):
    """A resource pool.

    A resource pool manages a set of registered resource types, and acts as a
    resource cache. It will create any resource you ask for - typically
    resources are created via some factory class, which first checks for the
    existence of the resource before creating one from a pool.
    """
    def __init__(self, cache_size=None):
        self.resource_classes = {}
        cache = lru_cache(maxsize=cache_size)
        self.cached_get_resource = cache(self._get_resource)

    def register_resource(self, resource_class):
        resource_key = resource_class.key
        assert issubclass(resource_class, Resource)
        assert resource_key is not None

        cls_ = self.resource_classes.get(resource_key)
        if cls_ and cls_ != resource_class:
            raise ResourceError(
                "Error registering resource class %s: Resource pool has already "
                "registered %r to %s" % (resource_class.__class__.__name__,
                                         resource_key, cls_.__class__.__name__))

        self.resource_classes[resource_key] = resource_class

    def get_resource(self, resource_key, variables=None):
        handle = ResourceHandle(resource_key, variables)
        return self.get_resource_from_handle(handle)

    def get_resource_from_handle(self, resource_handle):
        return self.cached_get_resource(resource_handle)

    def clear_caches(self):
        self.cached_get_resource.cache_clear()

    def _get_resource(self, resource_handle):
        resource_key = resource_handle.key
        resource_class = self.resource_classes.get(resource_key)
        if resource_class is None:
            raise ResourceError("Error getting resource from pool: Unknown "
                                "resource type %r" % resource_key)

        return resource_class(resource_handle.variables)
