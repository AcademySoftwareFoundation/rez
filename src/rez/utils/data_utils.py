"""
Utilities related to managing data types.
"""
from rez.vendor.enum import Enum
from rez.vendor.schema.schema import Schema, Optional
from string import Formatter
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


class StringFormatType(Enum):
    """Behaviour of key expansion when using `ObjectStringFormatter`."""
    error = 1  # raise exception on unknown key
    empty = 2  # expand to empty on unknown key
    unchanged = 3  # leave string unchanged on unknown key


class ObjectStringFormatter(Formatter):
    """String formatter for objects.

    This formatter will expand any reference to an object's attributes.
    """
    error = StringFormatType.error
    empty = StringFormatType.empty
    unchanged = StringFormatType.unchanged

    def __init__(self, instance, pretty=False, expand=StringFormatType.error):
        """Create a formatter.

        Args:
            instance: The object to format with.
            pretty: If True, references to non-string attributes such as lists
                are converted to basic form, with characters such as brackets
                and parentheses removed.
            expand: `StringFormatType`.
        """
        self.instance = instance
        self.pretty = pretty
        self.expand = expand

    def convert_field(self, value, conversion):
        if self.pretty:
            if value is None:
                return ''
            elif isinstance(value, list):
                def _str(x):
                    if isinstance(x, unicode):
                        return x
                    else:
                        return str(x)

                return ' '.join(map(_str, value))

        return Formatter.convert_field(self, value, conversion)

    def get_field(self, field_name, args, kwargs):
        if self.expand == StringFormatType.error:
            return Formatter.get_field(self, field_name, args, kwargs)
        try:
            return Formatter.get_field(self, field_name, args, kwargs)
        except (AttributeError, KeyError, TypeError):
            reg = re.compile("[^\.\[]+")
            try:
                key = reg.match(field_name).group()
            except:
                key = field_name
            if self.expand == StringFormatType.empty:
                return ('', key)
            else:  # StringFormatType.unchanged
                return ("{%s}" % field_name, key)

    def get_value(self, key, args, kwds):
        if isinstance(key, str):
            if key:
                try:
                    # Check explicitly passed arguments first
                    return kwds[key]
                except KeyError:
                    pass

                try:
                    # we deliberately do not call hasattr() first - hasattr()
                    # silently catches exceptions from properties.
                    return getattr(self.instance, key)
                except AttributeError:
                    pass

                return self.instance[key]
            else:
                raise ValueError("zero length field name in format")
        else:
            return Formatter.get_value(self, key, args, kwds)


class StringFormatMixin(object):
    def format(self, s, pretty=False, expand=StringFormatType.error):
        """Format a string.

        Args:
            s (str): String to format, eg "hello {name}"
            pretty: If True, references to non-string attributes such as lists
                are converted to basic form, with characters such as brackets
                and parenthesis removed.
            expand: What to expand references to nonexistent attributes to:
                - None: raise an exception;
                - 'empty': expand to an empty string;
                - 'unchanged': leave original string intact, ie '{key}'

        Returns:
            The formatting string.
        """
        formatter = ObjectStringFormatter(self, pretty=pretty, expand=expand)
        return formatter.format(s)


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
