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
from rez.utils.data_utils import cached_property, AttributeForwardMeta, \
    LazyAttributeMeta
from rez.config import config
from rez.exceptions import ResourceError
from rez.backport.lru_cache import lru_cache
from rez.utils.logging_ import print_debug
from rez.vendor.six import six


class Resource(six.with_metaclass(LazyAttributeMeta, object)):
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
    key = None
    schema = None
    schema_error = Exception

    @classmethod
    def normalize_variables(cls, variables):
        """Give subclasses a chance to standardize values for certain variables
        """
        return variables

    def __init__(self, variables=None):
        self.variables = self.normalize_variables(variables or {})

    @cached_property
    def handle(self):
        """Get the resource handle."""
        return ResourceHandle(self.key, self.variables)

    @cached_property
    def _data(self):
        if not self.schema:
            return None

        data = self._load()
        if config.debug("resources"):
            print_debug("Loaded resource: %s" % str(self))
        return data

    def get(self, key, default=None):
        """Get the value of a resource variable."""
        return self.variables.get(key, default)

    def __str__(self):
        return "%s%r" % (self.key, self.variables)

    def __repr__(self):
        return "%s(%r)" % (self.__class__.__name__, self.variables)

    def __hash__(self):
        return hash((self.__class__, self.handle))

    def __eq__(self, other):
        return (self.handle == other.handle)

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

    def get(self, key, default=None):
        """Get the value of a resource variable."""
        return self.variables.get(key, default)

    def to_dict(self):
        """Serialize the contents of this resource handle to a dictionary
        representation.
        """
        return dict(key=self.key, variables=self.variables)

    @classmethod
    def from_dict(cls, d):
        """Return a `ResourceHandle` instance from a serialized dict

        This should ONLY be used with dicts created with ResourceHandle.to_dict;
        if you wish to create a "new" ResourceHandle, you should do it through
        PackageRepository.make_resource_handle
        """
        return cls(**d)

    def __str__(self):
        return str(self.to_dict())

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
        if cls_:
            if cls_ == resource_class:
                return  # already registered
            else:
                raise ResourceError(
                    "Error registering resource class %s: Resource pool has "
                    "already registered %r to %s"
                    % (resource_class.__class__.__name__, resource_key,
                       cls_.__class__.__name__))

        self.resource_classes[resource_key] = resource_class

    def get_resource_from_handle(self, resource_handle):
        return self.cached_get_resource(resource_handle)

    def clear_caches(self):
        self.cached_get_resource.cache_clear()

    def get_resource_class(self, resource_key):
        resource_class = self.resource_classes.get(resource_key)
        if resource_class is None:
            raise ResourceError("Error getting resource from pool: Unknown "
                                "resource type %r" % resource_key)
        return resource_class

    def _get_resource(self, resource_handle):
        resource_class = self.get_resource_class(resource_handle.key)
        return resource_class(resource_handle.variables)


class ResourceWrapper(six.with_metaclass(AttributeForwardMeta, object)):
    """An object that wraps a resource instance.

    A resource wrapper is useful for two main reasons. First, we can wrap
    several different resources with the one class, giving them a common
    interface. This is useful when the same resource can be loaded from various
    different sources (perhaps a database and the filesystem for example), and
    further common functionality needs to be supplied.

    Second, some resource attributes can be derived from the resource's
    variables, which means the resource's data doesn't need to be loaded to get
    these attributes. The wrapper can provide its own properties that do this,
    avoiding unnecessary data loads.

    You must subclass this class and provide `keys` - the list of attributes in
    the resource that you want to expose in the wrapper. The `schema_keys`
    function is provided to help get a list of keys from a resource schema.
    """
    keys = None

    def __init__(self, resource):
        self.wrapped = resource

    @property
    def resource(self):
        return self.wrapped

    @property
    def handle(self):
        return self.resource.handle

    @property
    def data(self):
        return self.resource._data

    def validated_data(self):
        return self.resource.validated_data()

    def validate_data(self):
        self.resource.validate_data()

    def __eq__(self, other):
        return (self.__class__ == other.__class__
                and self.resource == other.resource)

    def __str__(self):
        return "%s(%s)" % (self.__class__.__name__, str(self.resource))

    def __repr__(self):
        return "%s(%r)" % (self.__class__.__name__, self.resource)

    def __hash__(self):
        return hash((self.__class__, self.resource))


# Copyright 2013-2016 Allan Johns.
#
# This library is free software: you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.
