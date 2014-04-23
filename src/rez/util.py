"""
Misc useful stuff.
"""
from __future__ import with_statement
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
import yaml
import shutil
import textwrap
import tempfile
import threading
import subprocess as sp
from rez import module_root_path



WRITE_PERMS = stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH


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
    is used internally by Rez to dynamically create a script that uses Rez, even
    though the parent environ may not be configured to do so.
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

    os.chmod(filepath, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH \
        | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


_once_warnings = set()

def print_warning_once(msg):
    if msg not in _once_warnings:
        print >> sys.stderr, "WARNING: %s" % msg
        _once_warnings.add(msg)

def _mkdirs(*dirs):
    path = os.path.join(*dirs)
    if not os.path.exists(path):
        os.makedirs(path)
    return path

rm_tmdirs = True
_tmpdirs = set()
_tmpdir_lock = threading.Lock()

def mkdtemp_():
    from rez.settings import settings
    path = tempfile.mkdtemp(dir=settings.tmpdir, prefix='rez_')
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

@atexit.register
def _atexit():
    # remove temp dirs
    if rm_tmdirs:
        for path in _tmpdirs:
            rmdtemp(path)

def _get_rez_dist_path(dirname):
    path = os.path.join(module_root_path, dirname)
    if not os.path.exists(path):
        # this will happen if we are the bootstrapped rez pkg
        path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
        path = os.path.realpath(path)
        path = os.path.join(path, dirname)
        assert(os.path.exists(path))
    return path

def get_bootstrap_path():
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

# TODO remove
"""
def gen_dotgraph_image(dot_data, out_file):
    # shortcut if writing .dot file
    if out_file.endswith(".dot"):
        with open(out_file, 'w') as f:
            f.write(dot_data)
        return

    from rez.contrib.pydot import pydot
    graph = pydot.graph_from_dot_data(dot_data)

    # assume write format from image extension
    ext = "jpg"
    if '.' in out_file:
        ext = out_file.rsplit('.', 1)[-1]

    try:
        fn = getattr(graph, "write_" + ext)
    except Exception:
        sys.stderr.write("could not write to '" + out_file + "': unknown format specified")
        sys.exit(1)

    fn(out_file)
"""

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

def remove_write_perms(path):
    st = os.stat(path)
    mode = st.st_mode & ~WRITE_PERMS
    os.chmod(path, mode)

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

def get_epoch_time():
    """
    get time since the epoch as an int
    TODO switch everything to UTC
    """
    return int(time.mktime(time.localtime()))

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

class AttrDict(dict):
    """
    A dictionary with attribute-based lookup.
    """
    def __getattr__(self, attr):
        if attr.startswith('__') and attr.endswith('__'):
            d = self.__dict__
        else:
            d = self
        try:
            return d[attr]
        except KeyError:
            raise AttributeError("'%s' object has no attribute '%s'" % (self.__class__.__name__, attr))

    def copy(self):
        return AttrDict(dict.copy(self))


class AttrDictWrapper(UserDict.UserDict):
    """
    Wrap a custom dictionary with attribute-based lookup.
    """
    def __init__(self, data):
        self.__dict__['data'] = data


    def __getattr__(self, attr):
        if attr.startswith('__') and attr.endswith('__'):
            d = self.__dict__
        else:
            d = self.data
        try:
            return d[attr]
        except KeyError:
            raise AttributeError("'%s' object has no attribute '%s'" % (self.__class__.__name__, attr))

    def __setattr__(self, attr, value):
        # For things like '__class__', for instance
        if attr.startswith('__') and attr.endswith('__'):
            super(AttrDictWrapper, self).__setattr__(attr, value)
        self.data[attr] = value


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
    '''Encodes an arbitrary unicode string to a generic
    filesystem-compatible filename

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
    '''
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
    return ''.join(result)


_FILESYSTEM_TOKEN_RE = re.compile(r'(?P<as_is>[a-z0-9.-])|(?P<underscore>__)|_(?P<uppercase>[a-z])|_(?P<N>[0-9])')
_HEX_RE = re.compile('[0-9a-f]+$')

def decode_filesystem_name(filename):
    """Decodes a filename encoded using the rules given in
    encode_filesystem_name to a unicode string
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


def convert_old_commands(commands, annotate=True):
    """Converts old-style package commands into equivalent Rex code."""
    def _en(s):
        return s.encode("string-escape")

    loc = []
    for cmd in commands:
        if annotate:
            loc.append("comment('OLD COMMAND: %s')" % _en(cmd))

        toks = cmd.strip().split()
        if toks[0] == "export":
            var,value = cmd.split(' ', 1)[1].split('=', 1)
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]

            if var == "CMAKE_MODULE_PATH":
                value = value.replace(';', os.pathsep)

            parts = value.split(os.pathsep)
            parts = [x for x in parts if x]
            if len(parts) > 1:
                idx = None
                var1 = "$%s" % var
                var2 = "${%s}" % var
                if var1 in parts:
                    idx = parts.index(var1)
                elif var2 in parts:
                    idx = parts.index(var2)
                if idx in (0, len(parts)-1):
                    func = "appendenv" if idx==0 else "prependenv"
                    parts = parts[1:] if idx==0 else parts[:-1]
                    val = os.pathsep.join(parts)
                    loc.append("%s('%s', '%s')" % (func, var, _en(val)))
                    continue

            loc.append("setenv('%s', '%s')" % (var, _en(value)))
        elif toks[0].startswith('#'):
            loc.append("comment('%s')" % _en(' '.join(toks[1:])))
        elif toks[0] == "alias":
            match = re.search("alias (?P<key>.*)=(?P<value>.*)", cmd)
            key = match.groupdict()['key'].strip()
            value = match.groupdict()['value'].strip()
            if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            loc.append("alias('%s', '%s')" % (key, _en(value)))
        else:
            # assume we can execute this as a straight command
            loc.append("command('%s')" % _en(cmd))

    return '\n'.join(loc)

try:
    import collections
    OrderedDict = collections.OrderedDict  # @UndefinedVariable
except AttributeError:
    from UserDict import DictMixin

    class OrderedDict(dict, DictMixin):

        def __init__(self, *args, **kwds):
            if len(args) > 1:
                raise TypeError('expected at most 1 arguments, got %d' % len(args))
            try:
                self.__end
            except AttributeError:
                self.clear()
            self.update(*args, **kwds)

        def clear(self):
            self.__end = end = []
            end += [None, end, end]         # sentinel node for doubly linked list
            self.__map = {}                 # key --> [key, prev, next]
            dict.clear(self)

        def __setitem__(self, key, value):
            if key not in self:
                end = self.__end
                curr = end[1]
                curr[2] = end[1] = self.__map[key] = [key, curr, end]
            dict.__setitem__(self, key, value)

        def __delitem__(self, key):
            dict.__delitem__(self, key)
            key, prev, next = self.__map.pop(key)
            prev[2] = next
            next[1] = prev

        def __iter__(self):
            end = self.__end
            curr = end[2]
            while curr is not end:
                yield curr[0]
                curr = curr[2]

        def __reversed__(self):
            end = self.__end
            curr = end[1]
            while curr is not end:
                yield curr[0]
                curr = curr[1]

        def popitem(self, last=True):
            if not self:
                raise KeyError('dictionary is empty')
            if last:
                key = reversed(self).next()
            else:
                key = iter(self).next()
            value = self.pop(key)
            return key, value

        def __reduce__(self):
            items = [[k, self[k]] for k in self]
            tmp = self.__map, self.__end
            del self.__map, self.__end
            inst_dict = vars(self).copy()
            self.__map, self.__end = tmp
            if inst_dict:
                return (self.__class__, (items,), inst_dict)
            return self.__class__, (items,)

        def keys(self):
            return list(self)

        setdefault = DictMixin.setdefault
        update = DictMixin.update
        pop = DictMixin.pop
        values = DictMixin.values
        items = DictMixin.items
        iterkeys = DictMixin.iterkeys
        itervalues = DictMixin.itervalues
        iteritems = DictMixin.iteritems

        def __repr__(self):
            if not self:
                return '%s()' % (self.__class__.__name__,)
            return '%s(%r)' % (self.__class__.__name__, self.items())

        def copy(self):
            return self.__class__(self)

        @classmethod
        def fromkeys(cls, iterable, value=None):
            d = cls()
            for key in iterable:
                d[key] = value
            return d

        def __eq__(self, other):
            if isinstance(other, OrderedDict):
                if len(self) != len(other):
                    return False
                for p, q in  zip(self.items(), other.items()):
                    if p != q:
                        return False
                return True
            return dict.__eq__(self, other)

        def __ne__(self, other):
            return not self == other

class propertycache(object):
    '''Class for creating properties where the value is initially calculated then stored.

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

    def __init__(self, func):
        self.func = func
        self.name = func.__name__

    def __get__(self, instance, owner=None):
        if instance is None:
            return None
        try:
            result = self.func(instance)
        except self.DoNotCacheSignal, e:
            return e.default
        setattr(instance, self.name, result)
        return result
