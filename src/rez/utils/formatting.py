"""
Utilities related to formatting output or translating input.
"""
from __future__ import absolute_import

from string import Formatter
from rez.vendor.enum import Enum
from rez.vendor.version.requirement import Requirement
from rez.exceptions import PackageRequestError
from rez.vendor.six import six
from pprint import pformat
import os
import os.path
import re
import time


PACKAGE_NAME_REGSTR = r"[a-zA-Z_0-9](\.?[a-zA-Z0-9_]+)*"
PACKAGE_NAME_REGEX = re.compile(r"^%s\Z" % PACKAGE_NAME_REGSTR)

ENV_VAR_REGSTR = r'\$(\w+|\{[^}]*\})'
ENV_VAR_REGEX = re.compile(ENV_VAR_REGSTR)

FORMAT_VAR_REGSTR = "{(?P<var>.+?)}"
FORMAT_VAR_REGEX = re.compile(FORMAT_VAR_REGSTR)

# package names that are invalid because they may clash with reserved dir
# names in some package repos (eg filesystem)
#
invalid_package_names = (
    "__pycache__",
)


def is_valid_package_name(name, raise_error=False):
    """Test the validity of a package name string.

    Args:
        name (str): Name to test.
        raise_error (bool): If True, raise an exception on failure

    Returns:
        bool.
    """
    is_valid = (
        PACKAGE_NAME_REGEX.match(name)
        and name not in invalid_package_names
    )

    if raise_error and not is_valid:
        raise PackageRequestError("Not a valid package name: %r" % name)
    return is_valid


class PackageRequest(Requirement):
    """A package request parser.

    Valid requests include:

    * Any standard request, eg 'foo-1.2.3', '!foo-1', etc
    * "Ephemeral" request, eg '.foo-1.2.3'

    Example:

        >>> pr = PackageRequest("foo-1.3+")
        >>> print(pr.name, pr.range)
        foo 1.3+
    """
    def __init__(self, s):
        super(PackageRequest, self).__init__(s)

        # detect ephemeral package
        if s.startswith('.'):
            self.ephemeral = True
            is_valid_package_name(self.name[1:], True)
        else:
            self.ephemeral = False
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
                    if six.PY2:
                        if isinstance(x, unicode):
                            return x
                        else:
                            return str(x)
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
            reg = re.compile(r"[^\.\[]+")
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
        >>> print(dict_to_attributes_code(d))
        foo = 'bah'
        colors.red = 1
        colors.blue = 2

    Returns:
        str.
    """
    lines = []
    for key, value in dict_.items():
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
        suffix = positional_suffix[n % 10]
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


# regex used to expand user; set here to avoid recompile on every call
EXPANDUSER_RE = re.compile(
    r'(\A|\s|[{pathseps}])~([{seps}]|[{pathseps}]|\s|\Z)'.format(
        seps=re.escape(''.join(set([os.sep + (getattr(os, 'altsep') or os.sep)]))),
        pathseps=re.escape(''.join(set([os.pathsep + ';'])))
    )
)


def expanduser(path):
    """Expand '~' to home directory in the given string.

    Note that this function deliberately differs from the builtin
    os.path.expanduser() on Linux systems, which expands strings such as
    '~sclaus' to that user's homedir. This is problematic in rez because the
    string '~packagename' may inadvertently convert to a homedir, if a package
    happens to match a username.
    """
    if '~' not in path:
        return path

    if os.name == "nt":
        if 'HOME' in os.environ:
            userhome = os.environ['HOME']
        elif 'USERPROFILE' in os.environ:
            userhome = os.environ['USERPROFILE']
        elif 'HOMEPATH' in os.environ:
            drive = os.environ.get('HOMEDRIVE', '')
            userhome = os.path.join(drive, os.environ['HOMEPATH'])
        else:
            return path
    else:
        userhome = os.path.expanduser('~')

    def _expanduser(path):
        return EXPANDUSER_RE.sub(
            lambda m: m.groups()[0] + userhome + m.groups()[1],
            path)

    # only replace '~' if it's at start of string or is preceeded by pathsep or
    # ';' or whitespace; AND, is followed either by sep, pathsep, ';', ' ' or
    # end-of-string.
    #
    return os.path.normpath(_expanduser(path))


def as_block_string(txt):
    """Return a string formatted as a python block comment string, like the one
    you're currently reading. Special characters are escaped if necessary.
    """
    import json

    lines = []
    for line in txt.split('\n'):
        line_ = json.dumps(line, ensure_ascii=False)
        line_ = line_[1:-1].rstrip()  # drop double quotes
        lines.append(line_)

    return '"""\n%s\n"""' % '\n'.join(lines)


_header_br = '#' * 80
_header_br_minor = '-' * 80


def header_comment(executor, txt):
    """Convenience for creating header-like comment in a rex executor.

    Args:
        executor (`RexExecutor`): Executor.
        txt (str): Comment text.
    """
    executor.comment("")
    executor.comment("")
    executor.comment(_header_br)
    executor.comment(txt)
    executor.comment(_header_br)


def minor_header_comment(executor, txt):
    executor.comment("")
    executor.comment(txt)
    executor.comment(_header_br_minor)


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
