# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


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
from __future__ import annotations

import importlib.machinery
import sys
from functools import lru_cache, cached_property

# from functools import cached_property
from rez.exceptions import ResourceError, RezError
from rez.utils.logging_ import print_debug
from rez.vendor.schema.schema import Schema, Optional as SchemaOptional
from typing import Any, Generic, TypeVar, TYPE_CHECKING, ClassVar

from rez.utils._mypyc import mypyc_attr

if TYPE_CHECKING:
    # this is not available in typing until 3.11, but due to __future__.annotations
    # we can use it without really importing it
    from typing_extensions import Self


ResourceT = TypeVar("ResourceT", bound="Resource")

_EXTENSION_SUFFIXES = tuple(importlib.machinery.EXTENSION_SUFFIXES)


def _is_compiled_class(cls: type) -> bool:
    """Return True if `cls` is defined in a compiled extension module.

    Note that this also works while the defining module is still being
    initialized (i.e. at class-creation time).

    Known failure modes:

    - Classes synthesized at runtime whose ``__module__`` names a compiled
      module are misclassified as compiled; any injection attempted on them is
      silently skipped (``setattr`` on a native mypyc class raises
      ``TypeError``, so the skip is intentional, but the misclassification
      means the caller may not realise the class was runtime-synthesized).
    - If ``__file__`` is absent (e.g. built-in modules) or the module is
      ``__main__``, the function falls back to returning ``False`` (interpreted).
      A wrong answer in that direction fails loudly: ``setattr`` on a compiled
      class raises ``TypeError`` at class-creation time rather than silently
      applying a broken injection.
    """
    module = sys.modules.get(cls.__module__)
    filename: str | None = getattr(module, "__file__", None) if module is not None else None
    return filename is not None and filename.endswith(_EXTENSION_SUFFIXES)


# class Resource(object, metaclass=LazyAttributeMeta):

