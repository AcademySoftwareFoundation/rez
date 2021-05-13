"""
Filesystem-related utilities.
"""
from __future__ import print_function

from threading import Lock
from tempfile import mkdtemp
from contextlib import contextmanager
from uuid import uuid4
import errno
import weakref
import atexit
import posixpath
import ntpath
import os.path
import shutil
import os
import re
import stat
import platform

from rez.vendor.six import six
from rez.utils.platform_ import platform_


is_windows = platform.system() == "Windows"


class TempDirs(object):
    """Tempdir manager.

    Makes tmpdirs and ensures they're cleaned up on program exit.
    """
    instances_lock = Lock()
    instances = []

    def __init__(self, tmpdir, prefix="rez_"):
        self.tmpdir = tmpdir
        self.prefix = prefix
        self.dirs = set()
        self.lock = Lock()

        with TempDirs.instances_lock:
            TempDirs.instances.append(weakref.ref(self))

    def mkdtemp(self, cleanup=True):
        path = mkdtemp(dir=self.tmpdir, prefix=self.prefix)
        if not cleanup:
            return path

        with self.lock:
            self.dirs.add(path)

        return path

    def __del__(self):
        self.clear()

    def clear(self):
        with self.lock:
            if not self.dirs:
                return

            dirs = self.dirs
            self.dirs = set()

        for path in dirs:
            if os.path.exists(path) and not os.getenv("REZ_KEEP_TMPDIRS"):
                shutil.rmtree(path)

    @classmethod
    def clear_all(cls):
        with TempDirs.instances_lock:
            instances = cls.instances[:]

        for ref in instances:
            instance = ref()
            if instance is not None:
                instance.clear()


atexit.register(TempDirs.clear_all)


@contextmanager
def make_path_writable(path):
    """Temporarily make `path` writable, if possible.

    Args:
        path (str): Path to make temporarily writable
    """
    try:
        orig_mode = os.stat(path).st_mode
        new_mode = orig_mode

        if not os.access(path, os.W_OK):
            new_mode = orig_mode | stat.S_IWUSR

        # make writable
        if new_mode != orig_mode:
            os.chmod(path, new_mode)

    except OSError:
        # ignore access errors here, and just do nothing. It will be more
        # intuitive for the calling code to fail on access instead.
        #
        orig_mode = None
        new_mode = None

    # yield, then reset mode back to original
    try:
        yield
    finally:
        if new_mode != orig_mode:
            os.chmod(path, orig_mode)


@contextmanager
def retain_cwd():
    """Context manager that keeps cwd unchanged afterwards.
    """
    cwd = os.getcwd()
    try:
        yield
    finally:
        os.chdir(cwd)


def get_existing_path(path, topmost_path=None):
    """Get the longest parent path in `path` that exists.

    If `path` exists, it is returned.

    Args:
        path (str): Path to test
        topmost_path (str): Do not test this path or above

    Returns:
        str: Existing path, or None if no path was found.
    """
    prev_path = None

    if topmost_path:
        topmost_path = os.path.normpath(topmost_path)

    while True:
        if os.path.exists(path):
            return path

        path = os.path.dirname(path)
        if path == prev_path:
            return None

        if topmost_path and os.path.normpath(path) == topmost_path:
            return None

        prev_path = path


def safe_listdir(path):
    """Safe listdir.

    Works in a multithread/proc scenario where dirs may be deleted at any time
    """
    try:
        return os.listdir(path)
    except OSError as e:
        if e.errno in (errno.ENOENT, errno.ENOTDIR):
            return []
        raise


def safe_makedirs(path):
    """Safe makedirs.

    Works in a multithreaded scenario.
    """
    if not os.path.exists(path):
        try:
            os.makedirs(path)
        except OSError:
            if not os.path.exists(path):
                raise


def safe_remove(path):
    """Safely remove the given file or directory.

    Works in a multithreaded scenario.
    """
    if not os.path.exists(path):
        return

    try:
        if os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
    except OSError:
        if os.path.exists(path):
            raise


def forceful_rmtree(path):
    """Like shutil.rmtree, but may change permissions.

    Specifically, non-writable dirs within `path` can cause rmtree to fail. This
    func chmod's to writable to avoid this issue, if possible.

    Also handled:
        * path length over 259 char (on Windows)
        * unicode path
    """
    if six.PY2:
        path = unicode(path)

    def _on_error(func, path, exc_info):
        try:
            if is_windows:
                path = windows_long_path(path)

            parent_path = os.path.dirname(path)
            if not os.access(parent_path, os.W_OK):
                st = os.stat(parent_path)
                os.chmod(parent_path, st.st_mode | stat.S_IWUSR)

            if not os.access(path, os.W_OK):
                st = os.stat(path)
                os.chmod(path, st.st_mode | stat.S_IWUSR)

        except:
            # avoid confusion by ensuring original exception is reraised
            pass

        func(path)

    shutil.rmtree(path, onerror=_on_error)


