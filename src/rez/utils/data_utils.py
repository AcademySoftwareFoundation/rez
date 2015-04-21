"""
Utilities related to managing data types.
"""
from rez.vendor.schema.schema import Schema, Optional
from rez.exceptions import RexError
from collections import MutableMapping
from inspect import getsourcelines, getargspec
from threading import Lock
from textwrap import dedent


class _Missing: pass
_missing = _Missing()


class SourceCode(object):
    """Very simple wrapper for python source code."""
    def __init__(self, source):
        self.source = source.rstrip()

    @classmethod
    def from_function(cls, func):
        argspec = getargspec(func)
        if argspec.args or argspec.varargs or argspec.keywords:
            raise RexError('top level functions in python rez package files '
                           'cannot take any arguments')

        # now that we've verified that the func takes no args, can strip out
        # the first line of the sourcecode, with the argspec of the func...
        loc = getsourcelines(func)[0][1:]
        code = dedent(''.join(loc))

        # align lines that start with a comment (#)
        codelines = code.split('\n')
        linescount = len(codelines)
        for i, line in enumerate(codelines):
            if line.startswith('#'):
                nextindex = i+1 if i < linescount else i-1
                nextline = codelines[nextindex]
                while nextline.startswith('#'):
                    nextline = codelines[nextindex]
                    nextindex = nextindex+1 if nextindex < linescount else nextindex-1
                firstchar = len(nextline)-len(nextline.lstrip())
                codelines[i] = '%s%s' % (nextline[:firstchar], line)

        code = '\n'.join(codelines).rstrip()
        code = dedent(code)

        value = SourceCode.__new__(SourceCode)
        value.source = code
        return value

    def corrected_for_indent(self):
        if self.source and self.source[0] in (' ', '\t'):
            new_source = "if True:\n" + self.source
            return SourceCode(new_source)
        else:
            return self

    def __eq__(self, other):
        return (isinstance(other, SourceCode)
                and other.source == self.source)

    def __ne__(self, other):
        return not (other == self)

    def __str__(self):
        return self.source

    def __repr__(self):
        return "%s(%r)" % (self.__class__.__name__, self.source)


class cached_property(object):
    """Simple property caching descriptor.

    Example:

        >>> class Foo(object):
        >>>     @cached_property
        >>>     def bah(self):
        >>>         print 'bah'
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


class cached_class_property(object):
    """Simple class property caching descriptor.

    Example:

        >>> class Foo(object):
        >>>     @cached_class_property
        >>>     def bah(cls):
        >>>         print 'bah'
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
        result = getattr(owner, name, _missing)
        if result is _missing:
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
    for key, value in d.iteritems():
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


class AttributeForwardMeta(type):
    """Metaclass for forwarding attributes of class member `wrapped` onto the
    parent class.

    If the parent class already contains an attribute of the same name,
    forwarding is skipped for that attribute. If the wrapped object does not
    contain an attribute, the forwarded value will be None.

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
        >>> print y.a
        a_from_bah
        >>> print y.b
        b_from_foo
        >>> print y.c
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
            return getattr(self.wrapped, key, None)

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
            if key not in self._data:
                if optional:
                    return None
                raise self.schema_error("Required key is missing: %r" % key)

            attr = self._data[key]
            if hasattr(self, "_validate_key"):
                return self._validate_key(key, attr, key_schema)
            else:
                return self._validate_key_impl(key, attr, key_schema)

        return cached_property(getter, name=attribute)
