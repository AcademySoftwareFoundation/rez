"""
Utilities related to managing data types.
"""
from rez.vendor.schema.schema import Schema, Optional
from threading import Lock
import re


class cached_property(object):
    """simple property caching descriptor."""
    def __init__(self, func, name=None):
        self.func = func
        self.name = name or func.__name__

    def __get__(self, instance, owner=None):
        if instance is None:
            return self

        result = self.func(instance)
        setattr(instance, self.name, result)
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


class AttributeForwardMeta(type):
    """Metaclass for forwarding attributes of class member `wrapped` onto the
    parent class.

    If the parent class already contains an attribute of the same name,
    forwarding is skipped for that attribute.

    The class must contain:
    - keys (list of str): The attributes to be forwarded.

    Example:

        >>> class Foo(object):
        >>>     def __init__(self):
        >>>         self.a = "a_from_foo"
        >>>         self.b = "b_from_foo"
        >>>
        >>> class Bah(object):
        >>>     __metaclass__ = AttributeForwardMeta
        >>>     keys = ["a", "b"]
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
        >>> print y.a
        a_from_bah
        >>> print y.b
        b_from_foo
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
            return getattr(self.wrapped, key, None)

        return property(func)


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
          your own '_validate_key' function.
        - '_schema_keys' (frozenset): Keys in the schema.
    """
    def __new__(cls, name, parents, members):
        def _defined(x):
            return x in members or any(hasattr(p, x) for p in parents)

        schema = members.get('schema')
        keys = set()

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
            self.validated_data()
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


def get_object_completions(instance, prefix, types=None, instance_types=None):
    """Get completion strings based on an object's attributes/keys.

    Completion also works on dynamic attributes (eg implemented via
    __getattr__) if they are iterable.

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
