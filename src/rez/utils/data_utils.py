"""
Utilities related to managing data types.
"""
import os.path
import json

from rez.vendor.schema.schema import Schema, Optional
from threading import Lock
from rez.vendor.six import six

if six.PY2:
    from collections import MutableMapping
else:
    from collections.abc import MutableMapping


basestring = six.string_types[0]


class ModifyList(object):
    """List modifier, used in `deep_update`.

    This can be used in configs to add to list-based settings, rather than
    overwriting them.
    """
    def __init__(self, append=None, prepend=None):
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

        - yaml (*.yaml, *.yml)
        - json (*.json)
    """
    def __init__(self, filepath):
        self.filepath = os.path.expanduser(filepath)

    def __str__(self):
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


def remove_nones(**kwargs):
    """Return diict copy with nones removed.
    """
    return dict((k, v) for k, v in kwargs.items() if v is not None)


def deep_update(dict1, dict2):
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


def deep_del(data, fn):
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


def get_dict_diff(d1, d2):
    """Get added/removed/changed keys between two dicts.

    Each key in the return value is a list, which is the namespaced key that
    was affected.

    Returns:
        3-tuple:
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


def get_dict_diff_str(d1, d2, title):
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


class cached_property(object):
    """Simple property caching descriptor.

    Example:

        >>> class Foo(object):
        >>>     @cached_property
        >>>     def bah(self):
        >>>         print('bah')
        >>>         return 1
        >>>
        >>> f = Foo()
        >>> f.bah
        bah
        1
        >>> f.bah
        1
    """
    def __init__(self, func, name=None):
        self.func = func
        self.name = name or func.__name__

    def __get__(self, instance, owner=None):
        if instance is None:
            return self

        result = self.func(instance)
        try:
            setattr(instance, self.name, result)
        except AttributeError:
            raise AttributeError("can't set attribute %r on %r"
                                 % (self.name, instance))
        return result

    @classmethod
    def uncache(cls, instance, name):
        if hasattr(instance, name):
            delattr(instance, name)


class cached_class_property(object):
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
    def __init__(self, func, name=None):
        self.func = func

    def __get__(self, instance, owner=None):
        assert owner
        name = "_class_property_" + self.func.__name__
        result = getattr(owner, name, KeyError)

        if result is KeyError:
            result = self.func(owner)
            setattr(owner, name, result)
        return result


class LazySingleton(object):
    """A threadsafe singleton that initialises when first referenced."""
    def __init__(self, instance_class, *nargs, **kwargs):
        self.instance_class = instance_class
        self.nargs = nargs
        self.kwargs = kwargs
        self.lock = Lock()
        self.instance = None

    def __call__(self):
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


class AttrDictWrapper(MutableMapping):
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
    def __init__(self, data=None):
        self.__dict__['_data'] = {} if data is None else data

    @property
    def _data(self):
        return self.__dict__['_data']

    def __getattr__(self, attr):
        if attr.startswith('__') and attr.endswith('__'):
            d = self.__dict__
        else:
            d = self._data
        try:
            return d[attr]
        except KeyError:
            raise AttributeError("'%s' object has no attribute '%s'"
                                 % (self.__class__.__name__, attr))

    def __setattr__(self, attr, value):
        # For things like '__class__', for instance
        if attr.startswith('__') and attr.endswith('__'):
            super(AttrDictWrapper, self).__setattr__(attr, value)
        self._data[attr] = value

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        self._data[key] = value

    def __delitem__(self, key):
        del self._data[key]

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)

    def __str__(self):
        return str(self._data)

    def __repr__(self):
        return "%s(%r)" % (self.__class__.__name__, self._data)

    def copy(self):
        return self.__class__(self._data.copy())


class RO_AttrDictWrapper(AttrDictWrapper):
    """Read-only version of AttrDictWrapper."""
    def __setattr__(self, attr, value):
        self[attr]  # may raise 'no attribute' error
        raise AttributeError("'%s' object attribute '%s' is read-only"
                             % (self.__class__.__name__, attr))


def convert_dicts(d, to_class=AttrDictWrapper, from_class=dict):
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


def get_object_completions(instance, prefix, types=None, instance_types=None):
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
            if isinstance(attr, basestring):
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


def convert_json_safe(value):
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

        >>> import six
        >>>
        >>> class Foo(object):
        >>>     def __init__(self):
        >>>         self.a = "a_from_foo"
        >>>         self.b = "b_from_foo"
        >>>
        >>> class Bah(six.with_metaclass(AttributeForwardMeta, object)):
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
    def __new__(cls, name, parents, members):
        def _defined(x):
            return x in members or any(hasattr(p, x) for p in parents)

        keys = members.get('keys')
        if keys:
            for key in keys:
                if not _defined(key):
                    members[key] = cls._make_forwarder(key)

        return super(AttributeForwardMeta, cls).__new__(cls, name, parents, members)

    @classmethod
    def _make_forwarder(cls, key):
        def func(self):
            value = getattr(self.wrapped, key, None)

            if hasattr(self, "_wrap_forwarded"):
                value = self._wrap_forwarded(key, value)

            return value

        return property(func)


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
    def __new__(cls, name, parents, members):
        def _defined(x):
            return x in members or any(hasattr(p, x) for p in parents)

        schema = members.get('schema')
        keys = set()

        if schema:
            schema_dict = schema._schema
            for key, key_schema in schema_dict.items():
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

                    members[attr] = cls._make_getter(key, attr, optional, key_schema)

        if schema or not _defined("schema"):
            members["validate_data"] = cls._make_validate_data()
            members["validated_data"] = cls._make_validated_data()
            members["_validate_key_impl"] = cls._make_validate_key_impl()
            members["_schema_keys"] = frozenset(keys)

        return super(LazyAttributeMeta, cls).__new__(cls, name, parents, members)

    @classmethod
    def _make_validate_data(cls):
        def func(self):
            self.validated_data()
        return func

    @classmethod
    def _make_validated_data(cls):
        def func(self):
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
    def _make_getter(cls, key, attribute, optional, key_schema):
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

        return cached_property(getter, name=attribute)


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
