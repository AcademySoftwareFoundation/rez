"""
Utilities related to formatting output or translating input.
"""
from string import Formatter
from rez.vendor.enum import Enum
from rez.vendor.version.requirement import Requirement
from rez.exceptions import PackageRequestError
from pprint import pformat
import os
import re
import time


PACKAGE_NAME_REGSTR = "[a-zA-Z_0-9](\.?[a-zA-Z0-9_]+)*"
PACKAGE_NAME_REGEX = re.compile(r"^%s\Z" % PACKAGE_NAME_REGSTR)

ENV_VAR_REGSTR = r'\$(\w+|\{[^}]*\})'
ENV_VAR_REGEX = re.compile(ENV_VAR_REGSTR)

FORMAT_VAR_REGSTR = "{(?P<var>.+?)}"
FORMAT_VAR_REGEX = re.compile(FORMAT_VAR_REGSTR)


def is_valid_package_name(name, raise_error=False):
    """Test the validity of a package name string.

    Args:
        name (str): Name to test.
        raise_error (bool): If True, raise an exception on failure

    Returns:
        bool.
    """
    is_valid = PACKAGE_NAME_REGEX.match(name)
    if raise_error and not is_valid:
        raise PackageRequestError("Not a valid package name: %r" % name)
    return is_valid


class PackageRequest(Requirement):
    """A package request parser.

    Example:

        >>> pr = PackageRequirement("foo-1.3+")
        >>> print pr.name, pr.range
        foo 1.3+
    """
    def __init__(self, s):
        super(PackageRequest, self).__init__(s)
        is_valid_package_name(self.name, True)


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
    """Turn any object into a string formatter.

    An object inheriting this mixin will have a `format` function added, that is
    able to format using attributes of the object.
    """
    format_expand = StringFormatType.error
    format_pretty = True

    def format(self, s, pretty=None, expand=None):
        """Format a string.

        Args:
            s (str): String to format, eg "hello {name}"
            pretty (bool): If True, references to non-string attributes such as
                lists are converted to basic form, with characters such as
                brackets and parenthesis removed. If None, defaults to the
                object's 'format_pretty' attribute.
            expand (`StringFormatType`): Expansion mode. If None, will default
                to the object's 'format_expand' attribute.

        Returns:
            The formatting string.
        """
        if pretty is None:
            pretty = self.format_pretty
        if expand is None:
            expand = self.format_expand

        formatter = ObjectStringFormatter(self, pretty=pretty, expand=expand)
        return formatter.format(s)


def expand_abbreviations(txt, fields):
    """Expand abbreviations in a format string.

    If an abbreviation does not match a field, or matches multiple fields, it
    is left unchanged.

    Example:

        >>> fields = ("hey", "there", "dude")
        >>> expand_abbreviations("hello {d}", fields)
        'hello dude'

    Args:
        txt (str): Format string.
        fields (list of str): Fields to expand to.

    Returns:
        Expanded string.
    """
    def _expand(matchobj):
        s = matchobj.group("var")
        if s not in fields:
            matches = [x for x in fields if x.startswith(s)]
            if len(matches) == 1:
                s = matches[0]
        return "{%s}" % s
    return re.sub(FORMAT_VAR_REGEX, _expand, txt)


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
    if '$' not in text:
        return text

    i = 0
    if environ is None:
        environ = os.environ

    while True:
        m = ENV_VAR_REGEX.search(text, i)
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


def indent(txt):
    """Indent the given text by 4 spaces."""
    lines = (("    " + x) for x in txt.split('\n'))
    return '\n'.join(lines)


def dict_to_attributes_code(dict_):
    """Given a nested dict, generate a python code equivalent.

    Example:
        >>> d = {'foo': 'bah', 'colors': {'red': 1, 'blue': 2}}
        >>> print dict_to_attributes_code(d)
        foo = 'bah'
        colors.red = 1
        colors.blue = 2

    Returns:
        str.
    """
    lines = []
    for key, value in dict_.iteritems():
        if isinstance(value, dict):
            txt = dict_to_attributes_code(value)
            lines_ = txt.split('\n')
            for line in lines_:
                if not line.startswith(' '):
                    line = "%s.%s" % (key, line)
                lines.append(line)
        else:
            value_txt = pformat(value)
            if '\n' in value_txt:
                lines.append("%s = \\" % key)
                value_txt = indent(value_txt)
                lines.extend(value_txt.split('\n'))
            else:
                line = "%s = %s" % (key, value_txt)
                lines.append(line)

    return '\n'.join(lines)


def columnise(rows, padding=2):
    """Print rows of entries in aligned columns."""
    strs = []
    maxwidths = {}

    for row in rows:
        for i, e in enumerate(row):
            se = str(e)
            nse = len(se)
            w = maxwidths.get(i, -1)
            if nse > w:
                maxwidths[i] = nse

    for row in rows:
        s = ''
        for i, e in enumerate(row):
            se = str(e)
            if i < len(row) - 1:
                n = maxwidths[i] + padding - len(se)
                se += ' ' * n
            s += se
        strs.append(s)
    return strs