def replacing_symlink(source, link_name):
    """Create symlink that overwrites any existing target.
    """
    with make_tmp_name(link_name) as tmp_link_name:
        os.symlink(source, tmp_link_name)
        replace_file_or_dir(link_name, tmp_link_name)


def replacing_copy(src, dest, follow_symlinks=False):
    """Perform copy that overwrites any existing target.

    Will copy/copytree `src` to `dest`, and will remove `dest` if it exists,
    regardless of what it is.

    If `follow_symlinks` is False, symlinks are preserved, otherwise their
    contents are copied.

    Note that this behavior is different to `shutil.copy`, which copies src
    into dest if dest is an existing dir.
    """
    with make_tmp_name(dest) as tmp_dest:
        if os.path.islink(src) and not follow_symlinks:
            # special case - copy just a symlink
            src_ = os.readlink(src)
            os.symlink(src_, tmp_dest)
        elif os.path.isdir(src):
            # copy a dir
            shutil.copytree(src, tmp_dest, symlinks=(not follow_symlinks))
        else:
            # copy a file
            shutil.copy2(src, tmp_dest)

        replace_file_or_dir(dest, tmp_dest)


def replace_file_or_dir(dest, source):
    """Replace `dest` with `source`.

    Acts like an `os.rename` if `dest` does not exist. Otherwise, `dest` is
    deleted and `src` is renamed to `dest`.
    """
    from rez.vendor.atomicwrites import replace_atomic

    if not os.path.exists(dest):
        try:
            os.rename(source, dest)
            return
        except:
            if not os.path.exists(dest):
                raise

    try:
        replace_atomic(source, dest)
        return
    except:
        pass

    with make_tmp_name(dest) as tmp_dest:
        os.rename(dest, tmp_dest)
        os.rename(source, dest)


def additive_copytree(src, dst, symlinks=False, ignore=None):
    """Version of `copytree` that merges into an existing directory.
    """
    if not os.path.exists(dst):
        os.makedirs(dst)

    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)

        if os.path.isdir(s):
            additive_copytree(s, d, symlinks, ignore)
        else:
            shutil.copy2(s, d)


@contextmanager
def make_tmp_name(name):
    """Generates a tmp name for a file or dir.

    This is a tempname that sits in the same dir as `name`. If it exists on
    disk at context exit time, it is deleted.
    """
    path, base = os.path.split(name)
    tmp_base = ".tmp-%s-%s" % (base, uuid4().hex)
    tmp_name = os.path.join(path, tmp_base)

    try:
        yield tmp_name
    finally:
        safe_remove(tmp_name)


def is_subdirectory(path_a, path_b):
    """Returns True if `path_a` is a subdirectory of `path_b`."""
    path_a = os.path.realpath(path_a)
    path_b = os.path.realpath(path_b)
    try:
        relative = os.path.relpath(path_a, path_b)
    except ValueError:
        # Different mounts on Windows:
        # ValueError: path is on mount 'c:', start on mount 'd:'
        #
        return False

    return not relative.startswith(os.pardir + os.sep)


def find_matching_symlink(path, source):
    """Find a symlink under `path` that points at `source`.

    If source is relative, it is considered relative to `path`.

    Returns:
        str: Name of symlink found, or None.
    """
    def to_abs(target):
        if os.path.isabs(target):
            return target
        else:
            return os.path.normpath(os.path.join(path, target))

    abs_source = to_abs(source)

    for name in os.listdir(path):
        linkpath = os.path.join(path, name)
        if os.path.islink(linkpath):
            source_ = os.readlink(linkpath)
            if to_abs(source_) == abs_source:
                return name

    return None


