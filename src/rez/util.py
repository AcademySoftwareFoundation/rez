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

    content = dump_yaml(doc)
    with open(filepath, 'w') as f:
        # TODO make cross platform
        f.write("#!/usr/bin/env _rez_fwd\n")
        f.write(content)

    os.chmod(filepath, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH
             | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


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


_templates = {}

# Note this is the very start of adding support for pluggable project template, ala rez-make-project.
def render_template(template, **variables):
    """
    Returns template from template/<template>, rendered with the given variables.
    """
    templ = _templates.get(template)
    if not templ:
        path = os.path.join(module_root_path, "template", os.path.join(*(template.split('/'))))
        if os.path.exists(path):
            with open(path) as f:
                templ = f.read()
                _templates[template] = templ
        else:
            raise Exception("Unknown template '%s'" % template)

    # TODO support template plugins, probably using Jinja2
    return templ % variables


def convert_old_command_expansions(command):
    """Convert expansions from !OLD! style to {new}."""
    command = command.replace("!VERSION!",       "{version}")
    command = command.replace("!MAJOR_VERSION!", "{version.major}")
    command = command.replace("!MINOR_VERSION!", "{version.minor}")
    command = command.replace("!BASE!",          "{base}")
    command = command.replace("!ROOT!",          "{root}")
    command = command.replace("!USER!",          "{system.user}")
    return command


def convert_old_environment_variable_references(input_):

    def repl(matchobj):
        return "{env.%s}" % matchobj.groupdict()['variable']

    return re.sub("\$\{?(?P<variable>[a-zA-Z][_a-zA-Z0-9]*)\}?", repl, input_)


def convert_old_commands(commands, annotate=True):
    """Converts old-style package commands into equivalent Rex code."""
    from rez.config import config

    def _encode(s):
        s = s.replace('\\"', '"')
        return s.encode("string-escape")

    loc = []
    for cmd in commands:
        if annotate:
            loc.append("comment('OLD COMMAND: %s')" % _encode(cmd))

        cmd = convert_old_command_expansions(cmd)
        toks = cmd.strip().split()

        if toks[0] == "export":
            var, value = cmd.split(' ', 1)[1].split('=', 1)
            for bookend in ('"', "'"):
                if value.startswith(bookend) and value.endswith(bookend):
                    value = value[1:-1]
                    break

            separator = config.env_var_separators.get(var, os.pathsep)

            # This is a special special case.  We don't want to include "';'" in
            # our env var separators map as it's not really the correct
            # behaviour/something we want to promote.  It's included here for
            # backwards compatibility only, and to not propogate elsewhere.
            if var == "CMAKE_MODULE_PATH":
                value = value.replace("'%s'" % separator, separator)
                value = value.replace('"%s"' % separator, separator)
                value = value.replace(":", separator)

            parts = value.split(separator)
            parts = [x for x in parts if x]
            if len(parts) > 1:
                idx = None
                var1 = "$%s" % var
                var2 = "${%s}" % var
                if var1 in parts:
                    idx = parts.index(var1)
                elif var2 in parts:
                    idx = parts.index(var2)
                if idx in (0, len(parts) - 1):
                    func = "appendenv" if idx == 0 else "prependenv"
                    parts = parts[1:] if idx == 0 else parts[:-1]
                    val = separator.join(parts)
                    val = convert_old_environment_variable_references(val)
                    loc.append("%s('%s', '%s')" % (func, var, _encode(val)))
                    continue

            value = convert_old_environment_variable_references(value)
            loc.append("setenv('%s', '%s')" % (var, _encode(value)))
        elif toks[0].startswith('#'):
            loc.append("comment('%s')" % _encode(' '.join(toks[1:])))
        elif toks[0] == "alias":
            match = re.search("alias (?P<key>.*?)=(?P<value>.*)", cmd)
            key = match.groupdict()['key'].strip()
            value = match.groupdict()['value'].strip()
            if (value.startswith('"') and value.endswith('"')) or \
                    (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            loc.append("alias('%s', '%s')" % (key, _encode(value)))
        else:
            # assume we can execute this as a straight command
            loc.append("command('%s')" % _encode(cmd))

    rex_code = '\n'.join(loc)
    if config.debug("old_commands"):
        br = '-' * 80
        msg = textwrap.dedent(
            """
            %s
            OLD COMMANDS:
            %s

            NEW COMMANDS:
            %s
            %s
            """) % (br, '\n'.join(commands), rex_code, br)
        print_debug(msg)
    return rex_code


_varprog = None


def expandvars(text, environ=None):
    """Expand shell variables of form $var and ${var}.

    Unknown variables are left unchanged.

    Args:
        text (str): String to expand.
        environ (dict): Environ dict to use for expansions, defaults to
            os.environ.

    Returns:
        The expanded string.
    """
    global _varprog
    if '$' not in text:
        return text
    if not _varprog:
        _varprog = re.compile(r'\$(\w+|\{[^}]*\})')

    i = 0
    if environ is None:
        environ = os.environ
    while True:
        m = _varprog.search(text, i)
        if not m:
            break
        i, j = m.span(0)
        name = m.group(1)
        if name.startswith('{') and name.endswith('}'):
            name = name[1:-1]
        if name in environ:
            tail = text[j:]
            text = text[:i] + environ[name]
            i = len(text)
            text += tail
        else:
            i = j
    return text


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
        # TODO need to deprecate this class in favor of data_utils.py version
        from rez.utils.formatting import ObjectStringFormatter
        formatter = ObjectStringFormatter(self, pretty=pretty,
                                          expand=ObjectStringFormatter.expand)
        return formatter.format(s)


@atexit.register
def _atexit():
    from rez.resolved_context import ResolvedContext
    ResolvedContext.tmpdir_manager.clear()