def print_colored_columns(printer, rows, padding=2):
    """Like `columnise`, but with colored rows.

    Args:
        printer (`colorize.Printer`): Printer object.

    Note:
        The last entry in each row is the row color, or None for no coloring.
    """
    rows_ = [x[:-1] for x in rows]
    colors = [x[-1] for x in rows]
    for col, line in zip(colors, columnise(rows_, padding=padding)):
        printer(line, col)


time_divs = (
    (365 * 24 * 3600, "years", 10),
    (30 * 24 * 3600, "months", 12),
    (7 * 24 * 3600, "weeks", 5),
    (24 * 3600, "days", 7),
    (3600, "hours", 10),
    (60, "minutes", 10),
    (1, "seconds", 60))


def readable_time_duration(secs):
    """Convert number of seconds into human readable form, eg '3.2 hours'.
    """
    return _readable_units(secs, time_divs, True)


memory_divs = (
    (1024 * 1024 * 1024 * 1024, "Tb", 128),
    (1024 * 1024 * 1024, "Gb", 64),
    (1024 * 1024, "Mb", 32),
    (1024, "Kb", 16),
    (1, "bytes", 1024))


def readable_memory_size(bytes_):
    """Convert number of bytes into human readable form, eg '1.2 Kb'.
    """
    return _readable_units(bytes_, memory_divs)


def _readable_units(value, divs, plural_aware=False):
    if value == 0:
        unit = divs[-1][1]
        return "0 %s" % unit
    neg = (value < 0)
    if neg:
        value = -value

    for quantity, unit, threshold in divs:
        if value >= quantity:
            f = value / float(quantity)
            rounding = 0 if f > threshold else 1
            f = round(f, rounding)
            f = int(f * 10) / 10.0
            if plural_aware and f == 1.0:
                unit = unit[:-1]
            txt = "%g %s" % (f, unit)
            break

    if neg:
        txt = '-' + txt
    return txt


def get_epoch_time_from_str(s):
    """Convert a string into epoch time. Examples of valid strings:

        1418350671  # already epoch time
        -12s        # 12 seconds ago
        -5.4m       # 5.4 minutes ago
    """
    try:
        return int(s)
    except:
        pass

    try:
        if s.startswith('-'):
            chars = {'d': 24 * 60 * 60,
                     'h': 60 * 60,
                     'm': 60,
                     's': 1}
            m = chars.get(s[-1])
            if m:
                n = float(s[1:-1])
                secs = int(n * m)
                now = int(time.time())
                return max((now - secs), 0)
    except:
        pass

    raise ValueError("'%s' is an unrecognised time format." % s)


positional_suffix = ("th", "st", "nd", "rd", "th", "th", "th", "th", "th", "th")


def positional_number_string(n):
    """Print the position string equivalent of a positive integer. Examples:

        0: zeroeth
        1: first
        2: second
        14: 14th
        21: 21st
    """
    if n > 20:
        suffix = positional_suffix(n % 10)
        return "%d%s" % (n, suffix)
    elif n > 3:
        return "%dth" % n
    elif n == 3:
        return "third"
    elif n == 2:
        return "second"
    elif n == 1:
        return "first"
    return "zeroeth"


def expanduser(path):
    """Expand paths beginning with '~'.
    
    True story... the implementation of os.path.expanduser differs between
    Windows (nt) and Linux (posix).  On posix platforms the `pwd` module is
    used so '~foo' will only expand if 'foo' is a valid user.  This is nice. On
    nt platforms the same check is not made - the '~' is always expanded based
    using string manipulation and environment variables.  This is bad.

    As a result, due to the way expansion is hard wired into the `config`
    module this means weak implicit packages (for example) in the config are
    expanded from '~os=={system.os}' to 'C:/Users/os=={system.os}' on nt
    platforms.

    Ideally, `PathStrList` based `Settings` would be the only setting type to
    use the `os.path.expanduser` method, thereby making it explicit that this
    level of expansion should take place.  This works for the main `Config`
    class however `_PluginConfig` follows a different code path that makes this
    all but impossible without a larger refactor (see comment in `_to_schema`
    method).  Therefore, to keep the behaviour consistent across all types of
    configuration and platform we change the os.path.expanduser implementation.

    As it is highly unlikely we should need to refer to someone else's home
    directory (thereby triggering the above 'feature') we use a custom
    `expanduser` method which can only expand '~'.  Others the path is returned
    without expansion applied."""
    if os.name == "nt":
        userpath = path
        if not path.startswith('~'):
            return path

        i = path.find(os.path.sep, 1)
        if i < 0:
            i = len(path)
        if i != 1:
            return path

        if 'HOME' in os.environ:
            userhome = os.environ['HOME']
        elif 'USERPROFILE' in os.environ:
            userhome = os.environ['USERPROFILE']
        elif not 'HOMEPATH' in os.environ:
            return path
        else:
            try:
                drive = os.environ['HOMEDRIVE']
            except KeyError:
                drive = ''
            userhome = os.path.join(drive, os.environ['HOMEPATH'])
        userpath = userhome + path[i:]

    else:
        userpath = os.path.expanduser(path)

    return userpath