def copy_or_replace(src, dst):
    '''try to copy with mode, and if it fails, try replacing
    '''
    try:
        shutil.copy(src, dst)
    except (OSError, IOError) as e:
        # It's possible that the file existed, but was owned by someone
        # else - in that situation, shutil.copy might then fail when it
        # tries to copy perms.
        # However, it's possible that we have write perms to the dir -
        # in which case, we can just delete and replace
        import errno

        if e.errno == errno.EPERM:
            import tempfile
            # try copying into a temporary location beside the old
            # file - if we have perms to do that, we should have perms
            # to then delete the old file, and move the new one into
            # place
            if os.path.isdir(dst):
                dst = os.path.join(dst, os.path.basename(src))

            dst_dir, dst_name = os.path.split(dst)
            dst_temp = tempfile.mktemp(prefix=dst_name + '.', dir=dst_dir)
            shutil.copy(src, dst_temp)
            if not os.path.isfile(dst_temp):
                raise RuntimeError(
                    "shutil.copy completed successfully, but path"
                    " '%s' still did not exist" % dst_temp)
            os.remove(dst)
            shutil.move(dst_temp, dst)


def copytree(src, dst, symlinks=False, ignore=None, hardlinks=False):
    '''copytree that supports hard-linking
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
        except (IOError, os.error) as why:
            errors.append((srcname, dstname, str(why)))
        # catch the Error from the recursive copytree so that we can
        # continue with other files
        except shutil.Error as err:
            errors.extend(err.args[0])
    try:
        shutil.copystat(src, dst)
    except shutil.WindowsError:
        # can't copy file access times on Windows
        pass
    except OSError as why:
        errors.extend((src, dst, str(why)))
    if errors:
        raise shutil.Error(errors)


def movetree(src, dst):
    """Attempts a move, and falls back to a copy+delete if this fails
    """
    try:
        shutil.move(src, dst)
    except:
        copytree(src, dst, symlinks=True, hardlinks=True)
        shutil.rmtree(src)


def safe_chmod(path, mode):
    """Set the permissions mode on path, but only if it differs from the current mode.
    """
    if stat.S_IMODE(os.stat(path).st_mode) != mode:
        os.chmod(path, mode)


def to_nativepath(path):
    path = path.replace('\\', '/')
    return os.path.join(*path.split('/'))


def to_ntpath(path):
    return ntpath.sep.join(path.split(posixpath.sep))


def to_posixpath(path):
    return posixpath.sep.join(path.split(ntpath.sep))


def canonical_path(path, platform=None):
    """ Resolves symlinks, and formats filepath.

    Resolves symlinks, lowercases if filesystem is case-insensitive,
    formats filepath using slashes appropriate for platform.

    Args:
        path (str): Filepath being formatted
        platform (rez.utils.platform_.Platform): Indicates platform path is being
            formatted for. Defaults to current platform.

    Returns:
        str: Provided path, formatted for platform.
    """
    if platform is None:
        platform = platform_

    path = os.path.normpath(os.path.realpath(path))

    if not platform.has_case_sensitive_filesystem:
        return path.lower()

    return path


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
    if isinstance(input_str, six.string_types):
        input_str = unicode(input_str)
    elif not isinstance(input_str, unicode):
        raise TypeError("input_str must be a %s" % six.string_types[0].__name__)

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
        elif match_dict['underscore']:
            result.append(u'_')
        elif match_dict['uppercase']:
            result.append(unicode(match_dict['uppercase'].upper()))
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
        else:
            raise ValueError("Unrecognized match type in filesystem name %r"
                             " (bad index: %d - %r)" % (filename, i, remain[:2]))

    return u''.join(result)


def test_encode_decode():
    def do_test(orig, expected_encoded):
        print('=' * 80)
        print(orig)
        encoded = encode_filesystem_name(orig)
        print(encoded)
        assert encoded == expected_encoded
        decoded = decode_filesystem_name(encoded)
        print(decoded)
        assert decoded == orig

    do_test("Foo_Bar (fun).txt", '_foo___bar_020_028fun_029.txt')

    # u'\u20ac' == Euro symbol
    do_test(u"\u20ac3 ~= $4.06", '_3e282ac3_020_07e_03d_020_0244.06')


def walk_up_dirs(path):
    """Yields absolute directories starting with the given path, and iterating
    up through all it's parents, until it reaches a root directory"""
    prev_path = None
    current_path = os.path.abspath(path)
    while current_path != prev_path:
        yield current_path
        prev_path = current_path
        current_path = os.path.dirname(prev_path)


def windows_long_path(dos_path):
    """Prefix '\\?\' for path longer than 259 char (Win32API limitation)
    """
    path = os.path.abspath(dos_path)

    if path.startswith("\\\\?\\"):
        pass
    elif path.startswith("\\\\"):
        path = "\\\\?\\UNC\\" + path[2:]
    else:
        path = "\\\\?\\" + path

    return path


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
