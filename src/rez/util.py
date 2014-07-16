"""
Misc useful stuff.
"""
import stat
import sys
import atexit
import os
import os.path
import shutil
import time
import posixpath
import ntpath
import UserDict
import re
import shutil
import subprocess
import textwrap
import tempfile
import threading
import time
import subprocess as sp
from collections import MutableMapping, defaultdict
import logging
from types import MethodType
from string import Formatter
from rez import module_root_path
from rez.vendor import yaml


logger = logging.getLogger(__name__)


try:
    import collections
    OrderedDict = collections.OrderedDict
except AttributeError:
    import backport.ordereddict
    OrderedDict = backport.ordereddict.OrderedDict


# TODO deprecate
class Common(object):
    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, str(self))


class LazySingleton(object):
    def __init__(self, type_, *nargs, **kwargs):
        self.type_ = type_
        self.nargs = nargs
        self.kwargs = kwargs
        self.lock = threading.Lock()
        self.instance = None

    def __call__(self):
        if self.instance is None:
            try:
                self.lock.acquire()
                if self.instance is None:
                    self.instance = self.type_(*self.nargs, **self.kwargs)
            finally:
                self.lock.release()
        return self.instance


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

    content = yaml.dump(doc, default_flow_style=False)
    with open(filepath, 'w') as f:
        f.write("#!/usr/bin/env _rez_fwd\n")
        f.write(content)

    os.chmod(filepath, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH
             | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def print_debug(msg):
    logger.debug(msg)


def print_info(msg):
    logger.info(msg)


def print_warning(msg):
    logger.warning(msg)


def print_error(msg):
    logger.error(msg)


def print_critical(msg):
    logger.critical(msg)


def _mkdirs(*dirs):
    path = os.path.join(*dirs)
    if not os.path.exists(path):
        os.makedirs(path)
    return path

rm_tmdirs = True
_tmpdirs = set()
_tmpdir_lock = threading.Lock()


def mkdtemp_():
    from rez.config import config
    path = tempfile.mkdtemp(dir=config.tmpdir, prefix='rez_')
    try:
        _tmpdir_lock.acquire()
        _tmpdirs.add(path)
    finally:
        _tmpdir_lock.release()
    return path


def rmdtemp(path):
    if os.path.exists(path):
        shutil.rmtree(path)


def set_rm_tmpdirs(enable):
    global rm_tmdirs
    rm_tmdirs = enable


def relative_path(from_path, to_path):
    from_path = os.path.realpath(from_path)
    to_path = os.path.realpath(to_path)
    return os.path.relpath(from_path, to_path)


def is_subdirectory(path, directory):
    relative = relative_path(path, directory)
    return not relative.startswith(os.pardir)


def _get_rez_dist_path(dirname):
    path = os.path.join(module_root_path, dirname)
    if not os.path.exists(path):
        # this will happen if we are the bootstrapped rez pkg
        path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
        path = os.path.realpath(path)
        path = os.path.join(path, dirname)

        # the dist may not be available - this happens when unit tests are
        # run from source
        if not os.path.exists(path):
            return None

    return path


def get_bootstrap_path():
    path = _get_rez_dist_path("packages/rez")
    if path:
        return os.path.dirname(path)
    else:
        return _get_rez_dist_path("packages")


def get_script_path():
    return _get_rez_dist_path("bin")


def get_rez_install_path():
    path = os.path.join(get_script_path(), "..")
    return os.path.realpath(path)


def _add_bootstrap_pkg_path(paths):
    bootstrap_path = get_bootstrap_path()
    return paths[:] + [bootstrap_path]


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

    return sorted(matches, key=lambda x:-x[1])


# fuzzy string matching on package names, such as 'boost', 'numpy-3.4'
def get_close_pkgs(pkg, pkgs, fuzziness=0.4):
    matches = get_close_matches(pkg, pkgs, fuzziness=fuzziness)
    fam_matches = get_close_matches(pkg.split('-')[0], pkgs, \
        fuzziness=fuzziness, key=lambda x:x.split('-')[0])

    d = {}
    for pkg_,r in (matches + fam_matches):
        d[pkg_] = d.get(pkg_, 0.0) + r

    combined = [(k,v*0.5) for k,v in d.iteritems()]
    return sorted(combined, key=lambda x:-x[1])


def columnise(rows, padding=2):
    strs = []
    maxwidths = {}

    for row in rows:
        for i,e in enumerate(row):
            se = str(e)
            nse = len(se)
            w = maxwidths.get(i,-1)
            if nse > w:
                maxwidths[i] = nse

    for row in rows:
        s = ''
        for i,e in enumerate(row):
            se = str(e)
            if i < len(row)-1:
                n = maxwidths[i] + padding - len(se)
                se += ' '*n
            s += se
        strs.append(s)
    return strs

def pretty_env_dict(d):
    rows = [x for x in sorted(d.iteritems())]
    return '\n'.join(columnise(rows))

def readable_time_duration(secs, approx=True, approx_thresh=0.001):
    divs = ((24 * 60 * 60, "days"), (60 * 60, "hours"), (60, "minutes"), (1, "seconds"))

    if secs == 0:
        return "0 seconds"
    neg = (secs < 0)
    if neg:
        secs = -secs

    results = []
    remainder = secs
    for seconds, label in divs:
        value, remainder = divmod(remainder, seconds)
        if value:
            results.append((value, label))
            if approx and (float(remainder) / secs) >= approx_thresh:
                # quit if remainder drops below threshold
                break
    s = ', '.join(['%d %s' % x for x in results])

    if neg:
        s = '-' + s
    return s


def get_epoch_time_from_str(s):
    try:
        return int(s)
    except:
        pass

    try:
        if s.startswith('-'):
            chars = {'d':24*60*60, 'h':60*60, 'm':60, 's':1}
            m = chars.get(s[-1])
            if m:
                n = float(s[1:-1])
                secs = int(n * m)
                now = int(time.time())
                return max((now - secs), 0)
    except:
        pass

    raise Exception("'%s' is an unrecognised time format." % s)


def copytree(src, dst, symlinks=False, ignore=None, hardlinks=False):
    '''
    copytree that supports hard-linking
    '''
    names = os.listdir(src)
    if ignore is not None:
        ignored_names = ignore(src, names)
    else:
        ignored_names = set()

    if hardlinks:
        def copy(srcname, dstname):
            try:
                # try hard-linking first
                os.link(srcname, dstname)
            except OSError:
                shutil.copy2(srcname, dstname)
    else:
        copy = shutil.copy2

    if not os.path.isdir(dst):
        os.makedirs(dst)

    errors = []
    for name in names:
        if name in ignored_names:
            continue
        srcname = os.path.join(src, name)
        dstname = os.path.join(dst, name)
        try:
            if symlinks and os.path.islink(srcname):
                linkto = os.readlink(srcname)
                os.symlink(linkto, dstname)
            elif os.path.isdir(srcname):
                copytree(srcname, dstname, symlinks, ignore)
            else:
                copy(srcname, dstname)
        # XXX What about devices, sockets etc.?
        except (IOError, os.error), why:
            errors.append((srcname, dstname, str(why)))
        # catch the Error from the recursive copytree so that we can
        # continue with other files
        except shutil.Error, err:
            errors.extend(err.args[0])
    try:
        shutil.copystat(src, dst)
    except shutil.WindowsError:
        # can't copy file access times on Windows
        pass
    except OSError, why:
        errors.extend((src, dst, str(why)))
    if errors:
        raise shutil.Error(errors)

def movetree(src, dst):
    """
    Attempts a move, and falls back to a copy+delete if this fails
    """
    try:
        shutil.move(src, dst)
    except:
        copytree(src, dst, symlinks=True, hardlinks=True)
        shutil.rmtree(src)

def safe_chmod(path, mode):
    """
    set the permissions mode on path, but only if it differs from the current mode.
    """
    if stat.S_IMODE(os.stat(path).st_mode) != mode:
        os.chmod(path, mode)

def to_nativepath(path):
    return os.path.join(path.split('/'))

def to_ntpath(path):
    return ntpath.sep.join(path.split(posixpath.sep))

def to_posixpath(path):
    return posixpath.sep.join(path.split(ntpath.sep))


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

def encode_filesystem_name(input_str):
    """Encodes an arbitrary unicode string to a generic filesystem-compatible
    non-unicode filename.

    The result after encoding will only contain the standard ascii lowercase
    letters (a-z), the digits (0-9), or periods, underscores, or dashes
    (".", "_", or "-").  No uppercase letters will be used, for
    comaptibility with case-insensitive filesystems.

    The rules for the encoding are:

    1) Any lowercase letter, digit, period, or dash (a-z, 0-9, ., or -) is
    encoded as-is.

    2) Any underscore is encoded as a double-underscore ("__")

    3) Any uppercase ascii letter (A-Z) is encoded as an underscore followed
    by the corresponding lowercase letter (ie, "A" => "_a")

    4) All other characters are encoded using their UTF-8 encoded unicode
    representation, in the following format: "_NHH..., where:
        a) N represents the number of bytes needed for the UTF-8 encoding,
        except with N=0 for one-byte representation (the exception for N=1
        is made both because it means that for "standard" ascii characters
        in the range 0-127, their encoding will be _0xx, where xx is their
        ascii hex code; and because it mirrors the ways UTF-8 encoding
        itself works, where the number of bytes needed for the character can
        be determined by counting the number of leading "1"s in the binary
        representation of the character, except that if it is a 1-byte
        sequence, there are 0 leading 1's).
        b) HH represents the bytes of the corresponding UTF-8 encoding, in
        hexadecimal (using lower-case letters)

        As an example, the character "*", whose (hex) UTF-8 representation
        of 2A, would be encoded as "_02a", while the "euro" symbol, which
        has a UTF-8 representation of E2 82 AC, would be encoded as
        "_3e282ac".  (Note that, strictly speaking, the "N" part of the
        encoding is redundant information, since it is essentially encoded
        in the UTF-8 representation itself, but it makes the resulting
        string more human-readable, and easier to decode).

    As an example, the string "Foo_Bar (fun).txt" would get encoded as:
        _foo___bar_020_028fun_029.txt
    """
    if isinstance(input_str, str):
        input_str = unicode(input_str)
    elif not isinstance(input_str, unicode):
        raise TypeError("input_str must be a basestring")

    as_is = u'abcdefghijklmnopqrstuvwxyz0123456789.-'
    uppercase = u'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    result = []
    for char in input_str:
        if char in as_is:
            result.append(char)
        elif char == u'_':
            result.append('__')
        elif char in uppercase:
            result.append('_%s' % char.lower())
        else:
            utf8 = char.encode('utf8')
            N = len(utf8)
            if N == 1:
                N = 0
            HH = ''.join('%x' % ord(c) for c in utf8)
            result.append('_%d%s' % (N, HH))
    return str(''.join(result))


_FILESYSTEM_TOKEN_RE = re.compile(r'(?P<as_is>[a-z0-9.-])|(?P<underscore>__)|_(?P<uppercase>[a-z])|_(?P<N>[0-9])')
_HEX_RE = re.compile('[0-9a-f]+$')

def decode_filesystem_name(filename):
    """Decodes a filename encoded using the rules given in encode_filesystem_name
    to a unicode string.
    """
    result = []
    remain = filename
    i = 0
    while remain:
        # use match, to ensure it matches from the start of the string...
        match = _FILESYSTEM_TOKEN_RE.match(remain)
        if not match:
            raise ValueError("incorrectly encoded filesystem name %r"
                             " (bad index: %d - %r)" % (filename, i,
                                                        remain[:2]))
        match_str = match.group(0)
        match_len = len(match_str)
        i += match_len
        remain = remain[match_len:]
        match_dict = match.groupdict()
        if match_dict['as_is']:
            result.append(unicode(match_str))
            # print "got as_is - %r" % result[-1]
        elif match_dict['underscore']:
            result.append(u'_')
            # print "got underscore - %r" % result[-1]
        elif match_dict['uppercase']:
            result.append(unicode(match_dict['uppercase'].upper()))
            # print "got uppercase - %r" % result[-1]
        elif match_dict['N']:
            N = int(match_dict['N'])
            if N == 0:
                N = 1
            # hex-encoded, so need to grab 2*N chars
            bytes_len = 2 * N
            i += bytes_len
            bytes = remain[:bytes_len]
            remain = remain[bytes_len:]

            # need this check to ensure that we don't end up eval'ing
            # something nasty...
            if not _HEX_RE.match(bytes):
                raise ValueError("Bad utf8 encoding in name %r"
                                 " (bad index: %d - %r)" % (filename, i, bytes))

            bytes_repr = ''.join('\\x%s' % bytes[i:i + 2]
                                 for i in xrange(0, bytes_len, 2))
            bytes_repr = "'%s'" % bytes_repr
            result.append(eval(bytes_repr).decode('utf8'))
            # print "got utf8 - %r" % result[-1]
        else:
            raise ValueError("Unrecognized match type in filesystem name %r"
                             " (bad index: %d - %r)" % (filename, i, remain[:2]))
        # print result
    return u''.join(result)


def test_encode_decode():
    def do_test(orig, expected_encoded):
        print '=' * 80
        print orig
        encoded = encode_filesystem_name(orig)
        print encoded
        assert encoded == expected_encoded
        decoded = decode_filesystem_name(encoded)
        print decoded
        assert decoded == orig

    do_test("Foo_Bar (fun).txt", '_foo___bar_020_028fun_029.txt')

    # u'\u20ac' == Euro symbol
    do_test(u"\u20ac3 ~= $4.06", '_3e282ac3_020_07e_03d_020_0244.06')


def convert_old_command_expansions(command):
    """Convert expansions from !OLD! style to {new}."""
    command = command.replace("!VERSION!",       "{version}")
    command = command.replace("!MAJOR_VERSION!", "{version.major}")
    command = command.replace("!MINOR_VERSION!", "{version.minor}")
    command = command.replace("!BASE!",          "{base}")
    command = command.replace("!ROOT!",          "{root}")
    command = command.replace("!USER!",          "{user}")
    return command


def convert_old_commands(commands, annotate=True):
    """Converts old-style package commands into equivalent Rex code."""
    from rez.config import config

    def _en(s):
        return s.encode("string-escape")

    loc = []
    for cmd in commands:
        if annotate:
            loc.append("comment('OLD COMMAND: %s')" % _en(cmd))

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
                    val = os.pathsep.join(parts)
                    loc.append("%s('%s', '%s')" % (func, var, _en(val)))
                    continue

            loc.append("setenv('%s', '%s')" % (var, _en(value)))
        elif toks[0].startswith('#'):
            loc.append("comment('%s')" % _en(' '.join(toks[1:])))
        elif toks[0] == "alias":
            match = re.search("alias (?P<key>.*?)=(?P<value>.*)", cmd)
            key = match.groupdict()['key'].strip()
            value = match.groupdict()['value'].strip()
            if (value.startswith('"') and value.endswith('"')) or \
                    (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            loc.append("alias('%s', '%s')" % (key, _en(value)))
        else:
            # assume we can execute this as a straight command
            loc.append("command('%s')" % _en(cmd))

    rex_code = '\n'.join(loc)
    from rez.config import config
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


class Timings(object):
    """Class for timing operations, for debugging purposes.

    Timing is a special case wrt configuration, you need to set
    $REZ_ENABLE_TIMING to turn it on.
    """
    enabled = bool(os.getenv("REZ_ENABLE_TIMING"))

    def __init__(self):
        self.timings = defaultdict(float)
        self.stack = []
        self.start("OTHER")

    def add(self, name, duration):
        self.timings[name] += duration

    def start(self, name):
        if self.enabled:
            t = (name, time.time())
            self.stack.append(t)

    def end(self, name):
        if self.enabled:
            external_time = 0.0
            t = self.stack.pop()
            if isinstance(t, float):
                external_time = t
                t = self.stack.pop()
            assert isinstance(t, tuple)
            name_, time_ = t
            assert name_ == name
            duration = time.time() - time_
            self.timings[name] += duration - external_time
            if self.stack:
                concat_duration = duration
                while self.stack and isinstance(self.stack[-1], float):
                    concat_duration += self.stack.pop()
                self.stack.append(concat_duration)

    def dump(self):
        self.end("OTHER")  # assumes dump() only called from atexit()
        total = sum(self.timings.values())
        total2 = total - self.timings["OTHER"]

        if self.enabled:
            rows = [["CATEGORY", "SECONDS", "%AGE (-other)"],
                    ["--------", "-------", "-------------"]]
            for (name, secs) in sorted(self.timings.items(),
                                       key=lambda x: x[1],
                                       reverse=True):
                if name == "OTHER":
                    pc = "-"
                else:
                    pc = "%.02f" % (secs * 100.0 / total2)
                rows.append((name, "%.02f" % secs, pc))

            rows.append(("TOTAL (-other)", "%.02f" % total2, ""))
            rows.append(("TOTAL", "%.02f" % total, ""))
            strs = columnise(rows)
            print '\n'.join(strs)


# singleton
timings = Timings()


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
        import re
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


def is_dict_subset(dict1, dict2):
    """Returns True if dict1 is a subset of dict2."""
    for k, v in dict1.iteritems():
        if k in dict2:
            if dict2[k] != v:
                return False
        else:
            return False
    return True


def dicts_conflicting(dict1, dict2):
    """Returns True if any key present in both dicts has differing values."""
    for k, v in dict1.iteritems():
        if k in dict2 and dict2[k] != v:
            return True
    return False


def deep_update(dict1, dict2):
    """Perform a deep merge of dict2 into dict1."""
    for k, v in dict2.iteritems():
        if k in dict1 and isinstance(v, dict) and isinstance(dict1[k], dict):
            deep_update(dict1[k], v)
        else:
            dict1[k] = v


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
        if instance is None:
            return None
        d = instance.__dict__.get('_cachedproperties', {})
        if self.name in d:
            return d[self.name]

        try:
            result = self.func(instance)
        except self.DoNotCacheSignal, e:
            return e.default

        d = instance.__dict__
        if '_cachedproperties' not in d:
            d['_cachedproperties'] = {}
        d['_cachedproperties'][self.name] = result
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
        o = self[attr]  # may raise 'no attribute' error
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


class RecursiveAttribute(UserDict.UserDict):
    """An object that can have new attributes added recursively::

        >>> a = RecursiveAttribute()
        >>> a.foo.bah = 5
        >>> a.foo['eek'] = 'hey'
        >>> a.fee = 1

        >>> print a.to_dict()
        {'foo': {'bah': 5, 'eek': 'hey'}, 'fee': 1}

    A recursive attribute can also be created from a dict, and made read-only::

        >>> d = {'fee': {'fi': {'fo': 'fum'}}, 'ho': 'hum'}
        >>> a = RecursiveAttribute(d, read_only=True)
        >>> print str(a)
        {'fee': {'fi': {'fo': 'fum'}}, 'ho': 'hum'}
        >>> print a.ho
        hum
        >>> a.new = True
        AttributeError: 'RecursiveAttribute' object has no attribute 'new'
    """
    def __init__(self, data=None, read_only=False):
        self.__dict__.update(dict(data={}, read_only=read_only))
        self._update(data or {})

    def __getattr__(self, attr):
        def _noattrib():
            raise AttributeError("'%s' object has no attribute '%s'"
                                 % (self.__class__.__name__, attr))
        d = self.__dict__
        if attr.startswith('__') and attr.endswith('__'):
            try:
                return d[attr]
            except KeyError:
                _noattrib()
        if attr in d["data"]:
            return d["data"][attr]
        if d["read_only"]:
            _noattrib()

        # the new attrib isn't actually added to this instance until it's set
        # to something. This stops code like "print instance.notexist" from
        # adding empty attributes
        attr_ = self._create_child_attribute(attr)
        assert(isinstance(attr_, RecursiveAttribute))
        attr_.__dict__["pending"] = (attr, self)
        return attr_

    def __setattr__(self, attr, value):
        d = self.__dict__
        if d["read_only"]:
            if attr in d["data"]:
                raise AttributeError("'%s' object attribute '%s' is read-only"
                                     % (self.__class__.__name__, attr))
            else:
                raise AttributeError("'%s' object has no attribute '%s'"
                                     % (self.__class__.__name__, attr))
        elif attr.startswith('__') and attr.endswith('__'):
            d[attr] = value
        else:
            d["data"][attr] = value
            self._reparent()

    def __getitem__(self, attr):
        return getattr(self, attr)

    def __str__(self):
        return str(self.to_dict())

    def __repr__(self):
        return "%s(%r)" % (self.__class__.__name__, self.to_dict())

    def _create_child_attribute(self, attr):
        """Override this method to create new child attributes.

        Returns:
            `RecursiveAttribute` instance.
        """
        return self.__class__()

    def to_dict(self):
        """Get an equivalent dict representation."""
        d = {}
        for k, v in self.__dict__["data"].iteritems():
            if isinstance(v, RecursiveAttribute):
                d[k] = v.to_dict()
            else:
                d[k] = v
        return d

    def copy(self):
        return self.__class__(self.__dict__['data'].copy())

    def update(self, data):
        """Dict-like update operation."""
        if self.__dict__["read_only"]:
            raise AttributeError("read-only, cannot be updated")
        self._update(data)

    def _update(self, data):
        for k, v in data.iteritems():
            if isinstance(v, dict):
                v = RecursiveAttribute(v)
            self.__dict__["data"][k] = v

    def _reparent(self):
        d = self.__dict__
        if "pending" in d:
            attr_, parent = d["pending"]
            parent._reparent()
            parent.__dict__["data"][attr_] = self
            del d["pending"]


class _Scope(RecursiveAttribute):
    def __init__(self, name=None, context=None):
        RecursiveAttribute.__init__(self)
        self.__dict__.update(dict(name=name,
                                  context=context,
                                  locals=None))

    def __enter__(self):
        locals_ = sys._getframe(1).f_locals
        self.__dict__["locals"] = locals_.copy()
        return self

    def __exit__(self, *args):
        # find what's changed
        updates = {}
        d = self.__dict__
        locals_ = sys._getframe(1).f_locals
        self_locals = d["locals"]
        for k, v in locals_.iteritems():
            if not (k.startswith("__") and k.endswith("__")) \
                    and (k not in self_locals or v != self_locals[k]) \
                    and not isinstance(v, _Scope):
                updates[k] = v

        # merge updated local vars with attributes
        self.update(updates)

        # restore upper scope
        locals_.clear()
        locals_.update(self_locals)

        self_context = d["context"]
        if self_context:
            self_context._scope_exit(d["name"])

    def _create_child_attribute(self, attr):
        return RecursiveAttribute()


class ScopeContext(object):
    """A context manager for creating nested dictionaries::

        >>> scope = ScopeContext()
        >>>
        >>> with scope("animal"):
        >>>     count = 2
        >>>     with scope("cat"):
        >>>         friendly = False
        >>>     with scope("dog") as d:
        >>>         friendly = True
        >>>         d.num_legs = 4
        >>>         d.breed.sub_breed = 'yorkshire terrier'
        >>> with scope("animal"):
        >>>     count = 3
        >>>     with scope("cat"):
        >>>         num_legs = 4
        >>>     with scope("ostrich"):
        >>>         friendly = False
        >>>         num_legs = 2

    The dictionaries can then be retrieved::

        >>> print pprint.pformat(scope.to_dict())
        {'animal': {'count': 3,
                    'cat': {'friendly': False,
                            'num_legs': 4},
                    'dog': {'breed': {'sub_breed': 'yorkshire terrier'},
                            'friendly': True,
                            'num_legs': 4},
                    'ostrich': {'friendly': False,
                                'num_legs': 2}}}

    Note that scopes and recursive attributes can be referenced multiple times,
    and the assigned properties will be merged. If the same property is set
    multiple times, it will be overwritten.
    """
    def __init__(self):
        self.scopes = {}
        self.scope_stack = [_Scope()]

    def __call__(self, name):
        path = tuple([x.name for x in self.scope_stack[1:]] + [name])
        if path in self.scopes:
            scope = self.scopes[path]
        else:
            scope = _Scope(name, self)
            self.scopes[path] = scope

        self.scope_stack.append(scope)
        return scope

    def _scope_exit(self, name):
        scope = self.scope_stack.pop()
        assert(self.scope_stack)
        assert(name == scope.name)
        data = {scope.name: scope.to_dict()}
        self.scope_stack[-1].update(data)

    def to_dict(self):
        """Get an equivalent dict representation."""
        return self.scope_stack[-1].to_dict()

    def __str__(self):
        names = ('.'.join(y for y in x) for x in self.scopes.keys())
        return "%r" % (tuple(names),)


class ObjectStringFormatter(Formatter):
    """String formatter for objects.

    This formatter will expand any reference to an object's attributes.
    """
    def __init__(self, instance, pretty=False, expand=None):
        """Create a formatter.

        Args:
            instance: The object to format with.
            pretty: If True, references to non-string attributes such as lists
                are converted to basic form, with characters such as brackets
                and parentheses removed.
            expand: What to expand references to nonexistent attributes to:
                - None: raise an exception;
                - 'empty': expand to an empty string;
                - 'unchanged': leave original string intact, ie '{key}'
        """
        self.instance = instance
        self.pretty = pretty
        self.expand = expand

    def convert_field(self, value, conversion):
        if self.pretty:
            if value is None:
                return ''
            elif isinstance(value, list):
                return ' '.join(str(x) for x in value)
        return Formatter.convert_field(self, value, conversion)

    def get_field(self, field_name, args, kwargs):
        if self.expand is None:
            return Formatter.get_field(self, field_name, args, kwargs)
        try:
            return Formatter.get_field(self, field_name, args, kwargs)
        except (AttributeError, KeyError, TypeError):
            import re
            reg = re.compile("[^\.\[]+")
            try:
                key = reg.match(field_name).group()
            except:
                key = field_name
            if self.expand == 'empty':
                return ('', key)
            else:
                return ("{%s}" % field_name, key)

    def get_value(self, key, args, kwds):
        if isinstance(key, str):
            if key:
                try:
                    # Check explicitly passed arguments first
                    return kwds[key]
                except KeyError:
                    pass
                if hasattr(self.instance, key):
                    return getattr(self.instance, key)
                else:
                    return self.instance[key]
            else:
                raise ValueError("zero length field name in format")
        else:
            return Formatter.get_value(self, key, args, kwds)


class _WithDataAccessors(type):
    """Metaclass for adding properties to a class for accessing top-level keys
    in its metadata dictionary.

    Property names are derived from the keys of the class's `schema` object.
    If a schema key is optional, then the class property will evaluate to None
    if the key is not present in the metadata.

    If the class's `lazy_validate` attribute is True, then the attribute
    getters created by this metaclass will perform lazy data validation, OR,
    if the class has a `_validate_key` method, will call this method, passing
    the key, key value and key schema.

    This metaclass creates the following attributes:
        - for each key in cls.schema, creates an attribute of the same name,
          unless that attribute already exists;
        - '_schema_keys' (frozenset): Keys in the schema.
    """
    def __new__(cls, name, parents, members):
        from rez.vendor.schema.schema import Schema, Optional
        schema = members.get('schema')
        keys = set()

        if schema:
            schema_dict = schema._schema
            for key, key_schema in schema_dict.iteritems():
                optional = isinstance(key, Optional)
                while isinstance(key, Schema):
                    key = key._schema
                keys.add(key)
                if key not in members and \
                        isinstance(key, basestring) and \
                        not any(hasattr(x, key) for x in parents):
                    members[key] = cls._make_getter(key, optional, key_schema)

        members["_schema_keys"] = frozenset(keys)
        return super(_WithDataAccessors, cls).__new__(cls, name, parents,
                                                      members)

    @classmethod
    def _make_getter(cls, key, optional, key_schema):
        def getter(self):
            if optional and key not in self.metadata:
                return None
            attr = getattr(self.metadata, key)
            if self.lazy_validate:
                if hasattr(self, "_validate_key"):
                    attr = self._validate_key(key, attr, key_schema)
                else:
                    schema = (key_schema if isinstance(key_schema, Schema)
                              else Schema(key_schema))
                    attr = schema.validate(attr)
            return attr
        return propertycache(getter, name=key)


class DataWrapper(object):
    """Base class for implementing a class that contains validated data.

    Attributes:
        schema (Schema): Schema used to validate the data. They keys of the
            schema become attributes on the object (the metaclass does this).
        lazy_validate (bool): If True, the schema is not used to validate the
            data on load. Instead, attributes are validated the first time they
            are referenced.
    """
    __metaclass__ = _WithDataAccessors
    lazy_validate = False
    schema = None

    def get(self, key, default=None):
        """Get a key value by name."""
        return getattr(self, key, default)

    def validate_data(self):
        """Check that the object's contents are valid."""
        if self.schema and self.lazy_validate:
            for key in self._schema_keys:
                getattr(self, key)  # forces validation of key

    def _load_data(self):
        """Implement this method to return the object's data.

        Returns:
            Object data as a dict, or None if the object has no data.
        """
        raise NotImplementedError

    @propertycache
    def _data(self):
        """Loaded object data.

        This is private because it is preferred for users to go through the
        `metadata` property.  This is here to preserve the original dictionary
        loaded directly from the package's resource.

        Returns:
            Object data as a dict, or None if the object has no data.
        """
        k = "data.load.%s" % self.__class__.__name__
        timings.start(k)
        data = self._load_data()
        timings.end(k)
        if data and self.schema and not self.lazy_validate:
            k = "data.validate_on_load.%s" % self.__class__.__name__
            timings.start(k)
            try:
                data = self.schema.validate(data)
            finally:
                timings.end(k)
        return data

    @propertycache
    def metadata(self):
        """Read-only dictionary of metadata for this package with nested,
        attribute-based access for the keys in the dictionary.

        All of the dictionaries in `_data` are replaced with custom
        `UserDicts` to provide the attribute-lookups.  If you need the raw
        dictionary, use `_data`.

        Returns:
            `RO_AttrDictWrapper` instance, or None if the resource has no data.
        """
        if self._data is None:
            return None
        else:
            return convert_dicts(self._data, RO_AttrDictWrapper)

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
        formatter = ObjectStringFormatter(self, pretty=pretty, expand=expand)
        return formatter.format(s)


def get_object_completions(instance, prefix, types=None, instance_types=None):
    """Get completion strings based on an object's attributes/keys.

    Completion also works on dynamic attributes (eg implemented via
    __getattr__) if they are iterable.

    Args:
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
    value_ = None
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
                value_ = value

    qual_words = ['.'.join(word_toks + [x]) for x in words]

    if len(words) == 1 and value is not None and \
            (instance_types is None or isinstance(value, instance_types)):
        qual_word = qual_words[0]
        words = get_object_completions(value, '', types)
        for word in words:
            qual_words.append("%s.%s" % (qual_word, word))

    return qual_words


# returns (filepath, must_cleanup)
def write_graph(graph_str, dest_file=None, prune_pkg=None):
    tmp_dir = None
    cleanup = True

    if dest_file:
        cleanup = False
    else:
        from rez.env import get_context_file
        from rez.config import config
        fmt = config.dot_image_format

        current_rxt_file = get_context_file()
        if current_rxt_file:
            tmp_dir = os.path.dirname(current_rxt_file)
            if not os.path.exists(tmp_dir):
                tmp_dir = None

        if tmp_dir:
            # hijack current env's tmpdir, so we don't have to clean up
            from uuid import uuid4
            name = "resolve-dot-%s.%s" % (uuid4().hex, fmt)
            dest_file = os.path.join(tmp_dir, name)
            cleanup = False
        else:
            tmpf = tempfile.mkstemp(prefix='resolve-dot-', suffix='.' + fmt)
            os.close(tmpf[0])
            dest_file = tmpf[1]

    from rez.dot import save_graph
    print "rendering image to " + dest_file + "..."
    save_graph(graph_str, dest_file, prune_to_package=prune_pkg,
               prune_to_conflict=False)
    return dest_file, cleanup


def view_graph(graph_str, dest_file=None, prune_pkg=None):
    from rez.system import system
    from rez.config import config

    if (system.platform == "linux") and (not os.getenv("DISPLAY")):
        print >> sys.stderr, "Unable to open display."
        sys.exit(1)

    dest_file, cleanup = write_graph(graph_str, dest_file=dest_file,
                                     prune_pkg=prune_pkg)

    # view graph
    t1 = time.time()
    viewed = False
    prog = config.image_viewer or 'browser'
    print "loading image viewer (%s)..." % prog

    if config.image_viewer:
        proc = subprocess.Popen((config.image_viewer, dest_file))
        proc.wait()
        viewed = not bool(proc.returncode)

    if not viewed:
        import webbrowser
        webbrowser.open_new("file://" + dest_file)

    """
    if cleanup:
        # hacky - gotta delete tmp file, but hopefully not before app has loaded it
        t2 = time.time()
        if (t2 - t1) < 1:  # viewer is probably non-blocking
            # give app a chance to load image
            time.sleep(10)
        os.remove(dest_file)
    """


@atexit.register
def _atexit():
    # remove temp dirs
    if rm_tmdirs:
        for path in _tmpdirs:
            rmdtemp(path)

    # print timings
    print
    try:
        timings.dump()
    except:
        pass