@mypyc_attr(allow_interpreted_subclasses=True)
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
    """
    #: Unique identifier of the resource type.
    key: ClassVar[str]  # type: ignore[assignment]
    #: Schema for the resource data.
    #: Must validate a dict. Can be None, in which case the resource does
    #: not load any data.
    schema: ClassVar[Schema | None] = None
    #: The exception type to raise on key validation failure.
    schema_error: ClassVar[type[RezError]] = RezError

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Add lazily-validated attributes for each key in ``cls.schema``.

        This replicates the behavior of the ``LazyAttributeMeta`` metaclass,
        which cannot be used here because mypyc does not support custom
        metaclasses on compiled classes. Compiled (native) subclasses have
        their schema attributes explicitly written out instead (see the
        "AUTO-GENERATED METHODS" sections, created with
        ``rez.utils.data_utils.write_module_dynamic_members``), so they are
        skipped here; interpreted subclasses get the attributes injected at
        class-creation time, exactly as the metaclass did.
        """
        super().__init_subclass__(**kwargs)

        # use a `type`-typed alias for dunder access, which mypyc disallows
        # on the native class object
        klass: type = cls

        if _is_compiled_class(klass):
            # a compiled subclass: attributes are explicitly generated
            return

        schema = vars(klass).get("schema")
        if not schema:
            return

        from rez.utils.data_utils import LazyAttributeMeta

        for key, key_schema in schema._schema.items():
            optional = isinstance(key, SchemaOptional)
            while isinstance(key, Schema):
                key = key._schema
            if not isinstance(key, str):
                continue

            if hasattr(klass, key):
                attr = "_%s" % key
                if hasattr(klass, attr):
                    # both forms already provided - eg by the explicitly
                    # generated members of a compiled parent class, whose
                    # getters resolve the key's schema at runtime via
                    # `_get_item`, so they remain valid for this subclass's
                    # schema.
                    continue
            else:
                attr = key

            prop = LazyAttributeMeta._make_getter(key, attr, optional, key_schema)
            # functools.cached_property requires __set_name__, which python
            # only calls for descriptors present at class creation; this is a
            # post-creation setattr, so call it explicitly
            prop.__set_name__(klass, attr)
            setattr(klass, attr, prop)

    @classmethod
    def normalize_variables(cls, variables: dict[str, Any]) -> dict[str, Any]:
        """Give subclasses a chance to standardize values for certain variables
        """
        return variables

    def __init__(self, variables: dict[str, Any] | None = None) -> None:
        self.variables = self.normalize_variables(variables or {})

    @cached_property
    def _schema_dict(self) -> dict[str, Any]:
        """Unwrap the Schema into a dict where keys are strings"""
        assert self.schema is not None
        d = {}
        for key, value in self.schema._schema.items():
            while isinstance(key, Schema):
                key = key._schema
            if isinstance(key, str):
                d[key] = value
        return d

    @cached_property
    def _schema_keys(self) -> frozenset[str]:
        if self.schema:
            return frozenset(self._schema_dict.keys())
        else:
            return frozenset()

    def validate_data(self) -> None:
        self.validated_data()

    def validated_data(self) -> dict[str, Any] | None:
        if self.schema:
            d = {}
            for key in self._schema_keys:
                d[key] = getattr(self, key)

            # arbitrary keys
            if self._data:
                akeys = set(self._data.keys()) - set(d.keys())
                for akey in akeys:
                    d[akey] = self._data[akey]

            return d
        else:
            return None

    def _validate_key_impl(self, key: str, attr: Any, schema: Any) -> Any:
        schema_ = schema if isinstance(schema, Schema) else Schema(schema)
        try:
            return schema_.validate(attr)
        except Exception as e:
            raise self.schema_error("Validation of key %r failed: "
                                    "%s" % (key, str(e)))

    def _get_item(self, key: str, optional: bool) -> Any:
        if self._data is None or key not in self._data:
            if optional:
                return None
            raise self.schema_error("Required key is missing: %r" % key)

        attr = self._data[key]
        key_schema = self._schema_dict[key]
        if hasattr(self, "_validate_key"):
            return self._validate_key(key, attr, key_schema)
        else:
            return self._validate_key_impl(key, attr, key_schema)

    @cached_property
    def handle(self) -> ResourceHandle:
        """Get the resource handle."""
        return ResourceHandle(self.key, self.variables)

    @cached_property
    def _data(self) -> dict[str, Any] | None:
        from rez.config import config

        if not self.schema:
            data = None
        else:
            data = self._load()
            if config.debug("resources"):
                print_debug("Loaded resource: %s" % str(self))

        return data

    def get(self, key: str, default: Any | None = None) -> Any | None:
        """Get the value of a resource variable."""
        return self.variables.get(key, default)

    def __str__(self) -> str:
        return "%s%r" % (self.key, self.variables)

    def __repr__(self) -> str:
        return "%s(%r)" % (self.__class__.__name__, self.variables)

    def __hash__(self) -> int:
        return hash((self.__class__, self.handle))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Resource):
            return NotImplemented
        return (self.handle == other.handle)

    def _load(self) -> dict[str, Any] | None:
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

    def __init__(self, key: str, variables: dict[str, Any] | None = None) -> None:
        self.key = key
        self.variables = variables or {}

    def get(self, key: str, default: Any | None = None) -> Any:
        """Get the value of a resource variable."""
        return self.variables.get(key, default)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the contents of this resource handle to a dictionary
        representation.
        """
        return dict(key=self.key, variables=self.variables)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Self:
        """Return a `ResourceHandle` instance from a serialized dict

        This should ONLY be used with dicts created with ResourceHandle.to_dict;
        if you wish to create a "new" ResourceHandle, you should do it through
        PackageRepository.make_resource_handle
        """
        return cls(**d)

    def _hashable_repr(self) -> tuple[str, tuple]:
        return (
            self.key,
            tuple(sorted(self.variables.items()))
        )

    def __str__(self) -> str:
        return str(self.to_dict())

    def __repr__(self) -> str:
        return "%s(%r, %r)" % (self.__class__.__name__, self.key, self.variables)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ResourceHandle):
            return NotImplemented
        return (self.key == other.key) and (self.variables == other.variables)

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __hash__(self) -> int:
        return hash(self._hashable_repr())


@mypyc_attr(allow_interpreted_subclasses=True)
class ResourcePool(object):
    """A resource pool.

    A resource pool manages a set of registered resource types, and acts as a
    resource cache. It will create any resource you ask for - typically
    resources are created via some factory class, which first checks for the
    existence of the resource before creating one from a pool.
    """

    def __init__(self, cache_size: int | None = None) -> None:
        self.resource_classes: dict[str, type[Resource]] = {}
        cache = lru_cache(maxsize=cache_size)
        self.cached_get_resource = cache(self._get_resource)

    def register_resource(self, resource_class: type[Resource]) -> None:
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

    def get_resource_from_handle(self, resource_handle: ResourceHandle) -> Resource:
        return self.cached_get_resource(resource_handle)

    def clear_caches(self) -> None:
        self.cached_get_resource.cache_clear()

    def get_resource_class(self, resource_key: str) -> type[Resource]:
        resource_class = self.resource_classes.get(resource_key)
        if resource_class is None:
            raise ResourceError("Error getting resource from pool: Unknown "
                                "resource type %r" % resource_key)
        return resource_class

    def _get_resource(self, resource_handle: ResourceHandle) -> Resource:
        resource_class = self.get_resource_class(resource_handle.key)
        return resource_class(resource_handle.variables)


# class ResourceWrapper(Generic[ResourceT], metaclass=AttributeForwardMeta):
@mypyc_attr(allow_interpreted_subclasses=True)
class ResourceWrapper(Generic[ResourceT]):
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
    keys: set[str] | None = None

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Add forwarding properties for each attribute named in ``cls.keys``.

        This replicates the behavior of the ``AttributeForwardMeta`` metaclass,
        which cannot be used here because mypyc does not support custom
        metaclasses on compiled classes. Compiled (native) subclasses have
        their forwarded attributes explicitly written out instead (see the
        "AUTO-GENERATED METHODS" sections, created with
        ``rez.utils.data_utils.write_module_dynamic_members``), so they are
        skipped here; interpreted subclasses get the attributes injected at
        class-creation time, exactly as the metaclass did.
        """
        super().__init_subclass__(**kwargs)

        # use a `type`-typed alias for dunder access, which mypyc disallows
        # on the native class object
        klass: type = cls

        if _is_compiled_class(klass):
            # a compiled subclass: attributes are explicitly generated
            return

        from rez.utils.data_utils import AttributeForwardMeta

        attr_info = AttributeForwardMeta._get_new_attrs(
            dict(vars(klass)), klass.__mro__[1:])
        for key in sorted(attr_info):
            setattr(klass, key, AttributeForwardMeta._make_forwarder(key))

    def __init__(self, resource: ResourceT) -> None:
        self.wrapped = resource

    @property
    def resource(self) -> ResourceT:
        return self.wrapped

    @property
    def handle(self) -> ResourceHandle:
        return self.resource.handle

    @property
    def data(self) -> dict[str, Any] | None:
        return self.resource._data

    def validated_data(self) -> dict[str, Any] | None:
        # provided by LazyAttributeMeta metaclass
        return self.resource.validated_data()  # type: ignore[attr-defined]

    def validate_data(self) -> None:
        # provided by LazyAttributeMeta metaclass
        self.resource.validate_data()  # type: ignore[attr-defined]

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ResourceWrapper):
            return NotImplemented
        return (
            self.__class__ is other.__class__
            and self.resource == other.resource
        )

    def __str__(self) -> str:
        return "%s(%s)" % (self.__class__.__name__, str(self.resource))

    def __repr__(self) -> str:
        return "%s(%r)" % (self.__class__.__name__, self.resource)

    def __hash__(self) -> int:
        return hash((self.__class__, self.resource))
