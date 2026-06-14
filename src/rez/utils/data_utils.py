# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Utilities related to managing data types.
"""
from __future__ import annotations

import os.path
import json
import functools
from functools import cached_property
import re

from rez.vendor.schema.schema import Schema, Optional, Or, And
from threading import Lock
from typing import Any, Callable, Generic, Mapping, MutableMapping, TypeVar, TYPE_CHECKING, NoReturn

if TYPE_CHECKING:
    import rez.config
    from rez.utils.resources import ResourceWrapper

T = TypeVar("T")


class ModifyList(object):
    """List modifier, used in `deep_update`.

    This can be used in configs to add to list-based settings, rather than
    overwriting them.
    """

    def __init__(self, append=None, prepend=None) -> None:
        for v in (prepend, append):
            if v is not None and not isinstance(v, list):
                raise ValueError("Expected list in ModifyList, not %r" % v)

        self.prepend = prepend
        self.append = append

    def apply(self, v):
        if v is None:
            v = []
        elif not isinstance(v, list):
            raise ValueError("Attempted to apply ModifyList to non-list: %r" % v)

        return (self.prepend or []) + v + (self.append or [])


class DelayLoad(object):
    """Used in config to delay load a config value from anothe file.

    Supported formats:

    - yaml (``*.yaml``, ``*.yml``)
    - json (``*.json``)
    """

    def __init__(self, filepath: str) -> None:
        self.filepath = os.path.expanduser(filepath)

    def __str__(self) -> str:
        return "%s(%s)" % (self.__class__.__name__, self.filepath)

    def get_value(self):
        def _yaml(contents):
            from rez.vendor import yaml
            return yaml.load(contents, Loader=yaml.FullLoader)

        def _json(contents):
            import json
            return json.loads(contents)

        ext = os.path.splitext(self.filepath)[-1]
        if ext in (".yaml", "yml"):
            loader = _yaml
        elif ext == ".json":
            loader = _json
        else:
            raise ValueError(
                "Error in DelayLoad - unsupported file format %s"
                % self.filepath
            )

        try:
            with open(self.filepath) as f:
                contents = f.read()
        except Exception as e:
            raise ValueError(
                "Error reading %s: %s: %s"
                % (self, e.__class__.__name__, str(e))
            )

        try:
            return loader(contents)
        except Exception as e:
            raise ValueError(
                "Error loading from %s: %s: %s"
                % (self, e.__class__.__name__, str(e))
            )


def remove_nones(**kwargs: Any | None) -> dict[str, Any]:
    """Return diict copy with nones removed.
    """
    return dict((k, v) for k, v in kwargs.items() if v is not None)


def deep_update(dict1: dict, dict2: dict) -> None:
    """Perform a deep merge of `dict2` into `dict1`.

    Note that `dict2` and any nested dicts are unchanged.

    Supports `ModifyList` instances.
    """
    def flatten(v):
        if isinstance(v, ModifyList):
            return v.apply([])
        elif isinstance(v, dict):
            return dict((k, flatten(v_)) for k, v_ in v.items())
        else:
            return v

    def merge(v1, v2):
        if isinstance(v1, dict) and isinstance(v2, dict):
            deep_update(v1, v2)
            return v1
        elif isinstance(v2, ModifyList):
            v1 = flatten(v1)
            return v2.apply(v1)
        else:
            return flatten(v2)

    for k1, v1 in dict1.items():
        if k1 not in dict2:
            dict1[k1] = flatten(v1)

    for k2, v2 in dict2.items():
        v1 = dict1.get(k2)

        if v1 is KeyError:
            dict1[k2] = flatten(v2)
        else:
            dict1[k2] = merge(v1, v2)


def deep_del(data: dict, fn) -> dict:
    """Create dict copy with removed items.

    Recursively remove items where fn(value) is True.

    Returns:
        dict: New dict with matching items removed.
    """
    result = {}

    for k, v in data.items():
        if not fn(v):
            if isinstance(v, dict):
                result[k] = deep_del(v, fn)
            else:
                result[k] = v

    return result


def get_dict_diff(d1: dict, d2: dict) -> tuple[list, list, list]:
    """Get added/removed/changed keys between two dicts.

    Each key in the return value is a list, which is the namespaced key that
    was affected.

    Returns:
        tuple: 3-tuple:
        - list of added keys;
        - list of removed key;
        - list of changed keys.
    """
    def _diff(d1_, d2_, namespace):
        added = []
        removed = []
        changed = []

        for k1, v1 in d1_.items():
            if k1 not in d2_:
                removed.append(namespace + [k1])
            else:
                v2 = d2_[k1]
                if v2 != v1:
                    if isinstance(v1, dict) and isinstance(v2, dict):
                        namespace_ = namespace + [k1]
                        added_, removed_, changed_ = _diff(v1, v2, namespace_)
                        added.extend(added_)
                        removed.extend(removed_)
                        changed.extend(changed_)
                    else:
                        changed.append(namespace + [k1])

        for k2 in d2_.keys():
            if k2 not in d1_:
                added.append(namespace + [k2])

        return added, removed, changed

    return _diff(d1, d2, [])


def get_dict_diff_str(d1: dict, d2: dict, title: str) -> str:
    """Returns same as `get_dict_diff`, but as a readable string.
    """
    added, removed, changed = get_dict_diff(d1, d2)
    lines = [title]

    if added:
        lines.append("Added attributes: %s"
                     % ['.'.join(x) for x in added])
    if removed:
        lines.append("Removed attributes: %s"
                     % ['.'.join(x) for x in removed])
    if changed:
        lines.append("Changed attributes: %s"
                     % ['.'.join(x) for x in changed])

    return '\n'.join(lines)


class cached_class_property(Generic[T]):
    """Simple class property caching descriptor.

    Example:

        >>> class Foo(object):
        >>>     @cached_class_property
        >>>     def bah(cls):
        >>>         print('bah')
        >>>         return 1
        >>>
        >>> Foo.bah
        bah
        1
        >>> Foo.bah
        1
    """

    def __init__(self, func: Callable[[Any], T], name=None) -> None:
        self.func = func
        # Make sure that Sphinx autodoc can follow and get the docstring from our wrapped function.
        # TODO: Doesn't work...
        functools.update_wrapper(self, func)  # type: ignore[arg-type]

    def __get__(self, instance: object, owner: type | None = None) -> T:
        assert owner
        name = "_class_property_" + self.func.__name__
        result: T | type[KeyError] = getattr(owner, name, KeyError)

        if result is KeyError:
            result = self.func(owner)
            setattr(owner, name, result)
        return result  # type: ignore[return-value]


class LazySingleton(Generic[T]):
    """A threadsafe singleton that initialises when first referenced."""

    def __init__(self, instance_class: type[T], *nargs: Any, **kwargs: Any) -> None:
        self.instance_class = instance_class
        self.nargs = nargs
        self.kwargs = kwargs
        self.lock = Lock()
        self.instance: T | None = None

    def __call__(self) -> T:
        if self.instance is None:
            try:
                self.lock.acquire()
                if self.instance is None:
                    self.instance = self.instance_class(*self.nargs, **self.kwargs)
                    self.nargs = None
                    self.kwargs = None
            finally:
                self.lock.release()
        return self.instance


class AttrDictWrapper(MutableMapping[str, Any]):
    """Wrap a custom dictionary with attribute-based lookup::

        >>> d = {'one': 1}
        >>> dd = AttrDictWrapper(d)
        >>> assert dd.one == 1
        >>> ddd = dd.copy()
        >>> ddd.one = 2
        >>> assert ddd.one == 2
        >>> assert dd.one == 1
        >>> assert d['one'] == 1
    """

    def __init__(self, data=None) -> None:
        self.__dict__['_data'] = {} if data is None else data

    @property
    def _data(self) -> dict:
        return self.__dict__['_data']

    def __getattr__(self, attr: str) -> Any:
        if attr.startswith('__') and attr.endswith('__'):
            d = self.__dict__
        else:
            d = self._data
        try:
            return d[attr]
        except KeyError:
            raise AttributeError("'%s' object has no attribute '%s'"
                                 % (self.__class__.__name__, attr))

    def __setattr__(self, attr: str, value) -> None:
        # For things like '__class__', for instance
        if attr.startswith('__') and attr.endswith('__'):
            super(AttrDictWrapper, self).__setattr__(attr, value)
        self._data[attr] = value

    def __getitem__(self, key: str):
        return self._data[key]

    def __setitem__(self, key: str, value) -> None:
        self._data[key] = value

    def __delitem__(self, key: str) -> None:
        del self._data[key]

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def __iter__(self):
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __str__(self) -> str:
        return str(self._data)

    def __repr__(self) -> str:
        return "%s(%r)" % (self.__class__.__name__, self._data)

    def copy(self):
        return self.__class__(self._data.copy())


class RO_AttrDictWrapper(AttrDictWrapper):
    """Read-only version of AttrDictWrapper."""

    def __setattr__(self, attr: str, value: object) -> NoReturn:
        self[attr]  # may raise 'no attribute' error
        raise AttributeError("'%s' object attribute '%s' is read-only"
                             % (self.__class__.__name__, attr))


def convert_dicts(d: Mapping, to_class: type[MutableMapping] = AttrDictWrapper,
                  from_class: type[MutableMapping] = dict) -> MutableMapping:
    """Recursively convert dict and UserDict types.

    Note that `d` is unchanged.

    Args:
        to_class (type): Dict-like type to convert values to, usually UserDict
            subclass, or dict.
        from_class (type): Dict-like type to convert values from. If a tuple,
            multiple types are converted.

    Returns:
        Converted data as `to_class` instance.
    """
    d_ = to_class()
    for key, value in d.items():
        if isinstance(value, from_class):
            d_[key] = convert_dicts(value, to_class=to_class,
                                    from_class=from_class)
        else:
            d_[key] = value
    return d_


def get_object_completions(instance: object, prefix: str,
                           types: tuple[type, ...] | None = None,
                           instance_types: tuple[type, ...] | None = None) -> list[str]:
    """Get completion strings based on an object's attributes/keys.

    Completion also works on dynamic attributes (eg implemented via __getattr__)
    if they are iterable.

    Args:
        instance (object): Object to introspect.
        prefix (str): Prefix to match, can be dot-separated to access nested
            attributes.
        types (tuple): Attribute types to match, any if None.
        instance_types (tuple): Class types to recurse into when a dotted
            prefix is given, any if None.

    Returns:
        List of strings.
    """
    word_toks = []
    toks = prefix.split('.')
    while len(toks) > 1:
        attr = toks[0]
        toks = toks[1:]
        word_toks.append(attr)
        try:
            instance = getattr(instance, attr)
        except AttributeError:
            return []
        if instance_types and not isinstance(instance, instance_types):
            return []

    prefix = toks[-1]
    words = []

    attrs = dir(instance)
    try:
        for attr in instance:
            if isinstance(attr, str):
                attrs.append(attr)
    except TypeError:
        pass

    for attr in attrs:
        if attr.startswith(prefix) and not attr.startswith('_') \
                and not hasattr(instance.__class__, attr):
            value = getattr(instance, attr)
            if types and not isinstance(value, types):
                continue
            if not callable(value):
                words.append(attr)

    qual_words = ['.'.join(word_toks + [x]) for x in words]

    if len(words) == 1 and value is not None and \
            (instance_types is None or isinstance(value, instance_types)):
        qual_word = qual_words[0]
        words = get_object_completions(value, '', types)
        for word in words:
            qual_words.append("%s.%s" % (qual_word, word))

    return qual_words


def convert_json_safe(value: Any) -> Any:
    """Convert data to JSON safe values.

    Anything not representable (eg python objects) will be stringified.
    """
    try:
        _ = json.dumps(value)  # noqa
        return value
    except TypeError:
        pass

    if isinstance(value, (list, tuple, set)):
        return type(value)(convert_json_safe(x) for x in value)

    if isinstance(value, dict):
        return type(value)(
            (convert_json_safe(k), convert_json_safe(v))
            for k, v in value.items()
        )

    return str(value)


class AttributeForwardMeta(type):
    """Metaclass for forwarding attributes of class member `wrapped` onto the
    parent class.

    If the parent class already contains an attribute of the same name,
    forwarding is skipped for that attribute. If the wrapped object does not
    contain an attribute, the forwarded value will be None.

    If the parent class contains method '_wrap_forwarded', then forwarded values
    are passed to this function, and the return value becomes the attribute
    value.

    The class must contain:
    - keys (list of str): The attributes to be forwarded.

    Example:

        >>> class Foo(object):
        >>>     def __init__(self):
        >>>         self.a = "a_from_foo"
        >>>         self.b = "b_from_foo"
        >>>
        >>> class Bah(object, metaclass=AttributeForwardMeta):
        >>>     keys = ["a", "b", "c"]
        >>>
        >>>     @property
        >>>     def a(self):
        >>>         return "a_from_bah"
        >>>
        >>>     def __init__(self, child):
        >>>         self.wrapped = child
        >>>
        >>> x = Foo()
        >>> y = Bah(x)
        >>> print(y.a)
        a_from_bah
        >>> print(y.b)
        b_from_foo
        >>> print(y.c)
        None
    """
    def __new__(cls, name: str, parents: tuple[type, ...], members: dict[str, Any]) -> AttributeForwardMeta:
        attr_info = cls._get_new_attrs(members, parents)

        for key in sorted(attr_info):
            members[key] = cls._make_forwarder(key)

        return super(AttributeForwardMeta, cls).__new__(cls, name, parents, members)

    @classmethod
    def _get_new_attrs(cls, members, parents):
        def _defined(x):
            return x in members or any(hasattr(p, x) for p in parents)

        attr_info = {}
        keys = members.get('keys')
        if keys:
            for key in keys:
                if not _defined(key):
                    attr_info[key] = _defined("_wrap_forwarded")
        return attr_info

    @classmethod
    def _make_forwarder(cls, key: str) -> property:
        def func(self: ResourceWrapper) -> Any:
            value = getattr(self.wrapped, key, None)

            if hasattr(self, "_wrap_forwarded"):
                value = self._wrap_forwarded(key, value)

            return value

        return property(func)

    @classmethod
    def get_getters(cls, typ) -> dict[str, dict]:
        result = {}
        attr_info = cls._get_new_attrs(typ.__dict__, typ.mro())

        for attr in sorted(attr_info):
            has_wrap_forwarded = attr_info[attr]
            s = "    @property\n"
            s += "    def {key}(self) -> {typestr}:\n"

            if has_wrap_forwarded:
                s += "        return self._wrap_forwarded('{key}', self.wrapped.{key})\n"
            else:
                s += "        return self.wrapped.{key}\n"
            s += "\n"
            result[attr] = {"key": attr, "template": s}
        return result


class LazyAttributeMeta(type):
    """Metaclass for adding properties to a class for accessing top-level keys
    in its `_data` dictionary, and validating them on first reference.

    Property names are derived from the keys of the class's `schema` object.
    If a schema key is optional, then the class property will evaluate to None
    if the key is not present in `_data`.

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
          your own '_validate_key' function;
        - '_schema_keys' (frozenset): Keys in the schema.
    """
    def __new__(cls, name: str, parents: tuple[type, ...], members: dict[str, Any]) -> LazyAttributeMeta:
        attr_info, add_extras = cls._get_new_attrs(members, parents)
        if attr_info:
            for attr, info in attr_info.items():
                members[attr] = cls._make_getter(info["key"], info["attr"],
                                                 info["optional"], info["key_schema"])
        if add_extras:
            members["validate_data"] = cls._make_validate_data()
            members["validated_data"] = cls._make_validated_data()
            members["_validate_key_impl"] = cls._make_validate_key_impl()
            members["_schema_keys"] = frozenset(attr_info)

        return super(LazyAttributeMeta, cls).__new__(cls, name, parents, members)

    @classmethod
    def _get_new_attrs(cls, members, parents):
        def _defined(x: str) -> bool:
            return x in members or any(hasattr(p, x) for p in parents)

        schema = members.get('schema')
        attr_info = {}
        if schema:
            schema_dict = schema._schema
            for key, key_schema in schema_dict.items():
                optional = isinstance(key, Optional)
                while isinstance(key, Schema):
                    key = key._schema
                if isinstance(key, str):
                    if _defined(key):
                        attr = "_%s" % key
                        if _defined(attr):
                            raise Exception("Couldn't make fallback attribute "
                                            "%r, already defined" % attr)
                    else:
                        attr = key
                    attr_info[attr] = {
                        "key": key, "attr": attr, "optional": optional, "key_schema": key_schema,
                    }

        return attr_info, schema or not _defined("schema")

    @classmethod
    def _make_validate_data(cls) -> Callable[[Any], None]:
        def func(self) -> None:
            self.validated_data()
        return func

    @classmethod
    def _make_validated_data(cls) -> Callable[[Any], dict[str, Any] | None]:
        def func(self: Any) -> dict[str, Any] | None:
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

        return func

    @classmethod
    def _make_validate_key_impl(cls) -> Callable[[Any, str, str, Schema], dict[str, Any]]:
        def func(self: Any, key: str, attr: str, schema: Schema) -> dict[str, Any]:
            schema_ = schema if isinstance(schema, Schema) else Schema(schema)
            try:
                return schema_.validate(attr)
            except Exception as e:
                raise self.schema_error("Validation of key %r failed: "
                                        "%s" % (key, str(e)))
        return func

    @classmethod
    def _make_getter(cls, key: str, attribute: str, optional: bool, key_schema: rez.config.Setting) -> cached_property:

        def getter(self):
            if key not in (self._data or {}):
                if optional:
                    return None
                raise self.schema_error("Required key is missing: %r" % key)

            attr = self._data[key]
            if hasattr(self, "_validate_key"):
                return self._validate_key(key, attr, key_schema)
            else:
                return self._validate_key_impl(key, attr, key_schema)

        prop = cached_property(getter)
        # prop._getter_info = {"key": key, "optional": optional, "schema": key_schema}
        return prop

    @classmethod
    def get_getters(cls, typ, extra_members: dict | None = None):
        result = {}
        members = extra_members.copy() or {}
        members.update(typ.__dict__)
        attr_info, make_extras = cls._get_new_attrs(members, typ.mro())
        for name in sorted(attr_info):
            info = attr_info[name]
            key = info["key"]

            typestr = get_typing_typestr(info["key_schema"])

            optional = info["optional"]
            if optional:
                typestr = f"{typestr} | None"

            s = "    @cached_property\n"
            s += "    def {name}(self) -> {typestr}:\n"
            s += f"        return self._get_item({repr(key)}, {optional})\n"
            s += "\n"
            result[key] = {"key": key, "name": name, "typestr": typestr, "template": s}
        return result


BEGIN = "    # -- BEGIN AUTO-GENERATED METHODS --\n"
END = "    # -- END AUTO-GENERATED METHODS --\n"


def write_module_dynamic_members(module, wrapped=None):
    import inspect

    wrapped = wrapped if wrapped else {}

    for name, obj in inspect.getmembers(module):
        if isinstance(obj, type) and obj.__module__ == module.__name__:
            write_cls_dynamic_members(obj, wrapped_cls=wrapped.get(name))


def remove_dynamic_members(module_name: str):
    import importlib.util

    spec = importlib.util.find_spec(module_name)
    assert spec and spec.origin

    skip = False
    lines = []
    with open(spec.origin) as f:
        for line in f:
            if line == END:
                skip = False

            if skip:
                continue
            else:
                lines.append(line)

            if line == BEGIN:
                skip = True
    with open(spec.origin, "w") as f:
        f.writelines(lines)


def write_cls_dynamic_members(obj, wrapped_cls=None, source_cls=None):
    name = obj.__name__

    print(name)

    if source_cls is None:
        source_cls = obj

    forward_getters = AttributeForwardMeta.get_getters(source_cls)
    lazy_getters = LazyAttributeMeta.get_getters(source_cls, forward_getters)

    if forward_getters or lazy_getters:
        # FIXME: I think we only need to do this if forward_getters exists
        if wrapped_cls and wrapped_cls.schema is not None:
            schema = wrapped_cls.schema._schema
            key_schemas = {}
            for key, value in schema.items():
                if isinstance(key, Optional):
                    optional = True
                    key = key._schema
                else:
                    optional = False
                key_schemas[key] = (value, optional)
        else:
            key_schemas = None
            optional = None

        members = []
        for key in sorted(forward_getters):
            data = forward_getters[key]

            typestr = "typing.Any"
            if key_schemas is not None:
                info = key_schemas.get(key)
                if info:
                    key_schema, optional = info
                    typestr = get_typing_typestr(key_schema)
                    if optional:
                        typestr = f"{typestr} | None"

            data["typestr"] = typestr
            members.append(data["template"].format(**data))

        for key in sorted(lazy_getters):
            data = lazy_getters[key]
            members.append(data["template"].format(**data))

        assert members

        import sys

        module_path = sys.modules[obj.__module__].__file__
        print(f"  Adding {len(members)} members to {module_path}")

        with open(module_path, "r") as f:
            all_lines = f.readlines()

        in_class = False
        reg = re.compile(rf"class {obj.__name__}\b")
        for i, line in enumerate(all_lines):
            if in_class and line == BEGIN:
                print("  Adding lines")
                all_lines[i + 1: i + 1] = members
                break
            if reg.match(line):
                in_class = True
        else:
            raise RuntimeError("Could not find BEGIN")

        with open(module_path, "w") as f:
            f.writelines(all_lines)


def write_all_dynamic_members():
    """
    ResourceWrapper                                             (metaclass=AttributeForwardMeta)
        PackageRepositoryResourceWrapper
            PackageBaseResourceWrapper
                Package                          [keys]
                    DeveloperPackage
                Variant                          [keys]
            PackageFamily                        [keys]
    Resource                                                     (metaclass=LazyAttributeMeta)
        PackageRepositoryResource
            PackageFamilyResource
                MemoryPackageFamilyResource
                FileSystemPackageFamilyResource
                FileSystemCombinedPackageFamilyResource [schema]
            PackageResource
                VariantResource
                    VariantResourceHelper        [keys] [schema] (metaclass=(AttributeForwardMeta, LazyAttributeMeta))
                        MemoryVariantResource
                        FileSystemVariantResource
                        FileSystemCombinedVariantResource
                PackageResourceHelper
                    MemoryPackageResource               [schema]
                    FileSystemPackageResource           [schema]
                    FileSystemCombinedPackageResource   [schema]

    VariantResourceHelper is the first in its hierarchy to introduce self.wrapped and therefore the
    AttributeForwardMeta, which adds the wrapped lookups
    """

    remove_dynamic_members("rez.packages")
    remove_dynamic_members("rez.package_resources")
    remove_dynamic_members("rezplugins.package_repository.filesystem")

    import rez.packages
    import rez.package_resources
    import rezplugins.package_repository.memory
    import rezplugins.package_repository.filesystem

    write_cls_dynamic_members(rez.packages.Package,
                              wrapped_cls=rezplugins.package_repository.memory.MemoryPackageResource)

    write_cls_dynamic_members(rez.packages.Variant,
                              wrapped_cls=rez.package_resources.VariantResourceHelper)

    write_cls_dynamic_members(rez.packages.PackageFamily,
                              wrapped_cls=rezplugins.package_repository.memory.MemoryPackageFamilyResource)

    # we graft this from MemoryPackageResource because all the children have the same schema, and
    # putting the members on the base class makes mypy happy
    write_cls_dynamic_members(rez.package_resources.PackageResourceHelper,
                              source_cls=rezplugins.package_repository.memory.MemoryPackageResource)

    write_cls_dynamic_members(rez.package_resources.VariantResourceHelper,
                              wrapped_cls=rezplugins.package_repository.memory.MemoryPackageResource)

    write_cls_dynamic_members(rezplugins.package_repository.filesystem.FileSystemCombinedPackageFamilyResource)

    return

    # FIXME: based on the hierarchy above, we should be able to run this on the
    #  five specific classes that introduce keys or schema attributes.
    import rez.utils.resources
    import rez.package_repository
    import rez.package_resources
    import rez.packages
    import rezplugins.package_repository.filesystem
    import rezplugins.package_repository.memory
    import rez.config

    write_module_dynamic_members(rez.utils.resources)
    write_module_dynamic_members(rez.package_repository)
    write_module_dynamic_members(
        rez.package_resources,
        # VariantResourceHelper used both AttributeForwardMeta & LazyAttributeMeta.
        # It wraps PackageResourceHelper, but that's abstract so we get the wrapped schema from one of the
        # three concrete subclasses of PackageResourceHelper
        wrapped={"VariantResourceHelper": rezplugins.package_repository.memory.MemoryPackageResource}
    )
    write_module_dynamic_members(
        rez.packages,
        # same story as VariantResourceHelper. yes, they both wrap the same object.  IDK WTF...
        wrapped={
            "Package": rezplugins.package_repository.memory.MemoryPackageResource,
            "Variant": rez.package_resources.VariantResourceHelper,
            "PackageFamily":  rezplugins.package_repository.memory.MemoryPackageFamilyResource,
        }
    )

    write_module_dynamic_members(rezplugins.package_repository.filesystem)
    write_module_dynamic_members(rezplugins.package_repository.memory)
    write_module_dynamic_members(rez.config)


def get_typing_typestr(obj, parent_setting=None):
    import rez.config

    # FIXME: remove parent_setting. it was a failed TypedDict experiment
    if isinstance(obj, Optional):
        return "typing.Optional[{}]".format(get_typing_typestr(obj._schema, parent_setting=parent_setting))
    if isinstance(obj, Schema):
        # FIXME: this is skipping over Optional, which inherits from Schema
        return get_typing_typestr(obj._schema, parent_setting=parent_setting)
    elif isinstance(obj, list):
        return "list[{}]".format(get_typing_typestr(obj[0], parent_setting=parent_setting))
    elif isinstance(obj, dict):
        items = []
        typeddict = True
        all_items = list(obj.items())
        for key, value in all_items:
            optional = False
            if isinstance(key, Optional):
                key = key._schema

                if value is object:
                    # an Optional key where the value is `object` indicates a dict that supports
                    # arbitrary keys. see extensible_schema_dict
                    pass
                    # we don't write this into the TypedDict
                    continue
                else:
                    # a single optional key
                    optional = True

            if len(all_items) == 1 and not isinstance(key, str):
                # case:  dict[X, Y]
                typeddict = False

            key_str = get_typing_typestr(key, parent_setting=parent_setting)
            value_str = get_typing_typestr(value, parent_setting=parent_setting)
            items.append((key_str, value_str, optional))

        if typeddict:
            # FIXME: not supported.  Inlined typedDicts are not fully supported by mypy or other checkers.
            #  This means we'll have to generate TypedDict declarations which will be a PITA
            return "dict[str, typing.Any]"
            # inlined TypedDicts are not a standard feature yet. revisit
            # assert parent_setting is not None
            # if total:
            #     item_strs = []
            #     for key_str, value_str, optional in items:
            #         if optional:
            #             key_str = f"typing.NotRequired[{key_str}]"
            #         item_strs.append(f"{key_str}: {value_str}")
            #     typestr = "{" + ", ".join(item_strs) + "}"
            #     return f"typing.TypedDict({repr(parent_setting)}, {typestr})"
            # else:
            #     item_strs = []
            #     for key_str, value_str, optional in items:
            #         if not optional:
            #             key_str = f"typing.Required[{key_str}]"
            #         item_strs.append(f"{key_str}: {value_str}")
            #     typestr = "{" + ", ".join(item_strs) + "}"
            #     return f"typing.TypedDict({repr(parent_setting)}, {typestr}, total=False)"
        else:
            assert len(items) == 1
            key_str, value_str, optional = items[0]
            return f"dict[{key_str}, {value_str}]"

    elif isinstance(obj, type):
        if issubclass(obj, rez.config.Setting):
            return get_typing_typestr(obj.schema, parent_setting=parent_setting)
        # FIXME: use names to avoid circular import (rez.config imports data_utils)
        # if "Setting" in [t.__name__ for t in obj.mro()]:
        #     return get_typing_typestr(obj.schema, parent_setting=obj.__name__)
        else:
            return obj.__name__
    elif isinstance(obj, Or):
        return "typing.Union[{}]".format(
            ", ".join(get_typing_typestr(x, parent_setting=parent_setting) for x in obj._args))
    elif obj is callable:
        return "typing.Callable"
    elif obj is None:
        return "None"
    elif isinstance(obj, And):
        if len(obj._args) == 2 and isinstance(obj._args[1], rez.config.Use):
            # used to convert a type: e.g. And(str, Use(VersionRange))
            use = obj._args[1]
            if isinstance(use._callable, type):
                newtype = use._callable
            elif isinstance(use, type):
                newtype = use
            else:
                newtype = obj._args[0]
            return get_typing_typestr(newtype, parent_setting=parent_setting)
        return repr(obj)
    elif isinstance(obj, str):
        return repr(obj)
    else:
        # FIXME
        return "typing.Any"
