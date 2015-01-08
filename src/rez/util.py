"""
Misc useful stuff.
"""
import stat
import sys
import atexit
import os
import os.path
import copy
import re
import textwrap
from collections import MutableMapping, defaultdict
from rez import module_root_path
from rez.utils.yaml import dump_yaml
from rez.vendor.progress.bar import Bar
from rez.vendor.schema.schema import Schema, Optional


DEV_NULL = open(os.devnull, 'w')


"""
try:
    import collections
    OrderedDict = collections.OrderedDict
except AttributeError:
    import backport.ordereddict
    OrderedDict = backport.ordereddict.OrderedDict
"""


class _Missing:
    pass
_missing = _Missing()


# TODO deprecate
class Common(object):
    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, str(self))


class ProgressBar(Bar):
    def __init__(self, label, max):
        from rez.config import config
        if config.quiet or not config.show_progress:
            self.file = DEV_NULL
            self.hide_cursor = False

        super(Bar, self).__init__(label, max=max, bar_prefix=' [', bar_suffix='] ')


# TODO use distlib.ScriptMaker
# TODO or, do the work ourselves to make this cross platform
# FIXME *nix only
def create_executable_script(filepath, body, program=None):
    """Create an executable script.

    Args:
        filepath (str): File to create.
        body (str or callable): Contents of the script. If a callable, its code
            is used as the script body.
        program (str): Name of program to launch the script, 'python' if None
    """
    program = program or "python"
    if callable(body):
        from rez.utils.data_utils import SourceCode
        code = SourceCode.from_function(body)
        body = code.source

    if not body.endswith('\n'):
        body += '\n'

    with open(filepath, 'w') as f:
        # TODO make cross platform
        f.write("#!/usr/bin/env %s\n" % program)
        f.write(body)

    os.chmod(filepath, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH
             | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def create_forwarding_script(filepath, module, func_name, *nargs, **kwargs):
    """Create a 'forwarding' script.

    A forwarding script is one that executes some arbitrary Rez function. This
    is used internally by Rez to dynamically create a script that uses Rez,
    even though the parent environment may not be configured to do so.
    """
    doc = dict(
        module=module,
        func_name=func_name)

    if nargs:
        doc["nargs"] = nargs
    if kwargs:
        doc["kwargs"] = kwargs

    body = dump_yaml(doc)
    create_executable_script(filepath, body, "_rez_fwd")


def dedup(seq):
    """Remove duplicates from a list while keeping order."""
    seen = set()
    for item in seq:
        if item not in seen:
            seen.add(item)
            yield item


def shlex_join(value):
    import pipes

    def quote(s):
        return pipes.quote(s) if '$' not in s else s

    if hasattr(value, '__iter__'):
        return ' '.join(quote(x) for x in value)
    else:
        return str(value)


# returns path to first program in the list to be successfully found
def which(*programs):
    from rez.backport.shutilwhich import which as which_
    for prog in programs:
        path = which_(prog)
        if path:
            return path
    return None


# case-insensitive fuzzy string match
def get_close_matches(term, fields, fuzziness=0.4, key=None):
    import math
    import difflib

    def _ratio(a, b):
        return difflib.SequenceMatcher(None, a, b).ratio()

    term = term.lower()
    matches = []

    for field in fields:
        fld = field if key is None else key(field)
        if term == fld:
            matches.append((field, 1.0))
        else:
            name = fld.lower()
            r = _ratio(term, name)
            if name.startswith(term):
                r = math.pow(r, 0.3)
            elif term in name:
                r = math.pow(r, 0.5)
            if r >= (1.0 - fuzziness):
                matches.append((field, min(r, 0.99)))

    return sorted(matches, key=lambda x: -x[1])


# fuzzy string matching on package names, such as 'boost', 'numpy-3.4'
def get_close_pkgs(pkg, pkgs, fuzziness=0.4):
    matches = get_close_matches(pkg, pkgs, fuzziness=fuzziness)
    fam_matches = get_close_matches(pkg.split('-')[0], pkgs,
                                    fuzziness=fuzziness,
                                    key=lambda x: x.split('-')[0])

    d = {}
    for pkg_, r in (matches + fam_matches):
        d[pkg_] = d.get(pkg_, 0.0) + r

    combined = [(k, v * 0.5) for k, v in d.iteritems()]
    return sorted(combined, key=lambda x: -x[1])


def find_last_sublist(list_, sublist):
    """Given a list, find the last occurance of a sublist within it.

    Returns:
        Index where the sublist starts, or None if there is no match.
    """
    for i in reversed(range(len(list_) - len(sublist) + 1)):
        if list_[i] == sublist[0] and list_[i:i + len(sublist)] == sublist:
            return i
    return None


def deep_update(dict1, dict2):
    """Perform a deep merge of `dict2` into `dict1`.

    Note that `dict2` and any nested dicts are unchanged.
    """
    for k, v in dict2.iteritems():
        if k in dict1 and isinstance(v, dict) and isinstance(dict1[k], dict):
            deep_update(dict1[k], v)
        else:
            dict1[k] = copy.deepcopy(v)


class propertycache(object):
    '''Class for creating properties where the value is initially calculated
    then stored.

    Intended for use as a descriptor, ie:

    >>> class MyClass(object):
    ...     @propertycache
    ...     def aValue(self):
    ...         print "This is taking awhile"
    ...         return 42
    >>> c = MyClass()
    >>> c.aValue
    This is taking awhile
    42
    >>> c.aValue
    42

    A cached property can be uncached::

    >>> c = MyClass()
    >>> c.aValue
    This is taking awhile
    42
    >>> c.aValue
    42
    >>> propertycache.uncache(c, 'aValue')
    >>> c.aValue
    This is taking awhile
    42

    If you wish to signal that the return result of the decorated function
    should NOT be cached, raise a DoNotCacheSignal, with the value to return
    as the first argument (defaults to None):

    >>> class MyOtherClass(object):
    ...     def __init__(self):
    ...         self._timesCalled = 0
    ...
    ...     @propertycache
    ...     def aValue(self):
    ...         print "calcing aValue..."
    ...         self._timesCalled += 1
    ...         if self._timesCalled < 2:
    ...             raise propertycache.DoNotCacheSignal('foo')
    ...         return 'bar'
    >>> c = MyOtherClass()
    >>> c.aValue
    calcing aValue...
    'foo'
    >>> c.aValue
    calcing aValue...
    'bar'
    >>> c.aValue
    'bar'
    '''
    class DoNotCacheSignal(Exception):
        def __init__(self, default=None):
            self.default = default

        def __repr__(self):
            default = self.default
            try:
                defaultRepr = repr(default)
            except Exception:
                defaultRepr = '<<unable to get repr for default>>'
            return '%s(%s)' % (type(self).__name__, defaultRepr)

    def __init__(self, func, name=None):
        self.func = func
        self.name = name or func.__name__

    def __get__(self, instance, owner=None):
        """
        TODO: Fix this bug:

        class Foo(object):
            @propertycache
            def bah(self): return True

        class Bah(Foo):
            @propertycache
            def bah(self): return False

        a = Bah()
        super(Bah, a).bah()
        True
        a.bah()
        True  # should be False
        """
        if instance is None:
            return None

        d = instance.__dict__.get('_cachedproperties', {})
        value = d.get(self.name, _missing)
        if value is not _missing:
            return value

        try:
            result = self.func(instance)
        except self.DoNotCacheSignal, e:
            return e.default

        d = instance.__dict__
        d.setdefault('_cachedproperties', {})[self.name] = result
        return result

    @classmethod
    def uncache(cls, instance, name=None):
        d = instance.__dict__.get('_cachedproperties', {})
        if name:
            if name in d:
                del d[name]
        else:
            d.clear()


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


class _LazyAttributeValidator(type):
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

        members["_schema_keys"] = frozenset(keys)
        return super(_LazyAttributeValidator, cls).__new__(cls, name, parents,
                                                           members)

    @classmethod
    def _make_getter(cls, key, optional, key_schema):
        def getter(self):
            if key not in self._data:
                if optional:
                    return None
                raise self.schema_error("Required key is missing: %r" % key)

            attr = self._data[key]
            if hasattr(self, "_validate_key"):
                attr = self._validate_key(key, attr, key_schema)
            else:
                schema = (key_schema if isinstance(key_schema, Schema)
                          else Schema(key_schema))
                try:
                    attr = schema.validate(attr)
                except Exception as e:
                    raise self.schema_error("Validation of key %r failed: "
                                            "%s" % (key, str(e)))
            return attr

        return propertycache(getter, name=key)


class DataWrapper(object):
    """Base class for implementing a class that contains validated data.

    DataWrapper subclasses are expected to implement the `_data` property,
    which should return a dict matching the schema specified by the class's
    `schema` attribute. Keys in the schema become attributes in this class,
    and are lazily validated on first reference.

    Attributes:
        schema (Schema): Schema used to validate the data. They keys of the
            schema become attributes on the object (the metaclass does this).
        schema_error (Exception): The class type to raise if an error occurs
            during data load.
    """
    __metaclass__ = _LazyAttributeValidator
    schema_error = Exception
    schema = None

    def __init__(self):
        pass

    def get(self, key, default=None):
        """Get a key value by name."""
        return getattr(self, key, default)

    def validate_data(self):
        """Force validation on all of the object's data.

        Note: This method is deliberately not named 'validate'. This causes
            problems because a DataWrapper instance can in some cases be
            incorrectly picked up by the Schema library as a schema validator.
        """
        getattr(self, "validated_data")

    @propertycache
    def validated_data(self):
        """Return validated data.

        Returns:
            A dict containing all data for this object, or None if this class
            does not provide a data schema.
        """
        if self.schema:
            d = {}
            for key in self._schema_keys:
                d[key] = getattr(self, key)
            return d
        else:
            return None

    @property
    def _data(self):
        """Load raw object data.

        The data returned by this method should conform to the schema defined
        by the `schema` class attribute. You almost certainly want to decorate
        this property with a @propertycache, to avoid loading the data
        multiple times.

        Returns:
            dict.
        """
        raise NotImplementedError

    def format(self, s, pretty=False, expand=None):
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
        # TODO: need to deprecate this class in favor of data_utils.py version
        from rez.utils.data_utils import ObjectStringFormatter
        formatter = ObjectStringFormatter(self, pretty=pretty,
                                          expand=ObjectStringFormatter.expand)
        return formatter.format(s)


@atexit.register
def _atexit():
    from rez.resolved_context import ResolvedContext
    ResolvedContext.tmpdir_manager.clear()
